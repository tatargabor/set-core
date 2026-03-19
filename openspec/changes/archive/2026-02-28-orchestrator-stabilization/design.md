## Design Decisions

### D1: Three priority tiers — bugs first, then token savings, then spec sync

The 29 items are organized into three tiers that can be implemented sequentially:

**Tier 1 — Critical bugs (items 1–10)**: Code fixes in `bin/set-orchestrate`. These prevent data loss, infinite loops, and wasted tokens. Must be done before the orchestrator runs again.

**Tier 2 — Token efficiency (items 11–12)**: Spec summary caching and build-fix retry path. These reduce per-cycle cost from ~100k to ~5k tokens on retries.

**Tier 3 — Spec sync (items 13–29)**: Update existing specs to match code reality. No code changes, only `.md` file updates. This prevents future drift and makes the orchestrator self-documenting.

### D2: All changes in a single file — `bin/set-orchestrate`

The orchestrator is a single 3946-line bash script. All bug fixes are in this one file. The spec sync changes are in `openspec/specs/` and `openspec/changes/` markdown files. No new files needed for Tier 1–2.

### D3: Spec summary cache — file-based, keyed by brief_hash

In `auto_replan_cycle()`, before calling `cmd_plan`, check if `.claude/spec-summary-cache.json` exists with matching `brief_hash`. If match, skip the LLM summarization call and use cached summary text. Invalidate on brief_hash change. Cache format:
```json
{"brief_hash": "...", "summary": "...", "created_at": "..."}
```

### D4: Max replan retries — simple counter with configurable limit

Add `MAX_REPLAN_RETRIES=3` constant. In the `rc=2` branch of monitor_loop (line 2827), track retry count. After 3 consecutive failures on the same replan cycle, set status to `"done"` with a `"replan_exhausted": true` field and break. Log all failed change names as warnings.

### D5: Build-fix retry — resume agent with build error context instead of full replan

When a change fails with `build_result: "fail"`, instead of waiting for replan to rediscover it, immediately resume the agent with `retry_context` containing the build error output. This is ~50x cheaper than a full plan decomposition. Add to `resume_stalled_changes()` or create a `retry_failed_builds()` function called in the monitor loop.

### D6: Verify failure retry_context — copy pattern from test failure path

Lines 3234–3248 show the correct pattern for test failures:
```bash
update_change_field "$change_name" "retry_context" "\"$escaped_output\""
resume_change "$change_name"
```
Apply the same pattern at line 3451 for verify failures, using the verify command output.

### D7: Stale-running fix — set status before resume

In `poll_change()` stale-running path (lines 2997–3013), add `update_change_field "$change_name" "status" '"stalled"'` before calling `resume_change()`. This prevents parallel resume calls on consecutive poll cycles.

### D8: stall_count reset — add to resume_change()

In `resume_change()`, after setting status to `"running"`, also reset `stall_count` to 0. This prevents accumulated stall counts from killing a change that recovered and stalled again for a different reason.

### D9: Spec sync approach — update existing specs, mark deferred items

For the 11 unspecced features and 7 contradictions:
- Update the relevant spec files in `openspec/specs/` to match the code
- Add a `### Deferred` section to specs where items are not yet implemented (checkpoint 24h reminder, self-test fixtures, ASCII DAG)
- Do NOT create new spec files — add to existing ones

Affected specs:
- `openspec/specs/execution-model/spec.md` (if exists) or `openspec/specs/orchestration-engine/spec.md`
- `openspec/changes/orchestrator-layer/specs/*/spec.md`
- `openspec/changes/orchestrator-verify-gate/specs/*/spec.md`
- `openspec/changes/orchestrator-quality-gates/specs/*/spec.md`
- `openspec/changes/orchestrator-memory-integration/specs/*/spec.md`

### D10: Double checkpoint fix — break after completion checkpoint

At line 2833, after `trigger_checkpoint "completion"`, add `break` to exit the monitor loop. This prevents the loop from re-entering and triggering a second checkpoint.

### D11: auto_replan stdout — redirect both streams

Change line 2889 from `cmd_plan 2>>"$LOG_FILE"` to `cmd_plan &>>"$LOG_FILE"` to capture both stdout progress messages and stderr.
