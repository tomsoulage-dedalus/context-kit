#!/usr/bin/env bash
# Install context-kit into an existing repository.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: install.sh [options] <target-repository>

Options:
  --skills-dir DIR   where skills are installed, relative to the target (default: .github/skills)
                     e.g. .claude/skills for Claude Code, .opencode/skills for opencode
  --with-evals       also install context-evals/ (task format and config for context-eval)
  --force            overwrite project files that already exist (skills are always updated)
  --dry-run          print what would be done
  -h, --help         show this help

Project files (AGENTS.md, pointers, governance...) are never overwritten unless --force is given:
existing ones are reported and merged later by the context-init skill.
EOF
}

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR=".github/skills"
WITH_EVALS=0
FORCE=0
DRY_RUN=0
TARGET=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skills-dir) SKILLS_DIR="${2:?--skills-dir needs a value}"; shift 2 ;;
    --with-evals) WITH_EVALS=1; shift ;;
    --force) FORCE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
    *) TARGET="$1"; shift ;;
  esac
done

[[ -n "$TARGET" ]] || { usage >&2; exit 2; }
[[ -d "$TARGET" ]] || { echo "not a directory: $TARGET" >&2; exit 2; }
TARGET="$(cd "$TARGET" && pwd)"
git -C "$TARGET" rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "not a git repository: $TARGET" >&2; exit 2; }
PROJECT_NAME="$(basename "$(git -C "$TARGET" rev-parse --show-toplevel)")"

created=(); skipped=(); updated=()

run() { if [[ $DRY_RUN -eq 1 ]]; then echo "+ $*"; else "$@"; fi; }

install_project_file() {
  local rel="$1" src="$KIT_DIR/template/$1" dst="$TARGET/$1"
  if [[ -e "$dst" && $FORCE -eq 0 ]]; then
    skipped+=("$rel"); return
  fi
  run mkdir -p "$(dirname "$dst")"
  run cp "$src" "$dst"
  if [[ "$rel" == "AGENTS.md" && $DRY_RUN -eq 0 ]]; then
    sed "s/{{PROJECT_NAME}}/$PROJECT_NAME/g" "$dst" > "$dst.tmp" && mv "$dst.tmp" "$dst"
  fi
  created+=("$rel")
}

while IFS= read -r -d '' file; do
  rel="${file#"$KIT_DIR/template/"}"
  if [[ "$rel" == context-evals/* && $WITH_EVALS -eq 0 ]]; then continue; fi
  install_project_file "$rel"
done < <(find "$KIT_DIR/template" -type f -print0 | sort -z)

for skill in "$KIT_DIR"/skills/*/; do
  name="$(basename "$skill")"
  if [[ "$name" == "context-eval" && $WITH_EVALS -eq 0 ]]; then continue; fi
  dst="$TARGET/$SKILLS_DIR/$name"
  run rm -rf "$dst"
  run mkdir -p "$(dirname "$dst")"
  run cp -R "$skill" "$dst"
  run find "$dst" -name __pycache__ -prune -exec rm -rf {} +
  updated+=("$SKILLS_DIR/$name")
done

echo "context-kit installed into $TARGET"
for f in ${created[@]+"${created[@]}"}; do echo "  created  $f"; done
for f in ${updated[@]+"${updated[@]}"}; do echo "  skill    $f"; done
for f in ${skipped[@]+"${skipped[@]}"}; do echo "  skipped  $f (exists; context-init will merge it)"; done
cat <<EOF

Next steps, from the target repository with your agent:
  1. Run the context-init skill: it inventories the code and proposes the pilot modules.
  2. Review and commit AGENTS.md, ARCHITECTURE.md and the CONTEXT.md files it writes.
  3. Add to CI: python3 $SKILLS_DIR/context-check/scripts/check_context.py --changed-since origin/<base>
EOF
