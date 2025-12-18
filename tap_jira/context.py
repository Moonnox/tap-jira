from argparse import Namespace
from dataclasses import dataclass
from datetime import datetime
from logging import Logger
from typing import Any
from singer.utils import strptime_to_utc, strftime

from tap_jira.credentials_manager import JiraCredentialsManager
from tap_jira.jira import Jira


@dataclass
class Config:
    start_date: str

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        return cls(start_date=data["start_date"])


class Context:
    @classmethod
    def from_args(cls, args: Namespace, logger: Logger) -> "Context":
        config = Config.from_dict(args.config)

        credentials_manager = JiraCredentialsManager(logger)
        jira = Jira(credentials_manager)

        return cls(jira=jira, config=config, state=args.state, logger=logger)

    def __init__(
        self,
        jira: Jira,
        config: Config,
        logger: Logger,
        state: dict | None = None,
    ):
        self.jira = jira
        self.config = config
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
