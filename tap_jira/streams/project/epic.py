from tap_jira.streams.base import ProjectStream


class EpicStream(ProjectStream):
    @property
    def name(self) -> str:
        return "epics"

    @property
    def primary_keys(self) -> list[str]:
        return ["id"]

    def sync(self) -> None:
        for boards in self.context.jira.project_boards(self.project_id):
            for board in boards:
                board_id = board.get("id")

                for page in self.context.jira.board_epics(board_id):
                    self.write_page(page)
