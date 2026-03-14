"""Tests for the local web UI handler."""

import io
import json
import unittest
from typing import Optional
from unittest.mock import patch

from orchestrator.web_ui import LocalUIHandler, RECENT_RUN


class _TestHandler(LocalUIHandler):
    def __init__(
        self, path: str, body: bytes = b"", headers: Optional[dict[str, str]] = None
    ):
        self.path = path
        self.headers = headers or {}
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.responses = []

    def send_response(self, code: int, message=None) -> None:
        self.responses.append(("status", code))

    def send_header(self, key: str, value: str) -> None:
        self.responses.append(("header", key, value))

    def end_headers(self) -> None:
        self.responses.append(("end_headers",))


class WebUITests(unittest.TestCase):
    def setUp(self) -> None:
        RECENT_RUN.update(
            {"status": "idle", "message": "No run yet.", "reply": None, "report": None}
        )

    def test_root_serves_html(self) -> None:
        handler = _TestHandler("/")

        handler.do_GET()

        self.assertIn(("status", 200), handler.responses)
        self.assertIn(b"Cowork Local Review UI", handler.wfile.getvalue())

    def test_api_run_demo_returns_reply_and_report(self) -> None:
        body = json.dumps({"issue": {"issue_id": "R-1"}}).encode("utf-8")
        handler = _TestHandler("/api/run-demo", body, {"Content-Length": str(len(body))})

        class _Env:
            def __enter__(self):
                return None

            def __exit__(self, exc_type, exc, tb):
                return None

        with patch("orchestrator.web_ui.running_bridge_server", return_value=_Env()), patch(
            "orchestrator.web_ui.temporary_env", return_value=_Env()
        ), patch("orchestrator.web_ui.ask_claude_to_reply", return_value=[{"ok": True}]), patch(
            "orchestrator.web_ui.ask_claude_for_final_report",
            return_value={"merge_recommendation": "needs_human_approval"},
        ):
            handler.do_POST()

        self.assertIn(("status", 200), handler.responses)
        self.assertIn(b'"ok": true', handler.wfile.getvalue().lower())

    def test_status_endpoint_returns_worker_status(self) -> None:
        handler = _TestHandler("/api/status")

        handler.do_GET()

        self.assertIn(("status", 200), handler.responses)
        self.assertIn(b'"worker_status"', handler.wfile.getvalue())

    def test_preset_endpoint_returns_default_issue(self) -> None:
        handler = _TestHandler("/api/presets/default")

        handler.do_GET()

        self.assertIn(("status", 200), handler.responses)
        self.assertIn(b'"issue_id": "R-004"', handler.wfile.getvalue())
