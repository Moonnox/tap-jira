from dataclasses import dataclass
from enum import Enum
from requests import Response


class HotglueClientError(Exception):
    status: int
    message: str | None

    def __init__(self, message: str, status: int):
        self.message = message
        self.status = status


class JiraCredentialsManagerError(Exception):
    """Base exception for Jira credentials manager errors."""


class CredentialsExpiredError(JiraCredentialsManagerError):
    """Exception raised when credentials refresh is required."""


class CredentialsRefreshFailedError(JiraCredentialsManagerError):
    """Exception raised when credentials refresh fails."""


class JiraClientException(Exception):
    def __init__(self, message: str, response: Response | None = None):
        super().__init__(message)
        self.message = message
        self.response = response
        self.status_code = response.status_code if response else None


class JiraRefreshCredentialsException(JiraClientException):
    pass


class JiraForbiddenException(JiraClientException):
    pass


class JiraBadRequestException(JiraClientException):
    pass


class JiraUnauthorizedException(JiraClientException):
    pass


class JiraNotFoundException(JiraClientException):
    pass


class JiraConflictException(JiraClientException):
    pass


class JiraRateLimitException(JiraClientException):
    pass


class JiraSubRequestFailedException(JiraClientException):
    pass


class JiraInternalServerException(JiraClientException):
    pass


class JiraNotImplementedException(JiraClientException):
    pass


class JiraBadGatewayException(JiraClientException):
    pass


class JiraServiceUnavailableException(JiraClientException):
    pass


class JiraGatewayTimeoutException(JiraClientException):
    pass


@dataclass(frozen=True)
class ErrorMapping:
    exception_class: type[JiraClientException]
    default_message: str


class JiraErrorCode(Enum):
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    RATE_LIMIT = 429
    SUB_REQUEST_FAILED = 449
    INTERNAL_SERVER_ERROR = 500
    NOT_IMPLEMENTED = 501
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504


ERROR_MAPPINGS = {
    JiraErrorCode.BAD_REQUEST: ErrorMapping(
        JiraBadRequestException, "A validation exception has occurred."
    ),
    JiraErrorCode.UNAUTHORIZED: ErrorMapping(
        JiraUnauthorizedException, "Invalid authorization credentials."
    ),
    JiraErrorCode.FORBIDDEN: ErrorMapping(
        JiraForbiddenException,
        "User does not have permission to access the resource.",
    ),
    JiraErrorCode.NOT_FOUND: ErrorMapping(
        JiraNotFoundException,
        "The resource you have specified cannot be found.",
    ),
    JiraErrorCode.CONFLICT: ErrorMapping(
        JiraConflictException,
        "The request does not match our state in some way.",
    ),
    JiraErrorCode.RATE_LIMIT: ErrorMapping(
        JiraRateLimitException,
        (
            "The API rate limit for your organisation/application pairing "
            "has been exceeded."
        ),
    ),
    JiraErrorCode.SUB_REQUEST_FAILED: ErrorMapping(
        JiraSubRequestFailedException,
        "The API was unable to process every part of the request.",
    ),
    JiraErrorCode.INTERNAL_SERVER_ERROR: ErrorMapping(
        JiraInternalServerException,
        (
            "The server encountered an unexpected condition which prevented "
            "it from fulfilling the request."
        ),
    ),
    JiraErrorCode.NOT_IMPLEMENTED: ErrorMapping(
        JiraNotImplementedException,
        (
            "The server does not support the functionality required to "
            "fulfill the request."
        ),
    ),
    JiraErrorCode.BAD_GATEWAY: ErrorMapping(
        JiraBadGatewayException, "Server received an invalid response."
    ),
    JiraErrorCode.SERVICE_UNAVAILABLE: ErrorMapping(
        JiraServiceUnavailableException,
        "API service is currently unavailable.",
    ),
    JiraErrorCode.GATEWAY_TIMEOUT: ErrorMapping(
        JiraGatewayTimeoutException,
        "API service time out, please check Jira server.",
    ),
}


def raise_for_error(response: Response) -> None:
    if response.status_code < 400:
        return

    try:
        error_code = JiraErrorCode(response.status_code)
        error_mapping = ERROR_MAPPINGS[error_code]
    except ValueError:
        # Unknown status code, use generic exception
        error_mapping = ErrorMapping(
            JiraClientException, "Unknown error occurred."
        )

    try:
        response_json = response.json()
        error_messages = response_json.get("errorMessages", [])
        api_error_message = error_messages[0] if error_messages else None
    except Exception:  # pylint:disable=broad-except
        api_error_message = None

    message = (
        f"HTTP Code: {response.status_code}, "
        f"Error: {api_error_message or error_mapping.default_message}"
    )

    raise error_mapping.exception_class(message, response)
