"""Minimal HTTP bridge that proxies structured requests to Claude CLI."""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from orchestrator.claude_worker import _run_claude_cli


def _bridge_token() -> str:
    """Return the optional bearer token required by the bridge."""

    return os.environ.get("CLAUDE_BRIDGE_TOKEN", "").strip()


def _validate_auth(handler: BaseHTTPRequestHandler) -> bool:
    """Validate bearer auth when a bridge token is configured."""

    expected = _bridge_token()
    if not expected:
        return True

    header = handler.headers.get("Authorization", "")
    return header == f"Bearer {expected}"


def _json_response(
    handler: BaseHTTPRequestHandler, status: HTTPStatus, payload: dict[str, Any] | list[Any]
) -> None:
    """Write a JSON response."""

    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class ClaudeBridgeHandler(BaseHTTPRequestHandler):
    """HTTP handler for Claude bridge requests."""

    server_version = "CoworkClaudeBridge/0.1"

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/claude":
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        if not _validate_auth(self):
            _json_response(self, HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
            return

        prompt = payload.get("prompt")
        schema = payload.get("schema")
        if not isinstance(prompt, str) or not isinstance(schema, dict):
            _json_response(
                self,
                HTTPStatus.BAD_REQUEST,
                {"error": "prompt_and_schema_required"},
            )
            return

        if model := payload.get("model"):
            os.environ["CLAUDE_MODEL"] = str(model)

        try:
            result = _run_claude_cli(prompt, schema)
        except Exception as exc:  # noqa: BLE001
            _json_response(
                self,
                HTTPStatus.BAD_GATEWAY,
                {"error": "claude_execution_failed", "details": str(exc)},
            )
            return

        _json_response(self, HTTPStatus.OK, result)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            _json_response(self, HTTPStatus.OK, {"status": "ok"})
            return

        _json_response(self, HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def log_message(self, format: str, *args: object) -> None:
        """Silence default access logging."""

        return None


def main() -> int:
    """Run the bridge server."""

    host = os.environ.get("CLAUDE_BRIDGE_HOST", "127.0.0.1")
    port = int(os.environ.get("CLAUDE_BRIDGE_PORT", "8787"))
    server = ThreadingHTTPServer((host, port), ClaudeBridgeHandler)
    print(f"Claude bridge listening on http://{host}:{port}/claude")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
