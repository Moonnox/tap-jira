from pathlib import Path
import re
from singer.catalog import Catalog, CatalogEntry
from singer import metadata as metadata_utils

from tap_jira.context import Context
from tap_jira.streams.base import BaseStream
from tap_jira.streams.groups import STREAM_GROUPS


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ID_PATTERN = r"^project_(?P<project_id>.+)$"


def _filter_selected_entries(catalog: Catalog) -> list[CatalogEntry]:
    selected: list[CatalogEntry] = []

    for entry in catalog.streams:
        metadata = metadata_utils.to_map(entry.metadata)

        if metadata_utils.get(metadata, (), "selected"):
            selected.append(entry)

    return selected


def _get_selected_project_ids(entries: list[CatalogEntry]) -> list[str]:
    project_ids = set()

    for entry in entries:
        if not entry.tap_stream_id or not entry.metadata:
            continue

        match = re.match(PROJECT_ID_PATTERN, entry.tap_stream_id)
        if not match:
            continue

        (project_id,) = match.groups()
        project_ids.add(project_id)

    return list(project_ids)


def _get_streams(project_ids: list[str], context: Context) -> list[BaseStream]:
    streams: list[BaseStream] = []

    for group in STREAM_GROUPS:
        group_streams = group.build_streams(project_ids, context)
        streams.extend(group_streams)

    return streams


def run(context: Context, catalog: Catalog):
    selected_entries = _filter_selected_entries(catalog)
    if not selected_entries:
        return

    selected_project_ids = _get_selected_project_ids(selected_entries)
    if not selected_project_ids:
        return

    streams = _get_streams(selected_project_ids, context)
    if not streams:
        return

    emitted_streams = set()
    for stream in streams:
        if stream.name in emitted_streams:
            continue

        stream.output_schema()
        emitted_streams.add(stream.name)

    for stream in streams:
        stream.sync()
