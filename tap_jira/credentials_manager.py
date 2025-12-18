from contextlib import nullcontext
from dataclasses import dataclass
from logging import Logger
import os

import requests

from tap_jira.distributed_lock import DistributedLock
from tap_jira.exceptions import (
    CredentialsExpiredError,
    CredentialsRefreshFailedError,
    JiraCredentialsManagerError,
)
from tap_jira.hotglue import HotglueClient

API_BASE_URL = "https://api.atlassian.com"
ACCESSIBLE_RESOURCES_URL = f"{API_BASE_URL}/oauth/token/accessible-resources"
REFRESH_TOKEN_URL = "https://auth.atlassian.com/oauth/token"


@dataclass
class JiraCredentials:
    access_token: str
    cloud_id: str
    site_name: str


@dataclass
class JiraOAuthCredentials:
    access_token: str
    refresh_token: str
    client_id: str
    client_secret: str
    site_name: str


class JiraCredentialsManager:
    REQUIRED_CONFIG_FIELDS = [
        "access_token",
        "refresh_token",
        "client_id",
        "client_secret",
        "site_name",
    ]

    def __init__(self, logger: Logger, timeout: int = 30):
        self.tenant_id = os.environ["TENANT"]
        self.hotglue = HotglueClient.from_env()
        self.dlock = DistributedLock.from_env(logger)
        self.logger = logger
        self.timeout = timeout

        self._credentials: JiraOAuthCredentials | None = None
        self._cloud_id: str | None = None
        self._integration_id: str | None = None
        self._integration_id_fetched: bool = False

    def request_credentials(self, refresh: bool = False) -> JiraCredentials:
        if not refresh and (self._credentials and self._cloud_id):
            return JiraCredentials(
                access_token=self._credentials.access_token,
                site_name=self._credentials.site_name,
                cloud_id=self._cloud_id,
            )

        with self._lock_context():
            try:
                current_creds, cloud_id = self._fetch_credentials()

                # Check if another process already refreshed by comparing
                # access tokens
                if (
                    not self._credentials
                    or self._credentials.access_token
                    != current_creds.access_token
                ):
                    # Someone else already refreshed, use those credentials
                    self._credentials = current_creds
                else:
                    # We need to refresh
                    self._credentials = self._request_new_credentials(
                        current_creds
                    )

                    self.hotglue.update_connector(
                        tenant_id=self.tenant_id,
                        config={
                            "access_token": self._credentials.access_token,
                            "refresh_token": self._credentials.refresh_token,
                        },
                    )

                if not cloud_id:
                    cloud_id = self._fetch_cloud_id(self._credentials)

                self._cloud_id = cloud_id
                # self._sync_local_config(self._credentials)

                return JiraCredentials(
                    access_token=self._credentials.access_token,
                    site_name=self._credentials.site_name,
                    cloud_id=self._cloud_id,
                )
            except CredentialsExpiredError as e:
                if refresh:
                    raise CredentialsRefreshFailedError(
                        "Failed to refresh Jira credentials"
                    ) from e

                return self.request_credentials(refresh=True)
            except Exception as e:
                self.logger.exception(
                    "Failed to request Jira credentials",
                    extra={
                        "client_id": (
                            self._credentials.client_id
                            if self._credentials
                            else None
                        ),
                        "site_name": (
                            self._credentials.site_name
                            if self._credentials
                            else None
                        ),
                    },
                )

                raise CredentialsRefreshFailedError(
                    "Failed to request Jira credentials"
                ) from e

    def _fetch_credentials(self) -> tuple[JiraOAuthCredentials, str | None]:
        jira_connector = self._fetch_hotglue_connector()
        if not jira_connector.config:
            raise JiraCredentialsManagerError(
                "Jira connector has no configuration"
            )

        config = jira_connector.config

        missing_fields = [
            field
            for field in self.REQUIRED_CONFIG_FIELDS
            if not getattr(config, field, None)
        ]
        if missing_fields:
            raise JiraCredentialsManagerError(
                (
                    "Jira connector configuration missing fields: "
                    f"{', '.join(missing_fields)}"
                )
            )

        credentials = JiraOAuthCredentials(
            access_token=str(config.access_token),
            refresh_token=str(config.refresh_token),
            client_id=str(config.client_id),
            client_secret=str(config.client_secret),
            site_name=str(config.site_name),
        )

        # Get cloud id from cached config if available
        cloud_id = None
        if config.cloud_ids and config.site_name in config.cloud_ids:
            cloud_id = config.cloud_ids[config.site_name]

        return (credentials, cloud_id)

    def _fetch_cloud_id(self, credentials: JiraOAuthCredentials) -> str:
        headers = {
            "Authorization": f"Bearer {credentials.access_token}",
            "Accept": "application/json",
        }

        response = requests.get(
            ACCESSIBLE_RESOURCES_URL,
            headers=headers,
            timeout=self.timeout,
        )
        if response.status_code == 401:
            raise CredentialsExpiredError("Invalid or expired access token")

        response.raise_for_status()

        resources = response.json()
        resource = next(
            (r for r in resources if r.get("name") == credentials.site_name),
            None,
        )

        cloud_id = resource.get("id") if resource else None
        if not cloud_id:
            raise JiraCredentialsManagerError(
                (
                    f"Cloud ID for site '{credentials.site_name}' not found "
                    "in accessible resources"
                )
            )

        self.hotglue.update_connector(
            tenant_id=self.tenant_id,
            config={
                "cloud_ids": {
                    credentials.site_name: str(cloud_id),
                },
            },
        )

        return str(cloud_id)

    def _request_new_credentials(
        self, credentials: JiraOAuthCredentials
    ) -> JiraOAuthCredentials:
        payload = {
            "grant_type": "refresh_token",
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "refresh_token": credentials.refresh_token,
        }

        response = requests.post(
            REFRESH_TOKEN_URL,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()

        data = response.json()
        return JiraOAuthCredentials(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            site_name=credentials.site_name,
        )

    def _fetch_hotglue_connector(self):
        jira_connector = self.hotglue.get_connector(self.tenant_id)
        if not jira_connector:
            raise JiraCredentialsManagerError(
                "Jira connector not found in Hotglue connectors"
            )

        return jira_connector

    def _fetch_integration_id(self) -> str | None:
        tenant_config = self.hotglue.get_tenant_config(self.tenant_id)
        if not tenant_config or not tenant_config.integration_id:
            return None

        return tenant_config.integration_id

    def _lock_context(self):
        lock_key = self._lock_key()
        if not lock_key:
            return nullcontext()

        return self.dlock.acquire(lock_key)

    def _lock_key(self) -> str | None:
        if not self._integration_id_fetched:
            self._integration_id = self._fetch_integration_id()
            self._integration_id_fetched = True

        if not self._integration_id:
            return None

        return f"integrations:{self._integration_id}:credentials"
