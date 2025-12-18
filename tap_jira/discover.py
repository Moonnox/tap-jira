import json
from pathlib import Path
from itertools import chain

from singer.catalog import Catalog, CatalogEntry, Schema
import singer.metadata as Metadata

from tap_jira.context import Context

BASE_DIR = Path(__file__).resolve().parent
DISCOVERY_SCHEMA_NAME = "_discovery"


def _load_schema(name: str) -> dict:
    schema_path = BASE_DIR / "schemas" / f"{name}.json"

    return json.loads(schema_path.read_text(encoding="utf-8"))


def _build_metadata(schema: Schema, default: dict | None = None):
    metadata = Metadata.new()

    if not schema.properties:
        return Metadata.to_list(metadata)

    for prop in schema.properties:
        Metadata.write(
            metadata, ("properties", prop), "inclusion", "available"
        )

    if default:
        for key, value in default.items():
            Metadata.write(metadata, (), key, value)

    return Metadata.to_list(metadata)


def run(context: Context) -> Catalog:
    catalog = Catalog([])

    try:
        schema = Schema.from_dict(_load_schema(DISCOVERY_SCHEMA_NAME))
        metadata = _build_metadata(schema, {"group": "project"})
        projects = chain.from_iterable(context.jira.projects())

        for project in projects:
            stream_id = f"project_{project['id']}"
            stream_name = f"{project['name']} ({project['key']})"

            entry = CatalogEntry(
                tap_stream_id=stream_id,
                stream=stream_name,
                schema=schema,
                metadata=metadata,
            )
            catalog.streams.append(entry)

        return catalog
    except Exception as e:  # pylint: disable=broad-except
        context.logger.error(
            "Failed to discover streams. Please check your configuration "
            "and connection to Jira.",
            exc_info=e,
        )

        return catalog
