import re
from typing import Dict, Optional
from singer.catalog import CatalogEntry

from tap_jira.context import Context
from tap_jira.streams.base import StreamGroup, BaseStream
from tap_jira.streams.project.board import BoardStream

PROJECT_STREAM_GROUP_PATTERN = r"^project/(?P<project_id>.+)$"


class ProjectStreamGroup(StreamGroup):
    @property
    def group_name(self) -> str:
        return "project"

    @property
    def streams(self) -> Dict[str, type]:
        return {
            "boards": BoardStream,
        }

    def build_stream(
        self, entry: CatalogEntry, schema: dict, context: Context
    ) -> Optional[BaseStream]:
        if not entry.tap_stream_id:
            return None

        match = re.match(PROJECT_STREAM_GROUP_PATTERN, entry.tap_stream_id)
        if not match:
            return None

        (project_id,) = match.groups()
        return BoardStream(
            project_id, f"{entry.tap_stream_id}/boards", schema, context
        )


STREAM_GROUPS = [
    ProjectStreamGroup(),
]

STREAM_GROUPS_BY_NAME = {group.group_name: group for group in STREAM_GROUPS}
