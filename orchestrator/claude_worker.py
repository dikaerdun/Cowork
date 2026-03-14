"""Claude-facing entry points for rebuttal and final report generation."""

from __future__ import annotations

from typing import Any


def ask_claude_to_reply(pr_number: int, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ask Claude to respond to each structured issue item."""

    raise NotImplementedError("Implement once Claude GitHub or SDK path is chosen.")


def ask_claude_for_final_report(
    pr_number: int, codex_round2: list[dict[str, Any]]
) -> dict[str, Any]:
    """Ask Claude for the final dispute report after the recheck pass."""

    raise NotImplementedError("Implement once the rebuttal format is stable.")
