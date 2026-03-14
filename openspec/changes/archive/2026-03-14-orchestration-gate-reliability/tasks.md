## 1. ff→apply Chaining Fix

- [x] 1.1 In `lib/loop/engine.sh`, add `pre_action` variable — call `detect_next_change_action()` BEFORE the Claude invocation (before the `eval` block around line ~270) and save result to `pre_action`
- [x] 1.2 Change chaining condition at line ~669 from `[[ "$post_action" == apply:* ]] && $has_artifact_progress` to `[[ "$pre_action" == ff:* && "$post_action" == apply:* ]]` — trigger chaining when the action TRANSITIONED from ff to apply during this iteration (both conditions required)
- [x] 1.3 Keep `has_artifact_progress` for stall detection (line 556) unchanged — only decouple it from chaining

## 2. Verify Gate Strict Sentinel

- [x] 2.1 In `lib/orchestration/verifier.sh` lines 1353-1365, remove the heuristic fallback that treats missing sentinel as pass — change to `verify_ok=false` and `gate_spec_coverage="fail"`
- [x] 2.2 Move sentinel parsing (grep for `VERIFY_RESULT:`) to run on the FULL `verify_output` before any truncation
- [x] 2.3 Update retry_prompt for missing-sentinel case to clearly instruct: "re-run /opsx:verify and ensure VERIFY_RESULT: sentinel line is present"
- [x] 2.4 Sentinel detection must grep the FULL `verify_output` (already done at lines 1342-1347). For retry_prompt, use `${verify_output: -2000}` (last 2000 chars) instead of `${verify_output:0:2000}` to include the sentinel area. But sentinel parsing itself must always search the complete output.

## 3. Review Model Default

- [x] 3.1 In `bin/wt-orchestrate`, change `DEFAULT_REVIEW_MODEL="sonnet"` to `DEFAULT_REVIEW_MODEL="opus"`
- [x] 3.2 In `lib/orchestration/monitor.sh`, update the jq fallback for review_model (`.review_model // "sonnet"`) to use `// "opus"` for consistency with the new default

## 4. Monitor Self-Watchdog

- [x] 4.1 Add `DEFAULT_MONITOR_IDLE_TIMEOUT=300` to `bin/wt-orchestrate` defaults. Add `monitor_idle_timeout` to directive parsing in `lib/orchestration/utils.sh`
- [x] 4.2 In `lib/orchestration/monitor.sh`, add `last_progress_ts` variable initialized to `$(date +%s)` before the main loop
- [x] 4.3 Add `update_progress_ts()` helper function that sets `last_progress_ts=$(date +%s)` — this must be callable from both monitor.sh and verifier.sh (export or define in a shared location like utils.sh)
- [x] 4.4 Call `update_progress_ts` after: dispatch_ready_changes returns with dispatched count > 0, retry_merge_queue completes a merge, resume_stalled_changes resumes a change. For gate results inside poll_change/verifier.sh, call update_progress_ts at the end of poll_change when status changed
- [x] 4.4 Add idle check at end of main loop iteration: if `now - last_progress_ts > MONITOR_IDLE_TIMEOUT (300s)`, attempt recovery (force retry merge queue, check orphaned "done" changes)
- [x] 4.5 Add persistent idle escalation: if recovery doesn't reset `last_progress_ts` within another timeout period, emit `MONITOR_STALL` event and send sentinel notification

## 5. Monitor "done" Safety Net

- [x] 5.1 In `lib/orchestration/monitor.sh` line 197, add `"done"` to the jq status filter: `select(.status == "paused" or .status == "waiting:budget" or .status == "budget_exceeded" or .status == "done")`
- [x] 5.2 For "done" changes found by safety net: check if `jq '.merge_queue[]?' "$STATE_FILENAME"` contains the change name. If not, add it via `safe_jq_update` (same pattern as verifier.sh line ~1445: `.merge_queue += [$name]`), then set status to "running" and call poll_change

## 6. Smoke Dev Server Auto-Restart

- [x] 6.1 In `lib/orchestration/utils.sh`, add `smoke_dev_server_command` directive parsing (string type, default empty)
- [x] 6.2 Read `smoke_dev_server_command` from directives JSON in merger.sh directly (same pattern as `smoke_command` at merger.sh line ~207: `jq -r '.directives.smoke_dev_server_command // ""'`). No need to thread through positional args.
- [x] 6.3 In `lib/orchestration/merger.sh` blocking smoke section (line ~226), after health_check failure: if `smoke_dev_server_command` is non-empty, run `bash -c "$smoke_dev_server_command" &` and save PID to `_dev_server_pid`, then wait for health_check with 60s timeout
- [x] 6.4 If extended health_check succeeds, proceed with smoke tests normally
- [x] 6.5 If extended health_check fails, kill `$_dev_server_pid` and fall back to existing `smoke_blocked` behavior
- [x] 6.6 Add dev server PID cleanup: use global `_ORCH_DEV_SERVER_PID` variable, append to existing trap handler in `bin/wt-orchestrate` cleanup function. On exit: `[[ -n "$_ORCH_DEV_SERVER_PID" ]] && kill "$_ORCH_DEV_SERVER_PID" 2>/dev/null || true`
- [x] 6.7 Add `DEFAULT_SMOKE_DEV_SERVER_COMMAND=""` to `bin/wt-orchestrate` defaults and initialize in `parse_directives()` local variable

## 7. Merge Timeout

- [x] 7.1 In `lib/orchestration/utils.sh`, add `merge_timeout` directive parsing (integer, default 1800)
- [x] 7.2 In `lib/orchestration/merger.sh`, add a timeout check INSIDE `merge_change()` — track start time at function entry, check elapsed time at key checkpoints (after merge, after smoke, after fix). If elapsed > merge_timeout, abort remaining work. Do NOT use `timeout` command with subshell (flock and state writes would break in subshell context).
- [x] 7.3 On timeout: set status to `merge_timeout`, send sentinel notification, return from function (flock released naturally by function return)
- [x] 7.4 Add `DEFAULT_MERGE_TIMEOUT=1800` to `bin/wt-orchestrate` defaults

## 8. Documentation

- [x] 8.1 Update `docs/howitworks/en/07-quality-gates.md` to document: strict verify sentinel behavior, new smoke_dev_server_command directive, merge timeout, review_model default change
