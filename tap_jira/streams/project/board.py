from typing import Any
from tap_jira.jira import JiraPaginator
from tap_jira.streams.base import ProjectStream


class BoardStream(ProjectStream):
    @property
    def name(self) -> str:
        return "boards"

    @property
    def display_name(self) -> str:
        return "Boards"

    def sync(self) -> None:
        paginator = JiraPaginator.default().pages(self._fetch_project_boards)

        for page in paginator:
            self.write_page(page)

    def _fetch_project_boards(self, params: dict[str, str]) -> dict[str, Any]:
        path = "/rest/agile/1.0/board"
        params = {
            "projectKeyOrId": self.project_id,
            **params,
        }

        return self.context.jira.request(
            url=path,
            method="GET",
            params=params,
        )
