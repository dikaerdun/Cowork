"""Entry points for the first AI review orchestrator."""

from __future__ import annotations

from orchestrator.claude_worker import (
    ask_claude_for_final_report,
    ask_claude_to_reply,
)
from orchestrator.codex_parser import collect_codex_issues
from orchestrator.github_client import GitHubClient


def trigger_codex_review(client: GitHubClient, pr_number: int) -> None:
    """Trigger a Codex review through a PR comment."""

    client.add_label(pr_number, "ai-review-pending")
    client.create_issue_comment(pr_number, "@codex review")


def run_initial_loop(client: GitHubClient, pr_number: int) -> list[dict]:
    """Run the initial review and Claude rebuttal loop."""

    trigger_codex_review(client, pr_number)
    review_comments = client.fetch_review_comments(pr_number)
    issues = collect_codex_issues(review_comments)
    return ask_claude_to_reply(pr_number, issues)


def run_final_report(client: GitHubClient, pr_number: int) -> dict:
    """Run the second review pass and ask Claude for a dispute report."""

    review_comments = client.fetch_review_comments(pr_number)
    codex_round2 = collect_codex_issues(review_comments)
    return ask_claude_for_final_report(pr_number, codex_round2)
