# Herdr PR Loop

Reusable Herdr skill + `uv` tool for local task loops and optional PR review loops.

It creates Herdr tabs for independent agents:

- `tester`
- `coder`
- `reviewer`
- `child-coder-<pr>` when `CHILD_PRS` is set
- `child-reviewer-<pr>` when `CHILD_PRS` is set

The default is local-only: no fetch, pull, push, or GitHub dependency.

## Install

From GitHub:

```bash
bunx skills add sarmientoF/herdr-pr-loop --skill herdr-pr-loop --agent codex -g -y
```

Local checkout:

```bash
bunx skills add . --skill herdr-pr-loop --agent codex -g -y
```

Direct install without `bunx`:

```bash
uv run --script skills/herdr-pr-loop/scripts/herdr-pr-loop.py install --target codex-user
```

Prereqs: `herdr`, `uv`, and your agent CLI, default `claude`.

## Per-Project Setup

In any project repo:

```bash
TOOL="$HOME/.agents/skills/herdr-pr-loop/scripts/herdr-pr-loop.py"
uv run --script "$TOOL" init
uv run --script "$TOOL" doctor
uv run --script "$TOOL" launch
```

From this checkout, use `TOOL="$PWD/skills/herdr-pr-loop/scripts/herdr-pr-loop.py"`.

`init` creates:

- `.herdr-loop.env`: project config
- `.herdr-loop/review.md`: reviewer state and issue list
- `.herdr-loop/feedback.md`: tester/child-reviewer input queue
- `.herdr-loop/feedback.lock.d`: mkdir lock used while appending/draining feedback
- `.herdr-loop/loop-run-log.md`: human-readable run log
- `.herdr-loop/loop-run-log.jsonl`: machine-readable run log
- `.herdr-loop/loop-budget.md`: budget and attempt caps
- `.herdr-loop/denylist.md`: paths requiring human approval
- `.herdr-loop/state.json`: Herdr workspace/tab/pane state

For two projects, run `init` in each repo. Each project gets its own `.herdr-loop.env` and `.herdr-loop/` state.

## Manage

```bash
TOOL="$HOME/.agents/skills/herdr-pr-loop/scripts/herdr-pr-loop.py"
uv run --script "$TOOL" doctor
uv run --script "$TOOL" status
uv run --script "$TOOL" stop "pause reason"
uv run --script "$TOOL" start
uv run --script "$TOOL" close
```

`stop` writes `.herdr-loop/PAUSE`. Agents check that file each loop and stop at the next cycle.
`close` closes the Herdr workspace recorded in `.herdr-loop/state.json`.
`launch --replace` closes a recorded live workspace before launching again.

## Config

Config lookup order:

1. `--config /path/to/file`
2. `HERD_CONF=/path/to/file`
3. `./.herdr-loop.env`
4. `./herd.env`
5. bundled defaults

Key settings:

- `PROJECT_REPO`: repo each agent starts in
- `REVIEW_DIR`: state directory, default `$PROJECT_REPO/.herdr-loop`
- `SYNC_MODE`: `local` or `remote`
- `ALLOW_REMOTE`: must be `true` for remote mode
- `ALLOW_DESTRUCTIVE`: default `false`
- `MAX_ATTEMPTS`: cap before `NEEDS_REVIEW`
- `MAX_SUBAGENTS_PER_RUN`: reviewer fan-out cap
- `TOKEN_BUDGET_DAILY`: daily token budget note for agents
- `CLEAN_CHECK_COMMAND`, `REVIEW_COMMAND`, `FULL_REVIEW_COMMAND`: role commands
- `AGENT_BIN` / `AGENT_ARGS`: default `claude --permission-mode auto`
- `GUIDANCE_DIR`: optional custom review guidance; defaults to bundled guidance

## Remote PR Mode

Remote mode is explicit:

```env
SYNC_MODE=remote
ALLOW_REMOTE=true
PARENT_PR=100
PR_NUMBERS=100 101 102
CHILD_PRS=101 102
PARENT_BRANCH=feat/example
```

Use `examples/remote-pr-loop.env` as the shape for a parent PR plus child PRs.

## Loop Pattern

This follows the practical loop-engineering shape:

- durable state outside chat
- maker/checker split
- run log and budget
- pause file as kill switch
- denylist and human gates
- local report/assist first; remote automation only after opt-in
