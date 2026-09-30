# Architecture of {{SCOPE_NAME}}

Entry point of the agent documentation for `{{SCOPE_PATH}}`. Read this before searching the code, then
only the `CONTEXT.md` of the module concerned.

## Layers

| Layer | Import alias or package | Role | May depend on |
|---|---|---|---|
| `{{layer path}}` | `{{alias}}` | {{one line}} | {{layers}} |

## Routing

| I need to... | Read |
|---|---|
| {{task in the words of a ticket}} | [`{{module}}/CONTEXT.md`]({{module}}/CONTEXT.md) |

## Glossary

| Business term | Name in the code |
|---|---|
| {{term used in tickets}} | `{{Symbol or field}}` |

## Documented modules

| Module | Role | Context |
|---|---|---|
| `{{module path}}` | {{one line}} | [CONTEXT.md]({{module path}}/CONTEXT.md) |

## Documentation conventions

Rules for these files are owned by [`docs/context/README.md`]({{relative path to docs/context/README.md}}).
