#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
from __future__ import annotations

import argparse
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

DEFAULTS = {
    "WORKSPACE_LABEL": "pr-review-loop",
    "JAI_REPO": "$PWD",
    "AGENTS_GIT_URL": "https://github.com/ashleysmart-japanai/agents.git",
    "AGENTS_REPO": "$HOME/agents",
    "SKIP_AGENTS_SYNC": "0",
    "AGENT_BIN": "claude",
    "AGENT_ARGS": "--permission-mode auto",
    "POLL_SECONDS": "120",
    "SYNC_MODE": "local",
    "TASK_NAME": "local-task",
    "PARENT_PR": "",
    "PR_NUMBERS": "",
    "CHILD_PRS": "",
    "PARENT_BRANCH": "",
    "REVIEW_DIR": "$PWD/.herdr-pr-loop",
    "FEEDBACK_MD": "$REVIEW_DIR/feedback.md",
    "FEEDBACK_LOCK_MD": "$REVIEW_DIR/feedback.lock.md",
    "REVIEW_MD": "$REVIEW_DIR/review.md",
}


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def expand(value: str, cfg: dict[str, str]) -> str:
    merged = {**os.environ, **cfg, "PWD": os.getcwd()}

    def repl(match: re.Match[str]) -> str:
        default_var, default, braced, plain = match.groups()
        if default_var:
            current = os.environ.get(default_var, "")
            return current if current else expand(strip_quotes(default), cfg)
        return merged.get(braced or plain, match.group(0))

    return re.sub(
        r"\$\{([A-Za-z_][A-Za-z0-9_]*):-(.*?)\}|\$\{([^}:]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)",
        repl,
        value,
    )


def read_config(path: str | None) -> tuple[dict[str, str], Path | None]:
    cfg = dict(DEFAULTS)
    cfg_path = Path(path or os.environ.get("HERD_CONF") or "herd.conf.sh")
    if not cfg_path.exists():
        cfg_path = EXAMPLE_CONFIG

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
            cfg[key] = expand(strip_quotes(value), cfg)

    for key, value in list(cfg.items()):
        cfg[key] = expand(value, cfg)
    return cfg, cfg_path if cfg_path.exists() else None


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


def require_tools(*tools: str) -> None:
    missing = [tool for tool in tools if not shutil_which(tool)]
    if missing:
        raise SystemExit("missing: " + ", ".join(missing))


def shutil_which(cmd: str) -> str | None:
    for part in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(part) / cmd
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def sync_agents(cfg: dict[str, str]) -> None:
    if cfg.get("SKIP_AGENTS_SYNC") == "1" or not cfg.get("AGENTS_GIT_URL"):
        return
    repo = Path(cfg["AGENTS_REPO"]).expanduser()
    if (repo / ".git").exists():
        subprocess.run(["git", "-C", str(repo), "pull", "--ff-only"], check=True)
    else:
        repo.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", cfg["AGENTS_GIT_URL"], str(repo)], check=True)


def pane_cmd(cfg: dict[str, str], cfg_path: Path | None, role: str, child: str = "") -> str:
    env = f"HERD_CONF={shlex.quote(str(cfg_path))} " if cfg_path else ""
    tail = f" {shlex.quote(child)}" if child else ""
    return (
        f"cd {shlex.quote(cfg['JAI_REPO'])} && "
        f"{env}uv run --script {shlex.quote(str(Path(__file__).resolve()))} "
        f"run-agent {shlex.quote(role)}{tail}"
    )


def run_in_pane(pane: str, tab: str, name: str, command: str) -> None:
    subprocess.run(["herdr", "tab", "rename", tab, name], check=True)
    subprocess.run(["herdr", "pane", "rename", pane, name], check=True)
    subprocess.run(["herdr", "pane", "run", pane, command], check=True)


def cmd_launch(args: argparse.Namespace) -> None:
    cfg, cfg_path = read_config(args.config)
    require_tools("herdr", "git", "uv", cfg["AGENT_BIN"])
    sync_agents(cfg)

    Path(cfg["FEEDBACK_MD"]).parent.mkdir(parents=True, exist_ok=True)
    Path(cfg["FEEDBACK_MD"]).touch()
    Path(cfg["REVIEW_MD"]).touch()

    ws_json = run_json([
        "herdr",
        "workspace",
        "create",
        "--cwd",
        cfg["JAI_REPO"],
        "--label",
        cfg["WORKSPACE_LABEL"],
        "--focus",
    ])
    result = ws_json["result"]
    ws = result["workspace"]["workspace_id"]
    root_tab = result["tab"]["tab_id"]
    root_pane = result["root_pane"]["pane_id"]

    run_in_pane(root_pane, root_tab, "tester", pane_cmd(cfg, cfg_path, "tester"))

    for role in ("coder", "reviewer"):
        tab_json = run_json([
            "herdr",
            "tab",
            "create",
            "--workspace",
            ws,
            "--cwd",
            cfg["JAI_REPO"],
            "--label",
            role,
            "--no-focus",
        ])
        run_in_pane(
            tab_json["result"]["root_pane"]["pane_id"],
            tab_json["result"]["tab"]["tab_id"],
            role,
            pane_cmd(cfg, cfg_path, role),
        )

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
                cfg["JAI_REPO"],
                "--label",
                name,
                "--no-focus",
            ])
            run_in_pane(
                tab_json["result"]["root_pane"]["pane_id"],
                tab_json["result"]["tab"]["tab_id"],
                name,
                pane_cmd(cfg, cfg_path, role, child),
            )

    subprocess.run(["herdr", "workspace", "focus", ws], check=True)
    print(f"Herdr workspace: {cfg['WORKSPACE_LABEL']} ({ws})")


def cmd_run_agent(args: argparse.Namespace) -> None:
    cfg, _ = read_config(args.config)
    prompt = render(args.role, args.child_pr or "", cfg)
    if args.print:
        print(prompt)
        return
    os.chdir(cfg["JAI_REPO"])
    argv = [cfg["AGENT_BIN"], *shlex.split(cfg.get("AGENT_ARGS", "")), prompt]
    os.execvp(argv[0], argv)


def cmd_render(args: argparse.Namespace) -> None:
    cfg, _ = read_config(args.config)
    print(render(args.role, args.child_pr or "", cfg))


def cmd_check(args: argparse.Namespace) -> None:
    cfg, _ = read_config(args.config)
    assert "READY TO TEST" in render("tester", "", cfg)
    assert "NEEDS_REVIEW:coder" in render("coder", "", cfg)
    assert "child PR 13045" in render("child-coder", "13045", cfg)
    assert "CODE_REVIEW.md" in render("child-reviewer", "13045", cfg)
    print("ok")


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
    parser.add_argument("--config", help="Path to herd config file")
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

    p = sub.add_parser("launch", parents=[common])
    p.set_defaults(func=cmd_launch)

    p = sub.add_parser("install")
    p.add_argument(
        "--target",
        choices=["codex-user", "codex-repo", "claude-user", "claude-repo", "both-user"],
        default="codex-user",
    )
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_install)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
