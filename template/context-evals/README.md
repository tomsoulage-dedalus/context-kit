# Context evaluations

Replays past tickets to measure whether the agent context (`AGENTS.md`, `ARCHITECTURE.md`,
`CONTEXT.md`...) actually helps. LLM trials are slow, costly, and non-deterministic: this is not part
of the regular test suite. Run it before generalizing context files, and when their shape changes.

## Method

1. Pick 5 or 6 tickets already delivered that touch the documented modules.
2. For each, write a task in `tasks/*.json`:
   - `base_ref`: parent commit of the PR that fixed the ticket;
   - `prompt`: the ticket description as the developer received it;
   - `required_changed_paths`: files changed by the original PR (localization target);
   - `allowed_paths`, `max_changed_files`: patch scope;
   - `required_patterns` / `forbidden_patterns`: regular expressions checked on added lines only;
   - `prepare_commands`, `commands`: install, then lint and tests that must pass.
3. Run every task in each variant, several times. Variants differ only in context:
   - `no-context`: every file matching `context_globs` is removed from the trial worktree;
   - `context`: the same files are copied from the current working tree onto the historical commit.
   A variant may also use `"context_source": "<git ref>"` to compare two versions of the context.
4. Adopt a context change only if it improves success or localization without regression or
   unjustified cost.

## Commands

```bash
S=.github/skills/context-eval/scripts/context_eval.py
python3 $S run --task EXAMPLE-1234-cancel-order -n 1        # one task, all variants
python3 $S run --agent-command 'my-wrapper --repo {repo} --prompt-file {prompt_file} --metrics {metrics_file}'
python3 $S report context-evals/results/*.jsonl
```

Placeholders of `agent_command`: `{repo}`, `{prompt}`, `{prompt_file}`, `{task_id}`, `{metrics_file}`,
`{model}`. The agent runs with the trial worktree as working directory. A wrapper may write
`{"tokens": ..., "tool_calls": ...}` to `{metrics_file}` to have them reported.

## Metrics

| Column | Meaning |
|---|---|
| `success` | Trials where every check passed |
| `score` | Share of passed checks |
| `recall` | Share of `required_changed_paths` the agent actually changed (localization) |
| `files` | Number of changed files (patch scope) |
| `agent_s`, `tokens`, `tool_calls` | Cost |

Results (`results/*.jsonl`) contain the full diff and agent output tail: keep them out of git.
