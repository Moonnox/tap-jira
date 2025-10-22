from tap_jira.streams.base import ProjectBaseStream


class IssueStatusStream(ProjectBaseStream):
    @property
    def name(self) -> str:
        return "issue_statuses"

    @property
    def primary_keys(self) -> list[str]:
        return ["id"]

    def sync(self) -> None:
        project_statuses = self.context.jira.project_statuses(self.project_id)

        unique_statuses = {
            status["id"]: status
            for project_status in project_statuses
            for status in project_status.get("statuses", [])
        }
        issues_statuses = list(unique_statuses.values())

        for issue_status in issues_statuses:
            issue_status["projectId"] = self.project_id

        self.write_page(list(unique_statuses.values()))
