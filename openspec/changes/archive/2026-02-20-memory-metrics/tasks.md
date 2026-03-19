## 1. Metrics Infrastructure

- [x] 1.1 Create `lib/metrics.py` with SQLite schema creation, insert helpers, and query functions (sessions, injections, citations tables)
- [x] 1.2 Add enable/disable flag file logic (`~/.local/share/set-core/metrics/.enabled`) with helper functions for check/create/remove
- [x] 1.3 Add metrics check function to `wt-hook-memory` — early return if flag file absent (zero overhead when disabled)

## 2. Hook Instrumentation (wt-hook-memory)

- [x] 2.1 Add timing instrumentation: `_timer_start` at entry, `_timer_end` at exit, compute `duration_ms` for each handler
- [x] 2.2 Add `_metrics_append()` bash function: parse relevance scores from proactive/recall JSON output, compute avg/min/max, estimate tokens, append record to session cache `_metrics` array
- [x] 2.3 Instrument L1 (SessionStart): record timing, result counts, relevance scores after proactive context call
- [x] 2.4 Instrument L2 (UserPromptSubmit): record timing, result counts, relevance scores, emotion detection level after proactive recall
- [x] 2.5 Instrument L3 (PreToolUse/PostToolUse): record timing, result counts, relevance scores, dedup hit/miss flag
- [x] 2.6 Instrument L4 (PostToolUseFailure): record timing, result counts, relevance scores after error recall
- [x] 2.7 Cap `_metrics` array at 500 entries per session

## 3. Stop Hook Persistence

- [x] 3.1 Add SQLite flush in Stop handler: read `_metrics` from session cache, insert into `injections` table, write `sessions` summary row
- [x] 3.2 Add citation scanner: grep transcript JSONL for assistant-role messages matching citation patterns ("From memory:", "from past experience", "Based on memory", "a memória szerint", "From project memory", "Based on past"), insert into `citations` table
- [x] 3.3 Handle edge cases: missing session cache, empty metrics, SQLite write failure (log and continue)

## 4. CLI Commands (set-memory)

- [x] 4.1 Add `cmd_metrics()` function: read SQLite, compute aggregates (session count, injection count, token total, per-layer breakdown, relevance distribution, citation rate, dedup hit rate, top cited memories), format as TUI report
- [x] 4.2 Add `--since` flag parsing for `cmd_metrics` (default 7d, accepts Nd format)
- [x] 4.3 Add `--json` flag for `cmd_metrics` (structured JSON output)
- [x] 4.4 Add `--enable` / `--disable` flags for `cmd_metrics` (toggle flag file)
- [x] 4.5 Add `cmd_dashboard()` function: read SQLite, generate self-contained HTML with embedded Chart.js, write to `/tmp/set-memory-dashboard.html`, open in browser
- [x] 4.6 Add `metrics` and `dashboard` to main dispatch and usage text under "Metrics & Reporting" section

## 5. HTML Dashboard Template

- [x] 5.1 Create dashboard HTML template with Chart.js CDN (with table fallback for offline): relevance trend line chart, token burn per day bar chart, layer breakdown pie chart, citation rate sparkline
- [x] 5.2 Add session drill-down table: sortable columns (date, injections, tokens, avg relevance, citations), click-to-expand showing per-injection details
- [x] 5.3 Add empty state view with enable instructions when no data available

## 6. Integration & Testing

- [x] 6.1 Manual end-to-end test: enable metrics, run a session, verify session cache has `_metrics`, verify SQLite populated after Stop, verify `set-memory metrics` report output
- [x] 6.2 Verify zero overhead when disabled: time a hook invocation with metrics disabled vs baseline
