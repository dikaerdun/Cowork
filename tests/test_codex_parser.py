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

    def test_ignores_non_codex_json_comments(self) -> None:
        comments = [
            {
                "body": """Claude rebuttal response:
```json
[{"issue_id":"R-001","position":"accept"}]
```""",
            }
        ]

        parsed = parse_codex_review(comments)

        self.assertEqual(parsed.matched_comments, 0)
        self.assertEqual(parsed.issues, [])

    def test_ignores_malformed_json_blocks(self) -> None:
        comments = [
            {
                "body": """Manual Codex-style review result:

Structured issue list:
```json
{"issue_id":
```
```json
[
  {
    "issue_id": "R-002",
    "severity": "low",
    "file": "orchestrator/codex_parser.py",
    "lines": "1-5",
    "claim": "Valid payload still parses",
    "evidence": ["second block is well formed"],
    "suggested_fix": "Keep parsing subsequent blocks",
    "confidence": 0.61
  }
]
```""",
            }
        ]

        parsed = parse_codex_review(comments)

        self.assertEqual(parsed.matched_comments, 1)
        self.assertEqual(len(parsed.issues), 1)
        self.assertEqual(parsed.issues[0]["issue_id"], "R-002")


if __name__ == "__main__":
    unittest.main()
