from abc import ABC, abstractmethod

import singer
from singer.catalog import CatalogEntry
from singer.transform import Transformer

from tap_jira.context import Context


class BaseStream(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        pass

    def __init__(self, stream_id: str, schema: dict, context: Context):
        self.stream_id = stream_id
        self.context = context

        # if not entry.schema or not entry.metadata:
        #     raise ValueError(
        #         f"Stream {self.stream_id} does not have schema or metadata "
        #         "defined."
        #     )

        self.schema = schema
        # self.metadata = metadata_utils.to_map(entry.metadata)

    @abstractmethod
    def sync(self) -> None:
        pass

    def write_page(self, page: list[dict]):
        for item in page:
            with Transformer() as transformer:
                item = transformer.transform(item, self.schema)

            singer.write_record(self.stream_id, item)


class ProjectStream(BaseStream):
    def __init__(
        self,
        project_id: str,
        stream_id: str,
        schema: dict,
        context: Context,
    ):
        super().__init__(stream_id, schema, context)
        self.project_id = project_id


class StreamGroup(ABC):
    @property
    @abstractmethod
    def group_name(self) -> str:
        pass

    @property
    @abstractmethod
    def streams(self) -> dict[str, type]:
        pass

    @abstractmethod
    def build_stream(
        self, entry: CatalogEntry, schema: dict, context: Context
    ) -> BaseStream | None:
        pass
