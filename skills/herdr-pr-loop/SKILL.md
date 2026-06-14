---
name: herdr-pr-loop
description: Set up and launch Herdr-managed multi-agent PR review loops with tester, coder, reviewer, child-coder, and child-reviewer windows. Use when a user wants reusable Herdr orchestration, PR feedback/review file loops, role prompt generation, or a portable skill/tool setup for agent teams.
---

# Herdr PR Loop

Create a reusable Herdr workspace where each role runs in its own tab and coordinates through git plus `review.md` / `feedback.md`.

## Use

1. Create or edit a config from `assets/herd.env.example`.
2. Render one prompt before launch if changing roles:

```bash
uv run --script skills/herdr-pr-loop/scripts/herdr-pr-loop.py render tester
```

3. Smoke-check:

```bash
uv run --script skills/herdr-pr-loop/scripts/herdr-pr-loop.py check
```

4. Launch:

```bash
uv run --script skills/herdr-pr-loop/scripts/herdr-pr-loop.py launch
```

Set `HERD_CONF=/path/to/herd.env` or pass `--config /path/to/herd.env` before the command when config is not `./herd.conf.sh`.

## Tool

Use `scripts/herdr-pr-loop.py`; it is a `uv run --script` tool using only Python stdlib.

Commands:

- `render ROLE [CHILD_PR]`: print rendered role prompt.
- `run-agent [--print] ROLE [CHILD_PR]`: print prompt or exec configured agent.
- `check`: validate script syntax and prompt rendering.
- `launch`: create Herdr workspace/tabs and start agents.
- `install --target codex-user|codex-repo|claude-user|claude-repo|both-user [--force]`: copy this skill into an agent skill directory.

Roles: `tester`, `coder`, `reviewer`, `child-coder`, `child-reviewer`.

## Design Rules

- Keep roles independent; use `reviewer` as coordinator through `review.md`.
- Treat `feedback.md` as single tester/child-reviewer input queue.
- Prefer file/git coordination over hidden master state.
- Add a master/supervisor only after repeated missed handoffs, file conflicts, crash recovery needs, or global pause/resume requirements.

## Distribution

For Codex repo discovery, place this folder under `.agents/skills/herdr-pr-loop`. For Claude Code, place it under `.claude/skills/herdr-pr-loop`. For wider Codex distribution, package this skill in a plugin only after the workflow stabilizes.

Install with the bundled tool:

```bash
uv run --script skills/herdr-pr-loop/scripts/herdr-pr-loop.py install --target codex-user
```

Install from a published GitHub repo with the Agent Skills CLI:

```bash
bunx skills add sarmientoF/herdr-pr-loop --skill herdr-pr-loop --agent codex -g -y
```
