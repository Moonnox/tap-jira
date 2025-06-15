import json
from pathlib import Path
import singer
from singer.catalog import Catalog, CatalogEntry
from singer import metadata as metadata_utils

from tap_jira.context import Context
from tap_jira.streams.groups import STREAM_GROUPS_BY_NAME


BASE_DIR = Path(__file__).resolve().parent


def _load_schema(name: str) -> dict:
    schema_path = BASE_DIR / "schemas" / f"{name}.json"

    return json.loads(schema_path.read_text(encoding="utf-8"))


def _filter_selected_entries(catalog: Catalog) -> list[CatalogEntry]:
    selected: list[CatalogEntry] = []

    for entry in catalog.streams:
        metadata = metadata_utils.to_map(entry.metadata)

        if metadata_utils.get(metadata, (), "selected"):
            selected.append(entry)

    return selected


def _get_stream_from_entry(entry: CatalogEntry, context: Context):
    if not entry.tap_stream_id:
        return None

    stream_group = STREAM_GROUPS_BY_NAME.get("project")
    schema = _load_schema("boards")
    if stream_group:
        return stream_group.build_stream(entry, schema, context)

    return None


def run(context: Context, catalog: Catalog):
    selected = _filter_selected_entries(catalog)
    for entry in selected:
        stream = _get_stream_from_entry(entry, context)

        if not stream:
            continue

        schema = _load_schema("boards")
        singer.write_schema(stream.stream_id, schema, ["id"])

        stream.sync()
