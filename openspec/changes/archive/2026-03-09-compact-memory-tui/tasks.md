## 1. Backend: Project filtering in query_report

- [x] 1.1 Add `project=None` parameter to `query_report()` in `lib/metrics.py`
- [x] 1.2 Add project prefix `LIKE` clause to all SQL queries in `query_report()` when project is set
- [x] 1.3 Add `project` field to the returned dict so the TUI knows which filter was applied

## 2. TUI: Project auto-detection and CLI plumbing

- [x] 2.1 Add `--project` flag parsing to `cmd_tui()` in `lib/memory/ui.sh`
- [x] 2.2 Auto-detect project from git root basename when no `--project` flag is given
- [x] 2.3 Pass project to `query_report()` and `set-memory stats` calls in the inline Python

## 3. TUI: 3-column ANSI layout

- [x] 3.1 Add terminal width detection with `os.get_terminal_size()` and fallback logic (< 120 = old layout)
- [x] 3.2 Implement column rendering helper: build each column as list of lines, then merge side-by-side with `│` separators
- [x] 3.3 Render left column: header + DB stats + usage signals + relevance histogram + top tags
- [x] 3.4 Render center column: hook overhead + layer table + daily trend sparklines
- [x] 3.5 Render right column: recent sessions list with worktree name abbreviation
- [x] 3.6 Render header bar with project name and box-drawing top border
- [x] 3.7 Render footer with refresh interval message and box-drawing bottom border

## 4. Session list formatting

- [x] 4.1 Extract session list from `query_report()` data, limit to 15 most recent
- [x] 4.2 Implement worktree name abbreviation: strip base project prefix, show `(main)` for exact match, truncate to 22 chars
- [x] 4.3 Format each session line: `MM-DD HH:MM  <wt-name>  <inj>  <tok>  <cites>`

## 5. Testing (phase 1)

- [x] 5.1 Verify `query_report(project="set-core")` returns only set-core sessions (manual test from set-core dir)
- [x] 5.2 Verify `set-memory tui --once` from a project dir shows project-scoped data
- [x] 5.3 Verify narrow terminal (< 120) still renders single-column layout

## 6. Backend: Daily activity + importance data

- [x] 6.1 Add `daily_sessions` to `query_report()` return: per-day session count + token total
- [x] 6.2 Change default `since_days` to 30 when project filter is active

## 7. TUI: Right column enrichment

- [x] 7.1 Replace session list with daily activity table (date, session count, tokens) — top section
- [x] 7.2 Add importance histogram from `set-memory stats` to left column below relevance
- [x] 7.3 Show top tags (filtered to non-source tags) in right column below daily activity

## 8. Testing (phase 2)

- [x] 8.1 Verify daily activity table shows correct per-day data
- [x] 8.2 Verify 30d default when project-scoped, 7d when global
