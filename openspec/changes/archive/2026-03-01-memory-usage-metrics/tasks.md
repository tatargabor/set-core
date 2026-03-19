## 1. SQLite Schema Migration

- [x] 1.1 Add `context_ids TEXT DEFAULT '[]'` column to `injections` table in `lib/metrics.py` SCHEMA_SQL and add migration logic in `_get_db()` for existing DBs
- [x] 1.2 Create `mem_matches` table with columns: `id` (autoincrement), `session_id` (text), `context_id` (text), `match_type` (text), `UNIQUE(session_id, context_id)` in SCHEMA_SQL
- [x] 1.3 Add `matched_id_count INTEGER DEFAULT 0` and `injected_id_count INTEGER DEFAULT 0` columns to `sessions` table in SCHEMA_SQL with migration for existing DBs

## 2. Context ID Generation in Hook

- [x] 2.1 Add `_gen_context_id()` function to `bin/wt-hook-memory` that generates a 4-char hex ID unique within the session (use random with collision check via dedup cache)
- [x] 2.2 Modify `proactive_and_format()` to prefix each output line with `[MEM#xxxx]` and collect generated IDs + raw content into a returned structure (IDs via last stdout line or temp file)
- [x] 2.3 Modify `recall_and_format()` to prefix each output line with `[MEM#xxxx]` and collect generated IDs + raw content similarly
- [x] 2.4 Update `_metrics_append()` to accept and store a `context_ids` array parameter
- [x] 2.5 Store injected content in session cache `_injected_content` dict (keyed by context_id) for passive matching at session end
- [x] 2.6 Update all call sites of `_metrics_append()` across event handlers (SessionStart, UserPromptSubmit, PostToolUse, PostToolUseFailure, SubagentStart) to pass generated context_ids

## 3. Passive Transcript Matching

- [x] 3.1 Add `extract_keywords(text)` function to `lib/metrics.py` that extracts significant keywords from memory content (exclude common stopwords, min 3-char words, return top 5 keywords)
- [x] 3.2 Add `passive_match(injected_content, transcript_entries)` function to `lib/metrics.py` that checks keyword overlap between injected memories and assistant messages (2+ keyword threshold, 5-turn window)
- [x] 3.3 Extend `scan_transcript_citations()` to accept `injected_content` dict and return passive matches alongside legacy explicit citations
- [x] 3.4 Update `flush_session()` to accept `mem_matches` list, insert into `mem_matches` table, compute `injected_id_count` from metrics records' `context_ids` arrays, set `matched_id_count` on session

## 4. Stop Hook Integration

- [x] 4.1 Update `_stop_flush_metrics()` in `bin/wt-hook-memory` to read `_injected_content` from session cache and pass to transcript scanning
- [x] 4.2 Pass passive match results and injected ID count to `flush_session()`

## 5. Usage Rate Reporting

- [x] 5.1 Add usage rate queries to `query_report()` in `lib/metrics.py`: compute `total_injected_ids`, `total_matched_ids`, `usage_rate` from sessions table
- [x] 5.2 Update `format_tui_report()` to display usage rate in the USAGE SIGNALS section
- [x] 5.3 Update existing `set-memory metrics` JSON output to include `usage_rate`, `total_injected_ids`, `total_matched_ids`

## 6. TUI Dashboard Command

- [x] 6.1 Add `cmd_tui()` function to `bin/set-memory` with `--since` and `--json` argument parsing
- [x] 6.2 Implement Memory Database section: call `set-memory stats --json` and format total count, type distribution, noise ratio, top tags
- [x] 6.3 Implement Hook Overhead section: read from `query_report()` and format per-layer breakdown with count, avg tokens, avg relevance, avg duration
- [x] 6.4 Implement Usage Signals section: display usage rate (matched/injected), legacy citation rate, relevance distribution histogram (ASCII bars), empty injection rate
- [x] 6.5 Implement Daily Trend section: ASCII sparklines for token burn, relevance, and usage rate using block characters (▁▂▃▄▅▆▇█)
- [x] 6.6 Add `tui` to the command dispatch case statement in `bin/set-memory`
- [x] 6.7 Implement JSON output mode for `set-memory tui --json` combining all section data

## 7. Testing

- [x] 7.1 Test schema migration: verify ALTER TABLE runs cleanly on existing metrics.db with data
- [x] 7.2 Test context ID generation: verify uniqueness across multiple invocations within a session
- [x] 7.3 Test passive matching: verify keyword extraction, overlap detection, turn window, and stopword filtering
- [x] 7.4 Test TUI output: verify all sections render with both real data and empty/missing data
- [x] 7.5 Test backward compatibility: verify sessions without context_id data display gracefully (N/A usage rate)
