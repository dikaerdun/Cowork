# Claude Final Report Prompt

You are preparing the final human-facing dispute report for a pull request.

Use the second Codex pass plus Claude's prior responses to produce:

- a count of agreed items
- a count of partial items
- a count of disputed items
- a `disputes` array for items that still need human judgment
- a final `merge_recommendation`

Rules:

- Do not claim the PR can merge without human approval.
- Keep the report concise and machine-readable.
- Output JSON only.
