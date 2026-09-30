---
name: context-init
description: Bootstrap agent context in an existing repository. Inventories the code, proposes layers and a short pilot list of modules, then writes AGENTS.md routing and ARCHITECTURE.md indexes following the context-kit method. Use when a repository has no or little agent documentation, or after installing context-kit.
---

# context-init

Sets up the entry point (`AGENTS.md`) and the architecture index (`ARCHITECTURE.md`) of a repository,
then hands off module documentation to `context-module`. The rules of the method are owned by
`docs/context/README.md` in the target repository: read it first and follow it.

Never write before the user has validated the proposal of step 3. Never delete or rewrite existing
content without explicit approval.

## 1. Read what exists

- `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.github/instructions/**`,
  `docs/context/README.md`, root `README.md`, any `ARCHITECTURE.md` or `CONTEXT.md`.
- Note duplicated guidance (the same rule in several files) and long always-loaded files
  (`applyTo: "**"` or `**/*.ts` with hundreds of lines). Report them; do not fix them silently.

## 2. Inventory the code

Collect facts with commands, not guesses:

```bash
git ls-files | awk -F/ '{print $1"/"$2"/"$3}' | sort | uniq -c | sort -rn | head -40   # size by area
git ls-files | xargs wc -l 2>/dev/null | sort -rn | head -20                           # largest files
git log --since=1.year --name-only --format= | awk -F/ 'NF>2{print $1"/"$2"/"$3"/"$4}' \
  | sort | uniq -c | sort -rn | head -30                                               # churn by area
```

Also read build and module descriptors: `package.json`, `angular.json`, `ng-package.json`,
`tsconfig*.json` (`paths` = import aliases), `pom.xml` modules, `settings.gradle`, `go.mod`, etc.

Deduce:

- **Scopes**: one `ARCHITECTURE.md` per independently understood unit (repository root for a small
  repository; each application or library root in a monorepo).
- **Layers** of each scope, their import alias or package, and allowed dependencies (check imports).
- **Candidate modules**: folders that own a coherent responsibility. Rank them by churn, size, and
  number of importers. A good pilot module is often changed, large, and imported by many others.

## 3. Propose and wait for validation

Present, in a short message:

- the scopes and their layers;
- the 3 to 5 pilot modules with the reason for each (churn, size, fan-in);
- the files that will be created or modified, and how an existing `AGENTS.md` or
  `.github/copilot-instructions.md` will be merged;
- any duplicated or oversized guidance found in step 1.

Ask the user to validate or adjust, and ask for business terms that differ from code names
(for the glossary). Stop until answered.

## 4. Write

- `ARCHITECTURE.md` for each scope from [references/ARCHITECTURE.template.md](references/ARCHITECTURE.template.md).
  List pilot modules with `to be written` in the Context column until `context-module` creates them.
  Write routing rows in the words a ticket would use, not in code terms.
- `AGENTS.md`:
  - if it still contains `{{...}}` placeholders from context-kit, fill them (summary in 2 or 3
    sentences, one routing row per scope index and major concern, repository map);
  - if it is a pre-existing file, keep its content and add the sections "Instruction and evidence
    precedence", "Read only the context the task needs", and "Keeping context fresh" from the
    context-kit template, adapted.
- `CLAUDE.md` and `.github/copilot-instructions.md` must be thin pointers to `AGENTS.md`. If
  `.github/copilot-instructions.md` already holds guidance, do not delete it: add the pointer at the
  top and list what should move to `AGENTS.md` or `.github/instructions/` in your final message.
- Narrow `applyTo` of `.github/instructions/context.instructions.md` to the documented scopes if
  the repository is large and only part of it is documented.

## 5. Hand off and check

- Run `context-module` on each validated pilot module.
- Run `context-check` and fix every error.
- Suggest `context-eval` to measure the pilot on 5 or 6 historical tickets before extending it.

## Output budget

`AGENTS.md` about 80 lines, each `ARCHITECTURE.md` about 80 lines. An index lists and routes; it does
not explain modules (that is the job of `CONTEXT.md`).
