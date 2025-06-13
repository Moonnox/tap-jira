import json
from pathlib import Path
from itertools import chain

from singer.catalog import Catalog, CatalogEntry, Schema
import singer.metadata as Metadata

from tap_jira.context import Context

BASE_DIR = Path(__file__).resolve().parent
PROJECT_SCHEMA_NAME = "project"


def _load_schema(name: str) -> dict:
    schema_path = BASE_DIR / "schemas" / f"{name}.json"

    return json.loads(schema_path.read_text(encoding="utf-8"))


def _build_metadata(schema: Schema):
    metadata = Metadata.new()

    if not schema.properties:
        return Metadata.to_list(metadata)

    for prop in schema.properties:
        Metadata.write(
            metadata, ("properties", prop), "inclusion", "available"
        )

    return Metadata.to_list(metadata)


def run(context: Context):
    catalog = Catalog([])

    schema = Schema.from_dict(_load_schema(PROJECT_SCHEMA_NAME))
    metadata = _build_metadata(schema)

    if not context.config.site_name:
        return catalog

    projects = chain.from_iterable(context.jira.projects())
    for project in projects:
        stream_id = project["id"]
        stream_name = f"{project['name']} ({project['key']})"

        entry = CatalogEntry(
            tap_stream_id=stream_id,
            stream=stream_name,
            schema=schema,
            metadata=metadata,
        )
        catalog.streams.append(entry)

    return catalog
