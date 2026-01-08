import logging
from typing import Any

import requests
import singer
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_chain,
    wait_fixed,
)

from tap_jira.credentials_manager import (
    JiraCredentials,
    JiraCredentialsManager,
)
from tap_jira.exceptions import JiraBadRequestException, raise_for_error
from tap_jira.utils import is_transient_error

BASE_URL = "https://api.atlassian.com"
JIRA_CONNECTOR_ID = "jira"
WAIT_TIME_SECONDS = [3, 10, 30]
LOGGER = singer.get_logger()


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
            is_list_response = isinstance(response, list)

            # If the response is a list, use it directly
            if is_list_response:
                page = response
            else:
                page = response.get(self._items_key, [])

            yield page

            if not page:
                break

            if not is_list_response and response.get("nextPage") is None:
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
    def __init__(
        self, credentials_manager: JiraCredentialsManager, timeout: int = 30
    ):
        self.credentials_manager = credentials_manager
        self.timeout = timeout

        self._credentials: JiraCredentials | None = None

    def timezone(self):
        result = self.request(url="/rest/api/2/myself", method="GET")

        return result.get("timeZone")

    def users(self):
        yield from JiraOffsetPaginator.default().pages(
            lambda params: self.request(
                url="/rest/api/3/users/search",
                method="GET",
                params=params,
            )
        )

    def assignable_users(self, project_id: str):
        yield from JiraOffsetPaginator.default().pages(
            lambda params: self.request(
                url="/rest/api/3/user/assignable/search",
                method="GET",
                params={
                    "project": project_id,
                    **params,
                },
            )
        )

    def projects(self, ids: list[str] | None = None):
        yield from JiraOffsetPaginator.default().pages(
            lambda params: self._fetch_projects({**params, "id": ids})
        )

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
                url="/rest/api/3/search/jql",
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
        try:
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
        except JiraBadRequestException as e:
            if "the browse project permission" in str(e):
                # If the project does not have the browse permission, return
                # an empty iterator
                yield []
            else:
                raise e

    def project_statuses(self, project_id: str):
        try:
            return self.request(
                url=f"/rest/api/3/project/{project_id}/statuses",
                method="GET",
            )
        except JiraBadRequestException as e:
            if "the browse project permission" in str(e):
                # If the project does not have the browse permission, return
                # an empty iterator
                return []
            else:
                raise e

    def _fetch_projects(self, params: dict[str, Any]) -> dict[str, Any]:
        return self.request(
            url="/rest/api/3/project/search",
            method="GET",
            # Only fetch projects that are accessible to the user to browse
            params={"action": "browse", **params},
        )

    @retry(
        stop=stop_after_attempt(len(WAIT_TIME_SECONDS) + 1),
        wait=wait_chain(*[wait_fixed(t) for t in WAIT_TIME_SECONDS]),
        retry=retry_if_exception(is_transient_error),
        before_sleep=before_sleep_log(LOGGER, logging.WARNING),
        reraise=True,
    )
    def request(self, url: str, refresh=False, **kwargs):
        if not self._credentials:
            self._credentials = self.credentials_manager.request_credentials()

        endpoint = f"{BASE_URL}/ex/jira/{self._credentials.cloud_id}{url}"
        headers = {
            "Authorization": f"Bearer {self._credentials.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            response = requests.request(
                url=endpoint,
                headers=headers,
                timeout=self.timeout,
                **kwargs,
            )
            if response.status_code == 401 and not refresh:
                self._credentials = (
                    self.credentials_manager.request_credentials(refresh=True)
                )
                return self.request(url=url, refresh=True, **kwargs)

            raise_for_error(response)
            return response.json()
        except requests.RequestException as e:
            if e.response is not None:
                raise_for_error(e.response)

            raise e
