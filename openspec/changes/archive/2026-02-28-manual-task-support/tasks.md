## 1. Manual Task Parsing in wt-loop

- [x] 1.1 Add `count_manual_tasks()` function to `bin/wt-loop` that counts `- [?]` lines in tasks.md using regex `^\s*-\s*\[\?\]` — returns the count
- [x] 1.2 Add `parse_manual_tasks()` function that extracts structured info from `[?]` lines: task id (e.g. "3.3"), description, type annotation (`[input:KEY]` or `[confirm]`), and input key name. Output as JSON array.
- [x] 1.3 Modify `check_tasks_done()` (line ~296) to only count `- [ ]` patterns (exclude `[?]`). Current regex `^\s*-\s*\[\s*\]` already excludes `[?]` since `?` is not whitespace — verify this and add a comment confirming it.

## 2. waiting:human Status in wt-loop

- [x] 2.1 Add `waiting:human` detection in the stall block (after line ~884): when stall condition fires (no commits, no dirty files), check if `check_tasks_done` passes AND `count_manual_tasks > 0` — if both true, set status `"waiting:human"` instead of incrementing stall_count
- [x] 2.2 When transitioning to `waiting:human`: call `parse_manual_tasks()`, write `manual_tasks` array and `waiting_since` timestamp to loop-state.json, then exit 0 with a clear banner message
- [x] 2.3 Add `waiting:human` to the status display case in `cmd_status` (line ~1378): icon `⏸`, label "Waiting for human input"
- [x] 2.4 Add prompt instruction in `build_prompt()`: when tasks.md contains `[?]` lines, append "Tasks marked [?] require human action — do NOT attempt to complete them. Skip them and focus only on [ ] tasks."

## 3. Orchestrator: poll_change and Status

- [x] 3.1 Add `waiting:human` case in `poll_change()` (after `done)` case, line ~3240): update change status to `"waiting:human"`, do NOT increment stall_count, do NOT auto-resume, log manual task summary from loop-state.json's `manual_tasks` field
- [x] 3.2 Add `waiting:human` to the status display formatting in `print_status()` / TUI output: show `⏸ HUMAN` label with first pending manual task description and hint `Run: wt-manual show <change>`
- [x] 3.3 Handle resume from `waiting:human`: when change status changes from `waiting:human` to `dispatched` (set by `wt-manual resume`), orchestrator's next poll detects this and calls `resume_change()`

## 4. wt-manual CLI Tool

- [x] 4.1 Create `bin/wt-manual` with argument parsing skeleton: subcommands `list`, `show`, `input`, `done`, `resume`, plus `--help`
- [x] 4.2 Implement `wt-manual list`: read orchestration-state.json, find changes with status `waiting:human`, display change name + waiting duration + manual task summaries. If no orchestration state, scan worktrees for loop-state.json with status `waiting:human`.
- [x] 4.3 Implement `wt-manual show <change>`: locate the change's worktree (from orchestration-state.json or by name), read tasks.md, extract `[?]` tasks and their `### Manual:` instruction sections, display formatted output with task id, description, type, instructions, and worktree path
- [x] 4.4 Implement `wt-manual input <change> <KEY> <value>`: find the worktree, write/update `KEY=value` in worktree's `.env.local`, find the `[?]` task with matching `[input:KEY]` annotation, change it to `[x]` in tasks.md
- [x] 4.5 Implement `wt-manual done <change> <task-id>`: find the worktree, locate the `[?]` task with matching id (e.g. "3.3") in tasks.md, change it to `[x]`. Error if task-id not found.
- [x] 4.6 Implement `wt-manual resume <change>`: check if all `[?]` tasks are resolved. If yes, call `wt-loop resume` in the worktree. If orchestrator is running, also update change status to `"dispatched"` in orchestration-state.json. Warn if unresolved `[?]` tasks remain.
- [x] 4.7 Add `wt-manual` to install.sh / set-project init deployment so it's available on PATH

## 5. Planner Prompt Update

- [x] 5.1 Update the planner decomposition prompt in `set-orchestrate` (lines ~1690-1760) to include `has_manual_tasks: true|false` in the change JSON schema, with instruction to set it when the change involves external services, API keys, webhooks, or manual account setup
- [x] 5.2 Add examples to the planner prompt showing when to flag `has_manual_tasks`: Stripe API keys, Firebase project creation, DNS configuration, OAuth app registration, etc.
- [x] 5.3 Update plan validation (`validate_plan`) to accept the new `has_manual_tasks` field without error

## 6. FF/Task Generation Awareness

- [x] 6.1 Update the task generation prompt/instructions (used by /opsx:ff when creating tasks.md) to generate `[?]` tasks with `[input:KEY]` or `[confirm]` annotations when the change scope or proposal mentions external services or secrets
- [x] 6.2 Update the task generation prompt to include `### Manual:` instruction sections after `[?]` tasks with: what to do (numbered steps), relevant URLs, expected input format, and target file path

## 7. Plan-Review Enhancement

- [x] 7.1 Add a check in the plan-review skill (`.claude/commands/wt/plan-review.md`) that flags a warning when a change scope mentions external services (API keys, tokens, webhooks, third-party services) but has no `[?]` tasks in tasks.md — "Consider adding manual tasks for credential/setup steps"
