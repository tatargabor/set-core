# Tasks

## 1. Python: log gate success with timing

- [x] 1.1 In `lib/set_orch/merger.py` `_run_integration_gates()`, add INFO log for dep install success with elapsed_ms
- [x] 1.2 Add INFO log for build success with elapsed_ms
- [x] 1.3 Add INFO log for test success with elapsed_ms
- [x] 1.4 Add INFO log for e2e success with elapsed_ms
- [x] 1.5 Add summary line at end of all gates: "Integration gates for X: N/M passed in X.Xs"
- [x] 1.6 Track `gates_passed` and `gates_total` counters through the function

## 2. Python: emit granular gate events

- [x] 2.1 Emit `GATE_START` event before each gate step (dep_install, build, test, e2e) with `{gate, phase: "integration"}`
- [x] 2.2 Emit `GATE_PASS` event on each gate success with `{gate, elapsed_ms, phase: "integration"}`
- [x] 2.3 Emit `MERGE_START` before ff-only merge in `execute_merge_queue()`
- [x] 2.4 Emit `MERGE_COMPLETE` after successful merge with `{result: "success"}`

## 3. State: separate e2e from smoke

- [x] 3.1 In `lib/set_orch/state.py`, add `e2e_result: Optional[str] = None` and `gate_e2e_ms: int = 0` to Change dataclass
- [x] 3.2 In `merger.py`, update e2e gate to write `e2e_result` instead of `smoke_result`, and `gate_e2e_ms` for timing
- [x] 3.3 In `lib/set_orch/api/orchestration.py`, expose `e2e_result` and `gate_e2e_ms` in change response

## 4. Web: GateBar E2E icon + redispatch status

- [x] 4.1 In `web/src/lib/api.ts`, add `e2e_result` and `gate_e2e_ms` to ChangeInfo type
- [x] 4.2 In `web/src/components/GateBar.tsx`, add `{ name: 'e2e', status: e2e_result }` gate with label 'E'
- [x] 4.3 Add `redispatch: 'bg-amber-900 text-amber-300'` to statusStyle map

## 5. Web: activate EventFeed

- [x] 5.1 In `web/src/hooks/useWebSocket.ts`, add `gate_start`, `gate_pass`, `gate_fail`, `merge_start`, `merge_complete` to WSEvent type
- [x] 5.2 In `web/src/pages/Dashboard.tsx`, import and render EventFeed component (it exists at `web/src/components/EventFeed.tsx` but is unused)

## 6. Web: merge pipeline in ChangeTimeline

- [x] 6.1 In `web/src/components/ChangeTimeline.tsx`, add E2E phase between Smoke and Merge using `e2e_result` field
- [x] 6.2 Split Merge phase into Integration + Merge sub-steps when data is available

## 7. Python: save gate output for display

- [x] 7.1 In `lib/set_orch/merger.py` `_run_integration_gates()`, save gate output (last 2000 chars stdout) to state fields: `build_output`, `test_output`, `e2e_output` — for both pass and fail cases
- [x] 7.2 In `lib/set_orch/state.py`, add `build_output`, `test_output`, `e2e_output` Optional[str] fields to Change dataclass

## 8. Web: Gate Logs display

- [x] 8.1 In `web/src/lib/api.ts`, add `build_output`, `test_output`, `e2e_output` to ChangeInfo (they may already exist — verify and add if missing)
- [x] 8.2 In `web/src/components/GateDetail.tsx`, render gate output logs for build/test/e2e — expandable sections showing the command output with pre-wrapped monospace text
- [x] 8.3 Wire GateDetail into ChangeTable — clicking a gate icon (B/T/E) shows its output in an expandable row or panel
