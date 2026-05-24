import re


_PR_URL_RE = re.compile(
    r"https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)"
)


def parse_pr_url(pr_url: str) -> tuple[str, str, int]:
    """Return (owner, repo, pr_number) from a GitHub PR URL."""
    m = _PR_URL_RE.match(pr_url.rstrip("/"))
    if not m:
        raise ValueError(
            f"Invalid GitHub PR URL: {pr_url!r}. "
            "Expected format: https://github.com/owner/repo/pull/123"
        )
    return m.group("owner"), m.group("repo"), int(m.group("number"))


def validate_repo(repo: str) -> None:
    """Raise ValueError if repo is not in 'owner/name' format."""
    if "/" not in repo or repo.startswith("/") or repo.endswith("/"):
        raise ValueError(
            f"Invalid repo format: {repo!r}. Expected 'owner/name', e.g. 'acme/backend'"
        )
