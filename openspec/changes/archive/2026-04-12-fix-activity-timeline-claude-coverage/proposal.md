# Change: fix-activity-timeline-claude-coverage

## Why

The Activity view currently tracks only gate and merge time — on a typical 8h orchestration run it reports ~98% idle, because the biggest time sinks are invisible:

- **Agent sessions** (DISPATCH → CHANGE_DONE): the agent runs as a separate `claude -p` process in a worktree (ralph loop) and never emits `LLM_CALL` events to the orchestration event log. Implementing spans should fall back to `STEP_TRANSITION`, but `_set_step()` in `lib/set_orch/engine.py:1268` is dead code — it has no callsite, so `STEP_TRANSITION` is never emitted. Result: ~75% of wall time is unaccounted.
- **Orchestrator-side LLM calls** (verifier `review` / `spec_verify`, engine `replan`, profile `classify`): these DO emit `LLM_CALL` events with `purpose` + `duration_ms`, but `lib/set_orch/api/activity.py` has no handler for the `LLM_CALL` event type. Result: another ~25% of wall time lost.
- **Sentinel work**: `_detect_idle_gaps()` filters out every event with `_source == "sentinel"`, so sentinel LLM activity is also invisible. Sentinel runs in parallel with the main pipeline and should appear on its own lane without affecting idle detection.

Operators cannot answer "where did the 8 hours go?" — the current breakdown says "98% idle" which is false and misleading.

## What Changes

### 1. `LLM_CALL` → span in the activity aggregator

`lib/set_orch/api/activity.py` learns to handle `LLM_CALL` events:
- Each event produces a span with `category = f"llm:{purpose}"` (e.g., `llm:review`, `llm:spec_verify`, `llm:replan`, `llm:classify`, plus any future purpose).
- `end = event.ts`, `start = event.ts - data.duration_ms` (the event is emitted *after* the call returns).
- `change` field is copied from the event (may be empty for cross-change calls like `classify`).
- Model and cost fields are preserved in the span's `detail` for tooltip display.

### 2. `DISPATCH` → implementing span fallback

Until `_set_step()` is wired into the engine, reconstruct implementing spans from `DISPATCH` events:
- Open an implementing span when `DISPATCH` is seen for a change.
- Close it at the first of: next `CHANGE_DONE` for the same change, next `DISPATCH` for the same change (redispatch), `MERGE_START` for the same change, or end of event stream.
- When `STEP_TRANSITION` events are present (future), they take precedence and this fallback is skipped.

### 3. Sentinel activity on its own lane

Sentinel `LLM_CALL` events (from `.set/sentinel/events.jsonl`) produce spans with `category = f"sentinel:llm:{purpose}"`. The `_detect_idle_gaps()` filter still excludes sentinel events from idle detection (sentinel running doesn't mean the pipeline is active), but the spans themselves ARE emitted so the Activity view shows the sentinel lane with its real work.

### 4. Gap-detection tightening

`_detect_idle_gaps()` currently only checks event-to-event gaps. After adding implementing and LLM spans it must also check span coverage: a gap that's fully covered by any span (implementing, llm, gate, merge, etc.) is NOT idle. Walk the union of spans and emit idle only for intervals that no span touches.

### 5. Frontend: category ordering + color palette

`web/src/components/ActivityView.tsx` and the `CATEGORY_ORDER` constant in `activity.py` learn the new categories:
- `implementing` (already present, was unused)
- `llm:review`, `llm:spec_verify`, `llm:replan`, `llm:classify`
- `sentinel:llm:*`

The Gantt lane renderer skips empty lanes (already does), so only the purposes actually observed in the run get displayed. Color map in `ActivityView.tsx` is extended with a distinct hue for LLM categories (warm tones) and sentinel (muted).

## Capabilities

### Modified Capabilities
- `activity-timeline-api` — add `LLM_CALL` event handling, DISPATCH-based implementing fallback, span-coverage-aware idle gap detection, sentinel lane.

## Impact

- `lib/set_orch/api/activity.py` — new event handlers, new category ordering, reworked `_detect_idle_gaps()`
- `web/src/components/ActivityView.tsx` — new color entries, new category labels
- `tests/unit/test_activity_llm_spans.py` — new unit tests (synthetic event streams → expected spans)
- `openspec/changes/fix-activity-timeline-claude-coverage/specs/activity-timeline-api/spec.md` — MODIFIED requirement with new scenarios

## Out of Scope

- Wiring `_set_step()` into the engine (`engine.py:1268` → dispatcher/verifier callsites). This would fix the root cause of missing `STEP_TRANSITION` events but touches hot engine code. Tracked as a separate change to keep this one data-only and safe to deploy against running orchestrations.
- Per-turn session granularity from `~/.claude/projects/<wt>/*.jsonl`. That would give millisecond-accurate agent turn timing but requires filesystem scans per request. Future work.
- Cost/billing aggregation from `LLM_CALL.cost_usd`. Orthogonal feature.
- Real-time WebSocket streaming. Already OUT in the parent `activity-timeline` change.
