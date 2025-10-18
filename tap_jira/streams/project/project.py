from tap_jira.streams.base import ProjectBaseStream


class ProjectStream(ProjectBaseStream):
    @property
    def name(self) -> str:
        return "projects"

    @property
    def primary_keys(self) -> list[str]:
        return ["id"]

    def sync(self) -> None:
        for page in self.context.jira.projects(ids=[self.project_id]):
            self.write_page(page)
