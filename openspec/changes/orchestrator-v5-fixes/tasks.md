## 1. Merge Model Selection

- [x] 1.1 In `bin/wt-merge` `llm_resolve_conflicts()`, move hunk extraction and `total_lines` computation before the LLM call (already computed, just ensure it's available before model decision)
- [x] 1.2 Add size-based branching: if `total_lines > 200` → opus directly (600s), else → sonnet (300s) with opus fallback
- [x] 1.3 Log which model path was taken: `info "Using opus directly (${total_lines} conflict lines)"` or `info "Trying sonnet first (${total_lines} conflict lines)"`

## 2. Stale Warning Debounce

- [x] 2.1 In `bin/wt-orchestrate` `poll_change()` (~line 3318), change `log_info` to `log_debug` for the "loop-state stale but PID alive" message

## 3. Shared Resource Planner Hint

- [x] 3.1 In `bin/wt-orchestrate`, add SHARED RESOURCE RULE (~6 lines) to the spec-mode decomposition prompt after existing dependency/ordering rules (~line 1700)
- [x] 3.2 Add the same SHARED RESOURCE RULE to the brief-mode decomposition prompt (~line 1780)

## 4. Cycle Boundary Markers

- [x] 4.1 In `bin/wt-orchestrate` `auto_replan_cycle()`, emit `log_info "========== REPLAN CYCLE $cycle =========="` at the start of each new cycle
- [x] 4.2 In `auto_replan_cycle()`, set `cycle_started_at` ISO timestamp in state after `init_state()` reinit
- [x] 4.3 In `init_state()`, include `cycle_started_at` as a preservable field (null initial value)

## 5. TUI Token Persistence

- [x] 5.1 In `gui/tui/orchestrator_tui.py` `_update_header()`, handle replan transition: if `current_tokens == 0` and `prev_tokens > 0`, display `prev_tokens` as total
- [x] 5.2 In `gui/tui/orchestrator_tui.py`, render log lines matching `========== REPLAN CYCLE` with bold/highlighted styling

## 6. TUI Tests

- [x] 6.1 Add or update test in `tests/tui/` for TUI token display during replan (current_tokens=0, prev_total_tokens>0 → shows prev total)

## 7. Sentinel Wrapper

- [x] 7.1 Create `bin/wt-sentinel` bash script: run `wt-orchestrate start "$@"` in supervised loop
- [x] 7.2 Add exit decision logic: exit 0 + done → stop; exit 0 + stopped → stop (user Ctrl+C); non-zero + no SIGINT → restart with 30s backoff
- [x] 7.3 Add SIGINT/SIGTERM trap: set flag, forward signal to child, don't restart after exit
- [x] 7.4 Add stale state cleanup before restart: if state is `running` but no orchestrator PID alive → set to `stopped` via jq
- [x] 7.5 Add PID file write (`sentinel.pid`) on start and cleanup on exit (trap)
- [x] 7.6 Add restart counter: max 5 rapid crashes (<5 min each), reset on sustained run (>5 min)
- [x] 7.7 Add `--help` flag with usage documentation
