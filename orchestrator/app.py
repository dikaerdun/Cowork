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
ROUND_MARKER_PREFIX = "<!-- ai-review:"


def _build_codex_review_comment(round_number: int, recheck: bool = False) -> str:
    """Build the Codex trigger comment with a hidden round marker."""

    body = "@codex review"
    if recheck:
        body = (
            (Path(__file__).parent / "prompts" / "codex_recheck_comment.md").read_text().strip()
        )
    marker = f"<!-- ai-review: round={round_number}; phase={'recheck' if recheck else 'initial'} -->"
    return f"{body}\n\n{marker}"


def _comments_after_trigger(
    comments: list[dict[str, Any]], trigger_comment_id: str
) -> list[dict[str, Any]]:
    """Return only comments posted after the current round trigger comment."""

    if not trigger_comment_id:
        return comments

    for index, comment in enumerate(comments):
        if str(comment.get("id")) == str(trigger_comment_id):
            return comments[index + 1 :]

    return comments


def trigger_codex_review(
    client: GitHubClient, pr_number: int, round_number: int, recheck: bool = False
) -> dict[str, Any]:
    """Trigger a Codex review through a PR comment."""

    client.add_label(pr_number, "ai-review-pending")
    return client.create_issue_comment(
        pr_number, _build_codex_review_comment(round_number, recheck=recheck)
    )


def run_initial_loop(client: GitHubClient, pr_number: int) -> list[dict]:
    """Run the initial review and Claude rebuttal loop."""

    trigger_codex_review(client, pr_number, round_number=1)
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
    context.current_round += 1
    trigger_comment = trigger_codex_review(
        client,
        pr_number,
        round_number=context.current_round,
        recheck=context.current_round > 1,
    )
    context.state = PRState.PR_OPEN
    if "ai-review-pending" not in context.labels:
        context.labels.append("ai-review-pending")
    context.trigger_comment_id = str(trigger_comment.get("id", ""))
    save_context(state_root, context)
    return {
        "action": "triggered_codex_review",
        "pr_number": pr_number,
        "round": context.current_round,
    }


def handle_issue_comment_event(
    client: GitHubClient, payload: dict[str, Any], state_root: Path = STATE_ROOT
) -> dict[str, Any]:
    """Handle issue comment events on pull requests."""

    if not _issue_is_pull_request(payload):
        return {"action": "ignored_non_pr_comment"}

    pr_number = _pull_request_number(payload)
    context = load_context(state_root, pr_number)
    comments = client.fetch_issue_comments(pr_number)
    round_comments = _comments_after_trigger(comments, context.trigger_comment_id)
    parsed = parse_codex_review(round_comments)

    if parsed.matched_comments == 0:
        save_context(state_root, context)
        return {
            "action": "no_structured_codex_output",
            "pr_number": pr_number,
            "round": context.current_round,
        }

    if context.last_processed_round >= context.current_round:
        return {
            "action": "round_already_processed",
            "pr_number": pr_number,
            "round": context.current_round,
        }

    context.codex_issue_count = len(parsed.issues)
    context.state = (
        PRState.CODEX_INITIAL_REVIEWED if parsed.issues else PRState.CODEX_RECHECKED
    )

    if parsed.issues:
        replies = ask_claude_to_reply(pr_number, parsed.issues)
        client.create_issue_comment(
            pr_number,
            "Claude rebuttal response:\n```json\n"
            + json.dumps(replies, indent=2)
            + "\n```",
        )
        client.add_label(pr_number, "await-human")
        context.labels = sorted(set(context.labels + ["ai-review-pending", "await-human"]))
        context.last_processed_round = context.current_round
        context.current_round += 1
        trigger_comment = trigger_codex_review(
            client,
            pr_number,
            round_number=context.current_round,
            recheck=True,
        )
        context.trigger_comment_id = str(trigger_comment.get("id", ""))
    else:
        client.remove_label(pr_number, "ai-review-pending")
        client.add_label(pr_number, "await-human")
        client.add_label(pr_number, "ready-to-merge")
        context.labels = sorted(set(context.labels + ["await-human", "ready-to-merge"]))
        final_report = ask_claude_for_final_report(pr_number, parsed.issues)
        client.create_issue_comment(
            pr_number,
            "Claude final dispute report:\n```json\n"
            + json.dumps(final_report, indent=2)
            + "\n```",
        )
        context.last_processed_round = context.current_round

    save_context(state_root, context)
    return {
        "action": "processed_codex_comment",
        "pr_number": pr_number,
        "issues": len(parsed.issues),
        "round": context.last_processed_round,
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
