## Context

The orchestrator TUI (`gui/tui/orchestrator_tui.py`) is a Textual-based live dashboard that reads `orchestration-state.json` and displays change progress in a table with a header bar. After 4 MiniShop E2E runs, several information gaps have been identified.

Current state file has rich per-change data (`started_at`, `completed_at`, `smoke_status`, `smoke_fixed`) that the TUI doesn't use yet.

## Goals / Non-Goals

**Goals:**
- Show wall clock elapsed time alongside active time in the header
- Show per-change duration in the table (how long each change took)
- Add a summary row at the bottom of the change table
- Distinguish smoke-fixed from smoke-passed in gate display

**Non-Goals:**
- Changing the state file format (all needed data already exists)
- Run comparison across multiple orchestration runs
- Watchdog event counters in the header (nice-to-have for later)
- Changing the log panel or its behavior

## Decisions

**D1: Elapsed time calculation**
- Running: `now() - started_epoch`
- Finished (`done`/`stopped`/`time_limit`): `state_file.mtime - started_epoch`
- Rationale: Using mtime for finished runs gives accurate end time without adding a new field to the state format. The monitor writes state on every status transition, so mtime closely matches actual end time.

**D2: Per-change duration from ISO timestamps**
- Use `started_at` and `completed_at` fields (ISO 8601 strings already in state)
- Running changes: `now() - started_at`
- Pending/dispatched: show `-`
- Parse with `datetime.fromisoformat()` (Python 3.7+)
- Rationale: No new state fields needed; timestamps are already populated by the monitor.

**D3: Summary row as last table row**
- Add a styled summary row at the bottom of the DataTable (not a separate widget)
- Shows: merged/total count, average duration, total billed tokens (input+output)
- Rationale: Keeps everything in one scrollable table. Simpler than a separate footer widget.

**D4: Smoke fix indicator in gate_str**
- Extend `format_gates()` to check `smoke_status` field
- If `smoke_result == "pass"` and change has `smoke_fixed: true` or `smoke_status == "fixed"`: show `S✓(fix)`
- Rationale: Distinguishes first-pass smoke success from required-fix smoke success. Important for quality assessment.

## Risks / Trade-offs

- [Risk] `started_at`/`completed_at` might be missing on older state files → Mitigation: show `-` when fields are absent, same as current behavior for missing data
- [Risk] Summary row styling may conflict with DataTable cursor → Mitigation: use dim styling to visually separate from data rows
- [Trade-off] Using mtime for elapsed end time is slightly imprecise (~15s poll interval) → Acceptable for dashboard display purposes
