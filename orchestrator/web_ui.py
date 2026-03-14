"""本地 Web 工作台，用于运行 Claude 回复与总结演示。"""

from __future__ import annotations

import html
import json
import os
import shutil
from contextlib import contextmanager
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any, Iterator
from urllib.parse import urlparse

from orchestrator.bridge_server import ClaudeBridgeHandler
from orchestrator.claude_worker import ask_claude_for_final_report, ask_claude_to_reply
from orchestrator.codex_parser import parse_codex_review
from orchestrator.github_client import GitHubClient

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = ROOT / "contracts"
STATE_DIR = ROOT / ".orchestrator"
TEMPLATES_PATH = STATE_DIR / "ui_templates.json"
RECENT_RUN: dict[str, Any] = {
    "status": "idle",
    "message": "尚未运行。",
    "reply": None,
    "report": None,
    "source": "",
}
RUN_LOGS: list[dict[str, str]] = []


def _load_default_issue() -> str:
    """返回页面默认展示的问题 JSON。"""

    return (CONTRACTS_DIR / "codex_issue.example.json").read_text()


def _preset_payloads() -> dict[str, dict[str, Any]]:
    """返回界面可切换的预设模板。"""

    payloads = {
        "default": json.loads((CONTRACTS_DIR / "codex_issue.example.json").read_text()),
        "reply-example": json.loads((CONTRACTS_DIR / "claude_reply.example.json").read_text()),
        "final-report-example": json.loads(
            (CONTRACTS_DIR / "claude_final_report.example.json").read_text()
        ),
    }
    return payloads


def _saved_templates() -> dict[str, dict[str, Any]]:
    """读取用户保存的本地模板。"""

    if not TEMPLATES_PATH.exists():
        return {}
    return dict(json.loads(TEMPLATES_PATH.read_text()))


def _save_templates(templates: dict[str, dict[str, Any]]) -> None:
    """保存用户模板到本地状态目录。"""

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_PATH.write_text(json.dumps(templates, indent=2, ensure_ascii=False) + "\n")


def _all_templates() -> dict[str, dict[str, Any]]:
    """返回内置模板与本地模板的合并结果。"""

    templates = dict(_preset_payloads())
    for name, payload in _saved_templates().items():
        templates[f"user:{name}"] = payload
    return templates


def _append_log(kind: str, message: str) -> None:
    """追加一条最近日志。"""

    RUN_LOGS.insert(
        0,
        {
            "time": datetime.now().strftime("%H:%M:%S"),
            "kind": kind,
            "message": message,
        },
    )
    del RUN_LOGS[20:]


def _human_summary(report: dict[str, Any]) -> dict[str, Any]:
    """从最终报告生成更适合人工审批阅读的摘要。"""

    disputes = report.get("disputes", [])
    if disputes:
        headline = "仍有分歧，建议人工重点确认。"
    else:
        headline = "当前没有剩余分歧，可进入人工审批。"

    return {
        "headline": headline,
        "merge_recommendation": report.get("merge_recommendation", "unknown"),
        "agreed": report.get("agreed", 0),
        "partial": report.get("partial", 0),
        "disputed": report.get("disputed", 0),
        "disputes": disputes,
    }


def _parse_pr_reference(pr_ref: str) -> int:
    """从 PR 编号或 URL 中解析 PR 号。"""

    pr_ref = pr_ref.strip()
    if pr_ref.isdigit():
        return int(pr_ref)
    parsed = urlparse(pr_ref)
    if parsed.path:
        parts = [part for part in parsed.path.split("/") if part]
        if "pull" in parts:
            index = parts.index("pull")
            if index + 1 < len(parts) and parts[index + 1].isdigit():
                return int(parts[index + 1])
    raise ValueError("无法解析 PR 编号，请输入 PR 数字或完整 PR 链接。")


def _import_pr_issues(repository: str, pr_ref: str) -> dict[str, Any]:
    """从真实 PR 评论中提取结构化 issue。"""

    client = GitHubClient(repository=repository)
    pr_number = _parse_pr_reference(pr_ref)
    comments = client.fetch_issue_comments(pr_number)
    parsed = parse_codex_review(comments)
    issues = parsed.issues
    return {
        "repository": repository,
        "pr_number": pr_number,
        "issues": issues,
        "matched_comments": parsed.matched_comments,
        "comment_count": len(comments),
    }


def _worker_status() -> dict[str, Any]:
    """返回轻量级运行环境状态。"""

    return {
        "claude_cli_found": bool(shutil.which(os.environ.get("CLAUDE_CLI_PATH", "claude"))),
        "execution_mode": os.environ.get("CLAUDE_EXECUTION_MODE", "auto"),
        "bridge_url_configured": bool(os.environ.get("CLAUDE_BRIDGE_URL")),
        "bridge_token_configured": bool(os.environ.get("CLAUDE_BRIDGE_TOKEN")),
        "claude_model": os.environ.get("CLAUDE_MODEL", ""),
    }


@contextmanager
def temporary_env(**updates: str) -> Iterator[None]:
    """临时设置环境变量。"""

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
    """在临时端口启动本地 bridge 服务。"""

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


HTML_PAGE = """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Cowork 本地评审工作台</title>
    <style>
      :root {
        --bg: #f5f0e8;
        --panel: #fffaf3;
        --panel-strong: #f2e7d8;
        --ink: #1f1d1a;
        --muted: #6d655b;
        --accent: #b64d2d;
        --accent-deep: #8f3114;
        --line: #d9cdbd;
        --success: #1f7a4f;
        --warning: #8b5a12;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "PingFang SC", "Hiragino Sans GB", "Noto Serif SC", Georgia, serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(182, 77, 45, 0.12), transparent 28%),
          linear-gradient(180deg, #f8f3eb, #efe5d8 55%, #e8dbc9);
      }
      .shell {
        max-width: 1100px;
        margin: 0 auto;
        padding: 32px 20px 56px;
      }
      .hero {
        padding: 28px;
        border: 1px solid var(--line);
        background: rgba(255, 250, 243, 0.88);
        backdrop-filter: blur(6px);
        border-radius: 24px;
        box-shadow: 0 16px 50px rgba(63, 43, 24, 0.08);
      }
      h1 { margin: 0 0 10px; font-size: clamp(2rem, 5vw, 3.5rem); }
      h2 {
        margin: 0 0 12px;
        font-size: 1.25rem;
      }
      p { color: var(--muted); line-height: 1.5; }
      .hero-meta {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        margin-top: 16px;
      }
      .pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        border: 1px solid var(--line);
        border-radius: 999px;
        background: rgba(255,255,255,0.5);
        color: var(--muted);
        font-size: 0.92rem;
      }
      .grid {
        display: grid;
        grid-template-columns: 1.1fr 0.9fr;
        gap: 18px;
        margin-top: 18px;
      }
      .import-grid {
        display: grid;
        grid-template-columns: 1fr 1fr auto;
        gap: 10px;
        margin-top: 14px;
      }
      .flow {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 12px;
        margin-top: 18px;
      }
      .flow-step {
        border: 1px solid var(--line);
        background: rgba(255, 250, 243, 0.9);
        border-radius: 18px;
        padding: 14px 16px;
      }
      .flow-step strong {
        display: block;
        margin-bottom: 6px;
        color: var(--accent-deep);
      }
      .flow-step span {
        color: var(--muted);
        font-size: 0.95rem;
        line-height: 1.45;
      }
      .top-grid {
        display: grid;
        grid-template-columns: 0.8fr 1.2fr;
        gap: 18px;
        margin-top: 18px;
      }
      .card {
        border: 1px solid var(--line);
        background: var(--panel);
        border-radius: 22px;
        padding: 20px;
        box-shadow: 0 10px 30px rgba(63, 43, 24, 0.06);
      }
      label {
        display: block;
        font-size: 0.9rem;
        color: var(--muted);
        margin-bottom: 8px;
      }
      textarea, input {
        width: 100%;
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 14px;
        font: inherit;
        background: #fffdf9;
        color: var(--ink);
      }
      textarea {
        min-height: 360px;
        resize: vertical;
        font-family: "SFMono-Regular", Consolas, monospace;
        font-size: 13px;
      }
      .actions {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        align-items: center;
        margin-top: 14px;
      }
      select {
        border: 1px solid var(--line);
        border-radius: 999px;
        padding: 10px 14px;
        background: #fffdf9;
        font: inherit;
      }
      button {
        border: 0;
        border-radius: 999px;
        padding: 12px 18px;
        font: inherit;
        cursor: pointer;
        background: var(--accent);
        color: white;
      }
      button.secondary {
        background: #ddd2c3;
        color: var(--ink);
      }
      button.ghost {
        background: transparent;
        border: 1px solid var(--line);
        color: var(--ink);
      }
      .status {
        min-height: 24px;
        color: var(--success);
        font-size: 0.95rem;
      }
      pre {
        margin: 0;
        white-space: pre-wrap;
        word-break: break-word;
        border: 1px solid var(--line);
        border-radius: 16px;
        background: #fffdf9;
        padding: 14px;
        min-height: 160px;
        font-family: "SFMono-Regular", Consolas, monospace;
        font-size: 13px;
      }
      .stack {
        display: grid;
        gap: 14px;
      }
      .mini-stack {
        display: grid;
        gap: 10px;
      }
      .status-grid {
        display: grid;
        gap: 10px;
      }
      .status-row {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        padding: 10px 0;
        border-bottom: 1px dashed var(--line);
      }
      .status-row:last-child {
        border-bottom: 0;
      }
      .metric {
        color: var(--muted);
      }
      .metric strong {
        display: block;
        color: var(--ink);
        font-size: 1rem;
      }
      .recent-meta {
        color: var(--muted);
        font-size: 0.92rem;
        margin-bottom: 10px;
      }
      .banner {
        margin-top: 16px;
        padding: 14px 16px;
        border-radius: 18px;
        border: 1px solid var(--line);
        background: linear-gradient(135deg, rgba(182,77,45,0.08), rgba(255,255,255,0.4));
      }
      .banner strong {
        color: var(--accent-deep);
      }
      .summary-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 10px;
      }
      .summary-box {
        border: 1px solid var(--line);
        border-radius: 16px;
        background: #fffdf9;
        padding: 12px;
      }
      .summary-box strong {
        display: block;
        font-size: 1.15rem;
        color: var(--ink);
      }
      .summary-box span {
        color: var(--muted);
        font-size: 0.9rem;
      }
      .log-list {
        display: grid;
        gap: 8px;
      }
      .log-item {
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 10px 12px;
        background: #fffdf9;
      }
      .log-time {
        color: var(--muted);
        font-size: 0.84rem;
      }
      .hint {
        color: var(--muted);
        font-size: 0.92rem;
        line-height: 1.45;
      }
      @media (max-width: 860px) {
        .flow,
        .top-grid,
        .grid { grid-template-columns: 1fr; }
        .summary-grid,
        .import-grid { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body>
    <div class="shell">
      <section class="hero">
        <h1>Cowork 本地评审工作台</h1>
        <p>围绕你的业务流，这个页面把一次 AI 评审拆成可观察的 4 个阶段：Codex 提问题、Claude 回复、二轮复核、人工确认。你可以先在本地把 JSON 契约和提示词链路跑顺，再接入真实 PR。</p>
        <div class="hero-meta">
          <div class="pill">本地优先</div>
          <div class="pill">Bridge 驱动 Claude</div>
          <div class="pill">结构化 JSON 输出</div>
        </div>
        <div class="banner">
          <strong>建议用法：</strong>先在这里验证问题格式、回复结构和最终报告，再把同样的格式迁到真实 PR 流程里。
        </div>
      </section>
      <section class="flow">
        <div class="flow-step">
          <strong>第 1 步：输入问题</strong>
          <span>粘贴或加载一条 Codex 风格 issue，确认字段完整。</span>
        </div>
        <div class="flow-step">
          <strong>第 2 步：运行 Claude</strong>
          <span>通过本地 bridge 调 Claude，生成逐条回复。</span>
        </div>
        <div class="flow-step">
          <strong>第 3 步：查看总结</strong>
          <span>同时生成最终人类可读的决策报告。</span>
        </div>
        <div class="flow-step">
          <strong>第 4 步：准备接 PR</strong>
          <span>把跑顺的 JSON 契约和提示词迁回自动编排器。</span>
        </div>
      </section>
      <section class="top-grid">
        <div class="card">
          <h2>环境状态</h2>
          <div id="worker-status" class="status-grid"></div>
        </div>
        <div class="card">
          <h2>最近一次运行</h2>
          <div id="recent-meta" class="recent-meta">尚未运行。</div>
          <pre id="recent-output">尚未运行。</pre>
        </div>
      </section>
      <section class="top-grid">
        <div class="card">
          <h2>从真实 PR 导入</h2>
          <p class="hint">输入 GitHub 仓库和 PR 编号或完整链接，页面会尝试从真实评论里提取结构化 issue 并自动填充。</p>
          <div class="import-grid">
            <input id="repo-input" value="dikaerdun/Cowork" placeholder="owner/repo">
            <input id="pr-input" placeholder="PR 编号或链接">
            <button id="import-pr">导入 PR</button>
          </div>
        </div>
        <div class="card">
          <h2>本地模板</h2>
          <p class="hint">把当前输入保存为本地模板，后续调试不同 issue 结构时可以直接切换。</p>
          <div class="import-grid">
            <input id="template-name" placeholder="模板名称">
            <select id="saved-template-select"></select>
            <button id="save-template">保存模板</button>
          </div>
          <div class="actions">
            <button id="load-template" class="ghost">加载所选模板</button>
          </div>
        </div>
      </section>
      <section class="grid">
        <div class="card">
          <h2>问题输入</h2>
          <label for="issue-json">问题 JSON</label>
          <textarea id="issue-json">__DEFAULT_ISSUE__</textarea>
          <div class="actions">
            <select id="preset-select">
              <option value="default">默认 Codex 问题</option>
              <option value="reply-example">Claude 回复示例</option>
              <option value="final-report-example">最终报告示例</option>
            </select>
            <button id="apply-preset" class="ghost">加载模板</button>
            <button id="run-demo">开始演练</button>
            <button id="reset" class="secondary">重置示例</button>
          </div>
        </div>
        <div class="stack">
          <div class="card">
            <h2>Claude 回复</h2>
            <label>回复结果</label>
            <pre id="reply-output">尚未运行。</pre>
          </div>
          <div class="card">
            <h2>最终报告</h2>
            <label>人工审批摘要</label>
            <pre id="report-output">尚未运行。</pre>
          </div>
          <div class="card">
            <h2>人工审批摘要视图</h2>
            <div id="human-summary" class="mini-stack">
              <div class="hint">运行后将在这里生成更适合人工审批的摘要视图。</div>
            </div>
          </div>
          <div class="card">
            <h2>运行状态</h2>
            <label>当前进度</label>
            <div id="status" class="status">就绪，可开始演练。</div>
          </div>
          <div class="card">
            <h2>运行日志与排障</h2>
            <div id="log-list" class="log-list"></div>
          </div>
        </div>
      </section>
    </div>
    <script>
      const issueBox = document.getElementById("issue-json");
      const replyBox = document.getElementById("reply-output");
      const reportBox = document.getElementById("report-output");
      const statusBox = document.getElementById("status");
      const workerStatusBox = document.getElementById("worker-status");
      const recentMetaBox = document.getElementById("recent-meta");
      const recentOutputBox = document.getElementById("recent-output");
      const presetSelect = document.getElementById("preset-select");
      const savedTemplateSelect = document.getElementById("saved-template-select");
      const humanSummaryBox = document.getElementById("human-summary");
      const logListBox = document.getElementById("log-list");
      const defaultIssue = issueBox.value;

      function renderHumanSummary(summary) {
        if (!summary) {
          humanSummaryBox.innerHTML = '<div class="hint">运行后将在这里生成更适合人工审批的摘要视图。</div>';
          return;
        }
        humanSummaryBox.innerHTML = `
          <div class="hint">${summary.headline}</div>
          <div class="summary-grid">
            <div class="summary-box"><strong>${summary.agreed}</strong><span>已接受</span></div>
            <div class="summary-box"><strong>${summary.partial}</strong><span>部分接受</span></div>
            <div class="summary-box"><strong>${summary.disputed}</strong><span>仍有分歧</span></div>
            <div class="summary-box"><strong>${summary.merge_recommendation}</strong><span>合并建议</span></div>
          </div>
          <pre>${JSON.stringify(summary.disputes, null, 2)}</pre>
        `;
      }

      function renderLogs(logs) {
        if (!logs.length) {
          logListBox.innerHTML = '<div class="hint">暂无日志。成功或失败都会记录到这里，方便你回看问题出在哪一步。</div>';
          return;
        }
        logListBox.innerHTML = logs.map(log => `
          <div class="log-item">
            <div class="log-time">${log.time} · ${log.kind}</div>
            <div>${log.message}</div>
          </div>
        `).join("");
      }

      async function loadStatus() {
        const response = await fetch("/api/status");
        const payload = await response.json();
        const status = payload.worker_status;
        const recent = payload.recent_run;
        const templates = payload.saved_templates;

        workerStatusBox.innerHTML = `
          <div class="status-row"><div class="metric"><strong>Claude CLI</strong>${status.claude_cli_found ? "已发现" : "未发现"}</div><div>${status.execution_mode}</div></div>
          <div class="status-row"><div class="metric"><strong>Bridge 地址</strong>${status.bridge_url_configured ? "已配置" : "未配置"}</div><div>${status.bridge_token_configured ? "已设置令牌" : "未设置令牌"}</div></div>
          <div class="status-row"><div class="metric"><strong>模型</strong>${status.claude_model || "默认模型"}</div><div>执行模式：${status.execution_mode}</div></div>
        `;

        recentMetaBox.textContent = recent.message;
        recentOutputBox.textContent = JSON.stringify(recent, null, 2);
        renderHumanSummary(recent.human_summary || null);
        renderLogs(payload.logs || []);

        const names = Object.keys(templates);
        savedTemplateSelect.innerHTML = names.length
          ? names.map(name => `<option value="${name}">${name}</option>`).join("")
          : '<option value="">暂无已保存模板</option>';
      }

      async function applyPreset() {
        const response = await fetch(`/api/presets/${presetSelect.value}`);
        const payload = await response.json();
        issueBox.value = JSON.stringify(payload, null, 2);
        statusBox.textContent = `已加载模板：${presetSelect.options[presetSelect.selectedIndex].text}`;
      }

      document.getElementById("reset").addEventListener("click", () => {
        issueBox.value = defaultIssue;
        statusBox.textContent = "已重置为默认问题示例。";
      });

      document.getElementById("apply-preset").addEventListener("click", applyPreset);

      document.getElementById("save-template").addEventListener("click", async () => {
        const name = document.getElementById("template-name").value.trim();
        if (!name) {
          statusBox.textContent = "请先输入模板名称。";
          return;
        }
        const response = await fetch("/api/templates", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, issue: JSON.parse(issueBox.value) })
        });
        const payload = await response.json();
        if (!response.ok) {
          statusBox.textContent = payload.error || "保存模板失败。";
          return;
        }
        statusBox.textContent = `模板已保存：${name}`;
        await loadStatus();
      });

      document.getElementById("load-template").addEventListener("click", async () => {
        if (!savedTemplateSelect.value) {
          statusBox.textContent = "当前没有可加载的本地模板。";
          return;
        }
        const response = await fetch(`/api/templates/${encodeURIComponent(savedTemplateSelect.value)}`);
        const payload = await response.json();
        if (!response.ok) {
          statusBox.textContent = payload.error || "加载模板失败。";
          return;
        }
        issueBox.value = JSON.stringify(payload, null, 2);
        statusBox.textContent = `已加载本地模板：${savedTemplateSelect.value}`;
      });

      document.getElementById("import-pr").addEventListener("click", async () => {
        const repository = document.getElementById("repo-input").value.trim();
        const pr = document.getElementById("pr-input").value.trim();
        if (!repository || !pr) {
          statusBox.textContent = "请填写仓库名和 PR 编号或链接。";
          return;
        }
        statusBox.textContent = "正在读取真实 PR 评论...";
        const response = await fetch("/api/import-pr", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ repository, pr })
        });
        const payload = await response.json();
        if (!response.ok) {
          statusBox.textContent = payload.error || "导入 PR 失败。";
          return;
        }
        if (payload.issues.length === 0) {
          statusBox.textContent = `已读取 PR #${payload.pr_number}，但没有提取到结构化 issue。`;
          return;
        }
        issueBox.value = JSON.stringify(payload.issues[0], null, 2);
        statusBox.textContent = `已从 PR #${payload.pr_number} 提取 ${payload.issues.length} 条 issue，并自动填充首条。`;
        await loadStatus();
      });

      document.getElementById("run-demo").addEventListener("click", async () => {
        statusBox.textContent = "正在通过本地 bridge 调用 Claude...";
        replyBox.textContent = "处理中...";
        reportBox.textContent = "处理中...";
        try {
          const response = await fetch("/api/run-demo", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ issue: JSON.parse(issueBox.value) })
          });
          const payload = await response.json();
          if (!response.ok) {
            throw new Error(payload.error || "Request failed");
          }
          replyBox.textContent = JSON.stringify(payload.reply, null, 2);
          reportBox.textContent = JSON.stringify(payload.report, null, 2);
          statusBox.textContent = "演练完成，可以继续调整问题格式或提示词。";
          renderHumanSummary(payload.human_summary || null);
          await loadStatus();
        } catch (error) {
          replyBox.textContent = "发生错误";
          reportBox.textContent = "发生错误";
          statusBox.textContent = error.message;
        }
      });

      loadStatus();
    </script>
  </body>
</html>
"""


class LocalUIHandler(BaseHTTPRequestHandler):
    """提供本地 HTML 工作台和演练 API。"""

    server_version = "CoworkLocalUI/0.1"

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/index.html"}:
            page = HTML_PAGE.replace(
                "__DEFAULT_ISSUE__", html.escape(_load_default_issue())
            )
            body = page.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/health":
            self._json_response(HTTPStatus.OK, {"status": "ok"})
            return

        if self.path == "/api/status":
            self._json_response(
                HTTPStatus.OK,
                {
                    "worker_status": _worker_status(),
                    "recent_run": RECENT_RUN,
                    "saved_templates": _saved_templates(),
                    "logs": RUN_LOGS,
                },
            )
            return

        if self.path.startswith("/api/templates/"):
            template_name = self.path.rsplit("/", 1)[-1]
            templates = _saved_templates()
            template = templates.get(template_name)
            if template is None:
                self._json_response(HTTPStatus.NOT_FOUND, {"error": "template_not_found"})
                return
            self._json_response(HTTPStatus.OK, template)
            return

        if self.path.startswith("/api/presets/"):
            preset_name = self.path.rsplit("/", 1)[-1]
            preset = _all_templates().get(preset_name)
            if preset is None:
                self._json_response(HTTPStatus.NOT_FOUND, {"error": "preset_not_found"})
                return
            self._json_response(HTTPStatus.OK, preset)
            return

        self._json_response(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/templates":
            self._handle_save_template()
            return

        if self.path == "/api/import-pr":
            self._handle_import_pr()
            return

        if self.path != "/api/run-demo":
            self._json_response(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            issue = payload["issue"]
            if not isinstance(issue, dict):
                raise ValueError("issue must be an object")
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        try:
            with running_bridge_server() as bridge_url, temporary_env(
                CLAUDE_EXECUTION_MODE="bridge",
                CLAUDE_BRIDGE_URL=bridge_url,
            ):
                _append_log("运行", "开始调用 Claude 回复与最终报告链路。")
                reply = ask_claude_to_reply(42, [issue])
                report = ask_claude_for_final_report(42, [])
            human_summary = _human_summary(report)
            RECENT_RUN.update(
                {
                    "status": "success",
                    "message": "上一次运行已成功完成。",
                    "reply": reply,
                    "report": report,
                    "human_summary": human_summary,
                    "source": "manual",
                }
            )
            _append_log("成功", "本次演练已完成，已生成 Claude 回复和人工审批摘要。")
        except Exception as exc:  # noqa: BLE001
            RECENT_RUN.update(
                {
                    "status": "error",
                    "message": str(exc),
                    "reply": None,
                    "report": None,
                    "human_summary": None,
                    "source": "manual",
                }
            )
            _append_log("错误", f"运行失败：{exc}")
            self._json_response(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
            return

        self._json_response(
            HTTPStatus.OK,
            {"reply": reply, "report": report, "human_summary": human_summary},
        )

    def _handle_save_template(self) -> None:
        """保存本地模板。"""

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            name = str(payload["name"]).strip()
            issue = payload["issue"]
            if not name:
                raise ValueError("模板名称不能为空。")
            if not isinstance(issue, dict):
                raise ValueError("模板内容必须是对象。")
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        templates = _saved_templates()
        templates[name] = issue
        _save_templates(templates)
        _append_log("模板", f"已保存本地模板：{name}")
        self._json_response(HTTPStatus.OK, {"ok": True, "name": name})

    def _handle_import_pr(self) -> None:
        """从真实 PR 评论导入 issue。"""

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            repository = str(payload["repository"]).strip()
            pr_ref = str(payload["pr"]).strip()
            if not repository or not pr_ref:
                raise ValueError("仓库名和 PR 编号都不能为空。")
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        try:
            result = _import_pr_issues(repository, pr_ref)
            issue_count = len(result["issues"])
            _append_log(
                "导入",
                f"已读取 {repository} PR #{result['pr_number']}，提取到 {issue_count} 条结构化 issue。",
            )
        except Exception as exc:  # noqa: BLE001
            _append_log("错误", f"导入 PR 失败：{exc}")
            self._json_response(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
            return

        self._json_response(HTTPStatus.OK, result)

    def _json_response(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """Silence default access logging."""

        return None


def main() -> int:
    """启动本地 Web 工作台。"""

    host = os.environ.get("COWORK_UI_HOST", "127.0.0.1")
    port = int(os.environ.get("COWORK_UI_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), LocalUIHandler)
    print(f"Cowork 本地评审工作台已启动：http://{host}:{port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
