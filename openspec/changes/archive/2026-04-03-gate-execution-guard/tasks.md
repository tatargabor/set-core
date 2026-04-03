# Tasks: Gate Execution Guard

- [x] Add `gates_executed = 0` counter at start of `_run_integration_gates()` in `merger.py`
- [x] Increment counter after each gate subprocess (build, test, e2e) actually runs
- [x] Add warning log + event emit at end when `gates_executed == 0` for non-infrastructure changes
- [x] Gates executed count visible in GATE_SKIP_WARNING event data for observability
