## 1. Project Setup

- [x] 1.1 Create `gui/tui/` directory and empty `__init__.py`
- [x] 1.2 Add `tui` subcommand dispatch in `bin/wt-orchestrate`: detect `tui)` case, call `python3 "$SCRIPT_DIR/../gui/tui/orchestrator_tui.py" "$STATE_FILENAME" "$LOG_FILE"`

## 2. Core App Shell

- [x] 2.1 Create `gui/tui/orchestrator_tui.py` with `OrchestratorTUI(App)` class: accept state_file and log_file as CLI args, set up 3s `set_interval` refresh timer, define CSS layout with header/table/log/footer sections
- [x] 2.2 Implement `compose()`: yield Header Static, DataTable, RichLog, Footer Static in a vertical layout with table 60% and log 40% height
- [x] 2.3 Implement keybindings: `q` quit, `r` force refresh, `a` approve, `l` toggle log view

## 3. State Reader

- [x] 3.1 Implement `_read_state()`: load orchestration-state.json, catch JSONDecodeError and FileNotFoundError gracefully (return None, skip refresh), extract top-level fields (status, plan_version, changes, checkpoints, active_seconds, started_epoch, time_limit_secs)
- [x] 3.2 Implement `_read_loop_state(worktree_path)`: read `{worktree_path}/.claude/loop-state.json` for iteration/max_iterations, return "iter/max" string or "-" on failure
- [x] 3.3 Implement `_read_log()`: track file byte offset between reads, read only new bytes appended since last read, return list of new log lines (cap at last 200 lines on first read)

## 4. Header Widget

- [x] 4.1 Implement `_update_header(state)`: format status with colored icon (● RUNNING green, ⏸ CHECKPOINT yellow bold, ⏱ TIME LIMIT yellow, etc.), plan version with replan cycle when >0 (e.g., "Plan v7 (replan #5)"), progress ratio (merged+done/total), cumulative total tokens (sum of current changes tokens_used + prev_total_tokens, formatted K/M suffix), active time vs limit with remaining
- [x] 4.2 Handle edge cases: no time limit (omit remaining), time_limit exceeded (show "exceeded" in red), replan_cycle=0 (omit replan suffix), stale detection (mtime > 120s shows "stale — process may have crashed")

## 5. Change Table

- [x] 5.1 Implement `_update_table(state)`: clear and repopulate DataTable with columns Name (25 char), Status (colored), Iter (from loop-state), Tokens (formatted), Gates (T/R/V/B with ✓/✗/-)
- [x] 5.2 Implement status coloring: map each change status to Rich color+icon per design D4 color table
- [x] 5.3 Implement gate formatting in execution order T/B/R/V: combine test_result, build_result, review_result, verify status into compact "T✓ B✗ R- V-" string with per-gate coloring (gates not yet reached show as "-")
- [x] 5.4 Show depends_on as dimmed text in Name column tooltip or parenthetical when change is blocked

## 6. Log Panel

- [x] 6.1 Implement `_update_log(new_lines)`: append new lines to RichLog widget with auto-scroll, color by log level ([INFO]=default, [WARN]=yellow, [ERROR]=red bold)
- [x] 6.2 Handle missing log file: show "No log file yet" in dimmed text
- [x] 6.3 Implement `l` toggle: switch between split view (table+log) and full-screen log by toggling table visibility and log height to 100%

## 7. Checkpoint Approval

- [x] 7.1 Implement `action_approve()`: check if current status is "checkpoint", if not show brief notification "Not at checkpoint" and return
- [x] 7.2 Implement atomic write: read state, set `checkpoints[-1]["approved"] = True` and `approved_at` to ISO timestamp, write to tempfile in same dir, `os.rename()` to state file path
- [x] 7.3 Show confirmation notification in TUI after successful approval ("Checkpoint approved")
- [x] 7.4 Enable/disable approve keybinding visibility in footer based on checkpoint status

## 8. Subcommand Integration

- [x] 8.1 In `bin/wt-orchestrate`, add `tui)` case to the main command dispatcher, passing resolved STATE_FILENAME and LOG_FILE paths
- [x] 8.2 Add `tui` to the usage/help text of wt-orchestrate
- [x] 8.3 Validate python3 and textual availability on launch, show actionable error if missing

## 9. Testing

- [x] 9.1 Create `tests/tui/test_orchestrator_tui.py`: test `_read_state()` with valid JSON, malformed JSON, and missing file
- [x] 9.2 Test `_read_log()` offset tracking: write lines, read, write more lines, read again — verify only new lines returned
- [x] 9.3 Test `_update_header()` formatting with various states (running, checkpoint, done, time_limit exceeded)
- [x] 9.4 Test approve action: create temp state file with checkpoint status, run approve, verify file updated atomically with approved=true
- [x] 9.5 Test gate formatting: verify all combinations of test/review/verify/build results produce correct compact string
