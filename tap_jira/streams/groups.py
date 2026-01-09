from tap_jira.context import Context
from tap_jira.streams.base import (
    CommonBaseStream,
    ProjectBaseStream,
    ProjectStreams,
    StreamGroup,
    BaseStream,
)
from tap_jira.streams.common.project import ProjectStream
from tap_jira.streams.common.settings import SettingsStream
from tap_jira.streams.common.user import UserStream
from tap_jira.streams.project.board import BoardStream
from tap_jira.streams.project.issue import IssueStream
from tap_jira.streams.project.issue_comment import IssueCommentStream
from tap_jira.streams.project.issue_status import IssueStatusStream


class CommonStreamGroup(StreamGroup):
    @property
    def streams(self) -> dict[str, type[CommonBaseStream]]:
        return {
            "projects": ProjectStream,
            "users": UserStream,
            "settings": SettingsStream,
        }

    def build_streams(
        self, project_ids: list[str], context: Context
    ) -> list[BaseStream]:
        streams: list[BaseStream] = []

        for stream_name, stream_class in self.streams.items():
            stream_id = stream_name
            streams.append(stream_class(project_ids, stream_id, context))

        return streams


class ProjectStreamGroup(StreamGroup):
    @property
    def streams(self) -> dict[str, type[ProjectBaseStream]]:
        return {
            "boards": BoardStream,
            "issues": IssueStream,
            "issue_comments": IssueCommentStream,
            "issue_statuses": IssueStatusStream,
        }

    def build_streams(
        self, project_ids: list[str], context: Context
    ) -> list[BaseStream]:
        streams: list[BaseStream] = []

        for project_id in project_ids:
            project_streams: ProjectStreams = {}

            for stream_name, stream_class in self.streams.items():
                stream_id = f"project_{project_id}_{stream_name}"
                stream = stream_class(
                    project_id, stream_id, context, project_streams
                )

                project_streams[stream_class] = stream
                streams.append(stream)

        return streams


STREAM_GROUPS: list[StreamGroup] = [
    CommonStreamGroup(),
    ProjectStreamGroup(),
]
