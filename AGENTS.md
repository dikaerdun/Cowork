# Repo Instructions for Codex

## Review guidelines
- Focus on correctness, security, reliability, missing tests, and regression risk.
- Do not nitpick style unless it can cause bugs.
- Review by issue item, not by long narrative.
- Each issue must include:
  - issue_id
  - severity
  - file
  - lines
  - claim
  - evidence
  - suggested_fix
  - confidence

## Done criteria
- CI passes.
- No unresolved high severity issue.
- Human approval is still required before merge.

## Boundaries
- Never approve bypassing branch protection.
- Never treat AI feedback as a replacement for human approval.
- Prefer actionable findings with concrete evidence over speculative concerns.
