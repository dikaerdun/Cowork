"""Tests for Claude worker command execution."""

import os
import stat
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from orchestrator.claude_worker import ask_claude_for_final_report, ask_claude_to_reply


class ClaudeWorkerTests(unittest.TestCase):
    def test_cli_reply_path_uses_configured_binary(self) -> None:
        with TemporaryDirectory() as tmp:
            script = Path(tmp) / "fake-claude"
            script.write_text(
                "#!/bin/sh\n"
                "printf '%s' '[{\"issue_id\":\"R-1\",\"position\":\"accept\",\"reason\":\"ok\",\"action\":\"patched\",\"patch_commit\":\"abc\",\"tests_added\":[\"t\"],\"residual_risk\":\"low\"}]'\n"
            )
            script.chmod(script.stat().st_mode | stat.S_IEXEC)

            env = os.environ.copy()
            env["CLAUDE_CLI_PATH"] = str(script)
            with patch.dict(os.environ, env, clear=True):
                replies = ask_claude_to_reply(12, [{"issue_id": "R-1"}])

        self.assertEqual(replies[0]["issue_id"], "R-1")
        self.assertEqual(replies[0]["position"], "accept")

    def test_cli_final_report_path_parses_json(self) -> None:
        with TemporaryDirectory() as tmp:
            script = Path(tmp) / "fake-claude"
            script.write_text(
                "#!/bin/sh\n"
                "printf '%s' '{\"pr\":2,\"agreed\":1,\"partial\":0,\"disputed\":0,\"disputes\":[],\"merge_recommendation\":\"needs_human_approval\"}'\n"
            )
            script.chmod(script.stat().st_mode | stat.S_IEXEC)

            env = os.environ.copy()
            env["CLAUDE_CLI_PATH"] = str(script)
            with patch.dict(os.environ, env, clear=True):
                report = ask_claude_for_final_report(2, [])

        self.assertEqual(report["pr"], 2)
        self.assertEqual(report["disputed"], 0)


if __name__ == "__main__":
    unittest.main()
