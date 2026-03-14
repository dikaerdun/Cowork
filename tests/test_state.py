"""Tests for filesystem-backed PR state."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from orchestrator.state import PRState, PullRequestContext, load_context, save_context


class StateTests(unittest.TestCase):
    def test_save_and_load_context(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = PullRequestContext(
                pr_number=7,
                state=PRState.CODEX_INITIAL_REVIEWED,
                labels=["ai-review-pending"],
                codex_issue_count=2,
            )

            save_context(root, context)
            loaded = load_context(root, 7)

            self.assertEqual(loaded.pr_number, 7)
            self.assertEqual(loaded.state, PRState.CODEX_INITIAL_REVIEWED)
            self.assertEqual(loaded.labels, ["ai-review-pending"])
            self.assertEqual(loaded.codex_issue_count, 2)


if __name__ == "__main__":
    unittest.main()
