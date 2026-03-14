"""Tests for Codex-style comment parsing."""

import unittest

from orchestrator.codex_parser import parse_codex_review


class ParseCodexReviewTests(unittest.TestCase):
    def test_supports_issue_lists(self) -> None:
        comments = [
            {
                "body": """Manual Codex-style review result:

Structured issue list:
```json
[
  {
    "issue_id": "R-001",
    "severity": "medium",
    "file": "orchestrator/app.py",
    "lines": "10-20",
    "claim": "Handler misses edge case",
    "evidence": ["missing guard", "no failing test"],
    "suggested_fix": "Add a guard and regression test",
    "confidence": 0.72
  }
]
```""",
            }
        ]

        parsed = parse_codex_review(comments)

        self.assertEqual(parsed.matched_comments, 1)
        self.assertEqual(len(parsed.issues), 1)
        self.assertEqual(parsed.issues[0]["issue_id"], "R-001")

    def test_tracks_no_findings_comments(self) -> None:
        comments = [
            {"body": "Manual Codex-style review result:\n\nNo findings.\n\nStructured issue list:"}
        ]

        parsed = parse_codex_review(comments)

        self.assertEqual(parsed.matched_comments, 1)
        self.assertEqual(parsed.issues, [])


if __name__ == "__main__":
    unittest.main()
