---
name: context-module
description: Write or update the CONTEXT.md card of one module (role, entry points, flows, dependencies, traps, where to look) from the code, tests and git history, and register it in the ARCHITECTURE.md index. Use when documenting a module for agents, or when a module public API, flows or invariants changed.
---

# context-module

Input: a module directory (for example `src/domain/orders`). Output: `<module>/CONTEXT.md` plus its
rows in the nearest `ARCHITECTURE.md`. Follow `docs/context/README.md` of the target repository.

## 1. Read

- `docs/context/README.md` (governance) and the nearest `ARCHITECTURE.md`.
- The existing `CONTEXT.md` if any. In update mode, start from its provenance commit:
  `git diff <sha>..HEAD --stat -- <module>` then read only what changed.
- [references/CONTEXT.template.md](references/CONTEXT.template.md).

## 2. Investigate the module

Collect evidence, in this order:

1. **Public surface**: barrel files (`index.ts`, `public-api.ts`, `ng-package.json`), exported
   classes, Java public services and REST resources, Python `__init__.py`. That gives Entry points.
2. **Tests**: spec and test files state the expected behavior; surprising assertions are traps.
3. **Largest files**: skim their structure (public methods, not bodies) to name the main flows.
4. **Imports out** of the module give "Uses". Imports of the module alias or package from elsewhere
   give "Used by"; include it only if the list is short and stable.
5. **History**: `git log --oneline -40 -- <module>`; fix commits and reverts often point to traps.
6. **Business vocabulary**: ticket words that differ from code names go to the index glossary.

## 3. Draft

Fill the template. Rules:

- About 50 lines, 80 maximum. A compass, not an encyclopedia: route to files, do not paraphrase code.
- Every identifier or path between backticks must exist in the code (`context-check` verifies it).
- No line numbers, no full signatures, no copied code blocks.
- Descriptive facts only. A rule ("always put X in Y") belongs to `.github/instructions/`: write a
  one-line pointer to it in "Traps and invariants", and propose the rule to the user if it does not
  exist yet.
- State what the module does not do, and which module does it.
- First line after the title: `Verified at commit <git rev-parse --short HEAD> on <today>.`

In update mode, change only the affected sections, delete stale lines instead of appending
corrections, and refresh the provenance line.

## 4. Validate, write, register

1. Show the draft to the user and wait for approval before writing.
2. Write `<module>/CONTEXT.md`.
3. In the nearest `ARCHITECTURE.md`: add or update the row in "Documented modules", add 1 to 3
   routing rows phrased as tasks, and glossary rows if any.
4. Run the check on the module and fix every error:
   `python3 <skills dir>/context-check/scripts/check_context.py <module> <ARCHITECTURE.md path>`
