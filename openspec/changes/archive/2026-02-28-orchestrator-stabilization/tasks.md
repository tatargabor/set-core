## 1. Critical Bug Fixes — Infinite Loops and Data Loss

- [x] 1.1 Add MAX_REPLAN_RETRIES=3 constant. In monitor_loop rc=2 branch (line ~2827), track consecutive replan failures. After 3 failures on same cycle, set status to "done" with "replan_exhausted": true and break. Reset counter on rc=0.
- [x] 1.2 Fix double checkpoint on completion: add `break` after `trigger_checkpoint("completion")` at line ~2833 to prevent the monitor loop from re-entering and triggering a second checkpoint.
- [x] 1.3 Fix stale-running parallel resume: in poll_change() stale-running path (line ~2997), add `update_change_field "$change_name" "status" '"stalled"'` BEFORE calling resume_change(), matching the normal stall path pattern.
- [x] 1.4 Reset stall_count on successful resume: in resume_change(), after setting status to "running", add `update_change_field "$change_name" "stall_count" "0"` to prevent accumulated counts from prematurely killing recovered changes.

## 2. Verify Gate Bug Fixes

- [x] 2.1 Add retry_context to verify failure path: at line ~3451 in handle_change_done(), before calling resume_change() on /opsx:verify failure, store the verify output in retry_context using the same pattern as the test-failure path (lines 3234–3248). Escape the output and call `update_change_field "$change_name" "retry_context"`.
- [x] 2.2 Move nested `_try_merge()` function out of retry_merge_queue() to top-level to prevent bash global function pollution across calls.

## 3. Output and Error Handling Fixes

- [x] 3.1 Fix auto_replan stdout flooding: change line ~2889 from `cmd_plan 2>>"$LOG_FILE"` to `cmd_plan &>>"$LOG_FILE"` to redirect both stdout and stderr during auto-replan.
- [x] 3.2 Fix openspec new change error swallowing: replace `openspec new change "$change_name" 2>/dev/null || true` at line ~2458 with proper error capture — log the error via log_error, only continue if the change directory was created.
- [x] 3.3 Fix indentation of orch_gate_stats at line ~2837 to match enclosing else block alignment.

## 4. Token Efficiency — Spec Summary Cache

- [x] 4.1 Create spec summary cache: in cmd_plan(), after LLM summarization completes, write result to `.claude/spec-summary-cache.json` with format `{"brief_hash": "...", "summary": "...", "created_at": "..."}`.
- [x] 4.2 Add cache check: in cmd_plan(), before calling LLM summarization, check if `.claude/spec-summary-cache.json` exists with matching brief_hash. If match, use cached summary and skip LLM call. Log "Using cached spec summary" when cache hits.
- [x] 4.3 Add failed-change deduplication in auto_replan_cycle(): after novel_count check, also check if ALL novel changes match names of previously-failed changes in state. If so, return 1 (no new work) instead of re-dispatching the same failures.

## 5. Build-Fix Retry Path

- [x] 5.1 Add retry_failed_builds() function: scan state for changes with status="failed" AND build_result="fail" AND gate_retry_count < max_verify_retries. For each, set retry_context to the build_output, increment gate_retry_count, and call resume_change().
- [x] 5.2 Call retry_failed_builds() in the monitor loop, after resume_stalled_changes() and before the "all done" check. This gives failed builds a chance to self-repair before triggering replan.

## 6. Spec Synchronization — Document Existing Unspecced Features

- [x] 6.1 Update orchestrator-layer specs to document auto_replan system: auto_replan directive, auto_replan_cycle(), replan_cycle tracking, prev_total_tokens/active_seconds preservation across reinits. Add to orchestration-engine/spec.md.
- [x] 6.2 Update orchestrator-layer specs to document --time-limit flag: parse_duration(), format_duration(), active-seconds tracking, DEFAULT_TIME_LIMIT="5h", "none" to disable. Add to orchestration-engine/spec.md.
- [x] 6.3 Update orchestrator-quality-gates specs to document check_base_build() + fix_base_build_with_llm() + sync_worktree_with_main(): main branch build verification and LLM auto-fix. Add to verify-gate-build/spec.md.
- [x] 6.4 Update orchestrator-layer specs to document stale loop-state mtime detection (5-minute threshold) in poll_change(). Add to ralph-loop/spec.md.
- [x] 6.5 Update orchestrator-quality-gates specs to document retroactive bootstrap_worktree() call in dispatch_change(). Add to worktree-bootstrap/spec.md.
- [x] 6.6 Update orchestrator-memory-integration specs to document orch_memory_audit() periodic health check. Add to orchestrator-memory/spec.md.
- [x] 6.7 Update orchestrator-quality-gates specs to document BASE_BUILD_STATUS/BASE_BUILD_OUTPUT cache and invalidation after merge. Add to verify-gate-build/spec.md.
- [x] 6.8 Update orchestrator-layer specs to document find_existing_worktree() flexible path discovery. Add to orchestration-engine/spec.md.

## 7. Spec Synchronization — Fix Contradictions

- [x] 7.1 Update verify-gate spec step order to match code: tests → build → test_files → review → verify (not the original tests → review → verify → test_files → build). Document the optimization rationale.
- [x] 7.2 Update human-checkpoint spec to document token budget wait-mode behavior (skip dispatch, not trigger checkpoint). Remove the "trigger checkpoint on budget exceeded" requirement.
- [x] 7.3 Update orchestrator-memory spec to fix stall memory save timing: fires on the give-up branch (stall_count > 3), not on the final retry attempt (attempt 3/3).
- [x] 7.4 Update orchestrator-layer/ralph-loop spec to document actual wt-loop launch flags: task description as positional arg, --label, --model opus.
- [x] 7.5 Update orchestrator-layer/orchestration-engine spec to document merge approach: wt-merge --llm-resolve directly (no dry-run pre-check).
- [x] 7.6 Update orchestrator-verify-gate spec to document verify_retry_count integer (not boolean verify_retried) with configurable max_verify_retries.

## 8. Spec Synchronization — Mark Deferred Items

- [x] 8.1 Add "### Deferred" section to human-checkpoint/spec.md marking the 24-hour checkpoint reminder as not-yet-implemented.
- [x] 8.2 Add "### Deferred" section to orchestration-engine/spec.md marking self-test Level 2-4 fixtures and integration test scripts as not-yet-implemented.
- [x] 8.3 Add "### Deferred" section to orchestration-engine/spec.md marking ASCII DAG dependency graph in `--show` output as not-yet-implemented.

## 9. Live Testing Fixes

Bugs discovered and fixed during live orchestrator operation on a 6-change batch.

- [x] 9.1 Fix stall_count reset race and merge-retry branch staleness: reset stall_count atomically when change recovers; ensure merge-retry branches track latest main. (dc6f24c41)
- [x] 9.2 Check PID before declaring change stale: poll_change() now verifies the loop process is actually dead before marking a change as stalled, preventing false stall detection on slow iterations. (d11363977)
- [x] 9.3 SIGTERM exits cleanly: trap SIGTERM in orchestrator main loop to exit gracefully instead of leaving orphan child processes. (220d147a6)
- [x] 9.4 wt-merge auto-stashes all main repo changes: unconditionally stash uncommitted changes before merge and restore on both success and failure paths, preventing false merge conflicts from dirty working tree. (469779c2e)
- [x] 9.5 Retry iterations use manual done-criteria: when resuming with retry_context (build fix), use `--done manual --max 2` instead of `--done openspec --max 30` so the agent reads the build error instead of openspec declaring "all tasks done" and exiting immediately. (b03d6edab)
- [x] 9.6 Recover verify-failed changes on restart: monitor_loop detects orphaned verify-failed changes, rebuilds retry_context from stored build_output, increments verify_retry_count, and resumes them. Previously verify-failed was a transient state with no recovery path after restart. (f5f4ee5fe)
- [x] 9.7 merge_change returns correct exit code on conflict: return 0 when agent rebase started (caller should wait), return 1 when merge-blocked (actual failure). Previously always returned 0, causing false "Merge succeeded" log messages. (337e98265)
