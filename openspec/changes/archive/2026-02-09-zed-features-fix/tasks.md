## 1. Editor Window Detection in wt-status

- [x] 1.1 Add `is_editor_open()` function to `bin/wt-status` that uses xdotool to check if an editor window exists for a given worktree basename. Return true/false.
- [x] 1.2 Add `/proc`-based fallback in `is_editor_open()` for when xdotool is unavailable: scan `/proc/*/cmdline` for editor processes with matching CWD.
- [x] 1.3 Add macOS support in `is_editor_open()` using osascript to query editor windows by title.
- [x] 1.4 Add `editor_open` boolean field to the JSON output in `collect_worktree_status()`, populated by `is_editor_open()`.

## 2. Orphan Agent Cleanup in wt-status

- [x] 2.1 Add `is_ralph_loop_active()` helper function that checks `.claude/loop-state.json` for status "running".
- [x] 2.2 Add `cleanup_orphan_agents()` function: for each worktree with agents but no editor window and no active Ralph loop, send SIGTERM to "waiting" agents and remove their `.set-core/agents/<pid>.skill` files.
- [x] 2.3 Integrate `cleanup_orphan_agents()` into `collect_worktree_status()` — call it after `detect_agents()` but before building the agents JSON array, so orphans are excluded from output.
- [x] 2.4 Add stderr logging when orphan agents are killed (PID, worktree path).

## 3. Zed Open Stability Verification

- [x] 3.1 Verify `wt-work` opens Zed correctly on Linux: test that the editor window appears and the worktree basename is in the title.
- [x] 3.2 Verify keystroke delivery: after `wt-work`, confirm a claude process starts in the worktree CWD within 10 seconds.
- [x] 3.3 Add window existence verification before keystroke: `wt-work` SHALL check via xdotool that the Zed window is present before sending Ctrl+Shift+L.
- [x] 3.4 Add retry logic in `wt-work` keystroke delivery: if no claude process detected after 5s, retry keystroke up to 2 times.
- [x] 3.5 Verify `wt-new` creates worktree and calls `wt-work` successfully, with `.zed/tasks.json` and `.zed/keymap.json` in place.

## 4. GUI Orphan Handling

- [x] 4.1 Update table rendering in `gui/control_center/mixins/table.py` to handle the `editor_open` field: dim/gray rows where `editor_open` is false and no agents are active.
- [x] 4.2 Verify that orphan agents killed by wt-status no longer appear in the GUI table on the next refresh (no code change expected — this is a verification task).

## 5. Integration Tests

- [x] 5.1 Create `tests/gui/test_17_orphan_detection.py`: test that status data with agents but `editor_open: false` results in dimmed/removed rows in the table.
- [x] 5.2 Add test for orphan exclusion: feed status data with waiting agents and `editor_open: false`, verify agents are not displayed or are grayed out.
- [x] 5.3 Add test for preserved agents with Ralph loop: feed status data with agents, `editor_open: false`, and ralph loop active — agents SHALL still be displayed normally.
- [x] 5.4 Add test for `editor_open: true` worktrees: verify normal rendering (no dimming).
- [x] 5.5 Create `tests/gui/test_18_zed_integration.py`: test that `on_focus()` and `on_double_click()` use platform abstraction correctly with mocked xdotool responses.
- [x] 5.6 Add test for `on_close_editor()` handler: mock platform `close_window()` and verify it is called with correct window ID.
- [x] 5.7 Add real process lifecycle test: fork a dummy process, feed its PID as agent, verify `is_process_running()` returns true, then kill it and verify false.
- [x] 5.8 Run full GUI test suite (`PYTHONPATH=. python -m pytest tests/gui/ -v --tb=short`) and fix any failures.

## 6. Install and Dependency Updates

- [x] 6.1 Ensure `install.sh` lists xdotool as explicit Linux dependency and installs it if missing.
- [x] 6.2 Verify installed `wt-status` symlink picks up the new `is_editor_open()` and `cleanup_orphan_agents()` functions.

## 7. End-to-End Verification

- [x] 7.1 Manual verification cycle: open Zed via wt-work, check status shows running, close Zed, wait for status refresh, verify agents are killed and removed from GUI.
- [x] 7.2 Verify wt-loop can be started on this change and runs tasks autonomously to completion.

## 8. Pre-existing Test Fixes

- [x] 8.1 Fix `test_set_session_key_saves_to_file` hanging: monkeypatch `get_text` helper (not `QInputDialog.getText`) since `show_set_session_key()` uses the always-on-top wrapper.
- [x] 8.2 Fix `test_btn_add_exists`: update tooltip assertion from "Add existing worktree" to "Add existing repository or worktree".
- [x] 8.3 Fix `test_table_columns_correct`: update expected first column from "Name" to "Branch".
- [x] 8.4 Fix `test_set_session_key_cancelled`: same `get_text` monkeypatch fix as 8.1.
- [x] 8.5 Fix `test_15_dialog_helpers.py`: use `QWidget`-based `WidgetParent` for dialog tests (PySide6 6.10.1 rejects non-QWidget parents).
- [x] 8.6 Run full GUI test suite — 98/98 pass.
