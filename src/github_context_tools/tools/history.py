from collections.abc import Callable
from typing import Annotated

from git_unified_diff_parse import DiffParser

from github_context_tools._utils import validate_repo
from github_context_tools.models import BlameEntry, CommitDiff, CommitSummary

_BLAME_QUERY = """
    query($owner: String!, $repo: String!, $expr: String!, $path: String!) {
        repository(owner: $owner, name: $repo) {
            object(expression: $expr) {
                ... on Commit {
                    blame(path: $path) {
                        ranges {
                            startingLine
                            endingLine
                            age
                            commit {
                                oid
                                message
                                commitUrl
                                author { name date }
                            }
                        }
                    }
                }
            }
        }
    }
"""


def _blame_entries_from_response(data: dict) -> list[BlameEntry]:
    if "errors" in data:
        messages = ", ".join(e.get("message", "unknown") for e in data["errors"])
        raise ValueError(f"GraphQL error from GitHub: {messages}")
    try:
        ranges = data["data"]["repository"]["object"]["blame"]["ranges"]
    except (KeyError, TypeError) as e:
        raise ValueError(
            "Unexpected GraphQL response shape — the file or ref may not exist"
        ) from e
    return [
        BlameEntry(
            start_line=r["startingLine"],
            end_line=r["endingLine"],
            sha=r["commit"]["oid"],
            message=r["commit"]["message"].splitlines()[0],
            author=r["commit"]["author"]["name"],
            date=r["commit"]["author"]["date"],
            commit_url=r["commit"]["commitUrl"],
            age=r["age"],
        )
        for r in ranges
    ]


def make_history_tools(get_json, get_text, post_json) -> list[Callable]:
    def get_file_commit_history(
        repo: Annotated[str, "Repository in 'owner/name' format, e.g. 'acme/backend'"],
        path: Annotated[
            str, "File path relative to the repo root, e.g. 'src/auth/oauth.py'"
        ],
        max_commits: Annotated[int, "Maximum number of commits per page"] = 10,
        page: Annotated[int, "Page number for pagination (1-indexed)"] = 1,
        sha: Annotated[
            str,
            "Branch name, tag, or SHA to start listing from. Defaults to the repo's default branch",
        ] = "",
        author: Annotated[
            str, "Filter by GitHub username or email address of the commit author"
        ] = "",
        since: Annotated[
            str,
            "Only include commits after this ISO 8601 timestamp, e.g. '2024-01-01T00:00:00Z'",
        ] = "",
        until: Annotated[
            str,
            "Only include commits before this ISO 8601 timestamp, e.g. '2024-12-31T23:59:59Z'",
        ] = "",
    ) -> Annotated[
        list[CommitSummary],
        (
            "Recent commits that touched the file, newest-first. Each entry contains: "
            "sha (full commit SHA), "
            "message (first line of the commit message), "
            "author (git author name), "
            "date (ISO 8601 authored timestamp), "
            "html_url (browser link to the commit on GitHub), "
            "parents (list of parent SHAs — more than one parent indicates a merge commit)."
        ),
    ]:
        """Fetch the commit history for a specific file."""
        validate_repo(repo)
        params = f"path={path}&per_page={max_commits}&page={page}"
        if sha:
            params += f"&sha={sha}"
        if author:
            params += f"&author={author}"
        if since:
            params += f"&since={since}"
        if until:
            params += f"&until={until}"
        data = get_json(f"/repos/{repo}/commits?{params}")
        results = []
        for item in data:
            commit = item["commit"]
            git_author = commit.get("author") or {}
            parents = tuple(p["sha"] for p in item.get("parents", []))
            results.append(
                CommitSummary(
                    sha=item["sha"],
                    message=commit["message"].splitlines()[0],
                    author=git_author.get("name", ""),
                    date=git_author.get("date", ""),
                    html_url=item.get("html_url", ""),
                    parents=parents,
                )
            )
        return results

    def get_commit_diff(
        repo: Annotated[str, "Repository in 'owner/name' format, e.g. 'acme/backend'"],
        commit_sha: Annotated[str, "Full or abbreviated commit SHA"],
    ) -> Annotated[
        CommitDiff,
        (
            "Parsed diff for the commit. Fields: "
            "sha (the commit SHA), "
            "diff (tuple of ChangedFile objects, one per file touched). "
            "Each ChangedFile has: old_path (path before the change, None for added files), "
            "new_path (path after the change, None for deleted files), "
            "status (one of 'added', 'modified', 'removed', 'renamed', 'copied'), "
            "is_binary (True for binary files — hunks will be empty), "
            "hunks (list of DiffHunk objects). "
            "Each DiffHunk has: header (raw @@ line), old_start, old_count, new_start, new_count, "
            "lines (list of DiffLine). "
            "Each DiffLine has: content (line text), is_addition, is_deletion, is_context (bool flags), "
            "new_line_number, old_line_number (None on the side where the line doesn't exist)."
        ),
    ]:
        """Fetch and parse the diff introduced by a single commit."""
        validate_repo(repo)
        diff_text = get_text(
            f"/repos/{repo}/commits/{commit_sha}",
            headers={"Accept": "application/vnd.github.diff"},
        )
        return CommitDiff(
            sha=commit_sha,
            diff=tuple(DiffParser().parse(diff_text)),
        )

    def get_blame(
        repo: Annotated[str, "Repository in 'owner/name' format, e.g. 'acme/backend'"],
        path: Annotated[
            str, "File path relative to the repo root, e.g. 'src/auth/oauth.py'"
        ],
        ref: Annotated[str, "Branch name, tag, or commit SHA to blame at"],
    ) -> Annotated[
        list[BlameEntry],
        (
            "Blame ranges for the entire file, one entry per contiguous block of lines last touched "
            "by the same commit. Each BlameEntry has: "
            "start_line, end_line (1-indexed, inclusive line range covered by this entry), "
            "sha (commit SHA that last modified these lines), "
            "message (first line of that commit's message), "
            "author (git author name), "
            "date (ISO 8601 authored timestamp), "
            "commit_url (browser link to the commit on GitHub), "
            "age (recency score 1–10 relative to other changes in this file: 1 = most recent, 10 = oldest)."
        ),
    ]:
        """Fetch git blame for an entire file via the GitHub GraphQL API."""
        validate_repo(repo)
        owner, repo_name = repo.split("/", 1)
        return _blame_entries_from_response(
            post_json(
                "/graphql",
                body={
                    "query": _BLAME_QUERY,
                    "variables": {
                        "owner": owner,
                        "repo": repo_name,
                        "expr": ref,
                        "path": path,
                    },
                },
            )
        )

    return [get_file_commit_history, get_commit_diff, get_blame]
