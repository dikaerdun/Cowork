"""Helpers for converting Codex review output into structured issues."""

from __future__ import annotations

from typing import Any


def collect_codex_issues(review_comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a normalized issue list from raw review comments.

    v1 deliberately leaves the mapping logic unimplemented so we can settle the
    exact review format with a manual PR before automating extraction.
    """

    raise NotImplementedError("Implement after validating live Codex review output.")
