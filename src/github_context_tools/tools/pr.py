from collections.abc import Callable
from typing import Annotated

from git_unified_diff_parse import DiffParser

from github_context_tools._utils import parse_pr_url
from github_context_tools.models import PRComment, PRDescription, PRDiff, PRMetadata


def make_pr_tools(get_json, get_text, _post_json) -> list[Callable]:
    def get_pr_metadata(
        pr_url: Annotated[
            str, "Full GitHub PR URL, e.g. 'https://github.com/owner/repo/pull/123'"
        ],
    ) -> Annotated[
        PRMetadata,
        (
            "Pull request metadata with fields: repo (owner/name), pr_number, title, description,"
            " author (GitHub login), base_branch, head_branch, base_sha, head_sha, html_url,"
            " state ('open' or 'closed'), commits (count), changed_files (count),"
            " additions (line count), deletions (line count)"
        ),
    ]:
        """Fetch pull request metadata."""
        owner, repo, pr_number = parse_pr_url(pr_url)
        repo_full = f"{owner}/{repo}"
        pr_data = get_json(f"/repos/{repo_full}/pulls/{pr_number}")
        return PRMetadata(
            repo=repo_full,
            pr_number=pr_data["number"],
            title=pr_data["title"],
            description=pr_data["body"] or "",
            author=pr_data["user"]["login"],
            base_branch=pr_data["base"]["ref"],
            head_branch=pr_data["head"]["ref"],
            base_sha=pr_data["base"]["sha"],
            head_sha=pr_data["head"]["sha"],
            html_url=pr_data["html_url"],
            state=pr_data["state"],
            commits=pr_data["commits"],
            changed_files=pr_data["changed_files"],
            additions=pr_data["additions"],
            deletions=pr_data["deletions"],
        )

    def get_parsed_pr_diff(
        pr_url: Annotated[
            str, "Full GitHub PR URL, e.g. 'https://github.com/owner/repo/pull/123'"
        ],
    ) -> Annotated[
        PRDiff,
        (
            "Parsed PR diff with fields: repo (owner/name), diff (tuple of ChangedFile objects)."
            " Each ChangedFile has: old_path, new_path, hunks (list of diff hunks)."
            " Each hunk has: old_start, old_count, new_start, new_count, lines (list of DiffLine)."
            " Each DiffLine has: kind ('added', 'removed', or 'context') and content (line text)."
        ),
    ]:
        """Fetch and parse the pull request diff."""
        owner, repo, pr_number = parse_pr_url(pr_url)
        repo_full = f"{owner}/{repo}"
        diff_text = get_text(
            f"/repos/{repo_full}/pulls/{pr_number}",
            headers={"Accept": "application/vnd.github.diff"},
        )
        return PRDiff(
            repo=repo_full,
            diff=tuple(DiffParser().parse(diff_text)),
        )

    def get_pr_description(
        pr_url: Annotated[
            str, "Full GitHub PR URL, e.g. 'https://github.com/owner/repo/pull/123'"
        ],
    ) -> Annotated[
        PRDescription,
        "PR description with fields: title (str), body (str, the full PR description text), labels (tuple of label name strings)",
    ]:
        """Fetch the pull request title, description body, and labels."""
        owner, repo, pr_number = parse_pr_url(pr_url)
        repo_full = f"{owner}/{repo}"
        data = get_json(f"/repos/{repo_full}/pulls/{pr_number}")
        return PRDescription(
            title=data["title"],
            body=data["body"] or "",
            labels=tuple(label["name"] for label in data.get("labels", [])),
        )

    def get_pr_comments(
        pr_url: Annotated[
            str, "Full GitHub PR URL, e.g. 'https://github.com/owner/repo/pull/123'"
        ],
    ) -> Annotated[
        list[PRComment],
        (
            "All comments on the pull request as a list of PRComment objects."
            " Each PRComment has: author (GitHub login), body (comment text), created_at (ISO timestamp),"
            " is_review_comment (True for inline file comments, False for PR-level conversation comments),"
            " html_url (link to the comment)."
            " For review comments (is_review_comment=True): path (file path), line (line number on the diff side),"
            " side ('RIGHT' for additions, 'LEFT' for deletions), original_line (line number on the base commit),"
            " original_side, start_line (first line for multi-line comments), start_side,"
            " diff_hunk (surrounding diff context), commit_id (SHA of commit the comment was made on),"
            " in_reply_to_id (ID of parent comment for replies, None for top-level)."
            " For issue comments (is_review_comment=False): path, line, side, original_line, original_side,"
            " start_line, start_side, diff_hunk, commit_id, in_reply_to_id are all None."
        ),
    ]:
        """Fetch all existing comments on a pull request."""
        owner, repo, pr_number = parse_pr_url(pr_url)
        repo_full = f"{owner}/{repo}"
        # Inline review comments attached to a specific file and line.
        review_comments = get_json(f"/repos/{repo_full}/pulls/{pr_number}/comments")
        # Every PR is also an issue in GitHub's data model and shares the same number.
        # PR-level conversation comments (not tied to a file) are exposed via the Issues API.
        issue_comments = get_json(f"/repos/{repo_full}/issues/{pr_number}/comments")
        comments = [
            PRComment(
                author=c["user"]["login"],
                body=c["body"],
                created_at=c["created_at"],
                path=c.get("path"),
                line=c.get("line"),
                side=c.get("side"),
                original_line=c.get("original_line"),
                original_side=c.get("original_side"),
                start_line=c.get("start_line"),
                start_side=c.get("start_side"),
                diff_hunk=c.get("diff_hunk"),
                commit_id=c.get("commit_id"),
                in_reply_to_id=c.get("in_reply_to_id"),
                html_url=c.get("html_url"),
                is_review_comment=True,
            )
            for c in review_comments
        ]
        comments += [
            PRComment(
                author=c["user"]["login"],
                body=c["body"],
                created_at=c["created_at"],
                path=None,
                line=None,
                side=None,
                original_line=None,
                original_side=None,
                start_line=None,
                start_side=None,
                diff_hunk=None,
                commit_id=None,
                in_reply_to_id=None,
                html_url=c.get("html_url"),
                is_review_comment=False,
            )
            for c in issue_comments
        ]
        return comments

    return [get_pr_metadata, get_parsed_pr_diff, get_pr_description, get_pr_comments]
