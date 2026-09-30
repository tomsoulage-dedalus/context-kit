---
name: context-check
description: Verify that agent context files (AGENTS.md, ARCHITECTURE.md, CONTEXT.md) are still accurate - quoted files and symbols exist, links resolve, provenance is recent, line budget respected, modules changed in a branch have their CONTEXT.md updated - and propose fixes. Use before opening a PR, in review, or periodically.
---

# context-check

Runs [scripts/check_context.py](scripts/check_context.py) (Python 3 standard library and git only),
then turns findings into fixes.

## Run

```bash
S=<skills dir>/context-check/scripts/check_context.py     # e.g. .github/skills/context-check/...
python3 $S                                  # whole repository
python3 $S src/domain/orders                # one module or scope
python3 $S --changed-since origin/main      # also: modules changed in this branch without CONTEXT.md update
python3 $S --format json --strict           # CI: exit 1 on warnings too
```

| Finding | Level | Meaning |
|---|---|---|
| `path not found`, `symbol not found in code`, `import alias not found`, `broken link` | error | The context quotes something that no longer exists (Markdown files are not searched) |
| `commit(s) touched the module since the card was last verified` | warning | Module code changed in commits after the last commit that touched its `CONTEXT.md` (or its provenance commit if uncommitted) |
| `CONTEXT.md did not` (with `--changed-since`) | warning | Module code changed since the merge base with REF but its card did not |
| `missing provenance`, `not linked`, `budget` | warning | Method not followed |

Exit code: 0 when no error (or no finding with `--strict`), 1 otherwise, 2 when git fails.

## Fix

- **Error**: find what the symbol or path became (`git log -S<symbol> --oneline`, rename detection
  with `git log --follow`), then update or delete the line.
- **Stale module**: read `git diff <sha>..HEAD -- <module>`. If the public API, flows, or invariants
  changed, update the card with `context-module` (update mode). Otherwise, only refresh the
  provenance line.
- **Changed without update**: same decision; say explicitly in the PR when no update is needed.
- Present the proposed edits to the user before writing them.

## CI

```yaml
- run: python3 .github/skills/context-check/scripts/check_context.py --changed-since origin/${{ github.base_ref }}
```

Start with errors only (default); add `--strict` once the pilot is stable.
