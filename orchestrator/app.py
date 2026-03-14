"""Entry points for the first AI review orchestrator."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from orchestrator.claude_worker import (
    ask_claude_for_final_report,
    ask_claude_to_reply,
)
from orchestrator.codex_parser import parse_codex_review
from orchestrator.github_client import GitHubClient
from orchestrator.state import PRState, load_context, save_context

STATE_ROOT = Path(".orchestrator")


def trigger_codex_review(client: GitHubClient, pr_number: int) -> None:
    """Trigger a Codex review through a PR comment."""

    client.add_label(pr_number, "ai-review-pending")
    client.create_issue_comment(pr_number, "@codex review")


def run_initial_loop(client: GitHubClient, pr_number: int) -> list[dict]:
    """Run the initial review and Claude rebuttal loop."""

    trigger_codex_review(client, pr_number)
    comments = client.fetch_issue_comments(pr_number)
    issues = parse_codex_review(comments).issues
    return ask_claude_to_reply(pr_number, issues)


def run_final_report(client: GitHubClient, pr_number: int) -> dict:
    """Run the second review pass and ask Claude for a dispute report."""

    comments = client.fetch_issue_comments(pr_number)
    codex_round2 = parse_codex_review(comments).issues
    return ask_claude_for_final_report(pr_number, codex_round2)


def _issue_is_pull_request(payload: dict[str, Any]) -> bool:
    """Return true when an issue_comment event refers to a pull request."""

    return bool(payload.get("issue", {}).get("pull_request"))


def _pull_request_number(payload: dict[str, Any]) -> int:
    """Extract the PR number across supported event payloads."""

    if "pull_request" in payload:
        return int(payload["pull_request"]["number"])
    if "issue" in payload and payload["issue"].get("pull_request"):
        return int(payload["issue"]["number"])
    raise ValueError("Unsupported event payload: missing pull request number.")


def _repository_name(payload: dict[str, Any]) -> str:
    """Extract the owner/repository name from the event payload."""

    return str(payload["repository"]["full_name"])


def handle_pull_request_event(
    client: GitHubClient, payload: dict[str, Any], state_root: Path = STATE_ROOT
) -> dict[str, Any]:
    """Handle opened or synchronized pull request events."""

    pr_number = _pull_request_number(payload)
    context = load_context(state_root, pr_number)
    trigger_codex_review(client, pr_number)
    context.state = PRState.PR_OPEN
    if "ai-review-pending" not in context.labels:
        context.labels.append("ai-review-pending")
    save_context(state_root, context)
    return {"action": "triggered_codex_review", "pr_number": pr_number}


def handle_issue_comment_event(
    client: GitHubClient, payload: dict[str, Any], state_root: Path = STATE_ROOT
) -> dict[str, Any]:
    """Handle issue comment events on pull requests."""

    if not _issue_is_pull_request(payload):
        return {"action": "ignored_non_pr_comment"}

    pr_number = _pull_request_number(payload)
    context = load_context(state_root, pr_number)
    comments = client.fetch_issue_comments(pr_number)
    parsed = parse_codex_review(comments)

    if parsed.matched_comments == 0:
        save_context(state_root, context)
        return {"action": "no_structured_codex_output", "pr_number": pr_number}

    context.codex_issue_count = len(parsed.issues)
    context.state = (
        PRState.CODEX_INITIAL_REVIEWED if parsed.issues else PRState.CODEX_RECHECKED
    )

    if parsed.issues:
        replies = ask_claude_to_reply(pr_number, parsed.issues)
        client.create_issue_comment(
            pr_number,
            "Claude scaffold reply payload:\n```json\n"
            + json.dumps(replies, indent=2)
            + "\n```",
        )
        client.add_label(pr_number, "await-human")
        context.labels = sorted(set(context.labels + ["ai-review-pending", "await-human"]))
    else:
        client.remove_label(pr_number, "ai-review-pending")
        client.add_label(pr_number, "await-human")
        client.add_label(pr_number, "ready-to-merge")
        context.labels = sorted(set(context.labels + ["await-human", "ready-to-merge"]))

    save_context(state_root, context)
    return {
        "action": "processed_codex_comment",
        "pr_number": pr_number,
        "issues": len(parsed.issues),
    }


def handle_review_event(
    payload: dict[str, Any], state_root: Path = STATE_ROOT
) -> dict[str, Any]:
    """Handle human review submissions."""

    pr_number = _pull_request_number(payload)
    context = load_context(state_root, pr_number)
    review_state = payload.get("review", {}).get("state", "").upper()

    if review_state == "APPROVED":
        context.state = PRState.HUMAN_APPROVED
    elif review_state == "CHANGES_REQUESTED":
        context.state = PRState.HUMAN_REQUEST_CHANGES

    save_context(state_root, context)
    return {"action": "stored_review_state", "pr_number": pr_number, "state": review_state}


def handle_event(
    event_name: str, payload: dict[str, Any], state_root: Path = STATE_ROOT
) -> dict[str, Any]:
    """Dispatch a GitHub event payload to the appropriate handler."""

    client = GitHubClient(repository=_repository_name(payload))

    if event_name == "pull_request":
        return handle_pull_request_event(client, payload, state_root=state_root)

    if event_name == "issue_comment":
        return handle_issue_comment_event(client, payload, state_root=state_root)

    if event_name == "pull_request_review":
        return handle_review_event(payload, state_root=state_root)

    return {"action": "ignored_event", "event_name": event_name}


def main() -> int:
    """Run the orchestrator from GitHub Actions environment variables."""

    event_name = os.environ["GITHUB_EVENT_NAME"]
    event_path = Path(os.environ["GITHUB_EVENT_PATH"])
    payload = json.loads(event_path.read_text())
    result = handle_event(event_name, payload)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0
