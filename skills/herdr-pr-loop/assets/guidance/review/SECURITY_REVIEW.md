# Security Review

Look for exploitable behavior, data leaks, auth bypasses, and unsafe defaults.

Check:
- authn/authz missing or checked after side effects
- tenant/workspace boundary leaks
- path traversal, shell injection, SQL injection
- secret/token logging
- untrusted input passed to external tools
- unsafe file writes/deletes
- missing rate limits on expensive or sensitive paths

Output:

```text
OPEN: <short title>
Evidence: <file:line or command output>
Impact: <what attacker can do>
Fix: <smallest safe change>
```

Do not report theoretical issues without a plausible path.
