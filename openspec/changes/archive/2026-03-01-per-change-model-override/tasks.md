## 1. Plan JSON Schema & State Init

- [x] 1.1 Add `model` (default null), `skip_review` (default false), `skip_test` (default false) fields to the change object in `init_state()` plan JSON parsing (~line 714)
- [x] 1.2 Add `default_model` to directives parsing in `monitor_loop()` (~line 2760) with default `"opus"`
- [x] 1.3 Add `change_type` field to state init (currently in plan JSON but not carried to state)

## 2. Model Resolution

- [x] 2.1 Create `resolve_change_model()` function implementing the 3-level fallback: change.model → default_model → heuristic(complexity, change_type)
- [x] 2.2 Update `dispatch_change()` (~line 2596) to call `resolve_change_model` and pass result to `wt-loop start --model`
- [x] 2.3 Update `resume_change()` (~line 2725) to call `resolve_change_model` and pass result to `wt-loop start --model`
- [x] 2.4 Pass `default_model` from `monitor_loop` through to dispatch/resume (via function params or global)

## 3. Gate Skip Logic

- [x] 3.1 In `handle_change_done()` (~line 3345), read `skip_test` from state and skip test execution when true, setting `test_result` to `"skipped"`
- [x] 3.2 In `handle_change_done()`, read `skip_review` from state and skip code review when true, setting `review_result` to `"skipped"`
- [x] 3.3 Update TUI status display to show `"skip"` for skipped gate results

## 4. Documentation

- [x] 4.1 Add model selection checklist item to `docs/plan-checklist.md` in Directives section
- [x] 4.2 Add gate skip checklist item to `docs/plan-checklist.md`
- [x] 4.3 Add "Model Selection Strategy" section to `docs/planning-guide.md` covering cost/quality tradeoffs and when to use sonnet vs opus
