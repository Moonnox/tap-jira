import re
from singer.catalog import CatalogEntry
import singer.metadata as metadata_utils

from tap_jira.context import Context
from tap_jira.streams.base import (
    ProjectStream,
    StreamGroup,
    BaseStream,
    StreamGroupType,
)
from tap_jira.streams.project.board import BoardStream
from tap_jira.streams.project.epic import EpicStream
from tap_jira.streams.project.issue import IssueStream
from tap_jira.streams.project.sprint import SprintStream
from tap_jira.streams.project.issue_comment import IssueCommentStream

PROJECT_STREAM_GROUP_PATTERN = r"^project_(?P<project_id>.+)$"


def _get_selected_streams(entry: CatalogEntry) -> list[str]:
    metadata = metadata_utils.to_map(entry.metadata)
    if not metadata:
        return []

    selected = []

    for breadcrumb, value in metadata.items():
        if len(breadcrumb) != 2 or breadcrumb[0] != "properties":
            continue

        (_, stream_name) = breadcrumb
        if value.get("selected"):
            selected.append(stream_name)

    return selected


class ProjectStreamGroup(StreamGroup):
    @property
    def group_type(self) -> StreamGroupType:
        return StreamGroupType.PROJECT

    @property
    def streams(self) -> dict[str, type[ProjectStream]]:
        return {
            "boards": BoardStream,
            "epics": EpicStream,
            "sprints": SprintStream,
            "issues": IssueStream,
            "issue_comments": IssueCommentStream,
        }

    def build_streams(
        self, entry: CatalogEntry, context: Context
    ) -> list[BaseStream]:
        if not entry.tap_stream_id or not entry.metadata:
            return []

        selected_streams = _get_selected_streams(entry)
        if not selected_streams:
            return []

        match = re.match(PROJECT_STREAM_GROUP_PATTERN, entry.tap_stream_id)
        if not match:
            return []

        (project_id,) = match.groups()

        streams = []

        for stream_name in selected_streams:
            stream_class = self.streams.get(stream_name)
            if not stream_class:
                continue

            stream_id = f"{entry.tap_stream_id}_{stream_name}"
            streams.append(stream_class(project_id, stream_id, context))

        return streams


STREAM_GROUPS = [
    ProjectStreamGroup(),
]

STREAM_GROUPS_BY_TYPE = {group.group_type: group for group in STREAM_GROUPS}
