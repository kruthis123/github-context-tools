import pytest
from github_context_tools.models import (
    PRMetadata,
    PRDiff,
    SearchResult,
    TextMatch,
    CommitSummary,
    BlameEntry,
    PRDescription,
    PRComment,
    Issue,
    RepoConventions,
)


class TestPRMetadata:
    def _make(self, **overrides):
        defaults = {
            "repo": "org/repo",
            "pr_number": 1,
            "title": "Fix bug",
            "description": "Fixes the thing",
            "author": "alice",
            "base_branch": "main",
            "head_branch": "fix/bug",
            "base_sha": "abc123",
            "head_sha": "def456",
            "html_url": "https://github.com/org/repo/pull/1",
            "state": "open",
            "commits": 1,
            "changed_files": 1,
            "additions": 5,
            "deletions": 2,
        }
        return PRMetadata(**{**defaults, **overrides})

    def test_is_frozen(self):
        meta = self._make()
        with pytest.raises(Exception):
            meta.title = "changed"  # type: ignore[misc]

    def test_fields(self):
        meta = self._make()
        assert meta.repo == "org/repo"
        assert meta.author == "alice"


class TestPRDiff:
    def _make(self, **overrides):
        defaults = {
            "repo": "org/repo",
            "diff": (),
        }
        return PRDiff(**{**defaults, **overrides})

    def test_is_frozen(self):
        d = self._make()
        with pytest.raises(Exception):
            d.repo = "other/repo"  # type: ignore[misc]

    def test_diff_is_tuple(self):
        d = self._make(diff=())
        assert isinstance(d.diff, tuple)


def _make_search_result(**overrides):
    defaults = {
        "path": "src/foo.py",
        "filename": "foo.py",
        "html_url": "https://github.com/org/repo/blob/main/src/foo.py",
        "sha": "abc111",
        "language": "Python",
        "score": 1.0,
        "line_numbers": ("10",),
        "text_matches": (),
        "snippet": "def foo",
    }
    return SearchResult(**{**defaults, **overrides})


class TestGroup1Models:
    def test_search_result_fields(self):
        r = _make_search_result()
        assert r.path == "src/foo.py"
        assert r.filename == "foo.py"
        assert r.language == "Python"

    def test_search_result_optional_language(self):
        r = _make_search_result(language=None)
        assert r.language is None

    def test_search_result_line_numbers_tuple(self):
        r = _make_search_result(line_numbers=("1", "2"))
        assert isinstance(r.line_numbers, tuple)

    def test_search_result_text_matches(self):
        tm = TextMatch(fragment="def foo():", matches=(("foo", (4, 7)),))
        r = _make_search_result(text_matches=(tm,))
        assert r.text_matches[0].fragment == "def foo():"
        assert r.text_matches[0].matches[0] == ("foo", (4, 7))


class TestGroup2Models:
    def test_commit_summary_frozen(self):
        c = CommitSummary(
            sha="abc", message="fix: thing", author="alice", date="2024-01-01",
            html_url="https://github.com/org/repo/commit/abc", parents=("def",),
        )
        with pytest.raises(Exception):
            c.sha = "xyz"  # type: ignore[misc]

    def test_blame_entry_line_range(self):
        b = BlameEntry(
            start_line=1, end_line=10, sha="abc", message="init", author="bob",
            date="2024-01-01", commit_url="https://github.com/org/repo/commit/abc", age=3,
        )
        assert b.end_line > b.start_line


class TestGroup3Models:
    def test_pr_description_labels_tuple(self):
        d = PRDescription(title="Add feature", body="Does X", labels=("enhancement",))
        assert isinstance(d.labels, tuple)

    def test_pr_comment_inline(self):
        c = PRComment(author="alice", body="nit", created_at="2024-01-01",
                      path="src/foo.py", line=5, side="RIGHT",
                      original_line=4, original_side="LEFT",
                      start_line=3, start_side="RIGHT",
                      diff_hunk="@@ -1 +1 @@\n-old\n+new",
                      commit_id="abc123", in_reply_to_id=None,
                      html_url="https://github.com/org/repo/pull/1#discussion_r1",
                      is_review_comment=True)
        assert c.path is not None and c.line is not None
        assert c.side == "RIGHT"
        assert c.original_line == 4
        assert c.start_line == 3
        assert c.diff_hunk is not None
        assert c.commit_id == "abc123"
        assert c.in_reply_to_id is None

    def test_pr_comment_top_level(self):
        c = PRComment(author="alice", body="lgtm", created_at="2024-01-01",
                      path=None, line=None, side=None,
                      original_line=None, original_side=None,
                      start_line=None, start_side=None,
                      diff_hunk=None, commit_id=None, in_reply_to_id=None,
                      html_url="https://github.com/org/repo/pull/1#issuecomment-1",
                      is_review_comment=False)
        assert c.path is None
        assert c.side is None
        assert c.diff_hunk is None

    def test_issue_comments_tuple(self):
        from github_context_tools.models import IssueComment
        comment = IssueComment(
            author="bob", body="first comment",
            created_at="2024-01-01T00:00:00Z",
            html_url="https://github.com/org/repo/issues/42#issuecomment-1",
        )
        i = Issue(
            number=42, title="Bug", body="It breaks", author="alice",
            state="open", state_reason=None, labels=(), created_at="2024-01-01T00:00:00Z",
            closed_at=None, comments=(comment,),
        )
        assert isinstance(i.comments, tuple)


class TestGroup4Models:
    def test_repo_conventions_files_tuple(self):
        c = RepoConventions(files=(("CONTRIBUTING.md", "# Contributing"),))
        assert c.files[0][0] == "CONTRIBUTING.md"

    def test_repo_conventions_empty(self):
        c = RepoConventions(files=())
        assert len(c.files) == 0


# ── FileContent ───────────────────────────────────────────────────────────────

class TestFileContent:
    def test_inline_content(self):
        from github_context_tools.models import FileContent
        f = FileContent(content="hello", download_url=None)
        assert f.content == "hello"
        assert f.download_url is None

    def test_large_file_no_content(self):
        from github_context_tools.models import FileContent
        f = FileContent(content=None, download_url="https://example.com/file")
        assert f.content is None
        assert f.download_url == "https://example.com/file"

    def test_is_frozen(self):
        from github_context_tools.models import FileContent
        f = FileContent(content="x", download_url=None)
        with pytest.raises(Exception):
            f.content = "y"  # type: ignore[misc]

    def test_both_none(self):
        from github_context_tools.models import FileContent
        f = FileContent(content=None, download_url=None)
        assert f.content is None
        assert f.download_url is None

    def test_both_set(self):
        from github_context_tools.models import FileContent
        f = FileContent(content="data", download_url="https://example.com/file")
        assert f.content == "data"
        assert f.download_url == "https://example.com/file"


# ── CommitDiff ────────────────────────────────────────────────────────────────

class TestCommitDiff:
    def test_fields(self):
        from github_context_tools.models import CommitDiff
        d = CommitDiff(sha="abc123", diff=())
        assert d.sha == "abc123"
        assert d.diff == ()

    def test_is_frozen(self):
        from github_context_tools.models import CommitDiff
        d = CommitDiff(sha="abc123", diff=())
        with pytest.raises(Exception):
            d.sha = "xyz"  # type: ignore[misc]

    def test_diff_is_tuple(self):
        from github_context_tools.models import CommitDiff
        d = CommitDiff(sha="abc", diff=())
        assert isinstance(d.diff, tuple)


# ── TextMatch ─────────────────────────────────────────────────────────────────

class TestTextMatch:
    def test_fields(self):
        from github_context_tools.models import TextMatch
        tm = TextMatch(fragment="def foo():", matches=(("foo", (4, 7)),))
        assert tm.fragment == "def foo():"
        assert tm.matches == (("foo", (4, 7)),)

    def test_is_frozen(self):
        from github_context_tools.models import TextMatch
        tm = TextMatch(fragment="x", matches=())
        with pytest.raises(Exception):
            tm.fragment = "y"  # type: ignore[misc]

    def test_empty_matches(self):
        from github_context_tools.models import TextMatch
        tm = TextMatch(fragment="line", matches=())
        assert tm.matches == ()

    def test_multiple_matches(self):
        from github_context_tools.models import TextMatch
        tm = TextMatch(fragment="foo foo", matches=(("foo", (0, 3)), ("foo", (4, 7))))
        assert len(tm.matches) == 2


# ── BlameEntry ────────────────────────────────────────────────────────────────

class TestBlameEntry:
    def _make(self, **overrides):
        defaults = {
            "start_line": 1, "end_line": 5, "sha": "abc111", "message": "fix: thing",
            "author": "alice", "date": "2024-01-01T00:00:00Z",
            "commit_url": "https://github.com/org/repo/commit/abc111", "age": 3,
        }
        return BlameEntry(**{**defaults, **overrides})

    def test_fields(self):
        b = self._make()
        assert b.start_line == 1
        assert b.end_line == 5
        assert b.sha == "abc111"
        assert b.message == "fix: thing"
        assert b.author == "alice"
        assert b.age == 3

    def test_is_frozen(self):
        b = self._make()
        with pytest.raises(Exception):
            b.sha = "xyz"  # type: ignore[misc]

    def test_age_bounds(self):
        b1 = self._make(age=1)
        b10 = self._make(age=10)
        assert b1.age == 1
        assert b10.age == 10

    def test_commit_url(self):
        b = self._make(commit_url="https://github.com/org/repo/commit/abc111")
        assert "github.com" in b.commit_url


# ── IssueComment ──────────────────────────────────────────────────────────────

class TestIssueComment:
    def test_fields(self):
        from github_context_tools.models import IssueComment
        c = IssueComment(
            author="bob", body="Looks good.",
            created_at="2024-01-01T00:00:00Z",
            html_url="https://github.com/org/repo/issues/1#issuecomment-1",
        )
        assert c.author == "bob"
        assert c.body == "Looks good."
        assert c.created_at == "2024-01-01T00:00:00Z"
        assert "issuecomment" in c.html_url

    def test_is_frozen(self):
        from github_context_tools.models import IssueComment
        c = IssueComment(author="a", body="b", created_at="2024-01-01", html_url="http://x")
        with pytest.raises(Exception):
            c.author = "z"  # type: ignore[misc]


# ── Issue ─────────────────────────────────────────────────────────────────────

class TestIssue:
    def _make(self, **overrides):
        from github_context_tools.models import Issue
        defaults = {
            "number": 1, "title": "Bug", "body": "It breaks", "author": "alice",
            "state": "open", "state_reason": None, "labels": ("bug",),
            "created_at": "2024-01-01T00:00:00Z", "closed_at": None, "comments": (),
        }
        return Issue(**{**defaults, **overrides})

    def test_fields(self):
        i = self._make()
        assert i.number == 1
        assert i.title == "Bug"
        assert i.author == "alice"
        assert i.state == "open"
        assert i.labels == ("bug",)
        assert i.closed_at is None

    def test_is_frozen(self):
        i = self._make()
        with pytest.raises(Exception):
            i.title = "changed"  # type: ignore[misc]

    def test_closed_issue(self):
        i = self._make(state="closed", state_reason="completed", closed_at="2024-02-01T00:00:00Z")
        assert i.state == "closed"
        assert i.state_reason == "completed"
        assert i.closed_at == "2024-02-01T00:00:00Z"

    def test_empty_labels(self):
        i = self._make(labels=())
        assert i.labels == ()

    def test_comments_tuple(self):
        from github_context_tools.models import IssueComment
        c = IssueComment(author="x", body="y", created_at="2024-01-01", html_url="http://x")
        i = self._make(comments=(c,))
        assert isinstance(i.comments, tuple)
        assert len(i.comments) == 1


# ── CommitSummary (additional) ────────────────────────────────────────────────

class TestCommitSummary:
    def _make(self, **overrides):
        defaults = {
            "sha": "abc111", "message": "fix: thing", "author": "alice",
            "date": "2024-01-01T00:00:00Z",
            "html_url": "https://github.com/org/repo/commit/abc111",
            "parents": ("abc000",),
        }
        return CommitSummary(**{**defaults, **overrides})

    def test_fields(self):
        c = self._make()
        assert c.sha == "abc111"
        assert c.message == "fix: thing"
        assert c.author == "alice"
        assert c.html_url == "https://github.com/org/repo/commit/abc111"

    def test_parents_is_tuple(self):
        c = self._make(parents=("abc000",))
        assert isinstance(c.parents, tuple)

    def test_merge_commit_two_parents(self):
        c = self._make(parents=("p1", "p2"))
        assert len(c.parents) == 2

    def test_is_frozen(self):
        c = self._make()
        with pytest.raises(Exception):
            c.sha = "xyz"  # type: ignore[misc]


# ── PRDescription (additional) ────────────────────────────────────────────────

class TestPRDescriptionModel:
    def test_fields(self):
        d = PRDescription(title="Add feature", body="Does X.", labels=("enhancement",))
        assert d.title == "Add feature"
        assert d.body == "Does X."

    def test_is_frozen(self):
        d = PRDescription(title="t", body="b", labels=())
        with pytest.raises(Exception):
            d.title = "changed"  # type: ignore[misc]

    def test_empty_labels(self):
        d = PRDescription(title="t", body="b", labels=())
        assert d.labels == ()


# ── SearchResult (additional) ─────────────────────────────────────────────────

class TestSearchResultModel:
    def test_is_frozen(self):
        r = _make_search_result()
        with pytest.raises(Exception):
            r.path = "other.py"  # type: ignore[misc]

    def test_snippet_from_text_matches(self):
        from github_context_tools.models import TextMatch
        tm = TextMatch(fragment="def foo():", matches=())
        r = _make_search_result(text_matches=(tm,), snippet="def foo():")
        assert r.snippet == "def foo():"

    def test_empty_snippet(self):
        r = _make_search_result(text_matches=(), snippet="")
        assert r.snippet == ""
