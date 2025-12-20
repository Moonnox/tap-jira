from tap_jira.streams.base import ProjectBaseStream


class UserStream(ProjectBaseStream):
    @property
    def name(self) -> str:
        return "users"

    @property
    def primary_keys(self) -> list[str]:
        return ["accountId"]

    def sync(self) -> None:
        for page in self.context.jira.users():
            self.write_page(page)
