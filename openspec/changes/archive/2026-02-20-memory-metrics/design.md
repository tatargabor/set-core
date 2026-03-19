## Context

The set-core memory system injects context into Claude Code sessions via 5 hook layers in `wt-hook-memory`. Each injection consumes tokens but we have zero visibility into whether this context is useful. The system already computes relevance scores, filters results, and maintains a dedup cache — but none of this is recorded.

Shodh-memory tracks per-memory `access_count` and `total_retrievals` (currently 4338), but has no query-level analytics, session-level metrics, or injection quality tracking. We need to build the operational telemetry layer ourselves.

## Goals / Non-Goals

**Goals:**
- Measure injection quality: relevance score distribution, hit/miss rates, filter-out rates
- Track actual LLM usage: citation scanning, keyword overlap analysis
- Provide TUI report and HTML dashboard for visualization
- Keep collection overhead under 5ms per hook invocation
- Make metrics collection toggleable (enable/disable)

**Non-Goals:**
- A/B testing (comparing sessions with/without memory)
- LLM-as-judge evaluation (too expensive per session — future extension)
- Modifying shodh-memory internals or adding upstream analytics
- Real-time monitoring or alerting
- Multi-machine aggregation (single-machine metrics only)

## Decisions

### 1. Collection: Session cache extension (not new file)

**Choice**: Extend the existing `/tmp/set-memory-session-{ID}.json` with a `_metrics` section.

**Alternatives considered:**
- Dedicated JSONL log file — rejected: no indexing, hard to query, grows unbounded
- Direct SQLite writes during hooks — rejected: 100-200ms Python startup overhead per write
- In-memory metrics in a long-running daemon — rejected: no daemon exists, overengineered

**Rationale**: The session cache is already read/written synchronously in every hook invocation. Adding a `_metrics` array costs <1ms extra JSON serialization. No new files, no new locks, no new dependencies.

### 2. Persistence: SQLite in Stop hook (async)

**Choice**: Flush session metrics to SQLite (`~/.local/share/set-core/metrics/metrics.db`) during the Stop hook.

**Rationale**: Stop hook already does async transcript extraction. SQLite write happens once per session (not per injection), so Python startup cost is amortized. SQLite gives us `GROUP BY`, `WHERE date >`, aggregation — exactly what the TUI and dashboard need.

**Schema:**
```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,         -- session_id
    project TEXT,                -- project name
    started_at TEXT,             -- first injection timestamp
    ended_at TEXT,               -- stop hook timestamp
    total_injections INTEGER,
    total_tokens INTEGER,
    citation_count INTEGER,      -- transcript grep hits
    layers_json TEXT             -- per-layer summary JSON
);

CREATE TABLE injections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    ts TEXT,                     -- ISO timestamp
    layer TEXT,                  -- L1/L2/L3/L4
    event TEXT,                  -- SessionStart/UserPromptSubmit/etc
    query TEXT,                  -- what was searched
    result_count INTEGER,        -- memories returned (pre-filter)
    filtered_count INTEGER,      -- memories after filtering
    avg_relevance REAL,          -- average relevance_score
    max_relevance REAL,
    min_relevance REAL,
    duration_ms INTEGER,         -- hook execution time
    token_estimate INTEGER,      -- estimated tokens in injection
    dedup_hit INTEGER            -- 1 if dedup cache hit
);

CREATE TABLE citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    citation_text TEXT,          -- matched text
    citation_type TEXT           -- "explicit" (From memory:) or "keyword" (overlap)
);

CREATE INDEX idx_injections_session ON injections(session_id);
CREATE INDEX idx_injections_ts ON injections(ts);
CREATE INDEX idx_sessions_project ON sessions(project);
```

### 3. Citation scanning: Grep-based (transcript)

**Choice**: In the Stop hook, grep the transcript JSONL for citation patterns.

**Patterns:**
- Explicit: `From memory:`, `from past experience`, `Based on memory`, `a memória szerint`, `From project memory`
- Role filter: only scan `assistant` role messages

**Rationale**: Free (no LLM cost), fast (~50ms for typical transcript), gives a lower-bound on actual usage. Not perfect — LLM may use memory without citing — but it's the cheapest signal we have.

### 4. Enable/disable: Flag file

**Choice**: `~/.local/share/set-core/metrics/.enabled` file presence toggles collection.

**Rationale**: File existence check is ~0.1ms. When disabled, hooks skip all metrics code (zero overhead). Toggled via `set-memory metrics --enable|--disable`.

### 5. TUI report: Rich-text CLI output

**Choice**: `set-memory metrics [--since 7d] [--json]` reads SQLite and prints formatted report.

**Sections**: Session count, injection count, token total, per-layer breakdown, relevance distribution histogram, citation rate, dedup hit rate, top cited memories, empty injection rate.

### 6. HTML dashboard: Self-contained single file

**Choice**: `set-memory dashboard [--port 0] [--since 30d]` generates a single HTML file with embedded Chart.js and opens it in browser.

**Rationale**: No web server dependency, no npm, no build step. Single file with inline JS/CSS. Charts: relevance trend over time, token burn per day, layer breakdown pie, citation rate sparkline, session drill-down table.

**Alternative considered:** Live web server with auto-refresh — rejected: overengineered for infrequent use.

## Risks / Trade-offs

- **[Risk] Session cache grows too large** → Mitigation: Cap `_metrics` array at 500 entries per session (more than enough, typical session has 50-100 injections)
- **[Risk] SQLite write fails in Stop hook** → Mitigation: Silent failure (log to stderr), metrics are best-effort not critical
- **[Risk] Citation patterns miss non-English citations** → Mitigation: Start with EN+HU patterns, extensible list
- **[Risk] Token estimation is inaccurate** → Mitigation: Use `len(text) / 4` heuristic (industry standard for English), good enough for relative comparison
- **[Risk] Dashboard HTML file becomes stale** → Mitigation: Regenerated on each `set-memory dashboard` invocation, not cached

## Open Questions

- Should we track which specific memory IDs were injected (for "most useful memory" ranking)? Adds ~50 bytes per injection record but enables powerful drill-down.
- Should the dashboard auto-open in browser or just print the path? Platform differences (xdg-open vs open).
