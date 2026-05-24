from dataclasses import dataclass
from typing import Optional

from git_unified_diff_parse import ChangedFile


# ── PR entry-point results ────────────────────────────────────────────────────

@dataclass(frozen=True)
class PRMetadata:
    repo:          str  # "owner/name"
    pr_number:     int
    title:         str
    description:   str
    author:        str  # GitHub login
    base_branch:   str
    head_branch:   str
    base_sha:      str
    head_sha:      str
    html_url:      str
    state:         str  # "open" or "closed"
    commits:       int
    changed_files: int
    additions:     int
    deletions:     int


@dataclass(frozen=True)
class PRDiff:
    repo: str  # "owner/name"
    diff: tuple[ChangedFile, ...]


# ── Group 1: Code understanding ───────────────────────────────────────────────

@dataclass(frozen=True)
class FileContent:
    # Decoded file content. None when the file exceeds GitHub's 1MB inline limit.
    content:      Optional[str]
    # Direct download URL. Present when the file is too large for inline delivery.
    download_url: Optional[str]


@dataclass(frozen=True)
class TextMatch:
    fragment: str
    matches:  tuple[tuple[str, tuple[int, int]], ...]  # (matched_text, (start, end))


@dataclass(frozen=True)
class SearchResult:
    path:         str
    filename:     str
    html_url:     str
    sha:          str
    language:     Optional[str]
    score:        float
    line_numbers: tuple[str, ...]
    text_matches: tuple[TextMatch, ...]
    # Kept for backwards compatibility — first fragment from text_matches, or empty string
    snippet:      str


# ── Group 2: History ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CommitSummary:
    sha:      str
    message:  str
    author:   str
    date:     str
    html_url: str
    parents:  tuple[str, ...]  # parent SHAs; len > 1 means merge commit


@dataclass(frozen=True)
class CommitDiff:
    sha:  str
    diff: tuple[ChangedFile, ...]


@dataclass(frozen=True)
class BlameEntry:
    start_line:  int
    end_line:    int
    sha:         str
    message:     str
    author:      str
    date:        str
    commit_url:  str
    age:         int  # 1 (newest) to 10 (oldest) relative to other changes in the file


# ── Group 3: PR intent ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PRDescription:
    title:  str
    body:   str
    labels: tuple[str, ...]


@dataclass(frozen=True)
class PRComment:
    author:            str
    body:              str
    created_at:        str
    path:              Optional[str]
    # Line number on the side of the diff specified by `side`.
    line:              Optional[int]
    # "RIGHT" = new file (addition side), "LEFT" = old file (deletion side).
    # None for non-review (conversation) comments.
    side:              Optional[str]
    # Line number in the file before the PR's changes (base commit).
    original_line:     Optional[int]
    original_side:     Optional[str]
    # For multi-line comments: the first line and its side.
    start_line:        Optional[int]
    start_side:        Optional[str]
    # Surrounding diff context at the point the comment was made.
    diff_hunk:         Optional[str]
    # SHA of the commit the comment was made on — None if made on a stale commit.
    commit_id:         Optional[str]
    # ID of the parent comment; set for replies in a thread, None for top-level.
    in_reply_to_id:    Optional[int]
    html_url:          Optional[str]
    is_review_comment: bool


@dataclass(frozen=True)
class IssueComment:
    author:     str
    body:       str
    created_at: str
    html_url:   str


@dataclass(frozen=True)
class Issue:
    number:       int
    title:        str
    body:         str
    author:       str
    state:        str
    state_reason: Optional[str]  # "completed", "not_planned", "reopened", or None
    labels:       tuple[str, ...]
    created_at:   str
    closed_at:    Optional[str]
    comments:     tuple[IssueComment, ...]


# ── Group 4: Conventions ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class RepoConventions:
    """Keys are filenames (e.g. 'CONTRIBUTING.md'), values are file contents."""
    files: tuple[tuple[str, str], ...]
