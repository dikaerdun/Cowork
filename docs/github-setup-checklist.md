# GitHub Setup Checklist

Use this checklist after pushing the repository to GitHub.

## Repository settings

- Set the default branch to `main`.
- Enable branch protection on `main`.
- Require a pull request before merging.
- Require approvals.
- Require review from Code Owners.
- Require status checks before merging.

Recommended first required status check:

- `Validate orchestrator scaffold`

## Labels

Create these labels manually:

- `ai-review-pending`
- `ai-disputed`
- `await-human`
- `ready-to-merge`

## AI integration decisions

Before turning on the orchestrator logic, choose:

- How Codex will be triggered:
  - GitHub-native `@codex review`
  - automatic GitHub review integration
  - a custom bot or API bridge
- How Claude will be triggered:
  - GitHub app with `@claude`
  - GitHub Action
  - SDK-backed worker

## Secrets and credentials

Do not add secrets until the trigger paths are chosen.

Likely future requirements:

- GitHub token or app installation credentials
- Claude credentials if using SDK or Action
- Any OpenAI credentials if using API-backed Codex flows
- OpenClaw gateway credentials only after the GitHub-only loop is stable

If using the current Claude worker on GitHub-hosted runners, add:

- `CLAUDE_BRIDGE_URL`
- `CLAUDE_BRIDGE_TOKEN` if your bridge requires auth
- `CLAUDE_MODEL` if you want to pin a model

## Safe rollout order

1. Push scaffold repository.
2. Enable branch protection and labels.
3. Make `CI` a required status check.
4. Open a tiny test PR.
5. Manually trigger Codex and Claude.
6. Only then replace scaffold workflow steps with real orchestrator calls.
