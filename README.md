# Cowork

This repository hosts a GitHub-gated AI review workflow scaffold.

Current goals:

- keep human approval mandatory before merge
- let Codex review pull requests in structured issue items
- let Claude respond item by item and prepare final dispute reports
- add automation only after the manual review loop is stable

See [docs/ai-review-rollout.md](docs/ai-review-rollout.md) for the rollout plan.

## Local demo

Run the end-to-end local demo with:

```bash
bash scripts/run_local_demo.sh
```

This starts the local Claude bridge on an ephemeral port, sends a sample Codex issue
through the bridge-backed Claude worker, and prints the reply plus final report.
