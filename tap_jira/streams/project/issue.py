from datetime import datetime
from zoneinfo import ZoneInfo

import singer

from tap_jira.streams.base import BaseStream, ProjectBaseStream


def _format_datetime(dt: datetime, timezone: str) -> str:
    local_dt = dt.astimezone(ZoneInfo(timezone))

    return local_dt.strftime("%Y-%m-%d %H:%M")


class IssueStream(ProjectBaseStream):
    @property
    def name(self) -> str:
        return "issues"

    @property
    def primary_keys(self) -> list[str]:
        return ["key"]

    def sync(self) -> None:
        updated_bookmark = (self.stream_id, "updated")
        page_bookmark = (self.stream_id, "page")

        timezone = self.context.jira.timezone()
        start_date = self.context.get_start_date(updated_bookmark)

        last_updated = _format_datetime(start_date, timezone)
        last_page = self.context.get_bookmark(page_bookmark)

        new_last_updated = start_date

        for page, next_page in self.context.jira.project_issues(
            self.project_id, updated_after=last_updated, from_page=last_page
        ):
            if not page:
                break

            self._sync_issue_comments(page)

            new_last_updated = page[-1].get("fields", {}).get("updated")
            self.write_page(page)

            self.context.set_bookmark(page_bookmark, next_page)
            singer.write_state(self.context.state)

        self.context.set_bookmark(page_bookmark, None)
        self.context.set_bookmark(updated_bookmark, new_last_updated)

        singer.write_state(self.context.state)

    def _sync_issue_comments(self, page: list[dict]) -> None:
        stream: BaseStream | None = None
        if "issue_comments" in self.context.selected_streams:
            stream = self.context.selected_streams.get("issue_comments")

        if not stream:
            return

        for issue in page:
            comments = (
                issue.get("fields", {}).get("comment", {}).get("comments", [])
            )
            if not comments:
                continue

            rendered_comments = (
                issue.get("renderedFields", {})
                .get("comment", {})
                .get("comments", [])
            )
            if not rendered_comments:
                continue

            for idx, comment in enumerate(comments):
                comment["issueId"] = issue["id"]
                comment["issueKey"] = issue["key"]
                comment["renderedBody"] = rendered_comments[idx].get("body")

            stream.write_page(comments)
