# Tasks

## 1. Python: current_step field

- [x] 1.1 In `lib/set_orch/state.py`, add `current_step: Optional[str] = None` to Change dataclass and include in serialization list
- [x] 1.2 Add helper `_set_step(state_file, change_name, step, event_bus)` in `lib/set_orch/engine.py` that updates current_step and emits STEP_TRANSITION event

## 2. Python: set step at transitions

- [x] 2.1 In `lib/set_orch/dispatcher.py` `dispatch_change()`, set `current_step = "planning"` after dispatch
- [x] 2.2 In `lib/set_orch/dispatcher.py` `resume_change()`, set `"fixing"` if retry_context else `"implementing"`
- [x] 2.3 In `lib/set_orch/engine.py` `_poll_active_changes()`, when agent done → set `"integrating"`
- [x] 2.4 In `lib/set_orch/merger.py` `_run_integration_gates()`, e2e fail + redispatch → set `"fixing"`
- [x] 2.5 In `lib/set_orch/merger.py` `execute_merge_queue()`, gates pass → set `"merging"`
- [x] 2.6 In `lib/set_orch/merger.py` `execute_merge_queue()`, merge success → set `"archiving"`, after archive → set `"done"`

## 3. Web: StepBar component

- [x] 3.1 In `web/src/lib/api.ts`, add `current_step?: string` to ChangeInfo type
- [x] 3.2 Create `web/src/components/StepBar.tsx` — renders P I F M A badges with color logic (green=done, blue+pulse=current, gray=pending, amber=fixing)
- [x] 3.3 In `web/src/hooks/useWebSocket.ts`, add `step_transition` to WSEvent type

## 4. Web: integrate StepBar in views

- [x] 4.1 In `web/src/components/ChangeTable.tsx`, render StepBar alongside GateBar for each change
- [x] 4.2 In `web/src/components/PhaseView.tsx`, render StepBar alongside GateBar
