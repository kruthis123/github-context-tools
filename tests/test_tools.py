import base64
import inspect
import pytest
from typing import Annotated, get_type_hints, get_args
from unittest.mock import MagicMock

from github_context_tools.tools import make_tools
from github_context_tools.models import (
    PRMetadata,
    PRDiff,
    CommitDiff,
    FileContent,
    SearchResult,
    CommitSummary,
    BlameEntry,
    PRDescription,
    PRComment,
    Issue,
    IssueComment,
    RepoConventions,
)
from github_context_tools._utils import parse_pr_url, validate_repo
from github_context_tools.tools.code import (
    _is_sibling,
    _build_tree,
    _build_search_query,
    _parse_text_matches,
    _search_results_from_response,
)
from github_context_tools.tools.history import _blame_entries_from_response


def get_tool(tools, name):
    return next(t for t in tools if t.__name__ == name)


# ── Fixtures & helpers ────────────────────────────────────────────────────────

PULL_REQUEST_RESPONSE = {
    "number": 42,
    "title": "Add feature",
    "body": "This adds the feature.",
    "html_url": "https://github.com/org/repo/pull/42",
    "user": {"login": "alice", "html_url": "https://github.com/alice"},
    "base": {
        "ref": "main",
        "sha": "base000",
        "repo": {"owner": {"login": "org"}, "name": "repo"},
    },
    "head": {"ref": "feature/add", "sha": "head111"},
    "state": "open",
    "commits": 3,
    "changed_files": 2,
    "additions": 10,
    "deletions": 4,
}

DIFF_TEXT = """\
diff --git a/src/foo.py b/src/foo.py
index 0000000..1111111 100644
--- a/src/foo.py
+++ b/src/foo.py
@@ -1,3 +1,4 @@
 def foo():
-    pass
+    return 1
+
"""

PR_URL = "https://github.com/org/repo/pull/42"


def make_mock_requester(pr_data=None, diff_text=None):
    pr_data = pr_data or PULL_REQUEST_RESPONSE
    diff = diff_text or DIFF_TEXT
    return (
        MagicMock(return_value=pr_data),
        MagicMock(return_value=diff),
        MagicMock(),
    )


@pytest.fixture
def tools(monkeypatch):
    monkeypatch.setattr(
        "github_context_tools.tools.factory.make_requester",
        lambda *_, **__: make_mock_requester(),
    )
    return make_tools(token="test-token")


FILE_CONTENT = "def foo():\n    return 1\n"

TREE_RESPONSE = {
    "tree": [
        {"path": "src/foo.py",       "type": "blob"},
        {"path": "src/bar.py",       "type": "blob"},
        {"path": "src/",             "type": "tree"},
        {"path": "tests/test_foo.py","type": "blob"},
    ]
}

SEARCH_RESPONSE = {
    "items": [
        {
            "path": "src/foo.py",
            "name": "foo.py",
            "html_url": "https://github.com/org/repo/blob/main/src/foo.py",
            "sha": "abc111",
            "language": "Python",
            "score": 1.0,
            "line_numbers": ["10", "20"],
            "text_matches": [
                {
                    "fragment": "def foo():",
                    "matches": [{"text": "foo", "indices": [4, 7]}],
                }
            ],
        },
        {
            "path": "src/bar.py",
            "name": "bar.py",
            "html_url": "https://github.com/org/repo/blob/main/src/bar.py",
            "sha": "abc222",
            "language": "Python",
            "score": 0.8,
            "line_numbers": ["5"],
            "text_matches": [
                {
                    "fragment": "foo()",
                    "matches": [{"text": "foo", "indices": [0, 3]}],
                }
            ],
        },
    ]
}


@pytest.fixture
def get_pr_metadata(tools):
    return get_tool(tools, "get_pr_metadata")


@pytest.fixture
def get_parsed_pr_diff(tools):
    return get_tool(tools, "get_parsed_pr_diff")


@pytest.fixture
def get_file_at_ref(tools):
    return get_tool(tools, "get_file_at_ref")


@pytest.fixture
def get_directory_tree(tools):
    return get_tool(tools, "get_directory_tree")


@pytest.fixture
def get_search_codebase(tools):
    return get_tool(tools, "search_codebase")


COMMITS_RESPONSE = [
    {
        "sha": "abc111",
        "html_url": "https://github.com/org/repo/commit/abc111",
        "parents": [{"sha": "abc000"}],
        "commit": {
            "message": "fix: prevent injection\nmore detail",
            "author": {"name": "alice", "date": "2024-01-01T00:00:00Z"},
        },
    },
    {
        "sha": "abc222",
        "html_url": "https://github.com/org/repo/commit/abc222",
        "parents": [{"sha": "abc111"}, {"sha": "abc100"}],
        "commit": {
            "message": "refactor: clean up",
            "author": {"name": "bob", "date": "2024-01-02T00:00:00Z"},
        },
    },
]

BLAME_RESPONSE = {
    "data": {
        "repository": {
            "object": {
                "blame": {
                    "ranges": [
                        {
                            "startingLine": 1,
                            "endingLine": 5,
                            "age": 2,
                            "commit": {
                                "oid": "abc111",
                                "message": "fix: prevent injection\nmore detail",
                                "commitUrl": "https://github.com/org/repo/commit/abc111",
                                "author": {"name": "alice", "date": "2024-01-01T00:00:00Z"},
                            },
                        },
                        {
                            "startingLine": 6,
                            "endingLine": 10,
                            "age": 8,
                            "commit": {
                                "oid": "abc222",
                                "message": "refactor: clean up",
                                "commitUrl": "https://github.com/org/repo/commit/abc222",
                                "author": {"name": "bob", "date": "2024-01-02T00:00:00Z"},
                            },
                        },
                    ]
                }
            }
        }
    }
}


@pytest.fixture
def get_file_commit_history(monkeypatch):
    monkeypatch.setattr(
        "github_context_tools.tools.factory.make_requester",
        lambda *_, **__: (
            MagicMock(return_value=COMMITS_RESPONSE),
            MagicMock(),
            MagicMock(),
        ),
    )
    return get_tool(make_tools(token="test-token"), "get_file_commit_history")


@pytest.fixture
def get_commit_diff(monkeypatch):
    monkeypatch.setattr(
        "github_context_tools.tools.factory.make_requester",
        lambda *_, **__: (
            MagicMock(),
            MagicMock(return_value=DIFF_TEXT),
            MagicMock(),
        ),
    )
    return get_tool(make_tools(token="test-token"), "get_commit_diff")


@pytest.fixture
def get_blame(monkeypatch):
    monkeypatch.setattr(
        "github_context_tools.tools.factory.make_requester",
        lambda *_, **__: (
            MagicMock(),
            MagicMock(),
            MagicMock(return_value=BLAME_RESPONSE),
        ),
    )
    return get_tool(make_tools(token="test-token"), "get_blame")


# ── parse_pr_url ──────────────────────────────────────────────────────────────

class TestParsePrUrl:
    def test_valid_url(self):
        owner, repo, number = parse_pr_url("https://github.com/org/repo/pull/42")
        assert owner == "org"
        assert repo == "repo"
        assert number == 42

    def test_trailing_slash(self):
        _, _, number = parse_pr_url("https://github.com/org/repo/pull/42/")
        assert number == 42

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Invalid GitHub PR URL"):
            parse_pr_url("https://github.com/org/repo")

    def test_non_github_url_raises(self):
        with pytest.raises(ValueError, match="Invalid GitHub PR URL"):
            parse_pr_url("https://gitlab.com/org/repo/merge_requests/1")


# ── validate_repo ─────────────────────────────────────────────────────────────

class TestValidateRepo:
    def test_valid_repo(self):
        validate_repo("org/repo")  # must not raise

    def test_valid_repo_with_hyphens(self):
        validate_repo("my-org/my-repo")  # must not raise

    def test_missing_slash_raises(self):
        with pytest.raises(ValueError, match="Invalid repo format"):
            validate_repo("orgrepository")

    def test_leading_slash_raises(self):
        with pytest.raises(ValueError, match="Invalid repo format"):
            validate_repo("/org/repo")

    def test_trailing_slash_raises(self):
        with pytest.raises(ValueError, match="Invalid repo format"):
            validate_repo("org/repo/")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Invalid repo format"):
            validate_repo("")


# ── make_tools ────────────────────────────────────────────────────────────────

class TestMakeTools:
    def test_returns_list_of_callables(self, tools):
        assert isinstance(tools, list)
        assert all(callable(t) for t in tools)

    def test_tool_names_are_set(self, tools):
        names = [t.__name__ for t in tools]
        assert "get_pr_metadata" in names
        assert "get_parsed_pr_diff" in names
        assert "get_pr_description" in names
        assert "get_pr_comments" in names
        assert "get_file_at_ref" in names
        assert "get_directory_tree" in names
        assert "search_codebase" in names
        assert "get_sibling_files" in names
        assert "get_file_commit_history" in names
        assert "get_commit_diff" in names
        assert "get_blame" in names
        assert "get_linked_issue" in names
        assert "get_repo_conventions" in names

    def test_tool_count(self, tools):
        assert len(tools) == 13


class TestMakeToolsFiltering:
    def _make(self, monkeypatch, **kwargs):
        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: make_mock_requester(),
        )
        return make_tools(token="test-token", **kwargs)

    def test_include_returns_only_named_tools(self, monkeypatch):
        tools = self._make(monkeypatch, include={"get_pr_metadata", "get_blame"})
        names = [t.__name__ for t in tools]
        assert names == ["get_pr_metadata", "get_blame"] or set(names) == {"get_pr_metadata", "get_blame"}
        assert len(tools) == 2

    def test_include_preserves_original_order(self, monkeypatch):
        tools = self._make(monkeypatch, include={"get_blame", "get_pr_metadata"})
        names = [t.__name__ for t in tools]
        assert names.index("get_pr_metadata") < names.index("get_blame")

    def test_include_single_tool(self, monkeypatch):
        tools = self._make(monkeypatch, include={"get_repo_conventions"})
        assert len(tools) == 1
        assert tools[0].__name__ == "get_repo_conventions"

    def test_include_unknown_name_raises(self, monkeypatch):
        with pytest.raises(ValueError, match="Unknown tool names in include"):
            self._make(monkeypatch, include={"not_a_real_tool"})

    def test_exclude_removes_named_tools(self, monkeypatch):
        tools = self._make(monkeypatch, exclude={"get_pr_metadata", "get_blame"})
        names = {t.__name__ for t in tools}
        assert "get_pr_metadata" not in names
        assert "get_blame" not in names
        assert len(tools) == 11

    def test_exclude_unknown_name_raises(self, monkeypatch):
        with pytest.raises(ValueError, match="Unknown tool names in exclude"):
            self._make(monkeypatch, exclude={"not_a_real_tool"})

    def test_include_and_exclude_applied_together(self, monkeypatch):
        tools = self._make(
            monkeypatch,
            include={"get_pr_metadata", "get_parsed_pr_diff", "get_blame"},
            exclude={"get_blame"},
        )
        names = {t.__name__ for t in tools}
        assert names == {"get_pr_metadata", "get_parsed_pr_diff"}

    def test_include_subset_of_exclude_raises(self, monkeypatch):
        with pytest.raises(ValueError, match="mutually exclusive"):
            self._make(
                monkeypatch,
                include={"get_pr_metadata"},
                exclude={"get_pr_metadata"},
            )

    def test_no_filters_returns_all(self, monkeypatch):
        tools = self._make(monkeypatch)
        assert len(tools) == 13

    def test_tools_are_plain_functions(self, tools):
        assert not any(inspect.iscoroutinefunction(t) for t in tools)

    def test_token_not_in_any_signature(self, tools):
        for tool in tools:
            params = inspect.signature(tool).parameters
            assert "token" not in params
            assert "http" not in params

    def test_parameters_are_annotated(self, tools):
        for tool in tools:
            sig = inspect.signature(tool)
            for name, param in sig.parameters.items():
                assert param.annotation is not inspect.Parameter.empty, (
                    f"{tool.__name__}: parameter '{name}' missing annotation"
                )

    def test_annotated_params_have_descriptions(self, tools):
        for tool in tools:
            hints = get_type_hints(tool, include_extras=True)
            for name, hint in hints.items():
                if name == "return":
                    continue
                args = get_args(hint)
                assert len(args) >= 2 and isinstance(args[1], str), (
                    f"{tool.__name__}: parameter '{name}' missing Annotated description"
                )


# ── get_pr_metadata ───────────────────────────────────────────────────────────

class TestGetPrMetadata:
    def test_returns_pr_metadata(self, get_pr_metadata):
        assert isinstance(get_pr_metadata(PR_URL), PRMetadata)

    def test_metadata_fields(self, get_pr_metadata):
        meta = get_pr_metadata(PR_URL)
        assert meta.repo == "org/repo"
        assert meta.pr_number == 42
        assert meta.title == "Add feature"
        assert meta.description == "This adds the feature."
        assert meta.author == "alice"
        assert meta.base_branch == "main"
        assert meta.head_branch == "feature/add"
        assert meta.base_sha == "base000"
        assert meta.head_sha == "head111"
        assert meta.html_url == "https://github.com/org/repo/pull/42"
        assert meta.state == "open"
        assert meta.commits == 3
        assert meta.changed_files == 2
        assert meta.additions == 10
        assert meta.deletions == 4

    def test_null_body_becomes_empty_string(self, monkeypatch):
        data = {**PULL_REQUEST_RESPONSE, "body": None}
        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: make_mock_requester(pr_data=data),
        )
        meta = get_tool(make_tools(token="test-token"), "get_pr_metadata")(PR_URL)
        assert meta.description == ""

    def test_invalid_pr_url_raises(self, get_pr_metadata):
        with pytest.raises(ValueError, match="Invalid GitHub PR URL"):
            get_pr_metadata("https://github.com/org/repo")


# ── get_parsed_pr_diff ────────────────────────────────────────────────────────

class TestGetParsedPrDiff:
    def test_returns_pr_diff(self, get_parsed_pr_diff):
        assert isinstance(get_parsed_pr_diff(PR_URL), PRDiff)

    def test_fields(self, get_parsed_pr_diff):
        diff = get_parsed_pr_diff(PR_URL)
        assert diff.repo == "org/repo"

    def test_diff_parsed(self, get_parsed_pr_diff):
        diff = get_parsed_pr_diff(PR_URL)
        assert len(diff.diff) == 1
        assert diff.diff[0].new_path == "src/foo.py"

    def test_diff_is_tuple(self, get_parsed_pr_diff):
        diff = get_parsed_pr_diff(PR_URL)
        assert isinstance(diff.diff, tuple)

    def test_invalid_pr_url_raises(self, get_parsed_pr_diff):
        with pytest.raises(ValueError, match="Invalid GitHub PR URL"):
            get_parsed_pr_diff("https://github.com/org/repo")


# ── get_file_at_ref ───────────────────────────────────────────────────────────

class TestGetFileAtRef:
    def _make_tools(self, monkeypatch, get_json_fn):
        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (get_json_fn, MagicMock(return_value=""), MagicMock()),
        )
        return get_tool(make_tools(token="test-token"), "get_file_at_ref")

    def test_returns_file_content(self, monkeypatch):
        encoded = base64.b64encode(FILE_CONTENT.encode()).decode()
        get_file = self._make_tools(
            monkeypatch,
            MagicMock(return_value={"content": encoded + "\n"}),
        )
        result = get_file("org/repo", "src/foo.py", "main")
        assert isinstance(result, FileContent)
        assert result.content == FILE_CONTENT
        assert result.download_url is None

    def test_large_file_returns_download_url(self, monkeypatch):
        download_url = "https://raw.githubusercontent.com/org/repo/main/src/foo.py"
        get_file = self._make_tools(
            monkeypatch,
            MagicMock(return_value={"download_url": download_url}),
        )
        result = get_file("org/repo", "src/foo.py", "main")
        assert isinstance(result, FileContent)
        assert result.content is None
        assert result.download_url == download_url

    def test_inline_file_includes_download_url_when_present(self, monkeypatch):
        encoded = base64.b64encode(FILE_CONTENT.encode()).decode()
        download_url = "https://raw.githubusercontent.com/org/repo/main/src/foo.py"
        get_file = self._make_tools(
            monkeypatch,
            MagicMock(return_value={"content": encoded + "\n", "download_url": download_url}),
        )
        result = get_file("org/repo", "src/foo.py", "main")
        assert result.content == FILE_CONTENT
        assert result.download_url == download_url

    def test_raises_when_no_content_or_download_url(self, monkeypatch):
        get_file = self._make_tools(monkeypatch, MagicMock(return_value={}))
        with pytest.raises(ValueError, match="Unable to fetch content"):
            get_file("org/repo", "src/foo.py", "main")


# ── get_directory_tree ────────────────────────────────────────────────────────

class TestGetDirectoryTree:
    def _make_tools(self, monkeypatch):
        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (MagicMock(return_value=TREE_RESPONSE), MagicMock(), MagicMock()),
        )
        return get_tool(make_tools(token="test-token"), "get_directory_tree")

    def test_returns_dict(self, monkeypatch):
        get_tree = self._make_tools(monkeypatch)
        result = get_tree("org/repo", "abc123")
        assert isinstance(result, dict)

    def test_files_are_nested_under_directories(self, monkeypatch):
        get_tree = self._make_tools(monkeypatch)
        result = get_tree("org/repo", "abc123")
        assert "src" in result
        assert isinstance(result["src"], dict)
        assert result["src"]["foo.py"] == "blob"
        assert result["src"]["bar.py"] == "blob"

    def test_top_level_directory_excluded_from_siblings(self, monkeypatch):
        get_tree = self._make_tools(monkeypatch)
        result = get_tree("org/repo", "abc123")
        assert "tests" in result
        assert result["tests"]["test_foo.py"] == "blob"

    def test_path_filter_restricts_to_subtree(self, monkeypatch):
        get_tree = self._make_tools(monkeypatch)
        result = get_tree("org/repo", "abc123", "src/")
        assert "src" in result
        assert "tests" not in result

    def test_files_are_blob_values(self, monkeypatch):
        get_tree = self._make_tools(monkeypatch)
        result = get_tree("org/repo", "abc123")
        assert result["src"]["foo.py"] == "blob"


# ── search_codebase ───────────────────────────────────────────────────────────

class TestSearchCodebase:
    def _make_tools(self, monkeypatch, response=None):
        data = response or SEARCH_RESPONSE
        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (MagicMock(return_value=data), MagicMock(), MagicMock()),
        )
        return get_tool(make_tools(token="test-token"), "search_codebase")

    def test_returns_list_of_search_results(self, monkeypatch):
        search = self._make_tools(monkeypatch)
        results = search("org/repo", content="foo")
        assert all(isinstance(r, SearchResult) for r in results)

    def test_result_fields(self, monkeypatch):
        search = self._make_tools(monkeypatch)
        results = search("org/repo", content="foo")
        r = results[0]
        assert r.path == "src/foo.py"
        assert r.filename == "foo.py"
        assert r.html_url == "https://github.com/org/repo/blob/main/src/foo.py"
        assert r.sha == "abc111"
        assert r.language == "Python"
        assert abs(r.score - 1.0) < 1e-9
        assert r.line_numbers == ("10", "20")
        assert r.snippet == "def foo():"
        assert len(r.text_matches) == 1
        assert r.text_matches[0].fragment == "def foo():"
        assert r.text_matches[0].matches == (("foo", (4, 7)),)

    def test_empty_items_returns_empty_list(self, monkeypatch):
        search = self._make_tools(monkeypatch, response={"items": []})
        assert search("org/repo", content="foo") == []

    def test_no_filters_raises(self, monkeypatch):
        search = self._make_tools(monkeypatch)
        with pytest.raises(ValueError):
            search("org/repo")

    def test_path_filter_included_in_query(self, monkeypatch):
        captured = {}
        def _fn(path, *, headers=None):
            captured["path"] = path
            return {"items": []}
        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (MagicMock(side_effect=_fn), MagicMock(), MagicMock()),
        )
        get_tool(make_tools(token="test-token"), "search_codebase")("org/repo", path="src/auth")
        assert "path:src/auth" in captured["path"]

    def test_filename_filter_included_in_query(self, monkeypatch):
        captured = {}
        def _fn(path, *, headers=None):
            captured["path"] = path
            return {"items": []}
        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (MagicMock(side_effect=_fn), MagicMock(), MagicMock()),
        )
        get_tool(make_tools(token="test-token"), "search_codebase")("org/repo", filename="conftest.py")
        assert "filename:conftest.py" in captured["path"]

    def test_symbol_filter_included_in_query(self, monkeypatch):
        captured = {}
        def _fn(path, *, headers=None):
            captured["path"] = path
            return {"items": []}
        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (MagicMock(side_effect=_fn), MagicMock(), MagicMock()),
        )
        get_tool(make_tools(token="test-token"), "search_codebase")("org/repo", symbol="MyClass")
        assert "MyClass" in captured["path"]
        assert "symbol:MyClass" not in captured["path"]

    def test_content_filter_included_in_query(self, monkeypatch):
        captured = {}
        def _fn(path, *, headers=None):
            captured["path"] = path
            return {"items": []}
        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (MagicMock(side_effect=_fn), MagicMock(), MagicMock()),
        )
        get_tool(make_tools(token="test-token"), "search_codebase")("org/repo", content="import os")
        assert "import os" in captured["path"]
        assert "content:import os" not in captured["path"]

    def test_multiple_filters_combined(self, monkeypatch):
        captured = {}
        def _fn(path, *, headers=None):
            captured["path"] = path
            return {"items": []}
        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (MagicMock(side_effect=_fn), MagicMock(), MagicMock()),
        )
        get_tool(make_tools(token="test-token"), "search_codebase")("org/repo", path="src", content="import os")
        assert "path:src" in captured["path"]
        assert "import os" in captured["path"]
        assert "content:import os" not in captured["path"]


# ── get_file_commit_history ───────────────────────────────────────────────────

class TestGetFileCommitHistory:
    def test_returns_list_of_commit_summaries(self, get_file_commit_history):
        result = get_file_commit_history("org/repo", "src/foo.py")
        assert all(isinstance(c, CommitSummary) for c in result)

    def test_commit_fields(self, get_file_commit_history):
        result = get_file_commit_history("org/repo", "src/foo.py")
        assert result[0].sha == "abc111"
        assert result[0].message == "fix: prevent injection"
        assert result[0].author == "alice"
        assert result[0].date == "2024-01-01T00:00:00Z"
        assert result[0].html_url == "https://github.com/org/repo/commit/abc111"

    def test_multiline_message_truncated_to_first_line(self, get_file_commit_history):
        result = get_file_commit_history("org/repo", "src/foo.py")
        assert "\n" not in result[0].message

    def test_parents_tuple(self, get_file_commit_history):
        result = get_file_commit_history("org/repo", "src/foo.py")
        assert result[0].parents == ("abc000",)

    def test_merge_commit_has_two_parents(self, get_file_commit_history):
        result = get_file_commit_history("org/repo", "src/foo.py")
        assert len(result[1].parents) == 2

    def test_max_commits_passed_in_query(self, monkeypatch):
        captured = {}
        def _fn(path, *, headers=None):
            captured["path"] = path
            return []
        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (MagicMock(side_effect=_fn), MagicMock(), MagicMock()),
        )
        get_tool(make_tools(token="test-token"), "get_file_commit_history")("org/repo", "src/foo.py", max_commits=5)
        assert "per_page=5" in captured["path"]

    def test_page_passed_in_query(self, monkeypatch):
        captured = {}
        def _fn(path, *, headers=None):
            captured["path"] = path
            return []
        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (MagicMock(side_effect=_fn), MagicMock(), MagicMock()),
        )
        get_tool(make_tools(token="test-token"), "get_file_commit_history")("org/repo", "src/foo.py", page=3)
        assert "page=3" in captured["path"]

    def test_optional_filters_appended_when_set(self, monkeypatch):
        captured = {}
        def _fn(path, *, headers=None):
            captured["path"] = path
            return []
        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (MagicMock(side_effect=_fn), MagicMock(), MagicMock()),
        )
        get_tool(make_tools(token="test-token"), "get_file_commit_history")(
            "org/repo", "src/foo.py",
            sha="main", author="alice",
            since="2024-01-01T00:00:00Z", until="2024-12-31T23:59:59Z",
        )
        assert "sha=main" in captured["path"]
        assert "author=alice" in captured["path"]
        assert "since=2024-01-01T00:00:00Z" in captured["path"]
        assert "until=2024-12-31T23:59:59Z" in captured["path"]

    def test_optional_filters_omitted_when_empty(self, monkeypatch):
        captured = {}
        def _fn(path, *, headers=None):
            captured["path"] = path
            return []
        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (MagicMock(side_effect=_fn), MagicMock(), MagicMock()),
        )
        get_tool(make_tools(token="test-token"), "get_file_commit_history")("org/repo", "src/foo.py")
        assert "sha=" not in captured["path"]
        assert "author=" not in captured["path"]
        assert "since=" not in captured["path"]
        assert "until=" not in captured["path"]


# ── get_commit_diff ───────────────────────────────────────────────────────────

class TestGetCommitDiff:
    def test_returns_commit_diff(self, get_commit_diff):
        result = get_commit_diff("org/repo", "abc111")
        assert isinstance(result, CommitDiff)

    def test_sha_preserved(self, get_commit_diff):
        result = get_commit_diff("org/repo", "abc111")
        assert result.sha == "abc111"

    def test_diff_is_tuple_of_changed_files(self, get_commit_diff):
        result = get_commit_diff("org/repo", "abc111")
        assert isinstance(result.diff, tuple)
        assert len(result.diff) == 1

    def test_changed_file_path(self, get_commit_diff):
        result = get_commit_diff("org/repo", "abc111")
        assert result.diff[0].new_path == "src/foo.py"

    def test_changed_file_has_hunks(self, get_commit_diff):
        result = get_commit_diff("org/repo", "abc111")
        assert len(result.diff[0].hunks) > 0


# ── get_blame ─────────────────────────────────────────────────────────────────

class TestGetBlame:
    def test_returns_list_of_blame_entries(self, get_blame):
        result = get_blame("org/repo", "src/foo.py", "main")
        assert all(isinstance(e, BlameEntry) for e in result)

    def test_blame_entry_fields(self, get_blame):
        result = get_blame("org/repo", "src/foo.py", "main")
        assert result[0].start_line == 1
        assert result[0].end_line == 5
        assert result[0].sha == "abc111"
        assert result[0].message == "fix: prevent injection"
        assert result[0].author == "alice"
        assert result[0].commit_url == "https://github.com/org/repo/commit/abc111"
        assert result[0].age == 2

    def test_multiple_ranges(self, get_blame):
        result = get_blame("org/repo", "src/foo.py", "main")
        assert len(result) == 2
        assert result[1].start_line == 6
        assert result[1].end_line == 10

    def test_multiline_message_truncated_to_first_line(self, get_blame):
        result = get_blame("org/repo", "src/foo.py", "main")
        assert "\n" not in result[0].message

    def test_graphql_variables(self, monkeypatch):
        captured = {}
        def _fn(path, body, *, headers=None):
            captured["body"] = body
            return BLAME_RESPONSE
        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (MagicMock(), MagicMock(), MagicMock(side_effect=_fn)),
        )
        get_tool(make_tools(token="test-token"), "get_blame")("org/repo", "src/foo.py", "abc123")
        variables = captured["body"]["variables"]
        assert variables["owner"] == "org"
        assert variables["repo"] == "repo"
        assert variables["expr"] == "abc123"
        assert variables["path"] == "src/foo.py"


# ── get_pr_description ────────────────────────────────────────────────────────

PR_DESCRIPTION_RESPONSE = {
    **PULL_REQUEST_RESPONSE,
    "labels": [{"name": "enhancement"}, {"name": "security"}],
}


class TestGetPrDescription:
    def _make_tools(self, monkeypatch, pr_data=None):
        data = pr_data or PR_DESCRIPTION_RESPONSE
        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (MagicMock(return_value=data), MagicMock(), MagicMock()),
        )
        return get_tool(make_tools(token="test-token"), "get_pr_description")

    def test_returns_pr_description(self, monkeypatch):
        fn = self._make_tools(monkeypatch)
        assert isinstance(fn(PR_URL), PRDescription)

    def test_fields(self, monkeypatch):
        fn = self._make_tools(monkeypatch)
        desc = fn(PR_URL)
        assert desc.title == "Add feature"
        assert desc.body == "This adds the feature."
        assert desc.labels == ("enhancement", "security")

    def test_null_body_becomes_empty_string(self, monkeypatch):
        fn = self._make_tools(monkeypatch, pr_data={**PR_DESCRIPTION_RESPONSE, "body": None})
        assert fn(PR_URL).body == ""

    def test_labels_is_tuple(self, monkeypatch):
        fn = self._make_tools(monkeypatch)
        assert isinstance(fn(PR_URL).labels, tuple)

    def test_no_labels(self, monkeypatch):
        fn = self._make_tools(monkeypatch, pr_data={**PR_DESCRIPTION_RESPONSE, "labels": []})
        assert fn(PR_URL).labels == ()


# ── get_pr_comments ───────────────────────────────────────────────────────────

REVIEW_COMMENTS = [
    {
        "user": {"login": "alice"},
        "body": "Fix this nit.",
        "created_at": "2024-01-01T00:00:00Z",
        "path": "src/foo.py",
        "line": 10,
        "side": "RIGHT",
        "original_line": 9,
        "original_side": "LEFT",
        "start_line": 8,
        "start_side": "RIGHT",
        "diff_hunk": "@@ -1,3 +1,4 @@\n def foo():\n-    pass\n+    return 1",
        "commit_id": "head111",
        "in_reply_to_id": None,
        "html_url": "https://github.com/org/repo/pull/42#discussion_r1",
    },
]

ISSUE_COMMENTS = [
    {
        "user": {"login": "bob"},
        "body": "Overall LGTM.",
        "created_at": "2024-01-02T00:00:00Z",
        "html_url": "https://github.com/org/repo/pull/42#issuecomment-1",
    },
]


class TestGetPrComments:
    def _make_tools(self, monkeypatch):
        def _fn(path, *, headers=None):
            if "pulls" in path and "comments" in path:
                return REVIEW_COMMENTS
            return ISSUE_COMMENTS

        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (MagicMock(side_effect=_fn), MagicMock(), MagicMock()),
        )
        return get_tool(make_tools(token="test-token"), "get_pr_comments")

    def test_returns_list_of_pr_comments(self, monkeypatch):
        fn = self._make_tools(monkeypatch)
        result = fn(PR_URL)
        assert all(isinstance(c, PRComment) for c in result)

    def test_review_comment_fields(self, monkeypatch):
        fn = self._make_tools(monkeypatch)
        result = fn(PR_URL)
        review = next(c for c in result if c.is_review_comment)
        assert review.author == "alice"
        assert review.body == "Fix this nit."
        assert review.path == "src/foo.py"
        assert review.line == 10
        assert review.side == "RIGHT"
        assert review.original_line == 9
        assert review.original_side == "LEFT"
        assert review.start_line == 8
        assert review.start_side == "RIGHT"
        assert review.diff_hunk == "@@ -1,3 +1,4 @@\n def foo():\n-    pass\n+    return 1"
        assert review.commit_id == "head111"
        assert review.in_reply_to_id is None
        assert review.html_url == "https://github.com/org/repo/pull/42#discussion_r1"
        assert review.is_review_comment is True

    def test_issue_comment_fields(self, monkeypatch):
        fn = self._make_tools(monkeypatch)
        result = fn(PR_URL)
        issue = next(c for c in result if not c.is_review_comment)
        assert issue.author == "bob"
        assert issue.body == "Overall LGTM."
        assert issue.path is None
        assert issue.line is None
        assert issue.side is None
        assert issue.original_line is None
        assert issue.original_side is None
        assert issue.start_line is None
        assert issue.start_side is None
        assert issue.diff_hunk is None
        assert issue.commit_id is None
        assert issue.in_reply_to_id is None
        assert issue.html_url == "https://github.com/org/repo/pull/42#issuecomment-1"
        assert issue.is_review_comment is False

    def test_both_comment_types_returned(self, monkeypatch):
        fn = self._make_tools(monkeypatch)
        result = fn(PR_URL)
        assert len(result) == 2


# ── get_linked_issue ──────────────────────────────────────────────────────────

ISSUE_RESPONSE = {
    "number": 42,
    "title": "Bug: foo breaks on empty input",
    "body": "Steps to reproduce...",
    "user": {"login": "alice"},
    "state": "open",
    "state_reason": None,
    "labels": [{"name": "bug"}, {"name": "priority:high"}],
    "created_at": "2024-01-01T00:00:00Z",
    "closed_at": None,
}

ISSUE_COMMENTS_RESPONSE = [
    {
        "user": {"login": "bob"},
        "body": "Can confirm this happens.",
        "created_at": "2024-01-02T00:00:00Z",
        "html_url": "https://github.com/org/repo/issues/42#issuecomment-1",
    },
    {
        "user": {"login": "alice"},
        "body": "Fix incoming in PR #55.",
        "created_at": "2024-01-03T00:00:00Z",
        "html_url": "https://github.com/org/repo/issues/42#issuecomment-2",
    },
]


class TestGetLinkedIssue:
    def _make_tools(self, monkeypatch):
        def _fn(path, *, headers=None):
            if path.endswith("/comments"):
                return ISSUE_COMMENTS_RESPONSE
            return ISSUE_RESPONSE

        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (MagicMock(side_effect=_fn), MagicMock(), MagicMock()),
        )
        return get_tool(make_tools(token="test-token"), "get_linked_issue")

    def test_returns_issue(self, monkeypatch):
        fn = self._make_tools(monkeypatch)
        assert isinstance(fn("org/repo", 42), Issue)

    def test_issue_fields(self, monkeypatch):
        fn = self._make_tools(monkeypatch)
        issue = fn("org/repo", 42)
        assert issue.number == 42
        assert issue.title == "Bug: foo breaks on empty input"
        assert issue.body == "Steps to reproduce..."
        assert issue.author == "alice"
        assert issue.state == "open"
        assert issue.state_reason is None
        assert issue.labels == ("bug", "priority:high")
        assert issue.created_at == "2024-01-01T00:00:00Z"
        assert issue.closed_at is None

    def test_comments_are_issue_comment_objects(self, monkeypatch):
        fn = self._make_tools(monkeypatch)
        issue = fn("org/repo", 42)
        assert isinstance(issue.comments, tuple)
        assert all(isinstance(c, IssueComment) for c in issue.comments)
        assert len(issue.comments) == 2

    def test_comment_fields(self, monkeypatch):
        fn = self._make_tools(monkeypatch)
        issue = fn("org/repo", 42)
        c = issue.comments[0]
        assert c.author == "bob"
        assert c.body == "Can confirm this happens."
        assert c.created_at == "2024-01-02T00:00:00Z"
        assert c.html_url == "https://github.com/org/repo/issues/42#issuecomment-1"

    def test_labels_is_tuple(self, monkeypatch):
        fn = self._make_tools(monkeypatch)
        assert isinstance(fn("org/repo", 42).labels, tuple)

    def test_null_body_becomes_empty_string(self, monkeypatch):
        def _fn(path, *, headers=None):
            if path.endswith("/comments"):
                return []
            return {**ISSUE_RESPONSE, "body": None}

        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (MagicMock(side_effect=_fn), MagicMock(), MagicMock()),
        )
        issue = get_tool(make_tools(token="test-token"), "get_linked_issue")("org/repo", 42)
        assert issue.body == ""

    def test_state_reason_set_when_closed(self, monkeypatch):
        def _fn(path, *, headers=None):
            if path.endswith("/comments"):
                return []
            return {**ISSUE_RESPONSE, "state": "closed", "state_reason": "completed", "closed_at": "2024-02-01T00:00:00Z"}

        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (MagicMock(side_effect=_fn), MagicMock(), MagicMock()),
        )
        issue = get_tool(make_tools(token="test-token"), "get_linked_issue")("org/repo", 42)
        assert issue.state_reason == "completed"
        assert issue.closed_at == "2024-02-01T00:00:00Z"


# ── get_repo_conventions ──────────────────────────────────────────────────────

CONTRIBUTING_CONTENT = "# Contributing\nPlease follow the style guide."
CURSOR_RULES_CONTENT = "Always write tests."


class TestGetRepoConventions:
    def _make_tools(self, monkeypatch, get_json_fn):
        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (get_json_fn, MagicMock(), MagicMock()),
        )
        return get_tool(make_tools(token="test-token"), "get_repo_conventions")

    def test_returns_repo_conventions(self, monkeypatch):
        encoded = base64.b64encode(CONTRIBUTING_CONTENT.encode()).decode()
        fn = self._make_tools(monkeypatch, MagicMock(return_value={"content": encoded}))
        assert isinstance(fn("org/repo"), RepoConventions)

    def test_found_files_included(self, monkeypatch):
        encoded = base64.b64encode(CONTRIBUTING_CONTENT.encode()).decode()
        fn = self._make_tools(monkeypatch, MagicMock(return_value={"content": encoded}))
        result = fn("org/repo")
        assert len(result.files) == 10
        assert result.files[0] == ("CONTRIBUTING.md", CONTRIBUTING_CONTENT)

    def test_missing_files_silently_skipped(self, monkeypatch):
        def _fn(path, *, headers=None):
            if "CONTRIBUTING" in path:
                return {"content": base64.b64encode(CONTRIBUTING_CONTENT.encode()).decode()}
            raise ValueError("404 Not Found")

        fn = self._make_tools(monkeypatch, MagicMock(side_effect=_fn))
        result = fn("org/repo")
        assert len(result.files) == 1
        assert result.files[0][0] == "CONTRIBUTING.md"

    def test_no_files_found_returns_empty(self, monkeypatch):
        fn = self._make_tools(monkeypatch, MagicMock(side_effect=ValueError("404 Not Found")))
        result = fn("org/repo")
        assert result.files == ()

    def test_files_is_tuple(self, monkeypatch):
        encoded = base64.b64encode(CONTRIBUTING_CONTENT.encode()).decode()
        fn = self._make_tools(monkeypatch, MagicMock(return_value={"content": encoded}))
        assert isinstance(fn("org/repo").files, tuple)

    def test_no_ref_in_request_url(self, monkeypatch):
        captured = {}
        def _fn(path, *, headers=None):
            captured["path"] = path
            raise ValueError("404 Not Found")

        fn = self._make_tools(monkeypatch, MagicMock(side_effect=_fn))
        fn("org/repo")
        assert "ref=" not in captured.get("path", "")


# ── get_sibling_files ─────────────────────────────────────────────────────────

FULL_TREE_RESPONSE = {
    "tree": [
        {"path": "src/auth/oauth.py",    "type": "blob"},
        {"path": "src/auth/token.py",    "type": "blob"},
        {"path": "src/auth/",            "type": "tree"},
        {"path": "src/auth/utils/",      "type": "tree"},
        {"path": "src/auth/utils/jwt.py","type": "blob"},
        {"path": "src/other.py",         "type": "blob"},
        {"path": "README.md",            "type": "blob"},
    ]
}

ROOT_TREE_RESPONSE = {
    "tree": [
        {"path": "README.md",   "type": "blob"},
        {"path": "setup.py",    "type": "blob"},
        {"path": "src/",        "type": "tree"},
        {"path": "src/foo.py",  "type": "blob"},
    ]
}


class TestGetSimilarFiles:
    def _make_tools(self, monkeypatch, response):
        monkeypatch.setattr(
            "github_context_tools.tools.factory.make_requester",
            lambda *_, **__: (MagicMock(return_value=response), MagicMock(), MagicMock()),
        )
        return get_tool(make_tools(token="test-token"), "get_sibling_files")

    def test_returns_siblings_in_same_directory(self, monkeypatch):
        fn = self._make_tools(monkeypatch, FULL_TREE_RESPONSE)
        result = fn("org/repo", "src/auth/oauth.py", "main")
        assert "src/auth/token.py" in result

    def test_excludes_the_file_itself(self, monkeypatch):
        fn = self._make_tools(monkeypatch, FULL_TREE_RESPONSE)
        result = fn("org/repo", "src/auth/oauth.py", "main")
        assert "src/auth/oauth.py" not in result

    def test_excludes_subdirectory_files(self, monkeypatch):
        fn = self._make_tools(monkeypatch, FULL_TREE_RESPONSE)
        result = fn("org/repo", "src/auth/oauth.py", "main")
        assert "src/auth/utils/jwt.py" not in result

    def test_excludes_files_in_other_directories(self, monkeypatch):
        fn = self._make_tools(monkeypatch, FULL_TREE_RESPONSE)
        result = fn("org/repo", "src/auth/oauth.py", "main")
        assert "src/other.py" not in result

    def test_file_at_repo_root(self, monkeypatch):
        fn = self._make_tools(monkeypatch, ROOT_TREE_RESPONSE)
        result = fn("org/repo", "README.md", "main")
        assert "setup.py" in result
        assert "src/foo.py" not in result
        assert "README.md" not in result


# ── _is_sibling ───────────────────────────────────────────────────────────────

class TestIsSibling:
    def test_sibling_in_subdirectory(self):
        assert _is_sibling("src/auth/token.py", "blob", "src/auth", "src/auth/oauth.py")

    def test_excludes_self(self):
        assert not _is_sibling("src/auth/oauth.py", "blob", "src/auth", "src/auth/oauth.py")

    def test_excludes_tree_entries(self):
        assert not _is_sibling("src/auth/", "tree", "src/auth", "src/auth/oauth.py")

    def test_excludes_nested_subdirectory_file(self):
        assert not _is_sibling("src/auth/utils/jwt.py", "blob", "src/auth", "src/auth/oauth.py")

    def test_excludes_file_in_other_directory(self):
        assert not _is_sibling("src/other.py", "blob", "src/auth", "src/auth/oauth.py")

    def test_root_level_sibling(self):
        assert _is_sibling("setup.py", "blob", "", "README.md")

    def test_root_level_excludes_self(self):
        assert not _is_sibling("README.md", "blob", "", "README.md")

    def test_root_level_excludes_nested_file(self):
        assert not _is_sibling("src/foo.py", "blob", "", "README.md")

    def test_root_level_excludes_tree_entry(self):
        assert not _is_sibling("src/", "tree", "", "README.md")


# ── _build_tree ───────────────────────────────────────────────────────────────

class TestBuildTree:
    ITEMS = [
        {"path": "src/auth/oauth.py", "type": "blob"},
        {"path": "src/auth/token.py", "type": "blob"},
        {"path": "src/auth/",         "type": "tree"},
        {"path": "src/utils.py",      "type": "blob"},
        {"path": "README.md",         "type": "blob"},
    ]

    def test_nested_structure(self):
        result = _build_tree(self.ITEMS, "")
        assert result["src"]["auth"]["oauth.py"] == "blob"
        assert result["src"]["auth"]["token.py"] == "blob"
        assert result["src"]["utils.py"] == "blob"
        assert result["README.md"] == "blob"

    def test_tree_entries_not_included_as_blobs(self):
        result = _build_tree(self.ITEMS, "")
        assert result["src"]["auth"].get("") != "blob"

    def test_path_prefix_filters_items(self):
        result = _build_tree(self.ITEMS, "src/auth")
        assert "src" in result
        assert "README.md" not in result

    def test_empty_items(self):
        assert _build_tree([], "") == {}

    def test_root_file(self):
        items = [{"path": "README.md", "type": "blob"}]
        result = _build_tree(items, "")
        assert result["README.md"] == "blob"


# ── _build_search_query ───────────────────────────────────────────────────────

class TestBuildSearchQuery:
    def test_content_filter(self):
        q = _build_search_query("org/repo", None, None, None, "import os")
        assert "import os" in q
        assert "repo:org/repo" in q

    def test_symbol_filter(self):
        q = _build_search_query("org/repo", None, None, "MyClass", None)
        assert "MyClass" in q
        assert "symbol:MyClass" not in q

    def test_path_filter(self):
        q = _build_search_query("org/repo", "src/auth", None, None, None)
        assert "path:src/auth" in q

    def test_filename_filter(self):
        q = _build_search_query("org/repo", None, "conftest.py", None, None)
        assert "filename:conftest.py" in q

    def test_multiple_filters_combined(self):
        q = _build_search_query("org/repo", "src", "app.py", None, "current_app")
        assert "path:src" in q
        assert "filename:app.py" in q
        assert "current_app" in q

    def test_no_filters_raises(self):
        with pytest.raises(ValueError, match="At least one"):
            _build_search_query("org/repo", None, None, None, None)

    def test_repo_always_included(self):
        q = _build_search_query("org/repo", None, None, None, "foo")
        assert "repo:org/repo" in q

    def test_content_not_prefixed_with_content_colon(self):
        q = _build_search_query("org/repo", None, None, None, "import os")
        assert "content:import os" not in q

    def test_symbol_not_prefixed_with_symbol_colon(self):
        q = _build_search_query("org/repo", None, None, "MyClass", None)
        assert "symbol:MyClass" not in q


# ── _parse_text_matches ───────────────────────────────────────────────────────

class TestParseTextMatches:
    def test_empty_input(self):
        assert _parse_text_matches([]) == ()

    def test_single_match(self):
        raw = [{"fragment": "def foo():", "matches": [{"text": "foo", "indices": [4, 7]}]}]
        result = _parse_text_matches(raw)
        assert len(result) == 1
        assert result[0].fragment == "def foo():"
        assert result[0].matches == (("foo", (4, 7)),)

    def test_multiple_matches_in_fragment(self):
        raw = [{"fragment": "foo foo", "matches": [
            {"text": "foo", "indices": [0, 3]},
            {"text": "foo", "indices": [4, 7]},
        ]}]
        result = _parse_text_matches(raw)
        assert len(result[0].matches) == 2

    def test_multiple_fragments(self):
        raw = [
            {"fragment": "line one", "matches": [{"text": "one", "indices": [5, 8]}]},
            {"fragment": "line two", "matches": [{"text": "two", "indices": [5, 8]}]},
        ]
        result = _parse_text_matches(raw)
        assert len(result) == 2

    def test_missing_matches_key_defaults_empty(self):
        raw = [{"fragment": "no matches here"}]
        result = _parse_text_matches(raw)
        assert result[0].matches == ()

    def test_missing_fragment_key_defaults_empty(self):
        raw = [{"matches": []}]
        result = _parse_text_matches(raw)
        assert result[0].fragment == ""

    def test_returns_tuple(self):
        assert isinstance(_parse_text_matches([]), tuple)


# ── _search_results_from_response ─────────────────────────────────────────────

class TestSearchResultsFromResponse:
    BASE_ITEM = {
        "path": "src/foo.py",
        "name": "foo.py",
        "html_url": "https://github.com/org/repo/blob/main/src/foo.py",
        "sha": "abc111",
        "language": "Python",
        "score": 1.0,
        "line_numbers": ["10"],
        "text_matches": [{"fragment": "def foo():", "matches": [{"text": "foo", "indices": [4, 7]}]}],
    }

    def test_parses_item(self):
        results = _search_results_from_response({"items": [self.BASE_ITEM]})
        assert len(results) == 1
        r = results[0]
        assert r.path == "src/foo.py"
        assert r.filename == "foo.py"
        assert r.sha == "abc111"
        assert r.language == "Python"
        assert abs(r.score - 1.0) < 1e-9

    def test_empty_items(self):
        assert _search_results_from_response({"items": []}) == []

    def test_snippet_from_first_text_match(self):
        results = _search_results_from_response({"items": [self.BASE_ITEM]})
        assert results[0].snippet == "def foo():"

    def test_no_text_matches_gives_empty_snippet(self):
        item = {**self.BASE_ITEM, "text_matches": []}
        results = _search_results_from_response({"items": [item]})
        assert results[0].snippet == ""

    def test_line_numbers_is_tuple(self):
        results = _search_results_from_response({"items": [self.BASE_ITEM]})
        assert isinstance(results[0].line_numbers, tuple)

    def test_missing_language_is_none(self):
        item = {**self.BASE_ITEM}
        del item["language"]
        results = _search_results_from_response({"items": [item]})
        assert results[0].language is None

    def test_missing_line_numbers_defaults_empty(self):
        item = {**self.BASE_ITEM, "line_numbers": None}
        results = _search_results_from_response({"items": [item]})
        assert results[0].line_numbers == ()

    def test_multiple_items(self):
        item2 = {**self.BASE_ITEM, "path": "src/bar.py", "name": "bar.py", "sha": "abc222"}
        results = _search_results_from_response({"items": [self.BASE_ITEM, item2]})
        assert len(results) == 2


# ── _blame_entries_from_response ──────────────────────────────────────────────

class TestBlameEntriesFromResponse:
    VALID_RESPONSE = {
        "data": {
            "repository": {
                "object": {
                    "blame": {
                        "ranges": [
                            {
                                "startingLine": 1,
                                "endingLine": 5,
                                "age": 3,
                                "commit": {
                                    "oid": "abc111",
                                    "message": "fix: thing\nmore detail",
                                    "commitUrl": "https://github.com/org/repo/commit/abc111",
                                    "author": {"name": "alice", "date": "2024-01-01T00:00:00Z"},
                                },
                            }
                        ]
                    }
                }
            }
        }
    }

    def test_parses_valid_response(self):
        entries = _blame_entries_from_response(self.VALID_RESPONSE)
        assert len(entries) == 1
        e = entries[0]
        assert e.start_line == 1
        assert e.end_line == 5
        assert e.sha == "abc111"
        assert e.message == "fix: thing"
        assert e.author == "alice"
        assert e.age == 3

    def test_multiline_message_truncated(self):
        entries = _blame_entries_from_response(self.VALID_RESPONSE)
        assert "\n" not in entries[0].message

    def test_graphql_errors_raises_value_error(self):
        response = {"errors": [{"message": "Field 'blame' doesn't exist"}]}
        with pytest.raises(ValueError, match="GraphQL error"):
            _blame_entries_from_response(response)

    def test_missing_object_raises_value_error(self):
        response = {"data": {"repository": {"object": None}}}
        with pytest.raises(ValueError, match="Unexpected GraphQL response shape"):
            _blame_entries_from_response(response)

    def test_missing_repository_raises_value_error(self):
        response = {"data": {}}
        with pytest.raises(ValueError, match="Unexpected GraphQL response shape"):
            _blame_entries_from_response(response)

    def test_multiple_ranges(self):
        response = {
            "data": {"repository": {"object": {"blame": {"ranges": [
                {
                    "startingLine": 1, "endingLine": 3, "age": 1,
                    "commit": {"oid": "aaa", "message": "first", "commitUrl": "https://x", "author": {"name": "a", "date": "2024-01-01"}},
                },
                {
                    "startingLine": 4, "endingLine": 8, "age": 5,
                    "commit": {"oid": "bbb", "message": "second", "commitUrl": "https://y", "author": {"name": "b", "date": "2024-01-02"}},
                },
            ]}}}}
        }
        entries = _blame_entries_from_response(response)
        assert len(entries) == 2
        assert entries[1].start_line == 4
