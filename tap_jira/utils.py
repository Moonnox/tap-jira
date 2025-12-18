import json
from pathlib import Path

import requests
import singer.metadata as metadata_utils
from singer.catalog import Schema

from tap_jira.exceptions import HotglueClientError, JiraClientException

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


def is_transient_error(exception: BaseException) -> bool:
    # Retry on connection errors or timeouts
    if isinstance(exception, (requests.ConnectionError, requests.Timeout)):
        return True

    # Retry on 5xx server errors and 429 Too Many Requests
    status = None
    if isinstance(exception, requests.HTTPError):
        status = exception.response.status_code if exception.response else None

    if isinstance(exception, HotglueClientError):
        status = exception.status

    if isinstance(exception, JiraClientException):
        status = exception.status_code

    if isinstance(status, int):
        return 500 <= status < 600 or status == 429

    return False
