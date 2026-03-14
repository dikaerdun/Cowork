"""State primitives for the PR review workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


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


@dataclass
class PullRequestContext:
    """Minimal in-memory PR state used by the scaffold."""

    pr_number: int
    state: PRState = PRState.PR_OPEN
    labels: list[str] = field(default_factory=list)
    codex_issue_count: int = 0

    def to_dict(self) -> dict:
        """Serialize the PR context for storage on disk."""

        return {
            "pr_number": self.pr_number,
            "state": self.state.value,
            "labels": self.labels,
            "codex_issue_count": self.codex_issue_count,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "PullRequestContext":
        """Hydrate a PR context from a stored payload."""

        return cls(
            pr_number=payload["pr_number"],
            state=PRState(payload.get("state", PRState.PR_OPEN.value)),
            labels=list(payload.get("labels", [])),
            codex_issue_count=int(payload.get("codex_issue_count", 0)),
        )


def state_file_path(root: Path, pr_number: int) -> Path:
    """Return the state file path for a PR."""

    return root / f"pr-{pr_number}.json"


def load_context(root: Path, pr_number: int) -> PullRequestContext:
    """Load a PR context from disk if present."""

    path = state_file_path(root, pr_number)
    if not path.exists():
        return PullRequestContext(pr_number=pr_number)

    return PullRequestContext.from_dict(json.loads(path.read_text()))


def save_context(root: Path, context: PullRequestContext) -> Path:
    """Persist a PR context to disk."""

    root.mkdir(parents=True, exist_ok=True)
    path = state_file_path(root, context.pr_number)
    path.write_text(json.dumps(context.to_dict(), indent=2, sort_keys=True) + "\n")
    return path
