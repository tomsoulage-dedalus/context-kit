#!/usr/bin/env python3
"""Check that agent context files (CONTEXT.md, ARCHITECTURE.md, AGENTS.md) are still accurate.

Checks:
  - files and symbols quoted between backticks still exist in the repository;
  - relative Markdown links resolve;
  - each CONTEXT.md has a provenance line and flags commits made on its module since then;
  - each CONTEXT.md stays within the line budget and is linked from an index;
  - with --changed-since, modules changed without their CONTEXT.md being updated.

Only the Python standard library and git are required.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from functools import lru_cache
from pathlib import PurePosixPath

CONTEXT_NAME = "CONTEXT.md"
INDEX_NAMES = ("ARCHITECTURE.md", "AGENTS.md")
PROVENANCE_RE = re.compile(r"Verified at commit ([0-9a-f]{7,40}) on (\d{4}-\d{2}-\d{2})")
BACKTICK_RE = re.compile(r"`([^`\n]+)`")
LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
IDENT_RE = re.compile(r"^[A-Za-z_$][\w$]*$")
CALL_RE = re.compile(r"^([A-Za-z_$][\w$.]*)\s*\(.*\)$")
FILE_NAME_RE = re.compile(
    r"^[\w.*-]+\.(ts|tsx|js|jsx|mjs|cjs|java|kt|py|go|cs|rb|php|md|adoc|json|html|scss|css|xml|"
    r"ya?ml|sql|properties|sh|gradle|toml)$")
STOP_WORDS = {
    "true", "false", "null", "undefined", "none", "any", "void", "string", "number", "boolean",
    "this", "new", "int", "long", "var", "let", "const", "object", "self", "yes", "no",
}
MIME_RE = re.compile(r"^(application|text|image|audio|video|multipart|font)/[\w.+-]+$")
METHOD_FILE_NAMES = {CONTEXT_NAME, *INDEX_NAMES, "CLAUDE.md"}
NON_CODE_EXCLUDES = [":(exclude,glob)**/*.md", ":(exclude,glob)**/*.adoc"]


@dataclass
class Finding:
    level: str
    file: str
    message: str


def git(root: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", root, *args], capture_output=True, text=True, check=check
    )


class Repo:
    def __init__(self, root: str):
        self.root = root
        out = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").stdout
        self.files = sorted({f for f in out.split("\0") if f and os.path.exists(os.path.join(root, f))})
        self.file_set = set(self.files)
        self.dirs = {str(p) for f in self.files for p in PurePosixPath(f).parents if str(p) != "."}

    def path_exists(self, rel: str) -> bool:
        rel = rel.strip("/")
        return rel in self.file_set or rel in self.dirs

    @lru_cache(maxsize=None)
    def path_ref_exists(self, ref: str, module_dir: str) -> bool:
        ref = ref.strip().rstrip("/")
        if ref.startswith("./"):
            ref = ref[2:]
        if not ref:
            return True
        candidates = [ref, f"{module_dir}/{ref}" if module_dir else ref]
        if any(self.path_exists(c) for c in candidates):
            return True
        if any(ch in ref for ch in "*?["):
            pattern = ref if "/" in ref else f"*{ref}"
            return any(fnmatch.fnmatch(f, pattern) or fnmatch.fnmatch(f, f"*/{ref}") for f in self.files)
        suffix = "/" + ref
        return any(f.endswith(suffix) for f in self.files) or any(d.endswith(suffix) for d in self.dirs)

    @lru_cache(maxsize=None)
    def text_exists(self, needle: str, scope: str, word: bool) -> bool:
        args = ["grep", "-q", "-I", "-F", "--untracked"]
        if word:
            args.append("-w")
        args += ["-e", needle, "--", scope or "."] + NON_CODE_EXCLUDES
        return git(self.root, *args, check=False).returncode == 0

    def symbol_exists(self, symbol: str, module_dir: str) -> bool:
        return self.text_exists(symbol, module_dir, True) or self.text_exists(symbol, "", True)


def parent_dir(rel: str) -> str:
    parent = str(PurePosixPath(rel).parent)
    return "" if parent == "." else parent


def strip_fenced_blocks(text: str) -> str:
    out, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            out.append("")
            continue
        out.append("" if fenced else line)
    return "\n".join(out)


def classify(token: str):
    """Return (kind, value) with kind in {path, alias, symbol, None}."""
    t = token.strip()
    if not t or t[0] in "'\"" or any(ch in t for ch in "<>{}") or "->" in t:
        return None, None
    call = CALL_RE.match(t)
    if call:
        t = call.group(1)
    elif " " in t:
        return None, None
    t = re.sub(r"(\[\])+$", "", t)
    if t.startswith("@") and "/" in t:
        return "alias", re.sub(r"/\*+$", "", t)
    if t in METHOD_FILE_NAMES or "://" in t or t.startswith("/") or MIME_RE.match(t):
        return None, None
    if "/" in t or FILE_NAME_RE.match(t):
        return "path", t
    parts = t.split(".")
    if all(IDENT_RE.match(p) for p in parts):
        parts = [p for p in parts if len(p) >= 3 and p.lower() not in STOP_WORDS]
        if parts:
            return "symbol", parts
    return None, None


def check_references(repo: Repo, rel: str, text: str, module_dir: str, findings: list[Finding]) -> None:
    body = strip_fenced_blocks(text)
    seen = set()
    for raw in BACKTICK_RE.findall(body):
        kind, value = classify(raw)
        if kind is None or (kind, str(value)) in seen:
            continue
        seen.add((kind, str(value)))
        if kind == "path" and not repo.path_ref_exists(value, module_dir):
            findings.append(Finding("error", rel, f"path not found: `{value}`"))
        elif kind == "alias" and not repo.text_exists(value, "", False):
            findings.append(Finding("error", rel, f"import alias not found in code: `{value}`"))
        elif kind == "symbol":
            for part in value:
                if not repo.symbol_exists(part, module_dir):
                    findings.append(Finding("error", rel, f"symbol not found in code: `{part}`"))
    file_dir = str(PurePosixPath(rel).parent)
    for target in LINK_RE.findall(body):
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue
        path = target.split("#", 1)[0]
        resolved = os.path.normpath(os.path.join(file_dir, path)).replace(os.sep, "/")
        if path and not repo.path_exists(resolved):
            findings.append(Finding("error", rel, f"broken link: {target}"))


def check_provenance(repo: Repo, rel: str, text: str, module_dir: str, stale_after: int,
                     findings: list[Finding]) -> None:
    match = PROVENANCE_RE.search(text)
    if not match:
        findings.append(Finding("warning", rel, "missing provenance line 'Verified at commit <sha> on <date>.'"))
        return
    sha = match.group(1)
    # A commit that touches the CONTEXT.md counts as a verification: code and card may change together.
    last_touch = git(repo.root, "log", "-1", "--format=%H", "--", rel, check=False).stdout.strip()
    anchor = last_touch or sha
    if not last_touch and git(repo.root, "cat-file", "-e", f"{sha}^{{commit}}", check=False).returncode != 0:
        findings.append(Finding("warning", rel, f"provenance commit {sha} not found in history"))
        return
    res = git(repo.root, "rev-list", "--count", f"{anchor}..HEAD", "--", module_dir or ".",
              f":(exclude){rel}", check=False)
    count = int(res.stdout.strip() or 0)
    if count >= stale_after:
        findings.append(Finding(
            "warning", rel,
            f"{count} commit(s) touched the module since the card was last verified: review it and refresh "
            f"the provenance line"))


def check_changed_modules(repo: Repo, contexts: list[str], ref: str, findings: list[Finding]) -> None:
    base = git(repo.root, "merge-base", ref, "HEAD", check=False)
    if base.returncode != 0:
        findings.append(Finding("error", "-", f"cannot find merge base with {ref}: {base.stderr.strip()}"))
        return
    res = git(repo.root, "diff", "--name-only", base.stdout.strip(), check=False)
    if res.returncode != 0:
        findings.append(Finding("error", "-", f"cannot diff against {ref}: {res.stderr.strip()}"))
        return
    untracked = git(repo.root, "ls-files", "--others", "--exclude-standard").stdout.splitlines()
    changed = set(res.stdout.splitlines()) | set(untracked)
    for ctx in contexts:
        module_dir = parent_dir(ctx)
        prefix = module_dir + "/" if module_dir else ""
        touched = [f for f in changed if f.startswith(prefix) and f != ctx and not f.endswith(".md")
                   and not re.search(r"\.(spec|test)\.\w+$|Test\.\w+$", f)]
        if touched and ctx not in changed:
            findings.append(Finding(
                "warning", ctx,
                f"{len(touched)} file(s) of the module changed since {ref} but CONTEXT.md did not "
                f"(e.g. {sorted(touched)[0]}); update it if the public API, flows or invariants changed"))


def run(args: argparse.Namespace) -> list[Finding]:
    root = git(args.root, "rev-parse", "--show-toplevel").stdout.strip()
    repo = Repo(root)
    contexts = [f for f in repo.files if PurePosixPath(f).name == CONTEXT_NAME]
    indexes = [f for f in repo.files if PurePosixPath(f).name in INDEX_NAMES]
    if args.path:
        scope = [p.strip("/") for p in args.path]
        keep = lambda f: any(f == s or f.startswith(s + "/") for s in scope)
        contexts, indexes = [f for f in contexts if keep(f)], [f for f in indexes if keep(f)]
    findings: list[Finding] = []
    index_text = {}
    for rel in indexes:
        with open(os.path.join(root, rel), encoding="utf-8") as fh:
            index_text[rel] = fh.read()
        check_references(repo, rel, index_text[rel], parent_dir(rel), findings)
    for rel in contexts:
        with open(os.path.join(root, rel), encoding="utf-8") as fh:
            text = fh.read()
        module_dir = parent_dir(rel)
        lines = len(text.splitlines())
        if lines > args.max_lines:
            findings.append(Finding("warning", rel, f"{lines} lines, budget is {args.max_lines}"))
        check_provenance(repo, rel, text, module_dir, args.stale_after, findings)
        check_references(repo, rel, text, module_dir, findings)
        linked = any(
            os.path.normpath(os.path.join(parent_dir(idx), t.split("#")[0])).replace(os.sep, "/") == rel
            for idx, itext in index_text.items() for t in LINK_RE.findall(itext))
        if not linked:
            findings.append(Finding("warning", rel, "not linked from any ARCHITECTURE.md or AGENTS.md"))
    if args.changed_since:
        check_changed_modules(repo, contexts, args.changed_since, findings)
    if not contexts and not indexes:
        findings.append(Finding("warning", "-", "no CONTEXT.md, ARCHITECTURE.md or AGENTS.md found"))
    return findings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", nargs="*", help="limit the check to these paths (relative to the repository root)")
    parser.add_argument("--root", default=".", help="any directory inside the repository (default: .)")
    parser.add_argument("--changed-since", metavar="REF", help="report modules changed since REF without CONTEXT.md update")
    parser.add_argument("--max-lines", type=int, default=80, help="line budget of a CONTEXT.md (default: 80)")
    parser.add_argument("--stale-after", type=int, default=1,
                        help="warn when this many commits touched a module since its provenance commit (default: 1)")
    parser.add_argument("--strict", action="store_true", help="exit with 1 on warnings too")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        findings = run(args)
    except subprocess.CalledProcessError as exc:
        print(f"git failed: {exc.stderr.strip()}", file=sys.stderr)
        return 2
    errors = sum(f.level == "error" for f in findings)
    warnings = sum(f.level == "warning" for f in findings)
    if args.format == "json":
        print(json.dumps({"errors": errors, "warnings": warnings, "findings": [asdict(f) for f in findings]}, indent=2))
    else:
        for f in sorted(findings, key=lambda f: (f.file, f.level)):
            print(f"{f.level.upper():7} {f.file}: {f.message}")
        print(f"\n{errors} error(s), {warnings} warning(s)")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
