"""Tests for round-aware orchestrator behavior."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from orchestrator.app import _build_codex_review_comment, _comments_after_trigger
from orchestrator.state import PullRequestContext, save_context


class AppTests(unittest.TestCase):
    def test_comments_after_trigger_filters_old_rounds(self) -> None:
        comments = [
            {"id": "1", "body": "@codex review"},
            {"id": "2", "body": "old round"},
            {"id": "3", "body": "@codex review"},
            {"id": "4", "body": "new round"},
        ]

        filtered = _comments_after_trigger(comments, "3")

        self.assertEqual(filtered, [{"id": "4", "body": "new round"}])

    def test_build_review_comment_marks_round_and_phase(self) -> None:
        comment = _build_codex_review_comment(2, recheck=True)

        self.assertIn("@codex review", comment)
        self.assertIn("round=2", comment)
        self.assertIn("phase=recheck", comment)

    def test_context_round_fields_persist(self) -> None:
        with TemporaryDirectory() as tmp:
            context = PullRequestContext(
                pr_number=5,
                current_round=2,
                last_processed_round=1,
                trigger_comment_id="abc123",
            )
            save_context(Path(tmp), context)

            payload = (Path(tmp) / "pr-5.json").read_text()

            self.assertIn('"current_round": 2', payload)
            self.assertIn('"last_processed_round": 1', payload)
            self.assertIn('"trigger_comment_id": "abc123"', payload)


if __name__ == "__main__":
    unittest.main()
