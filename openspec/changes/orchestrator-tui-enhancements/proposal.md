## Why

The orchestrator TUI (`gui/tui/orchestrator_tui.py`) shows active time but not wall clock (elapsed) time, making it hard to know how long a run has actually been going. Per-change duration is also missing — you can't see which changes are slow. After 4 MiniShop E2E runs, these gaps are clear pain points when monitoring orchestration progress.

## What Changes

- **Wall clock (elapsed) time in header** — show `Elapsed: 2h00m` alongside `Active: 1h18m`, computed from `started_epoch`. For finished runs (`done`/`stopped`/`time_limit`), use state file mtime as end time. *(Already implemented)*
- **Per-change duration column** — new `Dur` column in the change table, computed from `started_at` → `completed_at` (or now if still running)
- **Summary row at table bottom** — total merged/total, average duration, total billed tokens
- **Smoke fix indicator** — show `S✓(fix)` instead of plain `S✓` when `smoke_fixed: true` or `smoke_status` indicates a fix occurred

## Capabilities

### New Capabilities
- `tui-elapsed-time`: Wall clock elapsed time display in orchestrator TUI header
- `tui-change-duration`: Per-change duration column and summary row in change table
- `tui-smoke-indicator`: Enhanced smoke gate display showing fix attempts

### Modified Capabilities

## Impact

- `gui/tui/orchestrator_tui.py` — header rendering, table columns, gate formatting
- `tests/tui/test_orchestrator_tui.py` — new tests for duration calculation and smoke display
- No dependency changes, no API changes
