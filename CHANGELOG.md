# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-23

### Added
- `make_tools()` factory returning all tools as plain annotated callables
- **PR entry points**: `get_pr_metadata`, `get_parsed_pr_diff`
- **PR intent**: `get_pr_description`, `get_pr_comments`
- **Code understanding**: `get_file_at_ref`, `get_directory_tree`, `search_codebase`, `get_sibling_files`
- **History**: `get_file_commit_history`, `get_commit_diff`, `get_blame`
- **Issues**: `get_linked_issue`
- **Conventions**: `get_repo_conventions`
- Structured output models: `PRMetadata`, `PRDiff`, `PRDescription`, `PRComment`, `FileContent`, `SearchResult`, `CommitSummary`, `CommitDiff`, `BlameEntry`, `Issue`, `IssueComment`, `RepoConventions`
- Typed exceptions: `GitHubAPIError`, `NotFoundError`, `AuthenticationError`, `RateLimitError`
- Token resolution from `GH_TOKEN` / `GITHUB_TOKEN` environment variables
