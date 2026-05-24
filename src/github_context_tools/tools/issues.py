from collections.abc import Callable
from typing import Annotated

from github_context_tools._utils import validate_repo
from github_context_tools.models import Issue, IssueComment


def make_issues_tools(get_json, _get_text, _post_json) -> list[Callable]:
    def get_linked_issue(
        repo: Annotated[str, "Repository in 'owner/name' format, e.g. 'acme/backend'"],
        issue_number: Annotated[int, "GitHub issue number, e.g. 42"],
    ) -> Annotated[
        Issue,
        (
            "GitHub issue with fields: "
            "number (issue number), "
            "title, "
            "body (issue description text), "
            "author (GitHub login of the issue creator), "
            "state ('open' or 'closed'), "
            "state_reason (why it was closed: 'completed', 'not_planned', 'reopened', or null), "
            "labels (tuple of label name strings), "
            "created_at (ISO 8601 timestamp), "
            "closed_at (ISO 8601 timestamp or null), "
            "comments (tuple of IssueComment objects). "
            "Each IssueComment has: author (GitHub login), body (comment text), "
            "created_at (ISO 8601 timestamp), html_url (link to the comment)."
        ),
    ]:
        """Fetch a GitHub issue and its comments by issue number."""
        validate_repo(repo)
        data = get_json(f"/repos/{repo}/issues/{issue_number}")
        comments_data = get_json(f"/repos/{repo}/issues/{issue_number}/comments")
        return Issue(
            number=data["number"],
            title=data["title"],
            body=data["body"] or "",
            author=data["user"]["login"],
            state=data["state"],
            state_reason=data.get("state_reason"),
            labels=tuple(lb["name"] for lb in data.get("labels", [])),
            created_at=data["created_at"],
            closed_at=data.get("closed_at"),
            comments=tuple(
                IssueComment(
                    author=c["user"]["login"],
                    body=c["body"],
                    created_at=c["created_at"],
                    html_url=c["html_url"],
                )
                for c in comments_data
            ),
        )

    return [get_linked_issue]
