# Design: learnings-web-pipeline

## Context

The orchestration system generates learning data at four independent capture points: agent reflections (per-worktree `.claude/reflection.md`), review findings (JSONL + summary MD), gate statistics (in Change state extras), and sentinel findings (JSON). These data sources are stored in different formats and locations. The web dashboard currently shows gate results per-change (GateBar/GateDetail) and sentinel findings (SentinelPanel), but has no unified learnings view and no visibility into reflections or review findings.

Key broken feedback loops:
- `get_previous_iteration_summary()` exists in loop_prompt.py but is never called
- `orch_remember()`/`orch_recall()` are defined in orch_memory.py but called nowhere
- Review findings JSONL is not consumed by retry context builder
- State transitions are emitted as events but no API exposes them per-change

## Goals / Non-Goals

**Goals:**
- Close the three broken feedback loops (reflection → prompt, findings → retry, stats → memory)
- Expose all learning data via REST API endpoints
- Provide a unified Learnings tab on the web dashboard with drill-down
- Add per-change timeline detail view sourced from events.jsonl

**Non-Goals:**
- Cross-run trending/comparison (future — requires run metadata)
- Auto-generated rule suggestions from findings (future)
- WebSocket streaming for learnings (REST polling is adequate for non-real-time data)
- Modifying the gate pipeline or adding new gate types

## Decisions

### D1: Learnings data stays in existing storage — no new database or file format

All learning data already exists on disk (JSONL, MD, state JSON, events JSONL). The API endpoints aggregate at query time rather than maintaining a separate learnings store.

**Why:** Adding a new storage layer creates sync complexity. The data volume is small (tens of entries per run). Query-time aggregation from existing files is fast enough.

**Alternative considered:** Dedicated `learnings.json` file written at gate/merge time. Rejected because it duplicates data and requires new write paths.

### D2: Gate stats computed from state, not accumulated separately

The `/gate-stats` endpoint iterates over `state["changes"]` and aggregates gate results from each change's extras dict. Per-gate results are stored as `{gate}_result` (pass/fail/skip) and `gate_{gate}_ms` (timing) in Change extras. No running accumulator.

**Why:** State already contains all gate data. An accumulator would need reset logic and crash recovery. Computing from state is idempotent.

### D3: Timeline reconstructed from orchestration-state-events.jsonl, not stored in Change

The `/changes/{name}/timeline` endpoint reads `orchestration-state-events.jsonl` (path resolution follows existing pattern in api.py line 1548: first `project_path / "orchestration-state-events.jsonl"`, then fallback to `project_path / "wt" / "orchestration" / "orchestration-state-events.jsonl"`). It filters for `STATE_CHANGE` events matching the change name and returns sorted transitions.

**Why:** The events file already captures transitions with timestamps via `update_change_field()` in state.py (line 471-479 emits STATE_CHANGE events with `{"from": old_status, "to": new_status}`). Adding a `transitions[]` field to the Change dataclass would duplicate data and require migration.

**Trade-off:** Requires file I/O on each timeline request. Mitigated by: events files are small (< 1MB), rotated at 1MB, and the endpoint is not high-frequency.

### D4: Reflection injection is additive, not replacing prompt content

The previous iteration's reflection is injected by calling `get_previous_iteration_summary(wt_path)` (already defined at loop_prompt.py:202 but never called) inside `build_claude_prompt()` (loop_prompt.py:23). When non-empty, it's added as a new section after `prev_text` and before the reflection instruction.

**Why:** Reflection content is supplementary context, not task definition. The agent should still receive the full task prompt.

### D5: LearningsPanel is a top-level Dashboard tab, not embedded in other views

Learnings get their own tab rather than being scattered across Changes/Sessions/etc. The Dashboard.tsx PanelTab type (currently: 'changes' | 'phases' | 'plan' | ... | 'battle') is extended with 'learnings'. The tab is always visible (not conditionally hidden like Audit or Sentinel).

**Why:** Learnings span multiple changes and dimensions. A unified view with sections is more discoverable than per-change fragments. The existing pattern (Digest, Sentinel) shows that cross-cutting views work well as dedicated tabs.

### D6: Reflection memory saving filters trivial content and happens in cli.py

Only reflections with >50 chars and not matching trivial patterns ("No notable issues") are saved to memory via `orch_remember()`. The save happens in cli.py (where `build_claude_prompt` is called, around line 943) after the agent iteration loop completes — not in the dispatcher, because the dispatcher manages multi-change orchestration while reflection is per-worktree.

**Why:** Trivial reflections add noise to memory. The orchestrator runs many iterations — unfiltered remember calls would flood memory.

### D7: Review findings from JSONL are injected into retry context for the same change only

When building retry context for a review failure, `_build_unified_retry_context()` (verifier.py:411) receives new `change_name` and `findings_path` parameters. It reads JSONL entries matching `change_name` and includes the latest attempt's issues. All callers (build retry at line 1942, test retry at line 1978, review retry at ~2160) are updated to pass these parameters where context is available.

**Why:** Cross-change findings are noise in a retry prompt. The agent needs to know what was wrong with THIS change's code, not other changes.

### D8: Terminal learnings persistence via `_persist_run_learnings()` helper

A new `_persist_run_learnings(state_file)` helper in engine.py consolidates all end-of-run memory saves. It is called at each terminal state site alongside `_generate_review_findings_summary_safe()` (at lines 345, 875, 894, 918, 946, 960). The helper reads the review-findings JSONL from `wt/orchestration/review-findings.jsonl` (resolved relative to state_file as `os.path.join(os.path.dirname(state_file), "wt", "orchestration", "review-findings.jsonl")`).

**Why:** Consolidating memory saves in one helper avoids copy-pasting `orch_remember()` calls at 6+ terminal state sites.

## Risks / Trade-offs

- **[Risk] Reflection injection increases prompt size** → Mitigation: Reflection is typically 3-5 bullet points (~200 chars). Negligible compared to task context.
- **[Risk] Review findings JSONL grows unbounded across runs** → Mitigation: Not addressed in this change (documented as known limitation). Future: add run boundary markers or rotation.
- **[Risk] Timeline endpoint reads rotated event archives** → Mitigation: Only last 3 archives kept (existing rotation policy). File reads are fast for < 1MB files.
- **[Risk] `orch_remember()` calls at terminal state add latency** → Mitigation: `set-memory` CLI has 30s timeout, calls are fire-and-forget (failure logged, not blocking).

## Open Questions

- Should the JSONL get run boundary markers (run_id per entry) to enable per-run filtering in the web UI? (Deferred — not blocking for initial implementation.)
