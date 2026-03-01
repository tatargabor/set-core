# Tasks — ralph-loop-v2

## 1. Per-iteration log files

- [x] 1.1 Create `.claude/logs/` directory in `cmd_run()` on loop start
- [x] 1.2 Generate log file path per iteration: `.claude/logs/ralph-iter-NNN.log` (zero-padded)
- [x] 1.3 Route Claude invocation output through `tee` to both terminal and log file
- [x] 1.4 Store `log_file` path in each iteration record in `loop-state.json`
- [x] 1.5 Add post-iteration log summary: grep log for files read/written, skills invoked, errors

## 2. Session continuation via `--resume`

- [x] 2.1 Generate UUID on first iteration, store as `session_id` in `loop-state.json`
- [x] 2.2 Pass `--session-id <uuid>` to Claude CLI on first iteration
- [x] 2.3 On iteration N > 1, use `--resume <session_id>` instead of new session
- [x] 2.4 Build short continuation prompt for resumed iterations (not full task prompt)
- [x] 2.5 Detect resume failure (exit within 5s) → fallback to fresh session with new UUID
- [x] 2.6 Track `resume_failures` in state; after 3 failures, disable resume for this loop
- [x] 2.7 Add `resumed: true` field to iteration record when resume was used

## 3. Token budget → `waiting:budget` human checkpoint

- [x] 3.1 Replace `budget_exceeded` status with `waiting:budget` in budget enforcement block
- [x] 3.2 Instead of exiting on budget exceeded, enter a wait loop (sleep 30 + poll state file)
- [x] 3.3 Display checkpoint banner with current/budget token numbers
- [x] 3.4 Add `wt-loop budget <N>` subcommand: update `token_budget` in state, set status to `running`
- [x] 3.5 Ensure `wt-loop resume` also works from `waiting:budget` (sets status to `running`)
- [x] 3.6 Update `wt-loop stop` to work from `waiting:budget` status
- [x] 3.7 Update orchestrator `poll_change()` to treat `waiting:budget` like `waiting:human` (no auto-restart, no stall increment)

## 4. Real-time terminal output

- [x] 4.1 Route Claude output through `tee -a` to both terminal and per-iteration log file
- [x] 4.2 Ensure `--verbose` flag is always passed to Claude CLI
- [x] 4.3 No script wrapper needed — terminal emulator provides TTY, tee handles logging
- [x] 4.4 Output is line-buffered via terminal TTY + tee (stderr merged with 2>&1)

## 5. Universal done detection safety net

- [x] 5.1 After `check_done()` returns false, add fallback: check if tasks.md exists with all tasks `[x]`
- [x] 5.2 If fallback triggers, log warning: "Done by tasks.md fallback (primary criteria '{type}' said not done)"
- [x] 5.3 Ensure fallback uses `find_tasks_file()` (searches worktree root + change dirs)
- [x] 5.4 Ensure fallback does NOT trigger when no tasks.md exists

## 6. State file updates

- [x] 6.1 Add `session_id` field (string|null) to `init_loop_state()`
- [x] 6.2 Add `resume_failures` field (number, default 0) to `init_loop_state()`
- [x] 6.3 Add `"waiting:budget"` to valid status values in state documentation
- [x] 6.4 Remove old `ralph-loop.log` single-file logging in favor of per-iteration logs
