from tap_jira.streams.base import ProjectBaseStream


class UserStream(ProjectBaseStream):
    @property
    def name(self) -> str:
        return "users"

    @property
    def primary_keys(self) -> list[str]:
        return ["accountId"]

    def sync(self) -> None:
        assignable_user_ids = self._fetch_assignable_user_ids(self.project_id)

        for page in self.context.jira.users():
            for user in page:
                permissions = []

                is_assignable = user["accountId"] in assignable_user_ids
                if is_assignable:
                    permissions.append("ASSIGNABLE_USER")

                user["permissions"] = permissions

            self.write_page(page)

    def _fetch_assignable_user_ids(self, project_key: str) -> set[str]:
        user_ids = set()

        for page in self.context.jira.assignable_users(project_key):
            for user in page:
                user_ids.add(user["accountId"])

        return user_ids
