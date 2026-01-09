from abc import ABC, abstractmethod

import singer
from singer.transform import Transformer

from tap_jira import utils
from tap_jira.context import Context


class BaseStream(ABC):
    name: str

    @property
    @abstractmethod
    def primary_keys(self) -> list[str]:
        pass

    def __init__(
        self,
        stream_id: str,
        context: Context,
    ):
        self.stream_id = stream_id
        self.context = context
        self.schema = utils.load_schema(self.name)

    @abstractmethod
    def sync(self) -> None:
        pass

    def output_schema(self):
        singer.write_schema(
            self.name, self.schema, key_properties=self.primary_keys
        )

    def write_page(self, page: list[dict]):
        for item in page:
            with Transformer() as transformer:
                item = transformer.transform(item, self.schema)

            singer.write_record(self.name, item)


class ProjectBaseStream(BaseStream):
    def __init__(
        self,
        project_id: str,
        stream_id: str,
        context: Context,
        streams: "ProjectStreams",
    ):
        super().__init__(stream_id, context)
        self.project_id = project_id
        self.streams = streams


class CommonBaseStream(BaseStream):
    def __init__(
        self,
        project_ids: list[str],
        stream_id: str,
        context: Context,
    ):
        super().__init__(stream_id, context)
        self.project_ids = project_ids


class StreamGroup(ABC):
    @abstractmethod
    def build_streams(
        self, project_ids: list[str], context: Context
    ) -> list[BaseStream]:
        pass


ProjectStreams = dict[type[ProjectBaseStream], ProjectBaseStream]
