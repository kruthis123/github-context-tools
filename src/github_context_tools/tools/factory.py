"""
GitHub API tools for fetching code review context.

Call ``make_tools()`` once with an authenticated token to get a list of
plain callables. Pass them directly to any agent framework's tool registry.
The token is captured in a closure and never appears in any tool signature.

Usage::

    from github_context_tools import make_tools

    tools = make_tools(token="ghp_...")  # or omit to read from GH_TOKEN / GITHUB_TOKEN env var

    # Pass to any agent framework
    agent.run(tools=tools)
"""

from collections.abc import Callable

import httpx

from github_context_tools._request import make_requester
from github_context_tools.tools.code import make_code_tools
from github_context_tools.tools.conventions import make_conventions_tools
from github_context_tools.tools.history import make_history_tools
from github_context_tools.tools.issues import make_issues_tools
from github_context_tools.tools.pr import make_pr_tools


def make_tools(
    token: str | None = None,
    http_client: httpx.Client | None = None,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
) -> list[Callable]:
    """
    Return a list of GitHub API tool functions bound to the given token.

    Each tool is a plain callable with a clean signature — no token, no
    client object. Safe to call concurrently; each call opens and closes
    its own HTTP connection.

    :param token: GitHub personal access token. If omitted, reads from the
                  GH_TOKEN or GITHUB_TOKEN environment variable.
    :param http_client: Optional httpx.Client instance. Use this to configure
                        SSL settings, proxies, timeouts, etc. If omitted, a new
                        client is created.
    :param include: If provided, only tools whose names are in this set are
                    returned. Raises ValueError if any name is not recognised.
    :param exclude: If provided, tools whose names are in this set are removed
                    from the result. Raises ValueError if any name is not
                    recognised. When both include and exclude are given,
                    exclusions are applied after inclusions.
    """
    if include is not None and exclude is not None and include.issubset(exclude):
        raise ValueError(
            "include and exclude are mutually exclusive: every tool in "
            f"include {sorted(include)} is also in exclude {sorted(exclude)}, "
            "which would return no tools."
        )

    get_json, get_text, post_json = make_requester(token, http_client)
    all_tools = [
        *make_pr_tools(get_json, get_text, post_json),
        *make_code_tools(get_json, get_text, post_json),
        *make_history_tools(get_json, get_text, post_json),
        *make_issues_tools(get_json, get_text, post_json),
        *make_conventions_tools(get_json, get_text, post_json),
    ]

    if include is None and exclude is None:
        return all_tools

    all_names = {t.__name__ for t in all_tools}

    if include is not None:
        unknown = include - all_names
        if unknown:
            raise ValueError(f"Unknown tool names in include: {sorted(unknown)}")

    if exclude is not None:
        unknown = exclude - all_names
        if unknown:
            raise ValueError(f"Unknown tool names in exclude: {sorted(unknown)}")

    return [
        t for t in all_tools
        if (include is None or t.__name__ in include)
        and (exclude is None or t.__name__ not in exclude)
    ]
