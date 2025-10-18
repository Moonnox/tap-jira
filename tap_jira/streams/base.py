from abc import ABC, abstractmethod
from enum import Enum

import singer
from singer.catalog import CatalogEntry
from singer.transform import Transformer

from tap_jira import utils
from tap_jira.context import Context


class BaseStream(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

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
    ):
        super().__init__(stream_id, context)
        self.project_id = project_id


class StreamGroupType(Enum):
    PROJECT = "project"


class StreamGroup(ABC):
    @property
    @abstractmethod
    def group_type(self) -> StreamGroupType:
        pass

    @property
    @abstractmethod
    def streams(self) -> dict[str, type]:
        pass

    @abstractmethod
    def build_streams(
        self, entry: CatalogEntry, context: Context
    ) -> list[BaseStream]:
        pass
