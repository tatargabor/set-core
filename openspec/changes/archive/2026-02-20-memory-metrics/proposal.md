## Why

The memory system injects context into every Claude Code session via 5 hook layers (L1-L5), consuming ~2000-5000 tokens per session. We have no visibility into whether these injections are actually useful — whether the LLM uses the returned memories, whether relevance scores are good, or whether the token cost is justified. We need instrumentation to measure injection quality, track actual usage, and surface this data through reports.

## What Changes

- Add structured metrics collection to `wt-hook-memory` (all layers L1-L4), recording per-injection: timestamp, layer, query, result count, relevance scores, duration, token estimate, dedup hit/miss
- Store per-session metrics in the existing session cache (`/tmp/set-memory-session-{ID}.json`) with a `_metrics` section — zero new dependencies, <5ms overhead
- Persist aggregated metrics to SQLite (`~/.local/share/set-core/metrics/metrics.db`) asynchronously in the Stop hook (L5) — no impact on interactive latency
- Add citation scanning in the Stop hook: grep the transcript for explicit memory references ("From memory:", etc.) to measure actual LLM usage
- New CLI command `set-memory metrics [--since 7d]` for TUI report (relevance distribution, citation rate, dedup hit rate, top cited memories, token overhead %)
- New CLI command `set-memory dashboard` to generate and open a self-contained HTML dashboard with charts (Chart.js), session timeline, and drill-down
- Enable/disable toggle via `set-memory metrics --enable|--disable` (flag file, zero overhead when disabled)

## Capabilities

### New Capabilities
- `metrics-collection`: Real-time metrics gathering in hook layers (L1-L4) with session-cache storage and SQLite persistence
- `metrics-reporting`: TUI report (`set-memory metrics`) and HTML dashboard (`set-memory dashboard`) for visualizing injection quality, usage, and token overhead

### Modified Capabilities
- `unified-memory-hook`: Add timing instrumentation and metrics recording to each hook layer
- `memory-cli`: Add `metrics` and `dashboard` subcommands

## Impact

- **Modified**: `bin/wt-hook-memory` — metrics collection in L1-L4 handlers, SQLite flush + citation scan in L5
- **Modified**: `bin/set-memory` — new `metrics` and `dashboard` subcommands
- **New file**: Metrics SQLite schema and query helpers (likely `lib/metrics.py`)
- **New file**: HTML dashboard template (self-contained, single file with embedded Chart.js)
- **Dependencies**: Python `sqlite3` (stdlib, no new deps)
- **Storage**: `~/.local/share/set-core/metrics/metrics.db` (new, lightweight)
