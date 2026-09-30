---
name: context-eval
description: Measure whether agent context helps by replaying historical tickets on the parent commit of their PR, with and without the context files, and grading the resulting diffs. Builds tasks from merged PRs, runs trials, and reports success, localization and cost. Use before generalizing CONTEXT.md files or after changing their shape.
---

# context-eval

Runs [scripts/context_eval.py](scripts/context_eval.py) with tasks stored in `context-evals/` of the
target repository (see `context-evals/README.md` for the format and the method).

## 1. Build tasks from merged PRs

Ask the user for 5 or 6 delivered tickets that touch documented modules. For each PR:

```bash
gh pr view <number> --json number,title,body,mergeCommit,baseRefName,files
git rev-parse <mergeCommit>^1        # base_ref: state of the code before the PR
```

- `prompt`: the ticket description as the developer received it (fetch it from the tracker). Never
  mention the files changed by the PR.
- `required_changed_paths`: production files changed by the PR (tests optional).
- `allowed_paths`: the smallest globs that cover those files.
- `max_changed_files`: files changed by the PR plus a small margin.
- `forbidden_patterns`: repository rules checkable with a regular expression on added lines.
- `prepare_commands` and `commands`: install, then the lint and test commands of the touched package.

Show the tasks to the user before saving them to `context-evals/tasks/<name>.json`.

## 2. Run

```bash
S=<skills dir>/context-eval/scripts/context_eval.py
python3 $S run --task <id> -n 1                  # smoke test on one task
python3 $S run -n 3 --model <model id>           # full run: every task x every variant x 3
python3 $S report context-evals/results/*.jsonl
```

Trials are slow and consume AI credits: confirm the number of trials (tasks x variants x repetitions)
with the user before a full run. The default agent is `copilot -p {prompt} --allow-all-tools -s`;
the trial worktree is disposable but the agent has full permissions in it.

## 3. Conclude

Compare `context` with `no-context` per task, then overall:

- adopt or extend the context only if success or localization (`recall`) improve without regression;
- a lower cost (`agent_s`, tokens, tool calls) at equal success is also a gain;
- with fewer than 3 repetitions per variant, report the result as a trend, not a conclusion.

Write the conclusion (table plus decision) where the team tracks the pilot; do not commit results.
