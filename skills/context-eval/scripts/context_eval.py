#!/usr/bin/env python3
"""Replay historical tasks with and without agent context, then grade the results.

  context_eval.py run    [--config context-evals/config.json] [--task ID] [--variant NAME] [-n N]
  context_eval.py report  context-evals/results/<file>.jsonl

Each trial creates a git worktree at the task base_ref, applies a context variant (remove all context
files, then optionally copy them from the working tree or a git ref), commits that overlay, runs the
agent command, and grades the diff with deterministic checks. Results are appended as JSONL.

Task and config files may be JSON, or YAML when PyYAML is installed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

DEFAULT_CONTEXT_GLOBS = [
    "AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md",
    ".github/instructions/context.instructions.md", "docs/context/**",
    "ARCHITECTURE.md", "**/ARCHITECTURE.md", "CONTEXT.md", "**/CONTEXT.md",
]
PLACEHOLDER_RE = re.compile(r"\{(repo|prompt|prompt_file|task_id|metrics_file|model)\}")


def load(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yml", ".yaml"):
        try:
            import yaml  # type: ignore
        except ImportError:
            sys.exit(f"{path}: PyYAML is required for YAML files (pip install pyyaml) or use JSON")
        return yaml.safe_load(text)
    return json.loads(text)


def git(cwd, *args, check=True):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=check)


def match(path: str, globs) -> bool:
    return any(fnmatch.fnmatch(path, g) or (g.startswith("**/") and fnmatch.fnmatch(path, g[3:])) for g in globs)


def tracked(cwd) -> list[str]:
    return [f for f in git(cwd, "ls-files", "-z").stdout.split("\0") if f]


def apply_variant(root: Path, work: Path, variant: dict, globs) -> list[str]:
    for rel in tracked(work):
        if match(rel, globs):
            (work / rel).unlink()
    for rel in variant.get("remove_paths", []):
        target = work / rel
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    source = variant.get("context_source", "none")
    copied = []
    if source == "working-tree":
        files = [f for f in git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard").stdout.split("\0")
                 if f and match(f, globs) and (root / f).is_file()]
        for rel in files:
            (work / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / rel, work / rel)
            copied.append(rel)
    elif source != "none":
        for rel in [f for f in git(root, "ls-tree", "-r", "-z", "--name-only", source).stdout.split("\0") if f]:
            if match(rel, globs):
                (work / rel).parent.mkdir(parents=True, exist_ok=True)
                (work / rel).write_bytes(subprocess.run(
                    ["git", "-C", str(root), "show", f"{source}:{rel}"], capture_output=True, check=True).stdout)
                copied.append(rel)
    git(work, "add", "-A")
    git(work, "-c", "user.name=context-eval", "-c", "user.email=context-eval@localhost",
        "commit", "-q", "--allow-empty", "--no-verify", "-m", "context-eval: variant overlay")
    return copied, git(work, "rev-parse", "HEAD").stdout.strip()


def run_commands(work: Path, commands, timeout: int) -> list[dict]:
    results = []
    for cmd in commands or []:
        start = time.time()
        try:
            proc = subprocess.run(cmd["argv"], cwd=work / cmd.get("cwd", "."), capture_output=True, text=True,
                                  timeout=cmd.get("timeout", timeout))
            ok, tail = proc.returncode == 0, (proc.stdout + proc.stderr)[-2000:]
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            ok, tail = False, str(exc)
        results.append({"name": cmd.get("name", " ".join(cmd["argv"])), "passed": ok,
                        "seconds": round(time.time() - start, 1), "output_tail": tail})
    return results


def stage_all(work: Path) -> None:
    # The agent may have committed: move the index to the final tree, diffs are taken from the overlay.
    git(work, "add", "-A")


def added_lines(work: Path, base: str) -> dict[str, list[str]]:
    diff = git(work, "diff", "--cached", "-U0", base).stdout
    per_file, current = defaultdict(list), None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = None if line.endswith("/dev/null") else line[6:]
        elif line.startswith("+") and not line.startswith("+++") and current:
            per_file[current].append(line[1:])
    return per_file


def grade(work: Path, task: dict, timeout: int, base: str) -> dict:
    stage_all(work)
    changed = [f for f in git(work, "diff", "--cached", "--name-only", base).stdout.splitlines() if f]
    added = added_lines(work, base)
    checks = []

    def check(name, passed, detail=""):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    allowed = task.get("allowed_paths")
    if allowed:
        outside = [f for f in changed if not match(f, allowed)]
        check("changes stay in allowed_paths", not outside, ", ".join(outside))
    required = task.get("required_changed_paths", [])
    found = [g for g in required if any(match(f, [g]) for f in changed)]
    for g in required:
        check(f"changes {g}", g in found)
    if "max_changed_files" in task:
        check(f"at most {task['max_changed_files']} changed files", len(changed) <= task["max_changed_files"],
              str(len(changed)))
    for p in task.get("required_patterns", []):
        rx = re.compile(p["pattern"])
        check(p["name"], any(rx.search(l) for f, ls in added.items() if match(f, [p.get("glob", "**")]) for l in ls))
    for p in task.get("forbidden_patterns", []):
        rx = re.compile(p["pattern"])
        hits = [f for f, ls in added.items() if match(f, [p.get("glob", "**")]) and any(rx.search(l) for l in ls)]
        check(p["name"], not hits, ", ".join(hits))
    commands = run_commands(work, task.get("commands"), timeout)
    for c in commands:
        check(f"command: {c['name']}", c["passed"])
    passed = sum(c["passed"] for c in checks)
    return {
        "changed_files": changed,
        "localization_recall": round(len(found) / len(required), 3) if required else None,
        "checks": checks, "commands": commands,
        "score": round(passed / len(checks), 3) if checks else None,
        "success": all(c["passed"] for c in checks) if checks else None,
    }


def trial(root: Path, cfg: dict, task: dict, variant_name: str, rep: int, args) -> dict:
    variant = cfg["variants"][variant_name]
    globs = cfg.get("context_globs", DEFAULT_CONTEXT_GLOBS)
    tmp = Path(tempfile.mkdtemp(prefix=f"ctx-eval-{task['id']}-{variant_name}-"))
    work = tmp / "repo"
    git(root, "worktree", "add", "-q", "--detach", str(work), task["base_ref"])
    record = {"task": task["id"], "variant": variant_name, "repetition": rep, "base_ref": task["base_ref"],
              "model": args.model or cfg.get("model"), "started_at": dt.datetime.now().isoformat(timespec="seconds")}
    try:
        record["context_files"], overlay = apply_variant(root, work, variant, globs)
        prep = run_commands(work, task.get("prepare_commands"), args.timeout)
        record["prepare"] = [{k: c[k] for k in ("name", "passed")} for c in prep]
        prompt_file, metrics_file = tmp / "prompt.md", tmp / "metrics.json"
        prompt_file.write_text(task["prompt"], encoding="utf-8")
        values = {"repo": str(work), "prompt": task["prompt"], "prompt_file": str(prompt_file),
                  "task_id": task["id"], "metrics_file": str(metrics_file), "model": record["model"] or ""}
        argv = [PLACEHOLDER_RE.sub(lambda m: values[m.group(1)], part)
                for part in shlex.split(args.agent_command or cfg["agent_command"])]
        start = time.time()
        try:
            proc = subprocess.run(argv, cwd=work, capture_output=True, text=True, timeout=args.agent_timeout)
            record["agent_exit_code"], output = proc.returncode, proc.stdout + proc.stderr
        except subprocess.TimeoutExpired as exc:
            record["agent_exit_code"], output = "timeout", str(exc)
        record["agent_seconds"] = round(time.time() - start, 1)
        record["agent_output_tail"] = output[-4000:]
        if metrics_file.exists():
            record["metrics"] = json.loads(metrics_file.read_text() or "{}")
        record.update(grade(work, task, args.timeout, overlay))
        record["diff"] = git(work, "diff", "--cached", overlay).stdout[:200_000]
    finally:
        if args.keep:
            record["worktree"] = str(work)
        else:
            git(root, "worktree", "remove", "--force", str(work), check=False)
            shutil.rmtree(tmp, ignore_errors=True)
    return record


def cmd_run(args) -> int:
    root = Path(git(".", "rev-parse", "--show-toplevel").stdout.strip())
    cfg_path = root / args.config
    cfg = load(cfg_path)
    tasks = []
    for pattern in cfg.get("task_files", ["tasks/*.json", "tasks/*.yml", "tasks/*.yaml"]):
        for f in sorted(cfg_path.parent.glob(pattern)):
            tasks += load(f).get("tasks", [])
    if args.task:
        tasks = [t for t in tasks if t["id"] in args.task]
    variants = args.variant or list(cfg["variants"])
    if not tasks:
        sys.exit("no task selected")
    if not (args.agent_command or cfg.get("agent_command")):
        sys.exit("no agent command: set agent_command in the config or pass --agent-command")
    out = root / cfg.get("results_dir", "context-evals/results") / f"{dt.datetime.now():%Y%m%d-%H%M%S}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    reps = args.repetitions or cfg.get("repetitions", 1)
    with out.open("a", encoding="utf-8") as fh:
        for task in tasks:
            for rep in range(1, reps + 1):
                for variant in variants:
                    print(f"[{task['id']}] {variant} #{rep} ...", flush=True)
                    rec = trial(root, cfg, task, variant, rep, args)
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()
                    print(f"    success={rec.get('success')} score={rec.get('score')} "
                          f"recall={rec.get('localization_recall')} files={len(rec.get('changed_files', []))} "
                          f"agent={rec.get('agent_seconds')}s", flush=True)
    print(f"\nresults: {out}")
    return cmd_report(argparse.Namespace(results=[str(out)]))


def cmd_report(args) -> int:
    rows = defaultdict(list)
    for path in args.results:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                rows[(rec["task"], rec["variant"])].append(rec)

    def mean(values):
        values = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
        return f"{sum(values) / len(values):.2f}" if values else "-"

    header = ["task", "variant", "n", "success", "score", "recall", "files", "agent_s", "tokens", "tool_calls"]
    print("| " + " | ".join(header) + " |\n|" + "---|" * len(header))
    for (task, variant), recs in sorted(rows.items()):
        metrics = [r.get("metrics", {}) for r in recs]
        print("| " + " | ".join([
            task, variant, str(len(recs)),
            f"{sum(bool(r.get('success')) for r in recs)}/{len(recs)}",
            mean([r.get("score") for r in recs]), mean([r.get("localization_recall") for r in recs]),
            mean([len(r.get("changed_files", [])) for r in recs]), mean([r.get("agent_seconds") for r in recs]),
            mean([m.get("tokens") for m in metrics]), mean([m.get("tool_calls") for m in metrics]),
        ]) + " |")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run trials")
    run.add_argument("--config", default="context-evals/config.json", help="path relative to the repository root")
    run.add_argument("--task", action="append", help="task id (repeatable)")
    run.add_argument("--variant", action="append", help="variant name (repeatable)")
    run.add_argument("-n", "--repetitions", type=int)
    run.add_argument("--agent-command", help="overrides agent_command; placeholders: {repo} {prompt} "
                                             "{prompt_file} {task_id} {metrics_file} {model}")
    run.add_argument("--model", help="recorded in results and available as {model}")
    run.add_argument("--agent-timeout", type=int, default=1800)
    run.add_argument("--timeout", type=int, default=900, help="timeout of each prepare or grading command")
    run.add_argument("--keep", action="store_true", help="keep worktrees for inspection")
    run.set_defaults(func=cmd_run)
    report = sub.add_parser("report", help="summarize JSONL results as a Markdown table")
    report.add_argument("results", nargs="+")
    report.set_defaults(func=cmd_report)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
