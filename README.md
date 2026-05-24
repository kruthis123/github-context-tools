# github-context-tools

Typed GitHub API tools that give LLMs structured access to pull requests, code, history, and issues.

## Installation

```bash
pip install github-context-tools
```

## Quickstart

```python
from github_context_tools import make_tools

tools = make_tools(token="ghp_...")  # or set GH_TOKEN / GITHUB_TOKEN env var

# Pass the list to your agent framework's tool registry
agent.run(tools=tools)
```

## How it works

`make_tools()` returns a list of plain Python functions. You pass that list directly to your agent framework's tool registry — no adapters or glue code needed.

Each tool is fully typed using `Annotated[type, "description"]` on every parameter and return value. Agent frameworks (Anthropic SDK, LangChain, OpenAI, etc.) read these annotations to automatically generate tool schemas, so the LLM always knows what each tool does, what to pass in, and what to expect back.

## Available tools

### Pull requests

| Tool | Description | Returns |
|---|---|---|
| [`get_pr_metadata`](https://github.com/kruthis123/github-context-tools/blob/master/src/github_context_tools/tools/pr.py#L11) | Title, author, branch names, SHAs, state, and change stats for a PR | `PRMetadata` |
| [`get_parsed_pr_diff`](https://github.com/kruthis123/github-context-tools/blob/master/src/github_context_tools/tools/pr.py#L46) | Structured diff of every file changed in a PR, broken into hunks and individual lines | `PRDiff` |
| [`get_pr_description`](https://github.com/kruthis123/github-context-tools/blob/master/src/github_context_tools/tools/pr.py#L71) | Title, body, and labels of a PR | `PRDescription` |
| [`get_pr_comments`](https://github.com/kruthis123/github-context-tools/blob/master/src/github_context_tools/tools/pr.py#L89) | All inline review comments and conversation comments on a PR | `list[PRComment]` |

### Code

| Tool | Description | Returns |
|---|---|---|
| [`get_file_at_ref`](https://github.com/kruthis123/github-context-tools/blob/master/src/github_context_tools/tools/code.py#L85) | Contents of a file at any branch, tag, or commit SHA | `FileContent` |
| [`get_directory_tree`](https://github.com/kruthis123/github-context-tools/blob/master/src/github_context_tools/tools/code.py#L115) | Recursive file tree for a repo or subdirectory at a given ref | `dict` |
| [`search_codebase`](https://github.com/kruthis123/github-context-tools/blob/master/src/github_context_tools/tools/code.py#L142) | Search a repo by content, file path, filename, or symbol name | `list[SearchResult]` |
| [`get_sibling_files`](https://github.com/kruthis123/github-context-tools/blob/master/src/github_context_tools/tools/code.py#L189) | All other files in the same directory as a given file | `list[str]` |

### History

| Tool | Description | Returns |
|---|---|---|
| [`get_file_commit_history`](https://github.com/kruthis123/github-context-tools/blob/master/src/github_context_tools/tools/history.py#L60) | Recent commits that touched a file, newest-first. Supports filtering by author, date range, and branch | `list[CommitSummary]` |
| [`get_commit_diff`](https://github.com/kruthis123/github-context-tools/blob/master/src/github_context_tools/tools/history.py#L123) | Structured diff introduced by a single commit | `CommitDiff` |
| [`get_blame`](https://github.com/kruthis123/github-context-tools/blob/master/src/github_context_tools/tools/history.py#L154) | Blame ranges for an entire file, each annotated with the commit, author, and a recency score | `list[BlameEntry]` |

### Issues

| Tool | Description | Returns |
|---|---|---|
| [`get_linked_issue`](https://github.com/kruthis123/github-context-tools/blob/master/src/github_context_tools/tools/issues.py#L9) | Title, body, author, labels, state, and comments for a GitHub issue | `Issue` |

### Conventions

| Tool | Description | Returns |
|---|---|---|
| [`get_repo_conventions`](https://github.com/kruthis123/github-context-tools/blob/master/src/github_context_tools/tools/conventions.py#L36) | Contents of well-known convention and context files from the default branch (`CONTRIBUTING.md`, `CLAUDE.md`, `AGENTS.md`, `.cursor/rules`, `.cursorrules`, `.github/copilot-instructions.md`, `docs/architecture.md`, `docs/ARCHITECTURE.md`, `docs/development.md`, `DEVELOPMENT.md`) | `RepoConventions` |

## Selecting tools

By default `make_tools()` returns all 13 tools. Use `include` or `exclude` to control which tools are registered with your agent.

**Include only the tools you need:**

```python
tools = make_tools(
    token="ghp_...",
    include={"get_pr_metadata", "get_parsed_pr_diff", "get_pr_comments"},
)
```

**Exclude tools you don't want:**

```python
tools = make_tools(
    token="ghp_...",
    exclude={"get_blame", "search_codebase"},
)
```

Both parameters accept a `set[str]` of tool names (the function names listed in the [Available tools](#available-tools) table). Unrecognised names raise a `ValueError` immediately.

## Authentication

Pass a token directly or set an environment variable:

```bash
export GH_TOKEN=ghp_...
# or
export GITHUB_TOKEN=ghp_...
```

```python
tools = make_tools(token="ghp_...")
```

### Required token scopes

Use a classic personal access token (PAT) with the following scopes:

| Scope | Required for |
|---|---|
| `repo` | All tools on **private** repositories |
| `public_repo` | All tools on **public** repositories only |

Fine-grained PATs work too. Grant **read-only** access to the following permissions on the target repositories:

| Permission | Required for |
|---|---|
| Contents | `get_file_at_ref`, `get_directory_tree`, `get_sibling_files`, `get_repo_conventions` |
| Pull requests | `get_pr_metadata`, `get_parsed_pr_diff`, `get_pr_description`, `get_pr_comments` |
| Issues | `get_linked_issue` |
| Metadata | Required by GitHub for all repository access (granted automatically) |

`get_file_commit_history`, `get_commit_diff`, and `get_blame` use the Commits and GraphQL APIs, which are covered by the Contents and Metadata permissions above.

The token is captured in a closure and never appears in any tool signature, so it is never exposed to the LLM or included in generated schemas.

## License

[MIT](https://github.com/kruthis123/github-context-tools/blob/master/LICENSE)
