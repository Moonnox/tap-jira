from tap_jira.streams.base import ProjectBaseStream


class IssueCommentStream(ProjectBaseStream):
    @property
    def name(self) -> str:
        return "issue_comments"

    @property
    def primary_keys(self) -> list[str]:
        return ["id"]

    def sync(self) -> None:
        pass
