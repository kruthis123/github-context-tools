"""
Manual smoke-test script for github-context-tools tools.

Targets the public pallets/flask repo so no private token scopes are needed.
A classic PAT with public_repo (or just read:public repos) is sufficient.

Usage:
    # Run all tools
    GH_TOKEN=ghp_... uv run python manual_test.py

    # Run a single tool
    GH_TOKEN=ghp_... uv run python manual_test.py get_pr_metadata
    GH_TOKEN=ghp_... uv run python manual_test.py get_blame

    # Behind a corporate proxy with TLS inspection
    GH_TOKEN=ghp_... uv run python manual_test.py

    # List available tool names
    GH_TOKEN=ghp_... uv run python manual_test.py --list

Each test prints PASS / FAIL with a one-line summary, followed by the raw
tool output.
"""

import argparse
import pprint
import sys
import traceback

from github_context_tools import make_tools, PRMetadata, PRDiff, CommitDiff
from github_context_tools.models import (
    BlameEntry,
    CommitSummary,
    FileContent,
    Issue,
    IssueComment,
    PRComment,
    PRDescription,
    RepoConventions,
    SearchResult,
)

# ── Test targets ──────────────────────────────────────────────────────────────

REPO = "kruthis123/nextjs-concepts"
PR_URL = "https://github.com/kruthis123/nextjs-concepts/pull/1"
PR_NUMBER = 1
ISSUE_NUMBER = 1
FILE_PATH = "README.md"
REF = "branch-1"
COMMIT_SHA = "c391fd9bca5a5f487b3fb5193a1c4ad95366eeac"
SEARCH_REPO = "pallets/flask"
SEARCH_CONTENT = "current_app"
SEARCH_SYMBOL = "Flask"
SEARCH_PATH = "src/flask"
SEARCH_FILENAME = "app.py"
DIRECTORY_TREE_REPO = "kruthis123/git-unified-diff-parse"
DIRECTORY_TREE_REF = "main"
DIRECTORY_TREE_PATH = "src/git_unified_diff_parse"
CONVENTIONS_REPO = "public-apis/public-apis"

# ── Helpers ───────────────────────────────────────────────────────────────────

passed = 0
failed = 0
failed_checks: list[str] = []
_current_suite: str = ""


def check(name, fn):
    global passed, failed
    try:
        result = fn()
        if result is not None and result is not True and not result:
            raise AssertionError(f"check returned falsy value: {result!r}")
        print(f"  PASS  {name}")
        passed += 1
    except Exception:
        print(f"  FAIL  {name}")
        traceback.print_exc()
        failed += 1
        failed_checks.append(f"{_current_suite} › {name}")


def show(label, value):
    print(f"\n  {label}:")
    pprint.pprint(value, indent=4, width=100)


def _leaf_values(tree: dict):
    """Yield all leaf values (non-dict) from a nested dict."""
    for v in tree.values():
        if isinstance(v, dict):
            yield from _leaf_values(v)
        else:
            yield v


def _raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        assert False, f"expected {exc_type.__name__} but no exception was raised"
    except exc_type:
        pass


# ── Tool test suites ──────────────────────────────────────────────────────────


def test_get_pr_metadata(tools):
    fn = tools["get_pr_metadata"]
    result = fn(PR_URL)
    show("output", result)

    check("returns PRMetadata", lambda: isinstance(result, PRMetadata))
    check("repo field", lambda: result.repo == REPO)
    check("pr_number field", lambda: result.pr_number == PR_NUMBER)
    check("title is non-empty", lambda: bool(result.title))
    check("author is non-empty", lambda: bool(result.author))
    check(
        "base_sha and head_sha set", lambda: bool(result.base_sha and result.head_sha)
    )
    _raises(ValueError, fn, "https://github.com/pallets/flask")
    check("invalid URL raises ValueError", lambda: True)


def test_get_parsed_pr_diff(tools):
    fn = tools["get_parsed_pr_diff"]
    result = fn(PR_URL)
    show("output", result)

    check("returns PRDiff", lambda: isinstance(result, PRDiff))
    check("repo field", lambda: result.repo == REPO)
    check("has at least one file", lambda: len(result.diff) > 0)
    check("diff is a tuple", lambda: isinstance(result.diff, tuple))
    check(
        "each file has a path",
        lambda: all(f.new_path or f.old_path for f in result.diff),
    )


def test_get_pr_description(tools):
    fn = tools["get_pr_description"]
    result = fn(PR_URL)
    show("output", result)

    meta = tools["get_pr_metadata"](PR_URL)
    check("returns PRDescription", lambda: isinstance(result, PRDescription))
    check("title matches metadata", lambda: result.title == meta.title)
    check("labels is a tuple", lambda: isinstance(result.labels, tuple))


def test_get_pr_comments(tools):
    fn = tools["get_pr_comments"]
    result = fn("https://github.com/kruthis123/nextjs-concepts/pull/1")
    show("output", result)

    check(
        "returns list[PRComment]",
        lambda: isinstance(result, list)
        and all(isinstance(c, PRComment) for c in result),
    )
    check(
        "review comments have path",
        lambda: all(c.path is not None for c in result if c.is_review_comment),
    )
    check(
        "issue comments have no path",
        lambda: all(c.path is None for c in result if not c.is_review_comment),
    )


def test_get_file_at_ref(tools):
    fn = tools["get_file_at_ref"]
    result = fn(REPO, FILE_PATH, REF)
    show("output", result)

    check("returns FileContent", lambda: isinstance(result, FileContent))
    check(
        "content or download_url is set",
        lambda: bool(result.content or result.download_url),
    )
    check(
        "inline content is non-empty",
        lambda: len(result.content) > 0 if result.content else True,
    )
    check(
        "large file has download_url",
        lambda: result.download_url is not None if result.content is None else True,
    )
    _raises(Exception, fn, REPO, "does/not/exist.py", REF)
    check("invalid path raises", lambda: True)


def test_get_directory_tree(tools):
    fn = tools["get_directory_tree"]
    result = fn(DIRECTORY_TREE_REPO, DIRECTORY_TREE_REF, DIRECTORY_TREE_PATH)
    show("output", result)

    check("returns dict", lambda: isinstance(result, dict))
    check("tree is non-empty", lambda: len(result) > 0)
    check(
        "files are 'blob' values",
        lambda: all(v == "blob" for v in _leaf_values(result)),
    )
    subtree = fn(REPO, REF, "src")
    check("path filter returns subtree", lambda: isinstance(subtree, dict))


def test_search_codebase(tools):
    fn = tools["search_codebase"]
    result = fn(SEARCH_REPO, content=SEARCH_CONTENT)
    show("output (content search)", result)

    check("returns list[SearchResult]", lambda: isinstance(result, list))
    check("content search returns non-empty results", lambda: len(result) > 0)
    check(
        "each result is a SearchResult",
        lambda: all(isinstance(r, SearchResult) for r in result),
    )
    check("results have file paths", lambda: all(r.path for r in result))
    check("results have filenames", lambda: all(r.filename for r in result))
    check("results have html_urls", lambda: all(r.html_url for r in result))
    check(
        "line_numbers is a tuple",
        lambda: all(isinstance(r.line_numbers, tuple) for r in result),
    )
    check(
        "text_matches is a tuple",
        lambda: all(isinstance(r.text_matches, tuple) for r in result),
    )
    check(
        "content results have non-empty text_matches",
        lambda: all(len(r.text_matches) > 0 for r in result),
    )
    check(
        "snippet is populated from first text_match",
        lambda: all(r.snippet for r in result),
    )

    filename_result = fn(SEARCH_REPO, filename=SEARCH_FILENAME)
    check("filename filter returns non-empty results", lambda: len(filename_result) > 0)

    path_result = fn(SEARCH_REPO, path=SEARCH_PATH)
    check("path filter accepted", lambda: isinstance(path_result, list))

    symbol_result = fn(SEARCH_REPO, symbol=SEARCH_SYMBOL)
    check("symbol filter accepted", lambda: isinstance(symbol_result, list))

    no_match = fn(SEARCH_REPO, content="xyzzy_no_match_99999_unique")
    check("no-match returns empty list", lambda: no_match == [])

    _raises(ValueError, fn, SEARCH_REPO)
    check("no filters raises ValueError", lambda: True)


def test_get_sibling_files(tools):
    fn = tools["get_sibling_files"]
    result = fn(REPO, FILE_PATH, REF)
    show("output", result)

    directory = FILE_PATH.rsplit("/", 1)[0] if "/" in FILE_PATH else ""
    check(
        "returns list[str]",
        lambda: isinstance(result, list) and all(isinstance(p, str) for p in result),
    )
    check("file excluded from siblings", lambda: FILE_PATH not in result)
    check(
        "all siblings in same dir",
        lambda: all(
            (p.startswith(directory + "/") if directory else "/" not in p)
            for p in result
        ),
    )


def test_get_file_commit_history(tools):
    fn = tools["get_file_commit_history"]
    result = fn(REPO, FILE_PATH)
    show("output", result)

    check(
        "returns list[CommitSummary]",
        lambda: isinstance(result, list)
        and all(isinstance(c, CommitSummary) for c in result),
    )
    check("history is non-empty", lambda: len(result) > 0)
    check(
        "core fields populated",
        lambda: all(c.sha and c.message and c.author and c.date for c in result),
    )
    check("html_url populated", lambda: all(c.html_url for c in result))
    check(
        "parents is a tuple", lambda: all(isinstance(c.parents, tuple) for c in result)
    )
    check(
        "messages are single-line", lambda: all("\n" not in c.message for c in result)
    )

    max3 = fn(REPO, FILE_PATH, max_commits=3)
    check("max_commits=3 returns <=3", lambda: len(max3) <= 3)

    page2 = fn(REPO, FILE_PATH, page=2)
    check("page=2 accepted", lambda: isinstance(page2, list))

    sha_result = fn(REPO, FILE_PATH, sha="main")
    check("sha filter accepted", lambda: isinstance(sha_result, list))


def test_get_commit_diff(tools):
    fn = tools["get_commit_diff"]
    result = fn(REPO, COMMIT_SHA)
    show("output", result)

    check("returns CommitDiff", lambda: isinstance(result, CommitDiff))
    check("sha preserved", lambda: result.sha == COMMIT_SHA)
    check("diff is a tuple", lambda: isinstance(result.diff, tuple))
    check("at least one file changed", lambda: len(result.diff) > 0)
    check(
        "each file has a path",
        lambda: all(f.new_path or f.old_path for f in result.diff),
    )
    check(
        "each file has a status",
        lambda: all(f.status for f in result.diff),
    )


def test_get_blame(tools):
    fn = tools["get_blame"]
    result = fn(REPO, FILE_PATH, REF)
    show("output", result)

    check(
        "returns list[BlameEntry]",
        lambda: isinstance(result, list)
        and all(isinstance(e, BlameEntry) for e in result),
    )
    check("result is non-empty", lambda: len(result) > 0)
    check(
        "all fields populated",
        lambda: all(e.sha and e.message and e.author and e.date for e in result),
    )
    check("commit_url populated", lambda: all(e.commit_url for e in result))
    check(
        "age is int between 1 and 10",
        lambda: all(isinstance(e.age, int) and 1 <= e.age <= 10 for e in result),
    )
    check(
        "messages are single-line", lambda: all("\n" not in e.message for e in result)
    )


def test_get_linked_issue(tools):
    fn = tools["get_linked_issue"]
    result = fn(REPO, ISSUE_NUMBER)
    show("output", result)

    check("returns Issue", lambda: isinstance(result, Issue))
    check("issue number matches", lambda: result.number == ISSUE_NUMBER)
    check("title is non-empty", lambda: bool(result.title))
    check("author is non-empty", lambda: bool(result.author))
    check("state is open or closed", lambda: result.state in ("open", "closed"))
    check("labels is a tuple", lambda: isinstance(result.labels, tuple))
    check("created_at is non-empty", lambda: bool(result.created_at))
    check(
        "comments is a tuple of IssueComment",
        lambda: isinstance(result.comments, tuple)
        and all(isinstance(c, IssueComment) for c in result.comments),
    )
    check(
        "each comment has author and body",
        lambda: all(c.author and c.body for c in result.comments),
    )


def test_get_repo_conventions(tools):
    fn = tools["get_repo_conventions"]
    result = fn(CONVENTIONS_REPO)
    show("output", result)

    check("returns RepoConventions", lambda: isinstance(result, RepoConventions))
    check("files is a tuple", lambda: isinstance(result.files, tuple))
    check(
        "each entry is (name, content)",
        lambda: all(isinstance(e, tuple) and len(e) == 2 for e in result.files),
    )
    check(
        "no entry has empty content",
        lambda: all(content for _, content in result.files),
    )


# ── Registry ──────────────────────────────────────────────────────────────────

SUITES = {
    "get_pr_metadata": test_get_pr_metadata,
    "get_parsed_pr_diff": test_get_parsed_pr_diff,
    "get_pr_description": test_get_pr_description,
    "get_pr_comments": test_get_pr_comments,
    "get_file_at_ref": test_get_file_at_ref,
    "get_directory_tree": test_get_directory_tree,
    "search_codebase": test_search_codebase,
    "get_sibling_files": test_get_sibling_files,
    "get_file_commit_history": test_get_file_commit_history,
    "get_commit_diff": test_get_commit_diff,
    "get_blame": test_get_blame,
    "get_linked_issue": test_get_linked_issue,
    "get_repo_conventions": test_get_repo_conventions,
}

# ── Entry point ───────────────────────────────────────────────────────────────


def _run(args):
    import httpx

    client = httpx.Client()
    tools = {t.__name__: t for t in make_tools(http_client=client)}

    if args.tool:
        if args.tool not in SUITES:
            print(f"Unknown tool {args.tool!r}. Available tools:")
            for name in SUITES:
                print(f"  {name}")
            sys.exit(1)
        to_run = {args.tool: SUITES[args.tool]}
    else:
        to_run = SUITES

    global _current_suite
    for name, suite in to_run.items():
        print(f"\n── {name} {'─' * max(1, 57 - len(name))}")
        _current_suite = name
        suite(tools)

    total = passed + failed
    print(f"\n{'─' * 57}")
    print(f"  {passed}/{total} passed", end="")
    if failed:
        print(f"  ({failed} FAILED)")
        print("\nFailed checks:")
        for fc in failed_checks:
            print(f"  FAIL  {fc}")
        sys.exit(1)
    else:
        print("  — all good")


def main():
    parser = argparse.ArgumentParser(
        description="Manually smoke-test github-context-tools tools against pallets/flask."
    )
    parser.add_argument(
        "tool",
        nargs="?",
        help="Name of the tool to test. Omit to run all tools.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print available tool names and exit.",
    )
    args = parser.parse_args()

    if args.list:
        for name in SUITES:
            print(name)
        return

    _run(args)


if __name__ == "__main__":
    main()
