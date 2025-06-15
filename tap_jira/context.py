from argparse import Namespace
from dataclasses import dataclass

from tap_jira.jira import Jira


@dataclass
class Config:
    client_id: str
    client_secret: str
    access_token: str
    refresh_token: str
    site_name: str

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        return cls(
            client_id=data["client_id"],
            client_secret=data["client_secret"],
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            site_name=data["site_name"],
        )


class Context:
    @classmethod
    def from_args(cls, args: Namespace) -> "Context":
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

        return cls(jira=jira, config=config, config_path=args.config_path)

    def __init__(self, jira: Jira, config: Config, config_path: str):
        self.jira = jira
        self.config = config
        self.config_path = config_path
