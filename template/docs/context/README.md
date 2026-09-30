# Context governance

This file owns the rules for documentation written for coding agents (and useful to developers) in
this repository. It was installed by [context-kit](https://github.com/tomsoulage-dedalus/context-kit)
and is now owned by the repository team.

## Layout

| File | Role | Budget |
|---|---|---|
| `AGENTS.md` | Canonical entry point: precedence, routing table "task -> file to read", repository map | About 80 lines |
| `CLAUDE.md`, `.github/copilot-instructions.md` | Pointers to `AGENTS.md` | A few lines |
| `.github/instructions/*.instructions.md` | Procedural rules, loaded automatically by path (`applyTo`) | Short; routers when possible |
| `ARCHITECTURE.md` (repository or package root) | Index: layers, import aliases, glossary, routing table, documented modules | About 80 lines |
| `<module>/CONTEXT.md` | Descriptive card of one module, next to its code | About 50 lines, 80 maximum |

## Descriptive versus procedural knowledge

| Kind | Question answered | Owner |
|---|---|---|
| Descriptive | How does this module work? Where is X? | `CONTEXT.md`, `ARCHITECTURE.md` |
| Procedural | Which rule must I follow? Which mistake must I avoid? | `.github/instructions/` |

A `CONTEXT.md` may point to a rule in one line; it must not restate it.

## What belongs in the context

Add a fact only when it is durable, specific to this repository, not obvious from reading the code,
and likely to affect future work. Typical content: module role, public entry points, main flows,
invariants and traps, business vocabulary that differs from code names, "I want X -> look at Y".

Do not add: task plans, chat history, investigation logs, raw generated summaries, secrets or
credentials, full signatures, line numbers, or facts that are cheap to rediscover with a search.

## The code is the evidence

Source, tests, build configuration, schemas, and CI own actual behavior. When prose contradicts them,
fix the prose in the same change. Do not restate in prose what linters, formatters, or compilers
already enforce.

## One owner per fact

Each fact lives in exactly one file. Other files link to it. When two files disagree, delete the
copy instead of reconciling both.

## Freshness

- Every `CONTEXT.md` starts with a provenance line: `Verified at commit <sha> on <YYYY-MM-DD>.`
- Update the `CONTEXT.md` in the same change when the module public API, flows, or invariants change,
  then refresh the provenance line.
- Prefer generated or checked data over hand-written lists. The dependency section is the part that
  ages fastest: keep "Uses" and let agents search for consumers, or regenerate "Used by".
- `context-check` verifies that the files and symbols quoted between backticks still exist and
  reports modules changed since their provenance commit.

## Pruning

- Delete stale guidance; never append a contradictory correction.
- During review, ask whether each line still prevents a demonstrated mistake or supplies knowledge
  unavailable from the code. If not, remove it.

## Measuring

More context is not always better. Before generalizing `CONTEXT.md` files to many modules, measure the
gain on replayed historical tasks with `context-eval` (see `context-evals/README.md` when installed).
