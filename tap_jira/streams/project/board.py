from tap_jira.streams.base import ProjectBaseStream
from tap_jira.streams.project.sprint import SprintStream


class BoardStream(ProjectBaseStream):
    name = "boards"

    @property
    def primary_keys(self) -> list[str]:
        return ["id"]

    def sync(self) -> None:
        sprints_stream = self.streams.get(SprintStream)

        for boards_page in self.context.jira.project_boards(self.project_id):
            self.write_page(boards_page)
            if not sprints_stream:
                continue

            for board in boards_page:
                board_id = board["id"]

                for sprint_page in self.context.jira.sprints(board_id):
                    sprints_stream.write_page(sprint_page)
