import json
from typing import Any, Self

import requests

from tap_jira.exceptions import (
    JiraForbiddenException,
    JiraRefreshCredentialsException,
)

BASE_URL = "https://api.atlassian.com"
ACCESSIBLE_RESOURCES_URL = f"{BASE_URL}/oauth/token/accessible-resources"


class OauthStrategy:
    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        config_path: str | None = None,
    ):
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._client_id = client_id
        self._client_secret = client_secret
        self._config_path = config_path

        self._session = requests.Session()

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Self:
        access_token = data.get("access_token")
        if not access_token:
            raise ValueError("Access token is required for OAuth strategy.")

        refresh_token = data.get("refresh_token")
        if not refresh_token:
            raise ValueError("Refresh token is required for OAuth strategy.")

        client_id = data.get("client_id")
        if not client_id:
            raise ValueError("Client ID is required for OAuth strategy.")

        client_secret = data.get("client_secret")
        if not client_secret:
            raise ValueError("Client secret is required for OAuth strategy.")

        return cls(
            access_token=access_token,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )

    def request(self, **kwargs):
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }

        try:
            with self._session.request(headers=headers, **kwargs) as response:
                response.raise_for_status()

                return response.json()
        except requests.RequestException as e:
            if e.response is not None and e.response.status_code == 401:
                self._refresh_credentials()

                return self.request(**kwargs)

            raise e

    def _refresh_credentials(self) -> None:
        access_token, refresh_token = self._refresh_tokens()

        self._access_token = access_token
        self._refresh_token = refresh_token

        if self._config_path:
            try:
                with open(
                    self._config_path, "r", encoding="utf-8"
                ) as config_file:
                    config = json.load(config_file)
                    config.update(
                        {
                            "access_token": access_token,
                            "refresh_token": refresh_token,
                        }
                    )

                with open(
                    self._config_path, "w", encoding="utf-8"
                ) as config_file:
                    json.dump(config, config_file, indent=4)
            except Exception as e:
                raise JiraRefreshCredentialsException(
                    f"Failed to update config file: {e}"
                ) from e

    def _refresh_tokens(self) -> tuple[str, str]:
        url = f"{BASE_URL}/oauth/token"
        result = {
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_token,
        }

        try:
            with self._session.post(url, data=result) as response:
                response.raise_for_status()
                result = response.json()

                access_token = result.get("access_token")
                refresh_token = result.get("refresh_token")

                if not access_token or not refresh_token:
                    raise JiraRefreshCredentialsException(
                        "Failed to refresh credentials", response
                    )

                return access_token, refresh_token
        except requests.RequestException as e:
            error_message = f"Failed to refresh credentials: {e}"

            if e.response is not None:
                raise JiraRefreshCredentialsException(
                    error_message, e.response
                ) from e

            raise JiraRefreshCredentialsException(error_message) from e
        except Exception as e:
            raise JiraRefreshCredentialsException(
                f"Failed to refresh credentials: {e}"
            ) from e


class JiraPaginator:
    def __init__(self):
        self._offset = 0

    @classmethod
    def default(cls):
        return cls()

    def pages(self, callback):
        while True:
            params = {"startAt": self._offset}

            response = callback(params)
            page = response.get("values", [])

            yield page

            if response.get("nextPage") is None or not page:
                break

            self._offset += len(page)


class Jira:
    _cloud_id: str | None = None

    def __init__(
        self,
        oauth: dict[str, str],
        site_name: str,
    ):
        self._strategy = OauthStrategy.from_dict(oauth)
        self._site_name = site_name

    def projects(self):
        yield from JiraPaginator.default().pages(self._fetch_projects)

    def _fetch_projects(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            url="/project/search",
            method="GET",
            params=params,
        )

    def _request(self, url: str, **kwargs):
        if not self._cloud_id:
            self._cloud_id = self._get_cloud_id_or_fail()

        url = f"{BASE_URL}/ex/jira/{self._cloud_id}/rest/api/3{url}"
        return self._strategy.request(
            url=url,
            **kwargs,
        )

    def _get_cloud_id_or_fail(self) -> str:
        if self._cloud_id:
            return self._cloud_id

        resources = self._strategy.request(
            url=ACCESSIBLE_RESOURCES_URL,
            method="GET",
        )
        resource = next(
            (
                resource
                for resource in resources
                if resource.get("name") == self._site_name
            ),
            None,
        )

        cloud_id = resource.get("id") if resource else None
        if not cloud_id:
            raise JiraForbiddenException(
                f"Invalid or unauthorized site name: {self._site_name}"
            )

        return str(cloud_id)
