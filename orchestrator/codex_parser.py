"""Helpers for converting Codex review output into structured issues."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

JSON_BLOCK_RE = re.compile(r"```json\s*(.*?)```", re.DOTALL)
CODEX_REVIEW_MARKERS = (
    "Structured issue list:",
    "Manual Codex-style review result",
    "Manual Codex-style recheck result",
)


@dataclass
class ParsedCodexReview:
    """Structured review payload extracted from PR comments."""

    issues: list[dict[str, Any]] = field(default_factory=list)
    matched_comments: int = 0


def _normalize_issue(candidate: dict[str, Any]) -> dict[str, Any] | None:
    """Return a normalized issue when the minimum required fields exist."""

    required_keys = {
        "issue_id",
        "severity",
        "file",
        "lines",
        "claim",
        "evidence",
        "suggested_fix",
        "confidence",
    }
    if not required_keys.issubset(candidate):
        return None

    return {
        "issue_id": candidate["issue_id"],
        "severity": candidate["severity"],
        "file": candidate["file"],
        "lines": candidate["lines"],
        "claim": candidate["claim"],
        "evidence": list(candidate["evidence"]),
        "suggested_fix": candidate["suggested_fix"],
        "confidence": candidate["confidence"],
    }


def parse_codex_review(comments: list[dict[str, Any]]) -> ParsedCodexReview:
    """Parse structured Codex-style review payloads from issue comments."""

    parsed = ParsedCodexReview()
    for comment in comments:
        body = comment.get("body", "")
        if not any(marker in body for marker in CODEX_REVIEW_MARKERS):
            continue
        if "```json" not in body:
            if "No findings." in body and "Structured issue list:" in body:
                parsed.matched_comments += 1
            continue

        parsed.matched_comments += 1
        for block in JSON_BLOCK_RE.findall(body):
            try:
                payload = json.loads(block)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                issue = _normalize_issue(payload)
                if issue is not None:
                    parsed.issues.append(issue)
            elif isinstance(payload, list):
                for candidate in payload:
                    if isinstance(candidate, dict):
                        issue = _normalize_issue(candidate)
                        if issue is not None:
                            parsed.issues.append(issue)

    return parsed


def collect_codex_issues(review_comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a normalized issue list from raw review comments."""

    return parse_codex_review(review_comments).issues
