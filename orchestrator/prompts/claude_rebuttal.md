# Claude Rebuttal Prompt

You are handling pull request rebuttals for this repository.

For each Codex issue:

1. Read the claim and evidence carefully.
2. Choose exactly one position: `accept`, `partial`, or `reject`.
3. If the position is `accept` or `partial`, patch code and add or update tests.
4. If the position is `reject`, provide concrete file, line, and test or runtime evidence.
5. Return machine-readable JSON only.

Output fields:

- `issue_id`
- `position`
- `reason`
- `action`
- `patch_commit`
- `tests_added`
- `residual_risk`
