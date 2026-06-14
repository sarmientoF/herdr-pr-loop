# Reviewer Guidance

Review current code against the task and `review.md`.

Rules:
- Evidence first: cite file:line or command output.
- Do not reopen closed issues without showing current regression evidence.
- Deduplicate findings before writing `review.md`.
- Any finding you think should not be fixed becomes `NEEDS_REVIEW`, not CLOSED.
- Prefer small, independently fixable OPEN issues.

Issue statuses:
- `OPEN`: coder must fix.
- `CLOSED`: verified fixed against current code.
- `NEEDS_REVIEW`: human decision needed.

Each issue should include:
- status
- short title
- evidence
- expected behavior
- suggested fix
