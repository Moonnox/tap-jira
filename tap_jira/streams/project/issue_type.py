from tap_jira.streams.base import ProjectBaseStream


class IssueTypeStream(ProjectBaseStream):
    name = "issue_types"

    @property
    def primary_keys(self) -> list[str]:
        return ["id"]

    def sync(self) -> None:
        project = self.context.jira.project(self.project_id)
        issue_types = project.get("issueTypes", [])

        for issue_type in issue_types:
            issue_type["projectId"] = self.project_id

        self.write_page(issue_types)
