## 1. wt-loop: --change flag and state storage

- [x] 1.1 Add `--change` CLI flag parsing in `cmd_start()` argument loop (around line 1230)
- [x] 1.2 Pass `change` to `init_loop_state()` and store it in `loop-state.json` as `"change"` key
- [x] 1.3 Read `change` from state in `cmd_run()` (around line 656) alongside existing state reads

## 2. wt-loop: Scoped detect_next_change_action()

- [x] 2.1 Add optional second parameter `$target_change` to `detect_next_change_action()`
- [x] 2.2 When `$target_change` is set: skip the directory scan loop, only inspect `openspec/changes/$target_change/` — check tasks.md existence and unchecked count, return ff/apply/done accordingly
- [x] 2.3 When `$target_change` is empty: return `"none"` immediately (no alphabetical scan)

## 3. wt-loop: build_prompt() integration

- [x] 3.1 In `build_prompt()`, read `change` from loop state and pass it to `detect_next_change_action()` as second argument
- [x] 3.2 When no `--change` and `detect` returns `"none"`: use generic `$task` as `effective_task`, skip `openspec_instructions` injection

## 4. wt-loop: check_done_criteria() preservation

- [x] 4.1 In `check_done_criteria()` (around line 379), when `--change` is set, pass the change name to `detect_next_change_action()` so done-check only evaluates the assigned change
- [x] 4.2 When `--change` is NOT set, keep existing behavior (scan all changes for done-check)

## 5. set-orchestrate: dispatch integration

- [x] 5.1 In `dispatch_change()`, add `--change "$change_name"` to the `wt-loop start` invocation (around line 2819)

## 6. Verification

- [x] 6.1 Test: `wt-loop start "test" --change nonexistent --done openspec` in a project with OpenSpec changes — verify it doesn't pick up other changes
- [x] 6.2 Test: `wt-loop start "test" --done openspec` without `--change` — verify no OpenSpec prompt injection occurs
