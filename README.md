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
- `PR_NUMBERS`, `PARENT_PR`, `CHILD_PRS`, `PARENT_BRANCH`

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
