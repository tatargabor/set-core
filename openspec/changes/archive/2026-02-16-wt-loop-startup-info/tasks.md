## 1. --label flag parsing

- [x] 1.1 Add `--label` option to `cmd_start` argument parsing (after `--fullscreen`, before `-h`)
- [x] 1.2 Pass label to `init_loop_state` — add 9th parameter and write `"label"` field to JSON
- [x] 1.3 Pass label to the spawned terminal via the `run_cmd` or state file (it's already in state, `cmd_run` reads it)

## 2. Expanded startup banner

- [x] 2.1 In `cmd_run`, read label from state file: `label=$(jq -r '.label // empty' "$state_file")`
- [x] 2.2 Read additional context: `wt_path` (already have), git branch (`git -C "$wt_path" branch --show-current`), permission mode from state
- [x] 2.3 Detect memory status: run `set-memory health &>/dev/null` and set `memory_status` to "active" or "inactive"
- [x] 2.4 Replace the banner block (lines 576-581) with expanded version showing: worktree name, label (conditional), path, branch, full task, separator, config params, memory status, start timestamp

## 3. Terminal title with label

- [x] 3.1 In `cmd_run`, build a `title_suffix` variable: `" ($label)"` if label is set, empty otherwise
- [x] 3.2 Update all `update_terminal_title` calls to include `title_suffix`: iteration progress, done, stalled, stuck
- [x] 3.3 In `cmd_start`, include label in `terminal_title` variable used for terminal spawning

## 4. macOS AppleScript title fix

- [x] 4.1 In the macOS AppleScript block, add `set custom title of theTab to "$terminal_title"` after `do script`
