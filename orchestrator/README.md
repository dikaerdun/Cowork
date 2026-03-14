# Orchestrator v1

This directory contains the first implementation of the AI review orchestrator.

Design goals:

- Keep GitHub as the source of truth for merge gating.
- Keep Claude and Codex isolated behind a simple controller.
- Use PR comments and labels as initial state storage.
- Keep data contracts stable before adding infrastructure.

Suggested first integrations:

1. `trigger_codex_review(pr_number)`
2. `collect_codex_issues(pr_number)`
3. `ask_claude_to_reply(pr_number, issues)`
4. `ask_claude_for_final_report(pr_number, codex_round2)`

Do not let Claude and Codex talk directly to each other. Route all turns through the orchestrator.
