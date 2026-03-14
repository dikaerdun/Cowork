"""GitHub client boundary for the orchestrator workflow."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass
class GitHubClient:
    """Minimal GitHub CLI client used by the orchestrator."""

    repository: str

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Run a GitHub CLI command and return the completed process."""

        cmd = ["gh", *args]
        if args and args[0] != "api":
            cmd.extend(["-R", self.repository])
        return subprocess.run(cmd, check=True, text=True, capture_output=True)

    def add_label(self, pr_number: int, label: str) -> None:
        """Attach a label to a pull request."""

        self._run("issue", "edit", str(pr_number), "--add-label", label)

    def remove_label(self, pr_number: int, label: str) -> None:
        """Remove a label from a pull request."""

        self._run("issue", "edit", str(pr_number), "--remove-label", label)

    def create_issue_comment(self, pr_number: int, body: str) -> dict[str, Any]:
        """Post a PR comment."""

        result = self._run(
            "api",
            f"repos/{self.repository}/issues/{pr_number}/comments",
            "--method",
            "POST",
            "--field",
            f"body={body}",
        )
        return dict(json.loads(result.stdout))

    def fetch_issue_comments(self, pr_number: int) -> list[dict[str, Any]]:
        """Fetch PR issue comments for parsing."""

        result = self._run(
            "pr",
            "view",
            str(pr_number),
            "--json",
            "comments",
        )
        payload = json.loads(result.stdout)
        return list(payload.get("comments", []))

    def fetch_review_comments(self, pr_number: int) -> list[dict[str, Any]]:
        """Fetch PR review comments for parsing."""

        result = self._run(
            "api",
            f"repos/{self.repository}/pulls/{pr_number}/comments",
        )
        return list(json.loads(result.stdout))
