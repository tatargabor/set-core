## 1. API events endpoint reads the live stream

- [ ] 1.1 In `lib/set_orch/api/orchestration.py::get_events` (line 1640), replace the single `orchestration-state-events.jsonl` lookup with a 4-step resolver: live (`<project>/orchestration-events.jsonl`) → narrow (`<project>/orchestration-state-events.jsonl`) → legacy nested live (`<project>/set/orchestration/orchestration-events.jsonl`) → legacy nested narrow (`<project>/set/orchestration/orchestration-state-events.jsonl`). Returns the FIRST file that exists. [REQ: events-api-prefers-live-stream]
- [ ] 1.2 Preserve the existing `type` filter and `limit` semantics — applied to whichever file resolves. [REQ: events-api-prefers-live-stream]
- [ ] 1.3 Add a 1-line debug log on resolution: `logger.debug("events endpoint resolved %s for project %s", events_file, project)` so operators can trace which file the API picked. [REQ: events-api-prefers-live-stream]
- [ ] 1.4 When neither file exists, return `{"events": []}` (preserves current behavior). [REQ: events-api-prefers-live-stream]

## 2. Rotated-cycle inclusion in the events endpoint

- [ ] 2.1 In `lib/set_orch/api/orchestration.py::get_events`, when the resolved live file's event count is `< limit` AND `paths.LineagePaths` (or equivalent) reports rotated cycles via `rotated_event_files`, prepend events from the most recent rotated cycle(s) until either `limit` is reached or no more cycles remain. [REQ: events-api-includes-rotated-cycles]
- [ ] 2.2 Rotated cycles are read in CHRONOLOGICAL order (oldest cycle first); the live tail is the LAST chunk so the result remains time-ordered overall. [REQ: events-api-includes-rotated-cycles]
- [ ] 2.3 Apply the `type` filter equally to rotated cycles. [REQ: events-api-includes-rotated-cycles]
- [ ] 2.4 If `rotated_event_files` enumeration fails (path resolver missing, glob exception), log a WARNING with `exc_info=True` and proceed with just the live tail — never fail the endpoint because of rotation lookup. [REQ: events-api-includes-rotated-cycles]

## 3. State reconstruction prefers the live stream

- [ ] 3.1 In `lib/set_orch/state.py::reconstruct_state_from_events`, when `events_path` is None, apply the same 4-step resolver chain as the API endpoint (live → narrow → legacy nested live → legacy nested narrow). [REQ: state-reconstruct-uses-live-stream]
- [ ] 3.2 Log at INFO which file was selected: `logger.info("State reconstruct using events from %s", events_path)`. [REQ: state-reconstruct-uses-live-stream]
- [ ] 3.3 Add a `# TODO(observability-rotation):` comment block above the resolver call documenting that future rotation-aware reconstruction is a separate change. [REQ: state-reconstruct-uses-live-stream]

## 4. VERIFY_GATE event payload schema unification

- [ ] 4.1 In `lib/set_orch/verifier.py:4062` (uncommitted-work check emit), add `"gate": "uncommitted_check"` to the data dict alongside the existing `result`/`reason`/`uncommitted_check` fields. [REQ: verify-gate-event-schema-consistent]
- [ ] 4.2 In `lib/set_orch/verifier.py:4340-4349` (retry path emit), add `"gate": pipeline.stop_gate or ""` to the `_retry_evt` dict. The existing `"stop_gate"` field is preserved for back-compat. [REQ: verify-gate-event-schema-consistent]
- [ ] 4.3 In `lib/set_orch/verifier.py:4363-4372` (failed path emit), add `"gate": pipeline.stop_gate or ""` to the `_failed_evt` dict. The existing `"stop_gate"` field is preserved for back-compat. [REQ: verify-gate-event-schema-consistent]
- [ ] 4.4 In `lib/set_orch/verifier.py:4437-4455` (pass path emit), add `"gate": ""` and `"result": "pass"` to the `_event_data` dict. The empty `gate` value signals "all gates passed, no specific stop gate"; consumers can detect pass via `result == "pass"`. [REQ: verify-gate-event-schema-consistent]
- [ ] 4.5 Verify by inspection of `merger.py:1793,1851,1860,1868,2022,2195,2269,2407` that all integration-phase emits already include `gate` and `result` keys (no changes needed there). Add a one-line comment block above the verifier emits: `# VERIFY_GATE schema: every emit MUST include "gate" and "result" keys. See spec verify-gate-event-schema.` [REQ: verify-gate-event-schema-consistent]

## 5. paths.py docstring clarification

- [ ] 5.1 In `lib/set_orch/paths.py`, on `events_file` property (line 499), expand the docstring to: `"Live event stream — primary source for the API and state reconstruction. Contains STATE_CHANGE, GATE_*, MERGE_*, LLM_CALL, ITERATION_END, heartbeat, and most lifecycle events."` [REQ: events-api-prefers-live-stream]
- [ ] 5.2 On `state_events_file` property (line 507), expand the docstring to: `"Narrow event stream — back-compat source for forensics and migrations. Currently receives DIGEST_*, MEMORY_HYGIENE, SHUTDOWN_*, CHANGE_STOPPING/STOPPED. Readers should prefer events_file."` [REQ: events-api-prefers-live-stream]

## 6. Tests

- [ ] 6.1 Add `tests/unit/test_events_api_resolution.py` with cases: (a) live stream present + narrow present → API returns live events, (b) live absent + narrow present → API returns narrow events, (c) both absent + legacy nested live present → API returns nested live, (d) all four absent → empty list. Use `tmp_path` fixtures with hand-crafted JSONL. [REQ: events-api-prefers-live-stream]
- [ ] 6.2 Add a test for `type` filter equivalence: filter `type=STATE_CHANGE` returns same count whether file is live or narrow. [REQ: events-api-prefers-live-stream]
- [ ] 6.3 Add a test for `limit` honored: with 100 events in the file and `limit=10`, return the LAST 10 in time order. [REQ: events-api-prefers-live-stream]
- [ ] 6.4 Add `tests/unit/test_events_api_rotation.py` with cases: (a) live tail has 5 events, limit=20, one rotated cycle has 30 events → returns 20 events with rotated content first then live tail, (b) limit=3 with 50 live events and rotation present → returns last 3 live events only, (c) rotated_event_files raises → returns live tail only with WARNING logged. [REQ: events-api-includes-rotated-cycles]
- [ ] 6.5 Add `tests/unit/test_state_reconstruct_resolver.py`: write a state file + a live events stream with 3 STATE_CHANGE events, point reconstruct at the project dir without `events_path` arg, confirm the live stream's STATE_CHANGE events are replayed and the resulting state.changes have the corresponding statuses. [REQ: state-reconstruct-uses-live-stream]
- [ ] 6.6 Add `tests/unit/test_verify_gate_event_schema.py` with cases: (a) a successful pipeline emits VERIFY_GATE with `gate=""` and `result="pass"`, (b) a retry emits with `gate=<stop_gate>` and `result="retry"`, (c) a failed exhaustion emits with `gate=<stop_gate>` and `result="failed"`, (d) the uncommitted-check emit has `gate="uncommitted_check"` and `result="fail"`. Use a stub pipeline with `stop_gate="build"` and capture emits via a fake EventBus. [REQ: verify-gate-event-schema-consistent]
- [ ] 6.7 Add a regression test sweeping the file: `grep -nE 'event_bus\.emit\("VERIFY_GATE"' lib/set_orch/verifier.py lib/set_orch/merger.py | wc -l` SHALL return at least 12. (Sanity: prevents accidental removal of an emit site without spec review.) [REQ: verify-gate-event-schema-consistent]

## 7. Manual verification (no unit-test substitute)

- [ ] 7.1 Restart `set-web` after the change deploys: `systemctl --user restart set-web && sleep 5`. Open `http://localhost:7400/p/micro-web-run-20260501-1805/orch?tab=timeline` (or whichever tab consumes `/api/{project}/events`). Confirm the event list is populated (expect 5,000+ events). [REQ: events-api-prefers-live-stream]
- [ ] 7.2 Curl-verify: `curl -s http://localhost:7400/api/micro-web-run-20260501-1805/events?limit=100 | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('events',[])))"` returns a number `>= 100`. [REQ: events-api-prefers-live-stream]
- [ ] 7.3 Curl-verify: `curl -s http://localhost:7400/api/micro-web-run-20260502-0245/events?type=VERIFY_GATE | python3 -c "import json,sys; d=json.load(sys.stdin); evs=d.get('events',[]); empty=sum(1 for e in evs if not e.get('data',{}).get('gate'))/max(len(evs),1); print(f'empty-gate ratio: {empty:.2%}')"` returns 0% (no events with empty `gate` from the verifier paths after the fix; pre-fix this was ~75%). [REQ: verify-gate-event-schema-consistent]

## 8. Documentation

- [ ] 8.1 Add a 1-paragraph note to `docs/howitworks/en/06-monitor-and-watchdog.md` (or wherever event sources are first described) clarifying which event file is the canonical reader source. Cite the new resolver behavior. [REQ: events-api-prefers-live-stream]

## Acceptance Criteria (from spec scenarios)

### Capability: events-api

- [ ] AC-1: WHEN both `<project>/orchestration-events.jsonl` and `<project>/orchestration-state-events.jsonl` exist AND `/api/{project}/events` is called THEN the response contains events from `orchestration-events.jsonl` (the live stream). [REQ: events-api-prefers-live-stream, scenario: live-stream-wins-over-narrow]
- [ ] AC-2: WHEN only `<project>/orchestration-state-events.jsonl` exists AND `/api/{project}/events` is called THEN the response contains events from the narrow stream (back-compat). [REQ: events-api-prefers-live-stream, scenario: narrow-stream-fallback]
- [ ] AC-3: WHEN neither file exists at the project root AND a legacy nested `set/orchestration/orchestration-events.jsonl` exists THEN the response contains events from the legacy nested live file. [REQ: events-api-prefers-live-stream, scenario: legacy-nested-live-fallback]
- [ ] AC-4: WHEN none of the four files exist THEN the response is `{"events": []}`. [REQ: events-api-prefers-live-stream, scenario: no-events-file-returns-empty]
- [ ] AC-5: WHEN the resolved file contains 100 events and `limit=10` THEN the response contains the LAST 10 events in time order. [REQ: events-api-prefers-live-stream, scenario: limit-honored-on-resolved-file]
- [ ] AC-6: WHEN `type=STATE_CHANGE` is supplied AND the resolved file has 5 STATE_CHANGE events mixed with 200 other events THEN the response contains exactly those 5 STATE_CHANGE events (capped by limit). [REQ: events-api-prefers-live-stream, scenario: type-filter-applied-to-resolved-file]
- [ ] AC-7: WHEN `rotated_event_files` returns 1 rotated cycle with 30 events AND the live tail has 5 events AND `limit=20` THEN the response contains 20 events ordered as `rotated_cycle_events[-15:] + live_tail` (chronological). [REQ: events-api-includes-rotated-cycles, scenario: rotation-fills-up-to-limit]
- [ ] AC-8: WHEN the live tail alone has more than `limit` events THEN no rotated cycles are read. [REQ: events-api-includes-rotated-cycles, scenario: live-tail-sufficient]
- [ ] AC-9: WHEN `rotated_event_files` enumeration raises THEN a WARNING is logged with `exc_info=True` AND the response contains only the live tail (no exception propagated). [REQ: events-api-includes-rotated-cycles, scenario: rotation-lookup-failure-non-fatal]

### Capability: verify-gate-event-schema

- [ ] AC-10: WHEN the verify pipeline passes all gates AND the success VERIFY_GATE event is emitted THEN the event's data dict contains `"gate": ""` AND `"result": "pass"`. [REQ: verify-gate-event-schema-consistent, scenario: pass-emit-has-gate-and-result-keys]
- [ ] AC-11: WHEN the verify pipeline triggers a blocking-failure retry on gate `build` AND the retry VERIFY_GATE event is emitted THEN the event's data dict contains `"gate": "build"` AND `"result": "retry"`. [REQ: verify-gate-event-schema-consistent, scenario: retry-emit-has-gate-and-result-keys]
- [ ] AC-12: WHEN the verify pipeline exhausts retries on gate `e2e` AND the failed VERIFY_GATE event is emitted THEN the event's data dict contains `"gate": "e2e"` AND `"result": "failed"`. [REQ: verify-gate-event-schema-consistent, scenario: failed-emit-has-gate-and-result-keys]
- [ ] AC-13: WHEN the uncommitted-work check finds dirty files AND emits a VERIFY_GATE event THEN the event's data dict contains `"gate": "uncommitted_check"` AND `"result": "fail"`. [REQ: verify-gate-event-schema-consistent, scenario: uncommitted-check-has-gate-and-result-keys]
- [ ] AC-14: WHEN any of the merger.py integration-phase VERIFY_GATE emit sites fires THEN the event's data dict contains both `"gate"` and `"result"` keys (no schema regression in merger). [REQ: verify-gate-event-schema-consistent, scenario: merger-emits-already-conformant]

### Capability: state-reconstruct-uses-live-stream

- [ ] AC-13: WHEN `reconstruct_state_from_events(state_path)` is called without an explicit `events_path` AND a live stream `orchestration-events.jsonl` exists in the same directory THEN the live stream is read. [REQ: state-reconstruct-uses-live-stream, scenario: reconstruct-prefers-live-stream]
- [ ] AC-14: WHEN the live stream contains 12 STATE_CHANGE events for 12 different changes THEN the reconstructed state has 12 changes with their final statuses set from the events (modulo the existing "running → stalled" rule for live processes). [REQ: state-reconstruct-uses-live-stream, scenario: reconstruct-replays-state-changes]
- [ ] AC-15: WHEN only the narrow stream exists THEN the reconstruct falls back to it (back-compat preserved). [REQ: state-reconstruct-uses-live-stream, scenario: reconstruct-narrow-fallback]
