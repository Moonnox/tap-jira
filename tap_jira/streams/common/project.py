from tap_jira.streams.base import CommonBaseStream


class ProjectStream(CommonBaseStream):
    name = "projects"

    @property
    def primary_keys(self) -> list[str]:
        return ["id"]

    def sync(self) -> None:
        if not self.project_ids:
            return

        for page in self.context.jira.projects(ids=self.project_ids):
            for project in page:
                project["projectName"] = project["name"]

            self.write_page(page)
