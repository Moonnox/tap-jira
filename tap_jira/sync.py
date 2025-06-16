from pathlib import Path
from singer.catalog import Catalog, CatalogEntry
from singer import metadata as metadata_utils

from tap_jira.context import Context
from tap_jira.streams.base import BaseStream, StreamGroupType
from tap_jira.streams.groups import STREAM_GROUPS_BY_TYPE


BASE_DIR = Path(__file__).resolve().parent


def _filter_selected_entries(catalog: Catalog) -> list[CatalogEntry]:
    selected: list[CatalogEntry] = []

    for entry in catalog.streams:
        metadata = metadata_utils.to_map(entry.metadata)

        if metadata_utils.get(metadata, (), "selected"):
            selected.append(entry)

    return selected


def _get_streams_for_entry(
    entry: CatalogEntry, context: Context
) -> list[BaseStream]:
    if not entry.tap_stream_id:
        return []

    metadata = metadata_utils.to_map(entry.metadata)
    group = StreamGroupType(metadata_utils.get(metadata, (), "group"))

    stream_group = STREAM_GROUPS_BY_TYPE.get(group)
    if stream_group:
        return stream_group.build_streams(entry, context)

    return []


def run(context: Context, catalog: Catalog):
    selected = _filter_selected_entries(catalog)
    if not selected:
        return

    emitted_streams = set()

    for entry in selected:
        streams = _get_streams_for_entry(entry, context)
        context.set_selected_streams(streams)

        for stream in streams:
            if stream.name in emitted_streams:
                continue

            stream.output_schema()
            emitted_streams.add(stream.name)

        for stream in streams:
            stream.sync()

        context.set_selected_streams(None)
