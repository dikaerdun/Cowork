"""Claude-facing entry points for rebuttal and final report generation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

PROMPT_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    """Load a prompt template from disk."""

    return (PROMPT_DIR / name).read_text()


def _claude_command() -> str:
    """Return the configured Claude executable."""

    return os.environ.get("CLAUDE_CLI_PATH", "claude")


def _run_claude(prompt: str, schema: dict[str, Any]) -> Any:
    """Run Claude CLI and parse the JSON-only response."""

    command = _claude_command()
    if shutil.which(command) is None:
        raise RuntimeError(f"Claude CLI not found: {command}")

    args = [
        command,
        "-p",
        "--output-format",
        "text",
        "--json-schema",
        json.dumps(schema),
        "--permission-mode",
        "default",
        "--tools",
        "",
    ]
    model = os.environ.get("CLAUDE_MODEL")
    if model:
        args.extend(["--model", model])
    args.append(prompt)

    result = subprocess.run(args, check=True, text=True, capture_output=True)
    return json.loads(result.stdout)


def ask_claude_to_reply(pr_number: int, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ask Claude CLI to respond to each structured issue item."""

    prompt = (
        _load_prompt("claude_rebuttal.md")
        + "\n\nPR number:\n"
        + str(pr_number)
        + "\n\nIssues JSON:\n```json\n"
        + json.dumps(issues, indent=2)
        + "\n```"
    )
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "issue_id": {"type": "string"},
                "position": {"type": "string", "enum": ["accept", "partial", "reject"]},
                "reason": {"type": "string"},
                "action": {"type": "string"},
                "patch_commit": {"type": "string"},
                "tests_added": {"type": "array", "items": {"type": "string"}},
                "residual_risk": {"type": "string"},
            },
            "required": [
                "issue_id",
                "position",
                "reason",
                "action",
                "patch_commit",
                "tests_added",
                "residual_risk",
            ],
            "additionalProperties": False,
        },
    }
    return list(_run_claude(prompt, schema))


def ask_claude_for_final_report(
    pr_number: int, codex_round2: list[dict[str, Any]]
) -> dict[str, Any]:
    """Ask Claude CLI for the final human-facing dispute report."""

    prompt = (
        _load_prompt("claude_final_report.md")
        + "\n\nPR number:\n"
        + str(pr_number)
        + "\n\nRound 2 issues JSON:\n```json\n"
        + json.dumps(codex_round2, indent=2)
        + "\n```"
    )
    schema = {
        "type": "object",
        "properties": {
            "pr": {"type": "integer"},
            "agreed": {"type": "integer"},
            "partial": {"type": "integer"},
            "disputed": {"type": "integer"},
            "disputes": {"type": "array"},
            "merge_recommendation": {"type": "string"},
        },
        "required": [
            "pr",
            "agreed",
            "partial",
            "disputed",
            "disputes",
            "merge_recommendation",
        ],
        "additionalProperties": False,
    }
    return dict(_run_claude(prompt, schema))
