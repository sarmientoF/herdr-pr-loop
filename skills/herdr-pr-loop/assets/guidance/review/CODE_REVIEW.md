# Code Review

Look for correctness defects that can fail in production.

Check:
- broken control flow
- wrong data shape or type assumptions
- missing error handling at trust boundaries
- stale state or cache bugs
- concurrency/race risks
- migration/backfill gaps
- tests that do not exercise changed behavior

Output only actionable findings:

```text
OPEN: <short title>
Evidence: <file:line or command output>
Problem: <why this fails>
Fix: <smallest safe change>
```

Skip style-only feedback unless it hides a bug.
