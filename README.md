# Herdr PR Loop

Reusable Herdr PR-loop skill + `uv` tool.

Canonical package:

```text
skills/herdr-pr-loop/
```

## Configure

Copy/edit config:

```bash
cp skills/herdr-pr-loop/assets/herd.env.example herd.conf.sh
```

- `JAI_REPO`: repo each agent starts in
- `REVIEW_DIR`: directory containing `review.md` and `feedback.md`
- `AGENT_BIN` / `AGENT_ARGS`: default `claude --permission-mode auto`
- `TASK_NAME`: local task label
- `PR_NUMBERS`, `PARENT_PR`, `CHILD_PRS`, `PARENT_BRANCH`: optional, mainly remote PR mode
- `SYNC_MODE`: `local` avoids fetch/push; `remote` uses GitHub PR branches
- `GUIDANCE_DIR`: optional custom review guidance; defaults to bundled guidance in this skill

## Check

```bash
./bin/check
```

Same command without wrapper:

```bash
uv run --script skills/herdr-pr-loop/scripts/herdr-pr-loop.py check
```

## Launch

```bash
./bin/launch-herd
```

This creates one Herdr workspace with tabs:

- `tester`
- `coder`
- `reviewer`
- `child-coder-<pr>`
- `child-reviewer-<pr>`

## Local Vs Remote

Default is local:

```bash
SYNC_MODE=local
```

Local mode:

- no `git push`
- no required GitHub PR updates
- agents test/review current working tree and local commits
- `review.md` / `feedback.md` stay local

Remote mode:

```bash
SYNC_MODE=remote
```

Remote mode fetches/pulls/pushes PR branches and watches GitHub commits.

## Install As Skill

From GitHub after publish:

```bash
bunx skills add sarmientoF/herdr-pr-loop --skill herdr-pr-loop --agent codex -g -y
```

Local checkout:

```bash
bunx skills add . --skill herdr-pr-loop --agent codex -g -y
```

Codex repo skill:

```bash
uv run --script skills/herdr-pr-loop/scripts/herdr-pr-loop.py install --target codex-repo
```

Codex user skill:

```bash
uv run --script skills/herdr-pr-loop/scripts/herdr-pr-loop.py install --target codex-user
```

Claude project skill:

```bash
uv run --script skills/herdr-pr-loop/scripts/herdr-pr-loop.py install --target claude-repo
```

Restart agent if skill does not appear.

## GitHub Repo

Suggested repo name:

```text
herdr-pr-loop
```

Create/push after review:

```bash
git init
git add .
git commit -m "Initial herdr PR loop skill"
gh repo create herdr-pr-loop --public --source=. --remote=origin --push
```

After publish:

```bash
bunx skills add sarmientoF/herdr-pr-loop --skill herdr-pr-loop --agent codex -g -y
bunx skills use sarmientoF/herdr-pr-loop@herdr-pr-loop
```
