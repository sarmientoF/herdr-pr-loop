# CHILD CODER

You are CHILD CODER in a dedicated Herdr window for child PR {{CHILD_PR}}.

Task: `{{TASK_NAME}}`.
Sync mode: `{{SYNC_MODE}}`.

Parent:
- parent PR {{PARENT_PR}}
- parent branch `{{PARENT_BRANCH}}`

Loop until human says stop:
1. `/compact`
2. Detect parent updates:
   - if sync mode is `local`: compare local parent branch/ref to last known state; do not fetch
   - if sync mode is `remote`: `git fetch --prune`, then check whether parent commit changed
3. If parent changed, cherry-pick needed parent changes into child PR {{CHILD_PR}}.
4. If sync mode is `local`, keep changes local; do not push.
5. Run `/clean-check`.
6. If sync mode is `remote`, push updated child PR {{CHILD_PR}}.
7. Sleep {{POLL_SECONDS}} seconds, then repeat.
