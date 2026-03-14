## Context

The orchestration quality gate pipeline (verifier.sh, merger.sh, monitor.sh, engine.sh) has accumulated reliability issues observed across v9-v11 production runs on a large consumer project. The issues fall into three categories: broken logic (ff→apply chaining), silent failures (verify sentinel), and missing safety mechanisms (self-watchdog, merge timeout, smoke auto-restart).

Current gate pipeline: Ralph done → Build → Test → E2E → Scope → Test Files → Review → Rules → Verify → Merge → Smoke

## Goals / Non-Goals

**Goals:**
- Fix ff→apply chaining so it fires when artifacts are committed (not just dirty files)
- Make verify gate strict — missing sentinel line = FAIL
- Add self-watchdog to monitor loop for all-idle state detection
- Add "done" status to suspended-change safety net
- Enable smoke gate auto-restart of dev server on health_check failure
- Default review_model to opus for reliability
- Add merge operation timeout
- Fix verify output sentinel parsing before truncation

**Non-Goals:**
- Restructuring the gate pipeline order
- Adding new gate types
- Changing the retry/replan architecture
- Modifying the Ralph loop beyond the chaining fix
- Rewriting the smoke fix agent (just improving its preconditions)

## Decisions

### D1: ff→apply chaining condition — track previous action instead of dirty files

**Problem:** `engine.sh:669` checks `$has_artifact_progress` which requires uncommitted dirty files. After ff commits artifacts, this is always false.

**Decision:** Track `prev_action` across iterations. Before the iteration runs, call `detect_next_change_action()` and save it. After the iteration, call it again. If `prev_action == ff:*` and `post_action == apply:*`, trigger chaining regardless of `has_artifact_progress`.

**Why not just remove the `has_artifact_progress` check?** Because the chaining should only fire when the transition actually happened in this iteration (ff→apply), not when apply was already the action before the iteration started. Without the guard, every apply iteration would attempt chaining.

### D2: Verify sentinel — missing = FAIL with retry

**Problem:** `verifier.sh:1353-1365` treats missing sentinel as pass (heuristic fallback). This silently passes changes that the verify skill couldn't fully evaluate.

**Decision:** Missing sentinel = FAIL. The retry prompt already handles this case (line 1381: "re-run /opsx:verify and ensure output ends with VERIFY_RESULT:"). This gives the agent one chance to produce proper output before exhausting retries.

**Risk:** If the verify skill consistently omits the sentinel, this could block all changes. Mitigated by: the retry prompt explicitly asks for the sentinel, and max_verify_retries (default 2) limits blocking.

### D3: Self-watchdog — track last meaningful progress timestamp

**Problem:** Monitor loop has no way to detect its own stall. When all changes are in terminal states (done, merged) but merge queue isn't progressing, the loop spins forever.

**Decision:** Add `last_progress_ts` tracking. Update it whenever:
- A change transitions to a new status
- A merge completes
- A dispatch happens
- A gate produces a result

If `now - last_progress_ts > MONITOR_IDLE_TIMEOUT` (default 300s = 5 min), emit a warning event and attempt recovery:
1. Check merge queue — force retry
2. Check for orphaned "done" changes not in queue — add them
3. If still no progress after another timeout — set orchestrator status to "stalled" and send sentinel notification

### D4: Smoke dev server auto-start — new `smoke_dev_server_command` directive

**Problem:** `health_check()` only verifies the server is running. If it's not, the change goes to `smoke_blocked` requiring manual intervention.

**Decision:** New directive `smoke_dev_server_command` (e.g., `"npx next dev --turbopack --port 3002 &"`). When health_check fails:
1. If `smoke_dev_server_command` is set: start the server, wait for health_check with extended timeout (60s)
2. If still not responding: fall back to `smoke_blocked`
3. If not set: existing behavior (immediate `smoke_blocked`)

**Why a separate directive?** The smoke_command is the test runner, not the server. They're different concerns. The server command needs to run in background (`&`), the smoke command runs in foreground with timeout.

### D5: Review model default — opus

**Problem:** Sonnet reviews fail 50% on large projects (v11 data: 4/8 needed escalation). Each escalation wastes up to 360s.

**Decision:** Change `DEFAULT_REVIEW_MODEL` from `"sonnet"` to `"opus"` in `bin/wt-orchestrate:52`. Users can still override via directive. Keep escalation logic as-is for non-default models.

**Trade-off:** Higher token cost per review (~3-4x). Justified by: review is one call per change, the overhead of escalation (double invocation) often costs more than just using opus directly.

### D6: "done" safety net in monitor loop

**Problem:** `monitor.sh:197` safety net checks `paused | waiting:budget | budget_exceeded` but not `done`. A change stuck in "done" without being queued for merge is invisible.

**Decision:** Add `"done"` to the safety net status filter. When a "done" change is found without being in merge_queue, add it to the merge queue.

### D7: Merge timeout

**Problem:** `merge_change()` has no timeout. If it hangs (e.g., during blocking smoke), the merge lock is held forever.

**Decision:** Wrap the entire `merge_change()` body in a timeout (default 1800s = 30 min). On timeout: release lock, set status to `merge_timeout`, send sentinel notification. This is generous enough to cover blocking smoke + scoped fix retries.

### D8: Verify output sentinel parsing — search full output, then truncate

**Problem:** `verifier.sh:1379` truncates verify output to 2000 chars for retry_prompt. If the sentinel line is beyond 2000 chars, it's lost.

**Decision:** Parse the sentinel from full output first (lines 1341-1366, already happens). Only truncate for the retry_prompt storage (line 1379). Additionally, search for sentinel from the END of output (tail) since it's always the last line.

## Risks / Trade-offs

- [D2: Strict sentinel] If verify skill has a systemic bug preventing sentinel output → all changes blocked → **Mitigation:** max_verify_retries limits blocking, retry prompt explicitly requests sentinel
- [D3: Self-watchdog] False positive stall detection during legitimate long operations (large merge) → **Mitigation:** 5 min timeout is generous, watchdog only warns first then escalates
- [D4: Dev server auto-start] Zombie server processes if not cleaned up → **Mitigation:** Track PID, kill on orchestrator exit via trap
- [D5: Opus default] Higher cost → **Mitigation:** Review is 1 call/change, directive override available for cost-sensitive projects
- [D7: Merge timeout] 30 min may be too short for large smoke fix cycles → **Mitigation:** Configurable via directive, generous default
