import os
from typing import Any

import httpx

from github_context_tools.exceptions import (
    AuthenticationError,
    GitHubAPIError,
    NotFoundError,
    RateLimitError,
)

GITHUB_API_BASE = "https://api.github.com"

_HTTP_ERRORS: dict[int, tuple[type[GitHubAPIError], str]] = {
    401: (AuthenticationError, "Authentication failed — check your token"),
    403: (AuthenticationError, "Permission denied — token may lack required scopes"),
    404: (NotFoundError, "Resource not found"),
    429: (RateLimitError, "GitHub API rate limit exceeded"),
}


def _resolve_token(token: str | None) -> str:
    resolved = token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not resolved:
        raise ValueError(
            "No GitHub token provided. Pass token= to make_tools() or set the "
            "GH_TOKEN / GITHUB_TOKEN environment variable."
        )
    return resolved


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    try:
        detail = response.json().get("message", "")
    except Exception:
        detail = ""
    msg = f"{detail} ({response.url})" if detail else str(response.url)
    exc_class, prefix = _HTTP_ERRORS.get(
        response.status_code,
        (GitHubAPIError, f"GitHub API error {response.status_code}"),
    )
    raise exc_class(f"{prefix}: {msg}", status_code=response.status_code)


def make_requester(token: str | None = None, http_client: httpx.Client | None = None):
    """
    Returns a (get_json, get_text, post_json) triple of callables that share a
    resolved token and a single Client per make_requester call.

    The Client is thread-safe; concurrent tool calls from a thread pool work
    correctly without any additional synchronisation.

    :param token: GitHub personal access token. If omitted, reads from the
                  GH_TOKEN or GITHUB_TOKEN environment variable.
    :param http_client: Optional httpx.Client instance. Use this to configure
                        SSL settings, proxies, timeouts, etc. If omitted, a new
                        client is created.
    """
    resolved = _resolve_token(token)
    if http_client is not None:
        client = http_client
    else:
        client = httpx.Client()

    default_headers = {
        "Authorization": f"Bearer {resolved}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    def _url(path: str) -> str:
        return path if path.startswith("https://") else f"{GITHUB_API_BASE}{path}"

    def _get(path: str, *, headers: dict[str, str] | None = None) -> httpx.Response:
        merged = {**default_headers, **(headers or {})}
        response = client.get(_url(path), headers=merged)
        _raise_for_status(response)
        return response

    def _post(
        path: str, body: dict[str, Any], *, headers: dict[str, str] | None = None
    ) -> httpx.Response:
        merged = {
            **default_headers,
            "Content-Type": "application/json",
            **(headers or {}),
        }
        response = client.post(_url(path), json=body, headers=merged)
        _raise_for_status(response)
        return response

    def get_json(path: str, *, headers: dict[str, str] | None = None) -> Any:
        return _get(path, headers=headers).json()

    def get_text(path: str, *, headers: dict[str, str] | None = None) -> str:
        return _get(path, headers=headers).text

    def post_json(
        path: str, body: dict[str, Any], *, headers: dict[str, str] | None = None
    ) -> Any:
        return _post(path, body, headers=headers).json()

    return get_json, get_text, post_json
