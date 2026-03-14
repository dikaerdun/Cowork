# AI Review Rollout

This repository is being prepared for a gated PR review workflow:

1. GitHub enforces branch protection and human approval.
2. Codex performs PR review and emits structured issue items.
3. Claude replies to each issue, patches code when needed, and prepares a final dispute report.
4. Human reviewers make the final merge decision.

Current implementation note:

- The orchestrator can call Claude either through a local `claude` CLI or an HTTP bridge configured with `CLAUDE_BRIDGE_URL`.

## Phase 1: GitHub guardrails

Configure these in the GitHub repository settings before enabling any automation:

- Protect the default branch (`main` or `master`).
- Enable required pull request reviews.
- Enable required status checks.
- Enable review from Code Owners.
- Create these labels:
  - `ai-review-pending`
  - `ai-disputed`
  - `await-human`
  - `ready-to-merge`

Why this matters:

- AI automation can fail or misclassify issues.
- Branch protection ensures no workflow can bypass human approval.

## Phase 2: Repository-scoped agent rules

The repository keeps long-lived instructions in:

- `AGENTS.md` for Codex review behavior.
- `CLAUDE.md` for Claude authoring and rebuttal behavior.
- `.github/CODEOWNERS` for mandatory human reviewers by area.

## Phase 3: Manual three-round validation

Run the loop manually before writing an orchestrator:

1. Open a small PR.
2. Trigger `@codex review`.
3. Collect review items into a structured issue list.
4. Hand the issue list to Claude.
5. Let Claude patch code, add tests, and respond item by item.
6. Trigger `@codex review` again for recheck only.
7. Ask Claude for a final dispute report for the human reviewer.

## Phase 4: Orchestrator v1

Recommended initial layout:

```text
.github/workflows/ci.yml
.github/workflows/ai-orchestrator.yml
AGENTS.md
CLAUDE.md
.github/CODEOWNERS

orchestrator/
  app.py
  github_client.py
  codex_parser.py
  claude_worker.py
  state.py
  prompts/
    claude_rebuttal.md
    claude_final_report.md
```

Start with a simple state machine:

```text
PR_OPEN
-> CODEX_INITIAL_REVIEWED
-> CLAUDE_REPLIED
-> CODEX_RECHECKED
-> CLAUDE_ESCALATED
-> HUMAN_APPROVED / HUMAN_REQUEST_CHANGES
-> MERGED
```

Recommended v1 functions:

```python
def trigger_codex_review(pr_number): ...
def collect_codex_issues(pr_number): ...
def ask_claude_to_reply(pr_number, issues): ...
def ask_claude_for_final_report(pr_number, codex_round2): ...
```

## Data contracts

Codex issue payload:

```json
{
  "issue_id": "R-004",
  "severity": "high",
  "file": "src/auth/session.ts",
  "lines": "81-97",
  "claim": "refresh endpoint can bypass session check",
  "evidence": [
    "missing middleware",
    "no negative test"
  ],
  "suggested_fix": "wrap route and add regression test",
  "confidence": 0.86
}
```

Claude response payload:

```json
{
  "issue_id": "R-004",
  "position": "accept",
  "reason": "Codex claim is valid",
  "action": "patched",
  "patch_commit": "abc1234",
  "tests_added": ["auth_refresh_rejects_without_session"],
  "residual_risk": "low"
}
```

Claude final report payload:

```json
{
  "pr": 128,
  "agreed": 5,
  "partial": 1,
  "disputed": 1,
  "disputes": [
    {
      "issue_id": "R-004",
      "topic": "auth boundary enforcement",
      "codex_position": "still risky",
      "claude_position": "enforced upstream",
      "human_decision_needed": "whether to duplicate enforcement in app layer"
    }
  ],
  "merge_recommendation": "blocked"
}
```

## Next execution order

1. Create the GitHub repository if it does not exist yet.
2. Push this scaffold.
3. Configure branch protection and labels in GitHub.
4. Verify `@claude` and `@codex review` manually on a tiny PR.
5. Add the orchestrator only after the manual loop is stable.

## Claude execution modes

The current worker supports two runtime modes:

1. Local CLI mode
   - Install `claude` on the machine or runner.
   - Optionally set `CLAUDE_CLI_PATH` and `CLAUDE_MODEL`.
2. HTTP bridge mode
   - Set `CLAUDE_BRIDGE_URL`.
   - Optionally set `CLAUDE_BRIDGE_TOKEN` and `CLAUDE_MODEL`.
   - The bridge should accept `POST` JSON with:
     - `task`
     - `prompt`
     - `schema`
     - `model`
   - The bridge should return JSON matching the requested schema.

Bridge mode is the better fit for GitHub-hosted runners because they do not guarantee a preinstalled `claude` executable.

This repository also includes a minimal bridge server:

- Run `python -m orchestrator.bridge_server`
- Default address: `http://127.0.0.1:8787/claude`
- Optional health check: `GET /health`
- Optional bearer auth via `CLAUDE_BRIDGE_TOKEN`
