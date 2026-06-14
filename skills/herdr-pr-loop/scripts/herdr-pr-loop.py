#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import re
import shutil
import shlex
import subprocess
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
PROMPTS = SKILL_DIR / "assets" / "prompts"
EXAMPLE_CONFIG = SKILL_DIR / "assets" / "herd.env.example"
DEFAULT_CONFIG = ".herdr-loop.env"
CONFIG_CANDIDATES = (DEFAULT_CONFIG, "herd.env")

DEFAULTS = {
    "WORKSPACE_LABEL": "",
    "PROJECT_REPO": "$PWD",
    "GUIDANCE_DIR": "",
    "AGENT_BIN": "claude",
    "AGENT_ARGS": "--permission-mode auto",
    "POLL_SECONDS": "120",
    "SYNC_MODE": "local",
    "TASK_NAME": "",
    "PARENT_PR": "",
    "PR_NUMBERS": "",
    "CHILD_PRS": "",
    "PARENT_BRANCH": "",
    "REVIEW_DIR": "$PROJECT_REPO/.herdr-loop",
    "FEEDBACK_MD": "$REVIEW_DIR/feedback.md",
    "FEEDBACK_LOCK_MD": "$REVIEW_DIR/feedback.lock.md",
    "FEEDBACK_LOCK_DIR": "$REVIEW_DIR/feedback.lock.d",
    "REVIEW_MD": "$REVIEW_DIR/review.md",
    "RUN_LOG_MD": "$REVIEW_DIR/loop-run-log.md",
    "RUN_LOG_JSONL": "$REVIEW_DIR/loop-run-log.jsonl",
    "BUDGET_MD": "$REVIEW_DIR/loop-budget.md",
    "DENYLIST_MD": "$REVIEW_DIR/denylist.md",
    "STATE_JSON": "$REVIEW_DIR/state.json",
    "PAUSE_FILE": "$REVIEW_DIR/PAUSE",
    "MAX_ATTEMPTS": "3",
    "MAX_SUBAGENTS_PER_RUN": "6",
    "TOKEN_BUDGET_DAILY": "2000000",
    "AUTO_MERGE": "false",
    "ALLOW_REMOTE": "false",
    "ALLOW_DESTRUCTIVE": "false",
    "CLEAN_CHECK_COMMAND": "/clean-check",
    "REVIEW_COMMAND": "/review",
    "FULL_REVIEW_COMMAND": "/cr-full",
}


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def expand(value: str, cfg: dict[str, str], pwd: str | None = None) -> str:
    merged = {**os.environ, **cfg, "PWD": pwd or os.getcwd()}

    def repl(match: re.Match[str]) -> str:
        default_var, default, braced, plain = match.groups()
        if default_var:
            current = os.environ.get(default_var, "")
            return current if current else expand(strip_quotes(default), cfg, pwd)
        return merged.get(braced or plain, match.group(0))

    return re.sub(
        r"\$\{([A-Za-z_][A-Za-z0-9_]*):-(.*?)\}|\$\{([^}:]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)",
        repl,
        value,
    )


def slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-")
    return cleaned or "local-task"


def select_config(path: str | None) -> Path:
    explicit = path or os.environ.get("HERD_CONF")
    if explicit:
        cfg_path = Path(explicit).expanduser()
        if not cfg_path.exists():
            raise SystemExit(f"config not found: {cfg_path}")
        return cfg_path.resolve()
    for name in CONFIG_CANDIDATES:
        cfg_path = Path(name)
        if cfg_path.exists():
            return cfg_path.resolve()
    return EXAMPLE_CONFIG


def read_config(path: str | None) -> tuple[dict[str, str], Path | None]:
    cfg = dict(DEFAULTS)
    cfg_path = select_config(path)
    base_pwd = os.getcwd() if cfg_path == EXAMPLE_CONFIG else str(cfg_path.parent)

    for raw in cfg_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            cfg[key] = expand(strip_quotes(value), cfg, base_pwd)

    for key, value in list(cfg.items()):
        cfg[key] = expand(value, cfg, base_pwd)
    cfg["TASK_NAME"] = cfg.get("TASK_NAME") or slug(Path(cfg["PROJECT_REPO"]).resolve().name)
    cfg["WORKSPACE_LABEL"] = cfg.get("WORKSPACE_LABEL") or f"herdr-{slug(cfg['TASK_NAME'])}"
    cfg["GUIDANCE_DIR"] = cfg.get("GUIDANCE_DIR") or str(SKILL_DIR / "assets" / "guidance")
    if cfg["SYNC_MODE"] not in {"local", "remote"}:
        raise SystemExit("SYNC_MODE must be local or remote")
    if cfg["SYNC_MODE"] == "remote" and cfg.get("ALLOW_REMOTE", "").lower() != "true":
        raise SystemExit("remote sync requires ALLOW_REMOTE=true")
    return cfg, cfg_path if cfg_path.exists() else None


def validate_setup(cfg: dict[str, str], *, require_herdr: bool) -> list[str]:
    tools = ["uv", "git", cfg["AGENT_BIN"]]
    if require_herdr:
        tools.append("herdr")
    if cfg["SYNC_MODE"] == "remote":
        tools.append("gh")
    missing = [tool for tool in tools if not shutil_which(tool)]
    problems = []
    repo = Path(cfg["PROJECT_REPO"])
    if not repo.is_dir():
        problems.append(f"PROJECT_REPO not found: {repo}")
    else:
        proc = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"],
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0 or proc.stdout.strip() != "true":
            problems.append(f"PROJECT_REPO is not a git worktree: {repo}")
    if missing:
        problems.append("missing tools: " + ", ".join(missing))
    if cfg["SYNC_MODE"] == "remote":
        if not cfg.get("PR_NUMBERS"):
            problems.append("remote sync requires PR_NUMBERS")
        if not cfg.get("PARENT_BRANCH"):
            problems.append("remote sync requires PARENT_BRANCH")
    return problems


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_if_missing_or_empty(path: Path, text: str) -> None:
    if path.exists() and path.read_text().strip():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def init_loop_files(cfg: dict[str, str]) -> None:
    review_dir = Path(cfg["REVIEW_DIR"])
    review_dir.mkdir(parents=True, exist_ok=True)
    Path(cfg["FEEDBACK_MD"]).touch()
    write_if_missing_or_empty(
        Path(cfg["REVIEW_MD"]),
        f"""# Review State

## META
task: {cfg["TASK_NAME"]}
sync_mode: {cfg["SYNC_MODE"]}
last_head:
last_worktree:
max_attempts: {cfg["MAX_ATTEMPTS"]}
max_subagents_per_run: {cfg["MAX_SUBAGENTS_PER_RUN"]}
pause_file: {cfg["PAUSE_FILE"]}

## OPEN

## NEEDS_REVIEW

## CLOSED

## HUMAN_INBOX
""",
    )
    write_if_missing_or_empty(
        Path(cfg["RUN_LOG_MD"]),
        f"""# Loop Run Log

Append one concise entry per role run. Keep secrets and large logs out.

| time | role | event | items | outcome |
| --- | --- | --- | --- | --- |
""",
    )
    write_if_missing_or_empty(Path(cfg["RUN_LOG_JSONL"]), "")
    write_if_missing_or_empty(
        Path(cfg["BUDGET_MD"]),
        f"""# Loop Budget

- task: {cfg["TASK_NAME"]}
- max_tokens_per_day: {cfg["TOKEN_BUDGET_DAILY"]}
- max_subagents_per_run: {cfg["MAX_SUBAGENTS_PER_RUN"]}
- max_attempts_per_issue: {cfg["MAX_ATTEMPTS"]}
- auto_merge: {cfg["AUTO_MERGE"]}
- pause_file: {cfg["PAUSE_FILE"]}

Pause or escalate when the budget is exceeded, an issue hits the attempt cap, or a denylisted path must change.
""",
    )
    write_if_missing_or_empty(
        Path(cfg["DENYLIST_MD"]),
        """# Loop Denylist

Do not auto-edit these paths without human approval:

- `.env`
- `.env.*`
- `**/secrets/**`
- `**/credentials/**`
- `**/*_key*`
- `**/*_secret*`
- `.terraform/**`
- `k8s/production/**`
- `**/migrations/**`
- `auth/**`
- `payments/**`
- `billing/**`
""",
    )
    write_if_missing_or_empty(
        Path(cfg["STATE_JSON"]),
        json.dumps(
            {
                "task": cfg["TASK_NAME"],
                "sync_mode": cfg["SYNC_MODE"],
                "status": "initialized",
                "workspace_label": cfg["WORKSPACE_LABEL"],
                "workspace_id": None,
                "config": None,
                "project_repo": cfg["PROJECT_REPO"],
                "review_dir": cfg["REVIEW_DIR"],
                "roles": {},
                "updated_at": now_iso(),
            },
            indent=2,
        )
        + "\n",
    )


def append_run_log(cfg: dict[str, str], role: str, event: str, outcome: str) -> None:
    init_loop_files(cfg)
    stamp = now_iso()
    line = f"| {stamp} | {role} | {event} | - | {outcome} |\n"
    with Path(cfg["RUN_LOG_MD"]).open("a") as handle:
        handle.write(line)
    with Path(cfg["RUN_LOG_JSONL"]).open("a") as handle:
        handle.write(
            json.dumps(
                {
                    "time": stamp,
                    "role": role,
                    "event": event,
                    "items": [],
                    "outcome": outcome,
                },
                separators=(",", ":"),
            )
            + "\n"
        )


def load_state(cfg: dict[str, str], *, create: bool = True) -> dict:
    if create:
        init_loop_files(cfg)
    state_path = Path(cfg["STATE_JSON"])
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid state json: {state_path}: {exc}") from exc


def save_state(cfg: dict[str, str], state: dict) -> None:
    state["updated_at"] = now_iso()
    Path(cfg["STATE_JSON"]).write_text(json.dumps(state, indent=2) + "\n")


def record_role(
    cfg: dict[str, str],
    state: dict,
    role: str,
    tab_id: str,
    pane_id: str,
    command: str,
) -> None:
    state.setdefault("roles", {})[role] = {
        "tab_id": tab_id,
        "pane_id": pane_id,
        "command": command,
        "status": "started",
        "started_at": now_iso(),
    }
    save_state(cfg, state)


def ensure_not_paused(cfg: dict[str, str]) -> None:
    pause_file = Path(cfg["PAUSE_FILE"])
    if pause_file.exists():
        raise SystemExit(f"loop paused: remove {pause_file} to launch")


def render(role: str, child_pr: str, cfg: dict[str, str]) -> str:
    template = PROMPTS / f"{role}.md"
    if not template.exists():
        raise SystemExit(f"unknown role: {role}")
    if role in {"child-coder", "child-reviewer"} and not child_pr:
        raise SystemExit(f"{role} needs CHILD_PR")

    display = {
        "PARENT_PR": cfg.get("PARENT_PR") or "none",
        "PR_NUMBERS": cfg.get("PR_NUMBERS") or "none",
        "PARENT_BRANCH": cfg.get("PARENT_BRANCH") or "none",
    }
    values = {**cfg, **display, "CHILD_PR": child_pr}
    text = template.read_text()
    for key, value in values.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    leftovers = re.findall(r"\{\{[A-Z0-9_]+\}\}", text)
    if leftovers:
        raise SystemExit(f"unrendered placeholders: {', '.join(sorted(set(leftovers)))}")
    return text


def run_json(args: list[str]) -> dict:
    proc = subprocess.run(args, text=True, capture_output=True, check=True)
    return json.loads(proc.stdout)


def shutil_which(cmd: str) -> str | None:
    for part in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(part) / cmd
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def pane_cmd(cfg: dict[str, str], cfg_path: Path | None, role: str, child: str = "") -> str:
    env = f"HERD_CONF={shlex.quote(str(cfg_path))} " if cfg_path else ""
    tail = f" {shlex.quote(child)}" if child else ""
    return (
        f"cd {shlex.quote(cfg['PROJECT_REPO'])} && "
        f"{env}uv run --script {shlex.quote(str(Path(__file__).resolve()))} "
        f"run-agent {shlex.quote(role)}{tail}"
    )


def run_in_pane(pane: str, tab: str, name: str, command: str) -> None:
    subprocess.run(["herdr", "tab", "rename", tab, name], check=True, capture_output=True, text=True)
    subprocess.run(["herdr", "pane", "rename", pane, name], check=True, capture_output=True, text=True)
    subprocess.run(["herdr", "pane", "run", pane, command], check=True, capture_output=True, text=True)


def workspace_live(workspace_id: str | None) -> bool:
    if not workspace_id:
        return False
    proc = subprocess.run(
        ["herdr", "workspace", "get", workspace_id],
        text=True,
        capture_output=True,
    )
    return proc.returncode == 0


def close_workspace(workspace_id: str) -> None:
    subprocess.run(["herdr", "workspace", "close", workspace_id], check=True, capture_output=True, text=True)


def cmd_launch(args: argparse.Namespace) -> None:
    cfg, cfg_path = read_config(args.config)
    problems = validate_setup(cfg, require_herdr=True)
    if problems:
        raise SystemExit("\n".join(problems))
    ensure_not_paused(cfg)
    init_loop_files(cfg)
    state = load_state(cfg, create=False)
    old_ws = state.get("workspace_id")
    if old_ws and workspace_live(old_ws):
        if not args.replace:
            raise SystemExit(f"workspace already running: {old_ws} (use launch --replace)")
        close_workspace(old_ws)
    state.update(
        {
            "task": cfg["TASK_NAME"],
            "sync_mode": cfg["SYNC_MODE"],
            "status": "launching",
            "workspace_label": cfg["WORKSPACE_LABEL"],
            "config": str(cfg_path) if cfg_path else None,
            "project_repo": cfg["PROJECT_REPO"],
            "review_dir": cfg["REVIEW_DIR"],
            "roles": {},
            "launched_at": now_iso(),
        }
    )
    save_state(cfg, state)

    ws = None
    try:
        ws_json = run_json([
            "herdr",
            "workspace",
            "create",
            "--cwd",
            cfg["PROJECT_REPO"],
            "--label",
            cfg["WORKSPACE_LABEL"],
            "--focus",
        ])
        result = ws_json["result"]
        ws = result["workspace"]["workspace_id"]
        root_tab = result["tab"]["tab_id"]
        root_pane = result["root_pane"]["pane_id"]
        state["workspace_id"] = ws
        save_state(cfg, state)

        command = pane_cmd(cfg, cfg_path, "tester")
        run_in_pane(root_pane, root_tab, "tester", command)
        record_role(cfg, state, "tester", root_tab, root_pane, command)
        append_run_log(cfg, "tester", "spawned", "started")

        for role in ("coder", "reviewer"):
            tab_json = run_json([
                "herdr",
                "tab",
                "create",
                "--workspace",
                ws,
                "--cwd",
                cfg["PROJECT_REPO"],
                "--label",
                role,
                "--no-focus",
            ])
            pane_id = tab_json["result"]["root_pane"]["pane_id"]
            tab_id = tab_json["result"]["tab"]["tab_id"]
            command = pane_cmd(cfg, cfg_path, role)
            run_in_pane(pane_id, tab_id, role, command)
            record_role(cfg, state, role, tab_id, pane_id, command)
            append_run_log(cfg, role, "spawned", "started")

        for child in cfg.get("CHILD_PRS", "").split():
            for role in ("child-coder", "child-reviewer"):
                name = f"{role}-{child}"
                tab_json = run_json([
                    "herdr",
                    "tab",
                    "create",
                    "--workspace",
                    ws,
                    "--cwd",
                    cfg["PROJECT_REPO"],
                    "--label",
                    name,
                    "--no-focus",
                ])
                pane_id = tab_json["result"]["root_pane"]["pane_id"]
                tab_id = tab_json["result"]["tab"]["tab_id"]
                command = pane_cmd(cfg, cfg_path, role, child)
                run_in_pane(pane_id, tab_id, name, command)
                record_role(cfg, state, name, tab_id, pane_id, command)
                append_run_log(cfg, name, "spawned", "started")

        subprocess.run(["herdr", "workspace", "focus", ws], check=True, capture_output=True, text=True)
        state["status"] = "running"
        save_state(cfg, state)
        print(f"Herdr workspace: {cfg['WORKSPACE_LABEL']} ({ws})")
    except Exception as exc:
        state["status"] = "failed"
        state["failure"] = str(exc)
        if ws:
            try:
                close_workspace(ws)
            finally:
                state["workspace_id"] = None
                state["roles"] = {}
        save_state(cfg, state)
        raise


def cmd_run_agent(args: argparse.Namespace) -> None:
    cfg, _ = read_config(args.config)
    ensure_not_paused(cfg)
    prompt = render(args.role, args.child_pr or "", cfg)
    if args.print:
        print(prompt)
        return
    append_run_log(cfg, args.role, "agent-start", "exec")
    os.chdir(cfg["PROJECT_REPO"])
    argv = [cfg["AGENT_BIN"], *shlex.split(cfg.get("AGENT_ARGS", "")), prompt]
    os.execvp(argv[0], argv)


def cmd_render(args: argparse.Namespace) -> None:
    cfg, _ = read_config(args.config)
    print(render(args.role, args.child_pr or "", cfg))


def cmd_check(args: argparse.Namespace) -> None:
    cfg, _ = read_config(args.config)
    assert "READY TO TEST" in render("tester", "", cfg)
    assert "NEEDS_REVIEW:coder" in render("coder", "", cfg)
    assert "child PR 101" in render("child-coder", "101", cfg)
    assert "CODE_REVIEW.md" in render("child-reviewer", "101", cfg)
    assert "loop-run-log.md" in render("reviewer", "", cfg)
    assert "denylist.md" in render("coder", "", cfg)
    print("ok")


def cmd_doctor(args: argparse.Namespace) -> None:
    cfg, cfg_path = read_config(args.config)
    problems = validate_setup(cfg, require_herdr=True)
    for role in ("tester", "coder", "reviewer"):
        render(role, "", cfg)
    if problems:
        raise SystemExit("\n".join(problems))
    print(f"config: {cfg_path}")
    print(f"project_repo: {cfg['PROJECT_REPO']}")
    print(f"review_dir: {cfg['REVIEW_DIR']}")
    print("doctor: ok")


def cmd_init(args: argparse.Namespace) -> None:
    target = Path(args.config or DEFAULT_CONFIG).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or args.force:
        target.write_text(EXAMPLE_CONFIG.read_text())
    cfg, _ = read_config(str(target))
    init_loop_files(cfg)
    print(f"config: {target}")
    print(f"review_dir: {cfg['REVIEW_DIR']}")
    tool = Path(__file__).resolve()
    print(f"next: uv run --script {tool} doctor")
    print(f"then: uv run --script {tool} launch")


def cmd_status(args: argparse.Namespace) -> None:
    cfg, cfg_path = read_config(args.config)
    state = load_state(cfg, create=False)
    shown_state = dict(state)
    live = workspace_live(state.get("workspace_id"))
    if state.get("workspace_id") and not live and state.get("status") == "running":
        shown_state["status"] = "stale"
    paused = Path(cfg["PAUSE_FILE"]).exists()
    summary = {
        "config": str(cfg_path) if cfg_path else None,
        "project_repo": cfg["PROJECT_REPO"],
        "review_dir": cfg["REVIEW_DIR"],
        "state_json": cfg["STATE_JSON"],
        "run_log": cfg["RUN_LOG_MD"],
        "paused": paused,
        "workspace_live": live,
        "state": shown_state,
    }
    print(json.dumps(summary, indent=2))


def cmd_stop(args: argparse.Namespace) -> None:
    cfg, _ = read_config(args.config)
    init_loop_files(cfg)
    pause_file = Path(cfg["PAUSE_FILE"])
    pause_file.write_text((args.reason or "stopped by user") + "\n")
    state = load_state(cfg)
    state["status"] = "paused"
    state["pause_reason"] = args.reason or "stopped by user"
    save_state(cfg, state)
    append_run_log(cfg, "all", "stop", state["pause_reason"])
    print(f"paused: {pause_file}")


def cmd_start(args: argparse.Namespace) -> None:
    cfg, _ = read_config(args.config)
    pause_file = Path(cfg["PAUSE_FILE"])
    if pause_file.exists():
        pause_file.unlink()
    init_loop_files(cfg)
    state = load_state(cfg)
    if state.get("status") == "paused":
        state["status"] = "initialized"
        state.pop("pause_reason", None)
        save_state(cfg, state)
    append_run_log(cfg, "all", "resume", "pause-file-removed")
    print("resumed")


def cmd_close(args: argparse.Namespace) -> None:
    cfg, _ = read_config(args.config)
    state = load_state(cfg, create=False)
    ws = state.get("workspace_id")
    if not ws:
        raise SystemExit("no workspace_id in state")
    if workspace_live(ws):
        close_workspace(ws)
    state["status"] = "closed"
    state["workspace_id"] = None
    state["roles"] = {}
    save_state(cfg, state)
    append_run_log(cfg, "all", "close", ws)
    print(f"closed: {ws}")


def copy_skill(dst: Path, force: bool) -> None:
    target = dst.expanduser() / "herdr-pr-loop"
    if target.exists():
        if not force:
            raise SystemExit(f"exists: {target} (use --force)")
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILL_DIR, target)
    print(target)


def cmd_install(args: argparse.Namespace) -> None:
    targets = {
        "codex-user": Path("~/.agents/skills"),
        "codex-repo": Path(".agents/skills"),
        "claude-user": Path("~/.claude/skills"),
        "claude-repo": Path(".claude/skills"),
    }
    if args.target == "both-user":
        for name in ("codex-user", "claude-user"):
            copy_skill(targets[name], args.force)
        return
    copy_skill(targets[args.target], args.force)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", dest="global_config", help="Path to herd config file")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", help="Path to herd config file")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("render", parents=[common])
    p.add_argument("role")
    p.add_argument("child_pr", nargs="?")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("run-agent", parents=[common])
    p.add_argument("--print", action="store_true")
    p.add_argument("role")
    p.add_argument("child_pr", nargs="?")
    p.set_defaults(func=cmd_run_agent)

    p = sub.add_parser("check", parents=[common])
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("doctor", parents=[common])
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("init")
    p.add_argument("--config", help=f"Config file to create, default {DEFAULT_CONFIG}")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("launch", parents=[common])
    p.add_argument("--replace", action="store_true")
    p.set_defaults(func=cmd_launch)

    p = sub.add_parser("status", parents=[common])
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("stop", parents=[common])
    p.add_argument("reason", nargs="?")
    p.set_defaults(func=cmd_stop)

    p = sub.add_parser("start", parents=[common])
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("close", parents=[common])
    p.set_defaults(func=cmd_close)

    p = sub.add_parser("install")
    p.add_argument(
        "--target",
        choices=["codex-user", "codex-repo", "claude-user", "claude-repo", "both-user"],
        default="codex-user",
    )
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_install)

    args = parser.parse_args()
    if not hasattr(args, "config") or args.config is None:
        args.config = args.global_config
    args.func(args)


if __name__ == "__main__":
    main()
