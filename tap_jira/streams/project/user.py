from tap_jira.streams.base import ProjectStream


class UserStream(ProjectStream):
    @property
    def name(self) -> str:
        return "users"

    @property
    def primary_keys(self) -> list[str]:
        return ["accountId"]

    def sync(self) -> None:
        for page in self.context.jira.users():
            users = [
                user for user in page if user.get("accountType") == "atlassian"
            ]

            self.write_page(users)
