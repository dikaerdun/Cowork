"""Run a full local demo of the Claude bridge and worker integration."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from threading import Thread
from typing import Iterator

from http.server import ThreadingHTTPServer

from orchestrator.bridge_server import ClaudeBridgeHandler
from orchestrator.claude_worker import ask_claude_for_final_report, ask_claude_to_reply

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = ROOT / "contracts"


@contextmanager
def temporary_env(**updates: str) -> Iterator[None]:
    """Temporarily set environment variables."""

    previous = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextmanager
def running_bridge_server() -> Iterator[str]:
    """Start the local bridge server on an ephemeral port."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), ClaudeBridgeHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}/claude"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _load_contract(name: str) -> dict:
    """Load a JSON example contract."""

    return json.loads((CONTRACTS_DIR / name).read_text())


def main() -> int:
    """Run an end-to-end local demo."""

    issue = _load_contract("codex_issue.example.json")
    with running_bridge_server() as bridge_url, temporary_env(
        CLAUDE_EXECUTION_MODE="bridge",
        CLAUDE_BRIDGE_URL=bridge_url,
    ):
        replies = ask_claude_to_reply(42, [issue])
        report = ask_claude_for_final_report(42, [])

    print("Local demo complete.")
    print("\nClaude reply payload:")
    print(json.dumps(replies, indent=2))
    print("\nClaude final report:")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
