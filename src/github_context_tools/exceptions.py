class GitHubAPIError(Exception):
    """Raised when the GitHub API returns an unexpected error."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class NotFoundError(GitHubAPIError):
    """Raised when the requested resource does not exist (HTTP 404)."""


class AuthenticationError(GitHubAPIError):
    """Raised when the token is missing, invalid, or lacks required scopes (HTTP 401/403)."""


class RateLimitError(GitHubAPIError):
    """Raised when the GitHub API rate limit is exceeded (HTTP 429)."""
