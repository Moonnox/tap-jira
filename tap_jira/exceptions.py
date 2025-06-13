from requests import Response


class JiraClientException(Exception):
    def __init__(self, message: str, response: Response | None = None):
        super().__init__(message)

        self.message = message
        self.response = response


class JiraRefreshCredentialsException(JiraClientException):
    pass


class JiraForbiddenException(JiraClientException):
    pass
