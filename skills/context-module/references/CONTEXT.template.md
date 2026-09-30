# Context: {{module path}}

Verified at commit {{short sha}} on {{YYYY-MM-DD}}.
Import: `{{alias or package}}`

## Role

{{2 or 3 sentences: what the module owns, and what it explicitly does not do (with the module that does).}}

## Entry points

| Element | Usage |
|---|---|
| `{{PublicSymbol}}` | {{what it is for; the key method if any}} |

## Main flows

- {{Flow name}}: `{{a}}` -> `{{b}}` -> {{outcome, e.g. back-end call}}.

## Dependencies

- Uses: {{modules and external packages}}.
- Used by: {{optional; omit if it cannot be kept accurate}}.

## Traps and invariants

- {{Fact about behavior that is surprising or easy to get wrong.}}
- {{Rule owned elsewhere: see `.github/instructions/<file>` (one line, no restatement).}}

## Where to look

| I want to... | Look at |
|---|---|
| {{task}} | `{{file or symbol}}` |
