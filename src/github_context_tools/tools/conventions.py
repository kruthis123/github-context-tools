from base64 import b64decode
from collections.abc import Callable
from typing import Annotated

from github_context_tools._utils import validate_repo
from github_context_tools.models import RepoConventions

_CONVENTION_CANDIDATES = [
    "CONTRIBUTING.md",
    "CLAUDE.md",
    "AGENTS.md",
    ".cursor/rules",
    ".cursorrules",
    ".github/copilot-instructions.md",
    "docs/architecture.md",
    "docs/ARCHITECTURE.md",
    "docs/development.md",
    "DEVELOPMENT.md",
]


def _fetch_convention_files(get_json, repo: str) -> list[tuple[str, str]]:
    found = []
    for candidate in _CONVENTION_CANDIDATES:
        try:
            content = b64decode(
                get_json(f"/repos/{repo}/contents/{candidate}")["content"]
            ).decode("utf-8")
            found.append((candidate, content))
        except Exception:
            pass
    return found


def make_conventions_tools(get_json, _get_text, _post_json) -> list[Callable]:
    def get_repo_conventions(
        repo: Annotated[str, "Repository in 'owner/name' format, e.g. 'acme/backend'"],
    ) -> Annotated[
        RepoConventions,
        (
            "Contents of well-known convention and context files found in the repo's default branch. "
            "Files that do not exist are silently skipped. "
            "Returns a tuple of (filename, content) pairs for any of: "
            "CONTRIBUTING.md, CLAUDE.md, AGENTS.md, .cursor/rules, .cursorrules, "
            ".github/copilot-instructions.md, docs/architecture.md, docs/ARCHITECTURE.md, "
            "docs/development.md, DEVELOPMENT.md."
        ),
    ]:
        """Fetch well-known convention and context files from the repo's default branch."""
        validate_repo(repo)
        return RepoConventions(files=tuple(_fetch_convention_files(get_json, repo)))

    return [get_repo_conventions]
