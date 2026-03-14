"""Tests for the Claude bridge HTTP handler."""

import io
import json
import unittest
from typing import Optional
from unittest.mock import patch

from orchestrator.bridge_server import ClaudeBridgeHandler


class _TestHandler(ClaudeBridgeHandler):
    def __init__(self, path: str, body: bytes, headers: Optional[dict[str, str]] = None):
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


class BridgeServerTests(unittest.TestCase):
    def test_health_endpoint_returns_ok(self) -> None:
        handler = _TestHandler("/health", b"")

        handler.do_GET()

        self.assertIn(("status", 200), handler.responses)
        self.assertIn(b'"status": "ok"', handler.wfile.getvalue())

    def test_post_requires_prompt_and_schema(self) -> None:
        body = json.dumps({"task": "rebuttal"}).encode("utf-8")
        handler = _TestHandler(
            "/claude", body, headers={"Content-Length": str(len(body))}
        )

        handler.do_POST()

        self.assertIn(("status", 400), handler.responses)
        self.assertIn(b"prompt_and_schema_required", handler.wfile.getvalue())

    def test_post_runs_claude_cli(self) -> None:
        payload = {
            "task": "rebuttal",
            "prompt": "hello",
            "schema": {"type": "array"},
        }
        body = json.dumps(payload).encode("utf-8")
        handler = _TestHandler(
            "/claude", body, headers={"Content-Length": str(len(body))}
        )

        with patch(
            "orchestrator.bridge_server._run_claude_cli",
            return_value=[{"issue_id": "R-1"}],
        ):
            handler.do_POST()

        self.assertIn(("status", 200), handler.responses)
        self.assertIn(b'"issue_id": "R-1"', handler.wfile.getvalue())
