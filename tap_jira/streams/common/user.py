from tap_jira.streams.base import CommonBaseStream


class UserStream(CommonBaseStream):
    @property
    def name(self) -> str:
        return "users"

    @property
    def primary_keys(self) -> list[str]:
        return ["accountId"]

    def sync(self) -> None:
        assignable_user_ids = self._fetch_assignable_user_ids(self.project_ids)

        for page in self.context.jira.users():
            for user in page:
                permissions = []

                is_assignable = user["accountId"] in assignable_user_ids
                if is_assignable:
                    permissions.append("ASSIGNABLE_USER")

                user["permissions"] = permissions

            self.write_page(page)

    def _fetch_assignable_user_ids(self, project_ids: list[str]) -> list[str]:
        project_keys = self._fetch_project_keys(project_ids)
        if not project_keys:
            return []

        user_ids = set()

        for page in self.context.jira.assignable_users(project_keys):
            for user in page:
                user_ids.add(user["accountId"])

        return list(user_ids)

    def _fetch_project_keys(self, project_ids: list[str]) -> list[str]:
        project_keys = set()

        for page in self.context.jira.projects(ids=project_ids):
            for project in page:
                project_keys.add(project["key"])

        return list(project_keys)
