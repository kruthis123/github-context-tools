"""
github-context-tools
====================
A collection of GitHub API tools for fetching context for LLM-based workflows.

Quickstart::

    from github_context_tools import make_tools

    tools = make_tools(token="ghp_...")  # or set GH_TOKEN env var

    # Pass the list to your agent framework's tool registry
    agent.run(tools=tools)
"""

from importlib.metadata import version as _version

__version__ = _version("github-context-tools")

from github_context_tools.tools.factory import make_tools
from github_context_tools.models import (
    PRMetadata,
    PRDiff,
    PRDescription,
    PRComment,
    FileContent,
    SearchResult,
    TextMatch,
    CommitSummary,
    CommitDiff,
    BlameEntry,
    Issue,
    IssueComment,
    RepoConventions,
)
from github_context_tools.exceptions import (
    GitHubAPIError,
    NotFoundError,
    AuthenticationError,
    RateLimitError,
)

__all__ = [
    # Factory
    "make_tools",
    # PR entry points
    "PRMetadata",
    "PRDiff",
    # PR intent
    "PRDescription",
    "PRComment",
    # Code understanding
    "FileContent",
    "SearchResult",
    "TextMatch",
    # History
    "CommitSummary",
    "CommitDiff",
    "BlameEntry",
    # Issues
    "Issue",
    "IssueComment",
    # Conventions
    "RepoConventions",
    # Exceptions
    "GitHubAPIError",
    "NotFoundError",
    "AuthenticationError",
    "RateLimitError",
]
