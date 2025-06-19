from argparse import Namespace
from dataclasses import dataclass
from datetime import datetime
from logging import Logger
from typing import Any
from singer.utils import strptime_to_utc, strftime

from tap_jira.jira import Jira


@dataclass
class Config:
    client_id: str
    client_secret: str
    access_token: str
    refresh_token: str
    site_name: str
    start_date: str

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        return cls(
            client_id=data["client_id"],
            client_secret=data["client_secret"],
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            site_name=data["site_name"],
            start_date=data["start_date"],
        )


class Context:
    @classmethod
    def from_args(cls, args: Namespace, logger: Logger) -> "Context":
        config = Config.from_dict(args.config)
        jira = Jira(
            oauth={
                "access_token": config.access_token,
                "refresh_token": config.refresh_token,
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "config_path": args.config_path,
            },
            site_name=config.site_name,
        )

        return cls(
            jira=jira,
            config=config,
            config_path=args.config_path,
            state=args.state,
            logger=logger,
        )

    def __init__(
        self,
        jira: Jira,
        config: Config,
        config_path: str,
        logger: Logger,
        state: dict | None = None,
    ):
        self.jira = jira
        self.config = config
        self.config_path = config_path
        self.state = state or {}
        self.selected_streams = {}
        self.logger = logger

    def get_bookmarks(self) -> dict:
        if "bookmarks" not in self.state:
            self.state["bookmarks"] = {}

        return self.state["bookmarks"]

    def get_bookmark(self, path: tuple[str, ...]) -> Any:
        current = self.get_bookmarks()

        for key in path[:-1]:
            current = current.setdefault(key, {})

        last = path[-1]
        return current.setdefault(last, None)

    def get_start_date(self, path: tuple[str, ...]) -> datetime:
        value = self.get_bookmark(path)
        if not value:
            value = self.config.start_date

        return strptime_to_utc(value)

    def set_bookmark(self, path: tuple[str, ...], value: Any) -> None:
        if isinstance(value, datetime):
            value = strftime(value)

        bookmark = self.get_bookmark(path[:-1])
        bookmark[path[-1]] = value

    def set_selected_streams(self, streams: list[Any] | None = None) -> None:
        if streams is None:
            streams = []

        self.selected_streams = {stream.name: stream for stream in streams}
