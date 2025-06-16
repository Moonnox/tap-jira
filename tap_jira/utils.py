import json
from pathlib import Path

import singer.metadata as metadata_utils
from singer.catalog import Schema

BASE_DIR = Path(__file__).resolve().parent


def load_schema(name: str) -> dict:
    schema_path = BASE_DIR / "schemas" / f"{name}.json"

    return json.loads(schema_path.read_text(encoding="utf-8"))


def build_schema_metadata(
    schema: Schema, primary_keys: list[str] | None = None
) -> list[dict]:
    if primary_keys is None:
        primary_keys = []

    metadata = metadata_utils.new()

    if not schema.properties:
        return metadata_utils.to_list(metadata)

    for prop in schema.properties:
        inclusion = "automatic" if prop in primary_keys else "available"

        metadata_utils.write(
            metadata, ("properties", prop), "inclusion", inclusion
        )

    return metadata_utils.to_list(metadata)
