import json
from typing import Any

import requests

from tap_jira.exceptions import (
    JiraBadRequestException,
    JiraForbiddenException,
    JiraRefreshCredentialsException,
    raise_for_error,
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
    def from_dict(cls, data: dict[str, str]) -> "OauthStrategy":
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
            config_path=data.get("config_path"),
        )

    def request(self, **kwargs):
        return self._request_with_retry(**kwargs, _retry_count=0)

    def _request_with_retry(self, **kwargs):
        _retry_count = kwargs.pop("_retry_count", 0)
        max_refresh_attempts = 1

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            with self._session.request(headers=headers, **kwargs) as response:
                if response.status_code == 401:
                    if _retry_count >= max_refresh_attempts:
                        raise_for_error(response)

                    self._refresh_credentials()
                    return self._request_with_retry(
                        **kwargs, _retry_count=_retry_count + 1
                    )

                raise_for_error(response)
                return response.json()
        except requests.RequestException as e:
            if e.response is not None:
                raise_for_error(e.response)

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
        url = "https://auth.atlassian.com/oauth/token"
        result = {
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_token,
        }

        try:
            with requests.post(url, data=result, timeout=10) as response:
                raise_for_error(response)
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


class JiraOffsetPaginator:
    def __init__(self, items_key: str | None = None):
        self._offset = 0
        self._items_key = items_key or "values"

    @classmethod
    def default(cls, items_key: str | None = None) -> "JiraOffsetPaginator":
        return cls(
            items_key=items_key,
        )

    def pages(self, callback):
        while True:
            params = {"startAt": self._offset}

            response = callback(params)
            page = response.get(self._items_key, [])

            yield page

            if response.get("nextPage") is None or not page:
                break

            self._offset += len(page)


class JiraCursorPaginator:
    def __init__(
        self, next_page: str | None = None, items_key: str | None = None
    ):
        self._next_page = next_page
        self._items_key = items_key or "values"

    @classmethod
    def default(
        cls, next_page: str | None = None, items_key: str | None = None
    ) -> "JiraCursorPaginator":
        return cls(
            next_page=next_page,
            items_key=items_key,
        )

    @property
    def next_page(self) -> str | None:
        return self._next_page

    def pages(self, callback):
        while True:
            params = {"nextPageToken": self._next_page}

            response = callback(params)
            page = response.get(self._items_key, [])

            yield page

            next_page_token = response.get("nextPageToken", None)
            if next_page_token is None or not page:
                break

            self._next_page = next_page_token


class Jira:
    _cloud_id: str | None = None

    def __init__(
        self,
        oauth: dict[str, str],
        site_name: str,
    ):
        self._strategy = OauthStrategy.from_dict(oauth)
        self._site_name = site_name

    def timezone(self):
        result = self.request(url="/rest/api/2/myself", method="GET")

        return result.get("timeZone")

    def projects(self):
        yield from JiraOffsetPaginator.default().pages(self._fetch_projects)

    def project_issues(
        self,
        project_id: str,
        updated_after: str | None = None,
        from_page: str | None = None,
    ):
        jql = (
            f"project={project_id} "
            f"AND updated >= '{updated_after}' "
            "ORDER BY updated ASC"
        )

        paginator = JiraCursorPaginator.default(
            next_page=from_page, items_key="issues"
        )
        pages = paginator.pages(
            lambda params: self.request(
                url="/rest/api/2/search/jql",
                method="GET",
                params={
                    "expand": ["renderedFields"],
                    "jql": jql,
                    "fields": ["*all", "-worklog", "-operations"],
                    "fieldsByKeys": True,
                    **params,
                },
            )
        )

        for page in pages:
            if not page:
                break

            yield page, paginator.next_page

    def project_boards(self, project_id: str):
        yield from JiraOffsetPaginator.default().pages(
            lambda params: self.request(
                url="/rest/agile/1.0/board",
                method="GET",
                params={
                    "projectKeyOrId": project_id,
                    **params,
                },
            )
        )

    def board_epics(self, board_id: str):
        yield from JiraOffsetPaginator.default().pages(
            lambda params: self.request(
                url=f"/rest/agile/1.0/board/{board_id}/epic",
                method="GET",
                params=params,
            )
        )

    def board_sprints(self, board_id: str):
        try:
            yield from JiraOffsetPaginator.default().pages(
                lambda params: self.request(
                    url=f"/rest/agile/1.0/board/{board_id}/sprint",
                    method="GET",
                    params=params,
                )
            )
        except JiraBadRequestException as e:
            if "does not support sprints" in str(e):
                # If the board does not support sprints, return an empty
                # iterator
                yield []

    def _fetch_projects(self, params: dict[str, Any]) -> dict[str, Any]:
        return self.request(
            url="/rest/api/3/project/search",
            method="GET",
            params=params,
        )

    def request(self, url: str, **kwargs):
        if not self._cloud_id:
            self._cloud_id = self._get_cloud_id_or_fail()

        url = f"{BASE_URL}/ex/jira/{self._cloud_id}{url}"
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
