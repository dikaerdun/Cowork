"""State primitives for the PR review workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PRState(str, Enum):
    """Known states for the v1 PR review loop."""

    PR_OPEN = "PR_OPEN"
    CODEX_INITIAL_REVIEWED = "CODEX_INITIAL_REVIEWED"
    CLAUDE_REPLIED = "CLAUDE_REPLIED"
    CODEX_RECHECKED = "CODEX_RECHECKED"
    CLAUDE_ESCALATED = "CLAUDE_ESCALATED"
    HUMAN_APPROVED = "HUMAN_APPROVED"
    HUMAN_REQUEST_CHANGES = "HUMAN_REQUEST_CHANGES"
    MERGED = "MERGED"


@dataclass(slots=True)
class PullRequestContext:
    """Minimal in-memory PR state used by the scaffold."""

    pr_number: int
    state: PRState = PRState.PR_OPEN
    labels: list[str] = field(default_factory=list)
    codex_issue_count: int = 0
