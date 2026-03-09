## 1. Add Deference Principle section

- [x] 1.1 Add "Deference Principle" section to sentinel.md after the "Key principle" line, with Tier 1 (defer) and Tier 2 (act) classification table
- [x] 1.2 Add explicit examples for each Tier 1 situation: merge-blocked, verify failures, change failures, replan cycles, waiting:api

## 2. Simplify crash recovery

- [x] 2.1 Replace the elaborate error classification (Recoverable/Fatal/Unknown) in EVENT:process_exit with simple restart logic: check state for terminal → restart → track rapid crashes
- [x] 2.2 Remove the "Read the logs" and "Classify the error" steps from EVENT:process_exit — only read logs when rapid crash threshold (5 crashes) is hit
- [x] 2.3 Remove step 5 "fix stale state" (resetting running → stopped) from EVENT:process_exit — orchestrator handles this on resume

## 3. Tighten role boundary

- [x] 3.1 Add to "The sentinel MUST NOT" list: "Diagnose orchestration-level issues (merge conflicts, test failures, change failures) — these are the orchestrator's responsibility"
- [x] 3.2 Add to "The sentinel MUST NOT" list: "Reset orchestration state from running to stopped — the orchestrator handles stale state on resume"
- [x] 3.3 Update the summary sentence: "If the sentinel cannot fix a problem with a simple process restart, it MUST stop and report"

## 4. Update EVENT:running handler

- [x] 4.1 Add explicit instruction to EVENT:running: "Do NOT read logs, do NOT read state beyond the poll output, do NOT analyze change statuses". Preserve the existing one-line summary guidance.

## 5. Update stale documentation sections

- [x] 5.1 Update "What happens" summary section (line ~284) — change bullet 7 from "Crashes are diagnosed from log analysis" to reflect simplified restart behavior
- [x] 5.2 Update Guardrails authority list — change "Diagnose" (line ~252) to reflect reduced diagnostic scope (only on rapid crash threshold)
- [x] 5.3 Update the summary sentence (line ~265) to: "If the sentinel cannot fix a problem with a simple process restart, it MUST stop and report"

## 6. wt-loop API error detection

- [x] 6.1 Add `classify_api_error()` function to `lib/loop/engine.sh` that takes `$iter_log_file` and `$claude_exit_code` as args, greps the log file for API patterns (429, 503, 502, 500, rate limit, overloaded, ECONNRESET, connection reset, ETIMEDOUT, socket hang up), returns 0 if API error detected
- [x] 6.2 Add `waiting:api` to the status display in `bin/wt-loop` `cmd_status` case block with icon "⏳", and to `cmd_resume` known-status guard

## 7. wt-loop API error backoff

- [x] 7.1 In the iteration error handling block (after `claude_exit_code` capture), call `classify_api_error` BEFORE the existing 2-retry loop. If API error: enter separate exponential backoff (30s→60s→120s→240s cap), set status to `waiting:api`, retry same iteration. If not API error: fall through to existing 2-retry mechanism. The two paths are mutually exclusive.
- [x] 7.2 Reset backoff counter (`api_backoff_count=0`, `api_backoff_delay=30`) on successful iteration (exit code 0)
- [x] 7.3 After 10 consecutive API backoffs without success, set status to `stalled` with reason `api_unavailable` and break out of backoff loop

## 8. Watchdog + sentinel integration

- [x] 8.1 Update `lib/orchestration/watchdog.sh` in TWO locations: (1) `_watchdog_check_progress()` ~line 261 — add `waiting:api` to the `failed|paused|waiting:budget` skip case, (2) `_watchdog_action_hash()` ~line 225 — skip hash recording when loop status is `waiting:api`
- [x] 8.2 Add `waiting:api` to sentinel's Tier 1 (defer) list as a transient, self-recovering state (informational — sentinel poll doesn't surface loop-level status)
