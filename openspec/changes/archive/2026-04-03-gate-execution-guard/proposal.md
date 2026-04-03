# Proposal: Gate Execution Guard

## Why

Integration gates (build/test/e2e) in `_run_integration_gates()` silently skip when no commands are detected. This happens when:
- `project-type.yaml` is missing (NullProfile loaded → no `detect_build_command()`)
- Profile doesn't detect commands for the project type
- Directives have no test/build/e2e commands configured

The function returns `True` (all gates pass) even when **zero gates actually executed**. This means changes merge without any quality validation — no build check, no tests, no e2e.

This caused run8 and run9 to merge 6/6 changes with gate_ms=0 and zero playwright results.

## What

Add a gate execution counter to `_run_integration_gates()`. After all gates run, if zero gates actually executed for a "feature" type change, emit a WARNING event and log it. This makes silent gate skips visible.

## Scope

- `lib/set_orch/merger.py` — `_run_integration_gates()`: count executed gates, warn if 0
- Small, focused change — ~20 lines
