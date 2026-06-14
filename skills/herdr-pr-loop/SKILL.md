---
name: herdr-pr-loop
description: Set up, initialize, and launch Herdr-managed multi-agent loops for local tasks or PR review, with tester, coder, reviewer, child-coder, and child-reviewer windows. Use when a user wants reusable Herdr orchestration, per-project .env setup, review/feedback file loops, durable loop state, role prompt generation, local-only agent teams, or optional GitHub PR sync.
---

# Herdr PR Loop

Create a reusable Herdr workspace where each role runs in its own tab and coordinates through `review.md`, `feedback.md`, run logs, and optional git state.

`SYNC_MODE=local` keeps all code changes local and avoids fetch/push. `SYNC_MODE=remote` uses GitHub PR branches.

## Use

1. Initialize a project:

```bash
TOOL="$HOME/.agents/skills/herdr-pr-loop/scripts/herdr-pr-loop.py"
uv run --script "$TOOL" init
```

2. Edit `.herdr-loop.env` if needed.
3. Render one prompt before launch if changing roles:

```bash
uv run --script "$TOOL" render tester
```

4. Smoke-check prompts:

```bash
uv run --script "$TOOL" check
```

5. Check local prerequisites:

```bash
uv run --script "$TOOL" doctor
```

6. Launch:

```bash
uv run --script "$TOOL" launch
```

Set `HERD_CONF=/path/to/herd.env` or pass `--config /path/to/herd.env` when config is not `./.herdr-loop.env`.

## Tool

Use `scripts/herdr-pr-loop.py`; it is a `uv run --script` tool using only Python stdlib.

Commands:

- `init [--config .herdr-loop.env] [--force]`: create config plus review, feedback, state, log, budget, and denylist files.
- `render ROLE [CHILD_PR]`: print rendered role prompt.
- `run-agent [--print] ROLE [CHILD_PR]`: print prompt or exec configured agent.
- `check`: validate script syntax and prompt rendering.
- `doctor`: validate config, repo path, required CLIs, and core prompt rendering.
- `launch`: create Herdr workspace/tabs and start agents.
- `status`: print config, state, review dir, and pause state as JSON.
- `stop [reason]`: write the pause file and mark state paused.
- `start`: remove the pause file.
- `install --target codex-user|codex-repo|claude-user|claude-repo|both-user [--force]`: copy this skill into an agent skill directory.

Roles: `tester`, `coder`, `reviewer`, `child-coder`, `child-reviewer`.

Config lookup order: `--config`, `HERD_CONF`, `./.herdr-loop.env`, `./herd.env`, legacy `./herd.conf.sh`, bundled defaults.

Use `PROJECT_REPO` for the target repo. Legacy `JAI_REPO` remains an alias.

## Design Rules

- Keep roles independent; use `reviewer` as coordinator through `review.md`.
- Treat `feedback.md` as single tester/child-reviewer input queue.
- Use the `FEEDBACK_LOCK_DIR` mkdir lock before appending or draining `feedback.md`.
- Keep durable state in `state.json`, `loop-run-log.md`, and `loop-run-log.jsonl`.
- Respect `loop-budget.md`, `denylist.md`, `PAUSE`, and attempt caps.
- Default to `SYNC_MODE=local`; require `ALLOW_REMOTE=true` before remote sync.
- Use bundled review guidance from `assets/guidance` by default.
- Prefer file/git coordination over hidden master state.
- Add a master/supervisor only after repeated missed handoffs, file conflicts, crash recovery needs, or global pause/resume requirements.

## Distribution

For Codex repo discovery, place this folder under `.agents/skills/herdr-pr-loop`. For Claude Code, place it under `.claude/skills/herdr-pr-loop`. This repo also includes `.codex-plugin/plugin.json` for plugin-style packaging.

Install with the bundled tool:

```bash
uv run --script skills/herdr-pr-loop/scripts/herdr-pr-loop.py install --target codex-user
```

Install from a published GitHub repo with the Agent Skills CLI:

```bash
bunx skills add sarmientoF/herdr-pr-loop --skill herdr-pr-loop --agent codex -g -y
```
