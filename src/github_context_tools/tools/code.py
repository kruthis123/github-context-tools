from base64 import b64decode
from collections.abc import Callable
from typing import Annotated

from github_context_tools._utils import validate_repo
from github_context_tools.models import FileContent, SearchResult, TextMatch


def _is_sibling(item_path: str, item_type: str, directory: str, exclude: str) -> bool:
    if item_type != "blob" or item_path == exclude:
        return False
    if directory:
        prefix = directory + "/"
        return item_path.startswith(prefix) and "/" not in item_path[len(prefix):]
    return "/" not in item_path


def _build_tree(items: list[dict], path_prefix: str) -> dict:
    tree: dict = {}
    for item in items:
        if path_prefix and not item["path"].startswith(path_prefix):
            continue
        parts = item["path"].split("/")
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        if item["type"] == "blob":
            node[parts[-1]] = "blob"
    return tree


def _build_search_query(repo: str, path: str | None, filename: str | None, symbol: str | None, content: str | None) -> str:
    if not any([path, filename, symbol, content]):
        raise ValueError("At least one of path, filename, symbol, or content must be provided")
    # The classic GitHub code search API uses free-text terms for content/symbol matching.
    # `filename:` and `path:` are supported qualifiers; `content:` and `symbol:` are not —
    # they must be passed as plain search terms instead.
    qualifiers = [f"repo:{repo}"]
    terms = []
    if path:
        qualifiers.append(f"path:{path}")
    if filename:
        qualifiers.append(f"filename:{filename}")
    if symbol:
        terms.append(symbol)
    if content:
        terms.append(content)
    return "+".join(terms + qualifiers)


def _parse_text_matches(raw: list[dict]) -> tuple[TextMatch, ...]:
    return tuple(
        TextMatch(
            fragment=m.get("fragment", ""),
            matches=tuple(
                (hit["text"], (hit["indices"][0], hit["indices"][1]))
                for hit in m.get("matches", [])
            ),
        )
        for m in raw
    )


def _search_results_from_response(data: dict) -> list[SearchResult]:
    results = []
    for item in data.get("items", []):
        text_matches = _parse_text_matches(item.get("text_matches", []))
        results.append(
            SearchResult(
                path=item["path"],
                filename=item["name"],
                html_url=item["html_url"],
                sha=item["sha"],
                language=item.get("language"),
                score=item.get("score", 0.0),
                line_numbers=tuple(item.get("line_numbers") or []),
                text_matches=text_matches,
                snippet=text_matches[0].fragment if text_matches else "",
            )
        )
    return results


def make_code_tools(get_json, _get_text, _post_json) -> list[Callable]:
    def get_file_at_ref(
        repo: Annotated[str, "Repository in 'owner/name' format, e.g. 'acme/backend'"],
        path: Annotated[
            str, "File path relative to the repo root, e.g. 'src/auth/oauth.py'"
        ],
        ref: Annotated[str, "Any git ref — branch name, tag, or commit SHA"],
    ) -> Annotated[
        FileContent,
        (
            "File content with fields: content (str with decoded file text, None if file exceeds GitHub's 1MB inline limit),"
            " download_url (direct download URL, present when content is None for large files, otherwise may also be set)."
            " Always check content first; fall back to download_url if content is None."
        ),
    ]:
        """Fetch the content of a file at any git ref.

        For files under 1MB, content is returned inline.
        For larger files, content is None and download_url is provided instead.
        """
        validate_repo(repo)
        data = get_json(f"/repos/{repo}/contents/{path}?ref={ref}")
        if "content" in data:
            return FileContent(
                content=b64decode(data["content"]).decode("utf-8"),
                download_url=data.get("download_url"),
            )
        if data.get("download_url"):
            return FileContent(content=None, download_url=data["download_url"])
        raise ValueError(f"Unable to fetch content for {path!r} at ref {ref!r}")

    def get_directory_tree(
        repo: Annotated[str, "Repository in 'owner/name' format, e.g. 'acme/backend'"],
        ref: Annotated[str, "Any git ref — branch name, tag, or commit SHA"],
        path: Annotated[
            str,
            "Directory path to filter by, e.g. 'src/auth'. Pass empty string for the full repo tree",
        ] = "",
    ) -> Annotated[
        dict,
        (
            "Nested dict representing the directory tree rooted at the given path."
            " Directories are dicts mapping entry names to their children."
            " Files are the string 'blob'."
            " Example: {'src': {'auth': {'oauth.py': 'blob', 'token.py': 'blob'}, 'utils.py': 'blob'}}."
            " Pass an empty string for path to get the full repo tree."
        ),
    ]:
        """List the file tree for a directory (or the whole repo) at a given ref.

        Returns a nested dict where each directory is a dict of its children and
        each file is the string 'blob'. Example:
        {'src': {'auth': {'oauth.py': 'blob', 'token.py': 'blob'}, 'utils.py': 'blob'}}
        """
        validate_repo(repo)
        data = get_json(f"/repos/{repo}/git/trees/{ref}?recursive=1")
        return _build_tree(data["tree"], path)

    def search_codebase(
        repo: Annotated[str, "Repository in 'owner/name' format, e.g. 'acme/backend'"],
        path: Annotated[
            str | None,
            "Filter by file path or glob pattern, e.g. 'src/auth' or '*.py'. Matches anywhere in the file path",
        ] = None,
        filename: Annotated[
            str | None,
            "Filter by exact filename, e.g. 'conftest.py' or 'README.md'",
        ] = None,
        symbol: Annotated[
            str | None,
            "Search term to find a function, method, or class by name, e.g. 'WithContext' or 'OAuthHandler'. Used as a free-text search term.",
        ] = None,
        content: Annotated[
            str | None,
            "Search term to find files containing this string, e.g. a variable name, string literal, or import. Used as a free-text search term.",
        ] = None,
    ) -> Annotated[
        list[SearchResult],
        (
            "List of SearchResult objects, each with fields:"
            " path (file path relative to repo root),"
            " filename (just the file name, e.g. 'oauth.py'),"
            " html_url (GitHub web URL to view the file),"
            " sha (git blob SHA of the file),"
            " language (detected programming language, or None),"
            " score (relevance score from GitHub),"
            " line_numbers (tuple of line number strings where matches occur),"
            " text_matches (tuple of TextMatch objects, each with: fragment (code snippet),"
            " matches (tuple of (matched_text, (start_index, end_index)) pairs)),"
            " snippet (first fragment from text_matches for convenience, or empty string)."
        ),
    ]:
        """Search the repository by path, filename, symbol, or content.
        At least one of path, filename, symbol, or content must be provided.
        Rate-limited to 10 requests per minute for authenticated users.
        """
        validate_repo(repo)
        q = _build_search_query(repo, path, filename, symbol, content)
        return _search_results_from_response(
            get_json(
                f"/search/code?q={q}",
                headers={"Accept": "application/vnd.github.text-match+json"},
            )
        )

    def get_sibling_files(
        repo: Annotated[str, "Repository in 'owner/name' format, e.g. 'acme/backend'"],
        path: Annotated[str, "Path of the changed file, e.g. 'src/auth/oauth.py'"],
        ref: Annotated[str, "Any git ref — branch name, tag, or commit SHA"],
    ) -> Annotated[
        list[str],
        (
            "List of file paths (strings) for other files in the same directory as the given path."
            " The given file itself is excluded. Paths are relative to the repo root,"
            " e.g. ['src/auth/token.py', 'src/auth/utils.py']."
        ),
    ]:
        """List sibling files in the same directory as the given file."""
        validate_repo(repo)
        directory = path.rsplit("/", 1)[0] if "/" in path else ""
        data = get_json(f"/repos/{repo}/git/trees/{ref}?recursive=1")
        return [
            item["path"]
            for item in data["tree"]
            if _is_sibling(item["path"], item["type"], directory, path)
        ]

    return [get_file_at_ref, get_directory_tree, search_codebase, get_sibling_files]
