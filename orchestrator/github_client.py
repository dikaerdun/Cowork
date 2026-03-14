"""Small GitHub client boundary for the orchestrator scaffold."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GitHubClient:
    """Placeholder client for future GitHub API integration."""

    repository: str

    def add_label(self, pr_number: int, label: str) -> None:
        """Attach a label to a pull request."""
        raise NotImplementedError("Wire this to the GitHub API or gh CLI.")

    def create_issue_comment(self, pr_number: int, body: str) -> None:
        """Post a PR comment."""
        raise NotImplementedError("Wire this to the GitHub API or gh CLI.")

    def fetch_review_comments(self, pr_number: int) -> list[dict]:
        """Fetch PR review comments for parsing."""
        raise NotImplementedError("Wire this to the GitHub API or gh CLI.")
