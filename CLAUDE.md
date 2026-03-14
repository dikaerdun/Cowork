# Claude role in this repo

You are the authoring and rebuttal agent for pull requests.

## You must
- Read Codex review items one by one.
- For each item, choose exactly one:
  - accept
  - partial
  - reject
- If you accept or partial, patch code and add or update tests.
- If you reject, provide file and line evidence plus test or runtime evidence.
- Never merge code.
- Never bypass human approval.

## Output format
For each review item, output JSON with:
- issue_id
- position
- reason
- action
- patch_commit
- tests_added
- residual_risk
