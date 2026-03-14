"""Tests for the local end-to-end demo."""

import io
import os
import stat
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from orchestrator.local_demo import main


class LocalDemoTests(unittest.TestCase):
    def test_local_demo_runs_with_fake_claude(self) -> None:
        with TemporaryDirectory() as tmp:
            script = Path(tmp) / "fake-claude"
            script.write_text(
                "#!/bin/sh\n"
                "if printf '%s' \"$@\" | grep -q 'claude_rebuttal'; then\n"
                "  printf '%s' '[{\"issue_id\":\"R-004\",\"position\":\"accept\",\"reason\":\"ok\",\"action\":\"patched\",\"patch_commit\":\"abc\",\"tests_added\":[\"demo\"],\"residual_risk\":\"low\"}]'\n"
                "else\n"
                "  printf '%s' '{\"pr\":42,\"agreed\":1,\"partial\":0,\"disputed\":0,\"disputes\":[],\"merge_recommendation\":\"needs_human_approval\"}'\n"
                "fi\n"
            )
            script.chmod(script.stat().st_mode | stat.S_IEXEC)

            env = os.environ.copy()
            env["CLAUDE_CLI_PATH"] = str(script)
            with patch.dict(os.environ, env, clear=True), patch(
                "sys.stdout", new_callable=io.StringIO
            ) as stdout:
                exit_code = main()

        self.assertEqual(exit_code, 0)
        self.assertIn("Local demo complete.", stdout.getvalue())
