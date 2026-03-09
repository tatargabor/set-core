## 1. Elapsed Time in Header

- [x] 1.1 Add elapsed time calculation to `_update_header()` using `started_epoch` — for finished runs use state file mtime, for running use `now()` *(already implemented, verify correctness)*
- [x] 1.2 Display `Elapsed: <duration>` in header line2 between Active and limit text

## 2. Per-Change Duration Column

- [x] 2.1 Add helper function `format_change_duration(change)` — parse `started_at`/`completed_at` ISO timestamps, return formatted duration or `-`
- [x] 2.2 Add `Dur` column to DataTable after `Iter` column
- [x] 2.3 Populate duration for each change row: completed changes use `completed_at - started_at`, running changes use `now() - started_at`, pending/dispatched show `-`

## 3. Summary Row

- [x] 3.1 Add summary row as last row in `_update_table()` — show merged/total count, average duration, total billed tokens (input+output)
- [x] 3.2 Style summary row with `[bold]`/`[dim]` markup to visually separate from data rows

## 4. Smoke Fix Indicator

- [x] 4.1 Update `format_gates()` to check `smoke_fixed`/`smoke_status` fields — show `S✓(fix)` when smoke passed after fix cycle
- [x] 4.2 Verify gate display with state data that has `smoke_status: "fixed"` or `smoke_fixed: true`

## 5. Tests

- [x] 5.1 Add test for `format_change_duration()` — completed, running, pending cases
- [x] 5.2 Add test for smoke fix gate display — `S✓` vs `S✓(fix)` vs `S✗`
- [x] 5.3 Add test for summary row token calculation
