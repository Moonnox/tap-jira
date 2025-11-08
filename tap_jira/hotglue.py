from dataclasses import dataclass
import logging
import os
from typing import Any
from urllib.parse import urljoin
import singer
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_chain,
    wait_fixed,
)

import requests

from tap_jira.exceptions import HotglueClientError
from tap_jira.utils import is_transient_error

BASE_URL = "https://client-api.hotglue.xyz"
JIRA_CONNECTOR_ID = "jira"
WAIT_TIME_SECONDS = [3, 10, 30]
LOGGER = singer.get_logger()


@dataclass
class HotglueConfig:
    environment_id: str
    flow_id: str
    api_key: str


@dataclass
class HotglueConnectorConfig:
    client_id: str | None = None
    client_secret: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    site_name: str | None = None
    cloud_ids: dict[str, str] | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "HotglueConnectorConfig":
        return cls(
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            access_token=data.get("access_token"),
            refresh_token=data.get("refresh_token"),
            site_name=data.get("site_name"),
            cloud_ids=data.get("cloud_ids"),
        )


@dataclass
class HotglueTenantConfig:
    integration_id: str | None

    @classmethod
    def from_dict(cls, data: dict) -> "HotglueTenantConfig":
        return cls(integration_id=data.get("integration_id"))


@dataclass
class HotglueConnector:
    id: str
    config: HotglueConnectorConfig | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "HotglueConnector":
        config_data = data.get("config")
        config = (
            HotglueConnectorConfig.from_dict(config_data)
            if config_data
            else None
        )

        return cls(id=data["id"], config=config)


class HotglueClient:
    def __init__(self, config: HotglueConfig, timeout: int = 30) -> None:
        self.config = config
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> "HotglueClient":
        config = HotglueConfig(
            environment_id=os.environ["ENV_ID"],
            flow_id=os.environ["FLOW"],
            api_key=os.environ["API_KEY"],
        )

        return cls(config)

    def get_connectors(self, tenant_id: str) -> list[HotglueConnector]:
        path = (
            f"/v2/{self.config.environment_id}/"
            f"{self.config.flow_id}/"
            f"{tenant_id}/linkedConnectors?config=true"
        )
        result = self._request("GET", path)

        return [HotglueConnector.from_dict(connector) for connector in result]

    def get_connector(self, tenant_id: str) -> HotglueConnector | None:
        connectors = self.get_connectors(tenant_id)

        return next((c for c in connectors if c.id == JIRA_CONNECTOR_ID), None)

    def get_tenant_config(self, tenant_id: str) -> HotglueTenantConfig | None:
        try:
            path = f"/tenant/{self.config.environment_id}/{tenant_id}/config"
            result = self._request("GET", path)

            return HotglueTenantConfig.from_dict(result)
        except HotglueClientError as e:
            if e.message and "no config for the tenant" in e.message.lower():
                return None

            raise

    def update_connector(
        self,
        tenant_id: str,
        config: dict[str, Any],
    ):
        path = (
            f"/v2/{self.config.environment_id}/"
            f"{self.config.flow_id}/"
            f"{tenant_id}/linkedConnectors"
        )
        payload = {"connector_id": str(JIRA_CONNECTOR_ID), "config": config}

        self._request("PATCH", path, payload)

    @retry(
        stop=stop_after_attempt(len(WAIT_TIME_SECONDS) + 1),
        wait=wait_chain(*[wait_fixed(t) for t in WAIT_TIME_SECONDS]),
        retry=retry_if_exception(is_transient_error),
        before_sleep=before_sleep_log(LOGGER, logging.WARNING),
        reraise=True,
    )
    def _request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        params: dict | None = None,
    ):
        url = urljoin(BASE_URL, path)

        response = requests.request(
            method,
            url,
            json=payload,
            params=params,
            headers={
                "x-api-key": self.config.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=self.timeout,
        )

        try:
            response.raise_for_status()

            return response.json()
        except requests.HTTPError as e:
            raise HotglueClientError(
                response.text or str(e), response.status_code
            ) from e
