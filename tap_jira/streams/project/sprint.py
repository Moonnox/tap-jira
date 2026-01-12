from tap_jira.streams.base import ProjectBaseStream


class SprintStream(ProjectBaseStream):
    name = "sprints"

    @property
    def primary_keys(self) -> list[str]:
        return ["id"]

    def sync(self) -> None:
        pass
