# Agent context: {{PROJECT_NAME}}

> Read this file first. It is the canonical entry point for every coding agent.
> Assistant-specific files (`CLAUDE.md`, `.github/copilot-instructions.md`) are pointers only.

## What this repository is

{{PROJECT_SUMMARY}}

## Instruction and evidence precedence

1. The task and explicit developer instructions.
2. This file, the architecture indexes, and the module `CONTEXT.md` files it routes to.
3. Rules under `.github/instructions/`.
4. Other documentation (`README.md`, `docs/`).

For claims about current behavior, source code, tests, build configuration, schemas, and CI are the
evidence. If prose contradicts them, the prose is wrong: correct it in the same change.

## Read only the context the task needs

| Task | Read |
|---|---|
{{ROUTING_ROWS}}
| Maintain documentation for agents | [`docs/context/README.md`](docs/context/README.md) |

Do not load every linked file by default. Follow the route that matches the task, then inspect the
relevant implementation and tests.

## Repository map

| Path | Role |
|---|---|
{{REPOSITORY_MAP_ROWS}}

## Keeping context fresh

- A module that owns a `CONTEXT.md` must have it updated in the same change as its public API.
- Rules (what to do) live in `.github/instructions/`; facts (how it works) live in `CONTEXT.md`.
  Each fact has one owner; link instead of restating.
