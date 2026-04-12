# Tasks: fix-activity-timeline-claude-coverage

## 1. Backend: LLM_CALL span handling

- [x] 1.1 Add `LLM_CALL` handler in `_build_spans()` in `lib/set_orch/api/activity.py` — extract `purpose`, `duration_ms`, `model`, compute `start = ts - duration_ms`, `end = ts`, category `llm:{purpose}` for orchestration source and `sentinel:llm:{purpose}` for sentinel source. Preserve `model`, `cost_usd`, `input_tokens`, `output_tokens` in `detail` dict. [REQ: llm-call-spans]
- [x] 1.2 Handle missing or zero `duration_ms` defensively — if `duration_ms <= 0`, emit a zero-length span at `ts` (still useful as a marker) and log WARNING with the event data. [REQ: llm-call-spans]

## 2. Backend: DISPATCH-based implementing span fallback

- [x] 2.1 Track open implementing spans per change in `_build_spans()`. On `DISPATCH` event for change X, open a span with `category="implementing"`, `start=ts`, source marker `fallback=True`. [REQ: dispatch-implementing-fallback]
- [x] 2.2 Close the implementing span on any of: next `DISPATCH(change=X)`, `MERGE_START(change=X)`, `STATE_CHANGE(change=X, to in {failed, pending})`. NOTE: `CHANGE_DONE` is NOT a close trigger because a single dispatch can produce multiple `CHANGE_DONE` events as the verifier loops. Also handle `CHANGE_REDISPATCH` identically to `DISPATCH`. [REQ: dispatch-implementing-fallback]
- [x] 2.3 Flush any remaining open implementing spans at end of event stream — close at the **last event observed for that change** (not end-of-stream), so failed/abandoned changes don't produce wildly inflated spans. [REQ: dispatch-implementing-fallback]
- [x] 2.4 STEP_TRANSITION takes precedence: track changes that emit STEP_TRANSITION in a set, then post-filter dispatch-fallback implementing spans for those changes. [REQ: dispatch-implementing-fallback]
- [x] 2.5 Bonus: emit a `planning` span from `DIGEST_STARTED` to first `DISPATCH` to cover the pre-dispatch digest+decomposer+planner phase. [REQ: dispatch-implementing-fallback]

## 3. Backend: Span-coverage-aware idle detection

- [x] 3.1 Refactor `_detect_idle_gaps()` to build the union of all non-idle spans' intervals (merge overlapping), then walk complementary intervals over the event time range. Emit idle span for any complementary interval > 60s. [REQ: span-coverage-idle]
- [x] 3.2 Keep the existing sentinel/heartbeat event filter intact — only orchestration events count toward "no activity", but span coverage from LLM spans (including sentinel LLM) still suppresses idle emission. [REQ: span-coverage-idle]
- [x] 3.3 Add a log line at DEBUG level reporting: number of spans in union, number of idle gaps emitted, total idle ms. Helps debugging future false-idle cases. [REQ: span-coverage-idle]

## 4. Backend: Category ordering

- [x] 4.1 Update `CATEGORY_ORDER` in `activity.py` to include `llm:review`, `llm:spec_verify`, `llm:replan`, `llm:classify`, `sentinel:llm:review`, `sentinel:llm:spec_verify`, `sentinel:llm:replan`, `sentinel:llm:classify`. Position: after `implementing`/`fixing` but before gates, with sentinel LLM at the bottom near `sentinel`. [REQ: llm-call-spans]

## 5. Frontend: Color palette + category labels

- [x] 5.1 Extend the category color map in `web/src/components/ActivityView.tsx` with warm hues for `llm:*` (e.g., amber/yellow family) and muted cool hues for `sentinel:llm:*` (e.g., slate/blue-gray family). [REQ: frontend-llm-display]
- [x] 5.2 Add pretty labels for the new categories (e.g., `llm:review` → "LLM: Review", `sentinel:llm:spec_verify` → "Sentinel: Spec Verify"). [REQ: frontend-llm-display]
- [x] 5.3 Verify that empty-lane filtering still works — `sentinel:llm:*` lanes should only appear if sentinel actually ran LLM calls during the window. (No change required — existing filter in `Dashboard.tsx`/`ActivityView.tsx` filters by `data.spans` set, so categories with zero spans never appear.) [REQ: frontend-llm-display]
- [x] 5.4 Update the Activity header tooltip/label to note that `parallel_efficiency` may exceed 1.0 because sentinel LLM and verifier LLM can run in parallel with agent sessions. [REQ: frontend-llm-display]

## 6. Tests

- [x] 6.1 Create `tests/unit/test_activity_llm_spans.py`. [REQ: llm-call-spans]
- [x] 6.2 Test: `LLM_CALL` with `purpose=review`, `duration_ms=120000`, `ts=T` produces a span with `category=llm:review`, `start=T-120s`, `end=T`, `duration_ms=120000`. [REQ: llm-call-spans]
- [x] 6.3 Test: `LLM_CALL` with `_source=sentinel` produces `category=sentinel:llm:<purpose>`. [REQ: llm-call-spans]
- [x] 6.4 Test: `LLM_CALL` with missing/zero `duration_ms` produces a zero-length marker span (no crash). [REQ: llm-call-spans]
- [x] 6.5 Test: `DISPATCH` → `MERGE_START` pair produces an `implementing` span. (CHANGE_DONE deliberately not used as a close trigger — see task 2.2.) [REQ: dispatch-implementing-fallback]
- [x] 6.6 Test: `DISPATCH` → `DISPATCH` (redispatch) produces two `implementing` spans. [REQ: dispatch-implementing-fallback]
- [x] 6.7 Test: `DISPATCH` + `STEP_TRANSITION to=implementing` → only the STEP_TRANSITION span is emitted (DISPATCH fallback is suppressed). [REQ: dispatch-implementing-fallback]
- [x] 6.8 Test: implementing span + overlapping LLM span → `activity_time_ms > wall_time_ms` (parallel work correctly counted). [REQ: dispatch-implementing-fallback, llm-call-spans]
- [x] 6.9 Test: implementing span covers an event gap → no idle span emitted. [REQ: span-coverage-idle]
- [x] 6.10 Test: 5min gap with no covering span → idle span emitted; 30s gap with no covering span → NO idle span (below threshold). [REQ: span-coverage-idle]
- [x] 6.11 Bonus: test: `DIGEST_STARTED` → `DISPATCH` produces a `planning` span and suppresses idle. [REQ: dispatch-implementing-fallback]
- [x] 6.12 Bonus: test: open implementing span flushes to last-event-for-change, not end-of-stream. [REQ: dispatch-implementing-fallback]

## 7. Manual verification

- [x] 7.1 Run the endpoint against the live 9h craftbrew run via `curl http://localhost:7400/api/.../activity-timeline`. Result: wall=552m, activity=679m, implementing=507m (74.7%), llm:review=68m, llm:spec_verify=48m, planning=33m, idle=1m (0.1%). Activity time is 1.23x wall time due to verifier LLM overlap with implementing — semantically correct. [REQ: all]
- [x] 7.2 Verified frontend type-checks (`tsc --noEmit`) and builds (`pnpm build`) clean with new color/label additions. Bundle generated to `web/dist/`. [REQ: frontend-llm-display]
- [x] 7.3 No regression — pre-existing categories (gate:*, merge, dep-wait, manual-wait) still render. Breakdown table preserved, only new lanes added. [REQ: all]

## Acceptance Criteria

- [x] AC-1: WHEN the event log contains an `LLM_CALL` with `purpose=review` and `duration_ms=120000` at time T THEN a span is produced with `category=llm:review`, `start=T-120s`, `end=T`. (Verified by `test_llm_call_review_produces_span_with_computed_start`.) [REQ: llm-call-spans]
- [x] AC-2: WHEN the event log contains a `DISPATCH(change=X)` at T1 and `MERGE_START(change=X)` at T2 (and no `STEP_TRANSITION` for X) THEN an `implementing` span is produced with `start=T1`, `end=T2`, `change=X`. (Adjusted from CHANGE_DONE → MERGE_START because CHANGE_DONE fires multiple times per dispatch in real runs. Verified by `test_dispatch_to_merge_produces_implementing_span`.) [REQ: dispatch-implementing-fallback]
- [x] AC-3: WHEN a change has both `STEP_TRANSITION to=implementing` and `DISPATCH` events THEN only the STEP_TRANSITION-derived implementing span is emitted (DISPATCH fallback suppressed). (Verified by `test_step_transition_suppresses_dispatch_fallback`.) [REQ: dispatch-implementing-fallback]
- [x] AC-4: WHEN an `LLM_CALL` event is from `.set/sentinel/events.jsonl` (`_source=sentinel`) THEN the span category is `sentinel:llm:{purpose}`. (Verified by `test_sentinel_llm_call_uses_sentinel_prefix`.) [REQ: llm-call-spans]
- [x] AC-5: WHEN a gap in orchestration events is fully covered by an existing implementing or LLM span THEN no idle span is emitted for that gap. (Verified by `test_implementing_span_covers_event_gap`.) [REQ: span-coverage-idle]
- [x] AC-6: WHEN the endpoint is called on a real 9h run where previously 98% reported as idle THEN the reported idle percentage drops below 20%. **Result: 0.1% idle (1 minute / 552 minutes wall time).** [REQ: all]
- [x] AC-7: WHEN the Activity tab renders THEN new lanes `llm:review`, `llm:spec_verify`, `implementing`, `planning`, and `sentinel:llm:*` (if populated) appear with distinct colors and pretty labels. [REQ: frontend-llm-display]
