import os
import pytest
import httpx
import respx

from github_context_tools._request import _resolve_token, _raise_for_status, make_requester
from github_context_tools.exceptions import (
    AuthenticationError,
    GitHubAPIError,
    NotFoundError,
    RateLimitError,
)


# ── _resolve_token ────────────────────────────────────────────────────────────

class TestResolveToken:
    def test_explicit_token(self, monkeypatch):
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        assert _resolve_token("my-token") == "my-token"

    def test_falls_back_to_gh_token_env(self, monkeypatch):
        monkeypatch.setenv("GH_TOKEN", "env-token")
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        assert _resolve_token(None) == "env-token"

    def test_falls_back_to_github_token_env(self, monkeypatch):
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.setenv("GITHUB_TOKEN", "github-env-token")
        assert _resolve_token(None) == "github-env-token"

    def test_gh_token_takes_priority_over_github_token(self, monkeypatch):
        monkeypatch.setenv("GH_TOKEN", "primary")
        monkeypatch.setenv("GITHUB_TOKEN", "secondary")
        assert _resolve_token(None) == "primary"

    def test_explicit_token_takes_priority_over_env(self, monkeypatch):
        monkeypatch.setenv("GH_TOKEN", "env-token")
        assert _resolve_token("explicit") == "explicit"

    def test_raises_when_no_token(self, monkeypatch):
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(ValueError, match="No GitHub token"):
            _resolve_token(None)

    def test_raises_when_empty_string(self, monkeypatch):
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(ValueError, match="No GitHub token"):
            _resolve_token("")


# ── _raise_for_status ─────────────────────────────────────────────────────────

def _make_response(status_code: int, body: dict | None = None) -> httpx.Response:
    import json
    content = json.dumps(body or {}).encode()
    return httpx.Response(status_code, content=content, request=httpx.Request("GET", "https://api.github.com/test"))


class TestRaiseForStatus:
    def test_2xx_does_not_raise(self):
        _raise_for_status(_make_response(200))
        _raise_for_status(_make_response(201))

    def test_401_raises_authentication_error(self):
        with pytest.raises(AuthenticationError):
            _raise_for_status(_make_response(401))

    def test_403_raises_authentication_error(self):
        with pytest.raises(AuthenticationError):
            _raise_for_status(_make_response(403))

    def test_404_raises_not_found_error(self):
        with pytest.raises(NotFoundError):
            _raise_for_status(_make_response(404))

    def test_429_raises_rate_limit_error(self):
        with pytest.raises(RateLimitError):
            _raise_for_status(_make_response(429))

    def test_unknown_status_raises_github_api_error(self):
        with pytest.raises(GitHubAPIError):
            _raise_for_status(_make_response(500))

    def test_error_includes_message_from_body(self):
        with pytest.raises(NotFoundError, match="Not Found"):
            _raise_for_status(_make_response(404, {"message": "Not Found"}))

    def test_error_subclass_hierarchy(self):
        with pytest.raises(GitHubAPIError):
            _raise_for_status(_make_response(404))

    def test_status_code_attached(self):
        with pytest.raises(NotFoundError) as exc_info:
            _raise_for_status(_make_response(404))
        assert exc_info.value.status_code == 404

    def test_rate_limit_status_code_attached(self):
        with pytest.raises(RateLimitError) as exc_info:
            _raise_for_status(_make_response(429))
        assert exc_info.value.status_code == 429


# ── exceptions ────────────────────────────────────────────────────────────────

class TestExceptions:
    def test_github_api_error_message(self):
        e = GitHubAPIError("something went wrong", status_code=500)
        assert str(e) == "something went wrong"
        assert e.status_code == 500

    def test_github_api_error_default_status_code(self):
        e = GitHubAPIError("oops")
        assert e.status_code is None

    def test_not_found_is_github_api_error(self):
        assert issubclass(NotFoundError, GitHubAPIError)

    def test_authentication_error_is_github_api_error(self):
        assert issubclass(AuthenticationError, GitHubAPIError)

    def test_rate_limit_error_is_github_api_error(self):
        assert issubclass(RateLimitError, GitHubAPIError)

    def test_not_found_carries_status_code(self):
        e = NotFoundError("not found", status_code=404)
        assert e.status_code == 404

    def test_authentication_error_carries_status_code(self):
        e = AuthenticationError("forbidden", status_code=403)
        assert e.status_code == 403


# ── make_requester ────────────────────────────────────────────────────────────

class TestMakeRequester:
    def test_raises_without_token(self, monkeypatch):
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(ValueError, match="No GitHub token"):
            make_requester(token=None)

    def test_returns_three_callables(self, monkeypatch):
        monkeypatch.setenv("GH_TOKEN", "test-token")
        result = make_requester()
        assert len(result) == 3
        assert all(callable(fn) for fn in result)

    @respx.mock
    def test_get_json_returns_parsed_json(self, monkeypatch):
        monkeypatch.setenv("GH_TOKEN", "test-token")
        respx.get("https://api.github.com/repos/org/repo").mock(
            return_value=httpx.Response(200, json={"name": "repo"})
        )
        get_json, _, _ = make_requester()
        result = get_json("/repos/org/repo")
        assert result == {"name": "repo"}

    @respx.mock
    def test_get_text_returns_string(self, monkeypatch):
        monkeypatch.setenv("GH_TOKEN", "test-token")
        respx.get("https://api.github.com/repos/org/repo/pulls/1").mock(
            return_value=httpx.Response(200, text="diff --git a/foo b/foo")
        )
        _, get_text, _ = make_requester()
        result = get_text("/repos/org/repo/pulls/1")
        assert result == "diff --git a/foo b/foo"

    @respx.mock
    def test_post_json_sends_body_and_returns_json(self, monkeypatch):
        monkeypatch.setenv("GH_TOKEN", "test-token")
        respx.post("https://api.github.com/graphql").mock(
            return_value=httpx.Response(200, json={"data": {}})
        )
        _, _, post_json = make_requester()
        result = post_json("/graphql", body={"query": "{ viewer { login } }"})
        assert result == {"data": {}}

    @respx.mock
    def test_authorization_header_sent(self, monkeypatch):
        monkeypatch.setenv("GH_TOKEN", "test-token")
        route = respx.get("https://api.github.com/repos/org/repo").mock(
            return_value=httpx.Response(200, json={})
        )
        get_json, _, _ = make_requester()
        get_json("/repos/org/repo")
        assert route.called
        assert route.calls[0].request.headers["Authorization"] == "Bearer test-token"

    @respx.mock
    def test_404_raises_not_found(self, monkeypatch):
        monkeypatch.setenv("GH_TOKEN", "test-token")
        respx.get("https://api.github.com/repos/org/missing").mock(
            return_value=httpx.Response(404, json={"message": "Not Found"})
        )
        get_json, _, _ = make_requester()
        with pytest.raises(NotFoundError):
            get_json("/repos/org/missing")

    @respx.mock
    def test_custom_http_client_used(self, monkeypatch):
        monkeypatch.setenv("GH_TOKEN", "test-token")
        respx.get("https://api.github.com/repos/org/repo").mock(
            return_value=httpx.Response(200, json={"name": "repo"})
        )
        custom_client = httpx.Client()
        get_json, _, _ = make_requester(http_client=custom_client)
        result = get_json("/repos/org/repo")
        assert result == {"name": "repo"}

    def test_default_client_created_when_none_passed(self, monkeypatch):
        monkeypatch.setenv("GH_TOKEN", "test-token")
        get_json, _, _ = make_requester()
        assert callable(get_json)

    @respx.mock
    def test_absolute_url_passed_through(self, monkeypatch):
        monkeypatch.setenv("GH_TOKEN", "test-token")
        respx.get("https://raw.githubusercontent.com/org/repo/main/file.txt").mock(
            return_value=httpx.Response(200, text="content")
        )
        _, get_text, _ = make_requester()
        result = get_text("https://raw.githubusercontent.com/org/repo/main/file.txt")
        assert result == "content"
