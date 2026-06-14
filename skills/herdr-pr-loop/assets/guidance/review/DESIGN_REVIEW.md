# Design Review

Look for design mismatches that will make the change brittle or inconsistent.

Check:
- violates existing domain model or ownership boundary
- duplicates existing helper/API
- adds abstraction with one implementation
- spreads one behavior across unrelated layers
- changes public contract without migration path
- couples tests to implementation details
- ignores established repo conventions

Output:

```text
OPEN: <short title>
Evidence: <file:line>
Problem: <design mismatch>
Fix: <simpler aligned approach>
```

For anti-pattern checks, focus on what can be removed or simplified.
