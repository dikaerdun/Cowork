"""Tests for Claude worker command execution."""

import os
import stat
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from orchestrator.claude_worker import (
    _run_claude,
    ask_claude_for_final_report,
    ask_claude_to_reply,
)


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

    def test_bridge_reply_path_uses_configured_url(self) -> None:
        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def read(self) -> bytes:
                return (
                    b'[{"issue_id":"R-1","position":"accept","reason":"ok","action":"patched",'
                    b'"patch_commit":"abc","tests_added":["t"],"residual_risk":"low"}]'
                )

        env = os.environ.copy()
        env["CLAUDE_BRIDGE_URL"] = "https://bridge.example/claude"
        with patch.dict(os.environ, env, clear=True), patch(
            "orchestrator.claude_worker.shutil.which", return_value=None
        ), patch("orchestrator.claude_worker.request.urlopen", return_value=FakeResponse()) as mock_urlopen:
            replies = ask_claude_to_reply(4, [{"issue_id": "R-1"}])

        self.assertEqual(replies[0]["issue_id"], "R-1")
        self.assertTrue(mock_urlopen.called)

    def test_missing_cli_and_bridge_raises_clear_error(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch(
            "orchestrator.claude_worker.shutil.which", return_value=None
        ):
            with self.assertRaises(RuntimeError) as ctx:
                _run_claude("prompt", {"type": "object"}, task="rebuttal")

        self.assertIn("CLAUDE_BRIDGE_URL", str(ctx.exception))

    def test_bridge_mode_requires_url(self) -> None:
        with patch.dict(
            os.environ, {"CLAUDE_EXECUTION_MODE": "bridge"}, clear=True
        ), patch("orchestrator.claude_worker.shutil.which", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                _run_claude("prompt", {"type": "object"}, task="rebuttal")

        self.assertIn("CLAUDE_BRIDGE_URL", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
