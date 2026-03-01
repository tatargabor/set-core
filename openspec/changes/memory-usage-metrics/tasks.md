## 1. SQLite Schema Migration

- [ ] 1.1 Add `context_ids TEXT DEFAULT '[]'` column to `injections` table in `lib/metrics.py` SCHEMA_SQL and add migration logic in `_get_db()` for existing DBs
- [ ] 1.2 Create `mem_matches` table with columns: `id` (autoincrement), `session_id` (text), `context_id` (text), `match_type` (text), `UNIQUE(session_id, context_id)` in SCHEMA_SQL
- [ ] 1.3 Add `matched_id_count INTEGER DEFAULT 0` and `injected_id_count INTEGER DEFAULT 0` columns to `sessions` table in SCHEMA_SQL with migration for existing DBs

## 2. Context ID Generation in Hook

- [ ] 2.1 Add `_gen_context_id()` function to `bin/wt-hook-memory` that generates a 4-char hex ID unique within the session (use random with collision check via dedup cache)
- [ ] 2.2 Modify `proactive_and_format()` to prefix each output line with `[MEM#xxxx]` and collect generated IDs + raw content into a returned structure (IDs via last stdout line or temp file)
- [ ] 2.3 Modify `recall_and_format()` to prefix each output line with `[MEM#xxxx]` and collect generated IDs + raw content similarly
- [ ] 2.4 Update `_metrics_append()` to accept and store a `context_ids` array parameter
- [ ] 2.5 Store injected content in session cache `_injected_content` dict (keyed by context_id) for passive matching at session end
- [ ] 2.6 Update all call sites of `_metrics_append()` across event handlers (SessionStart, UserPromptSubmit, PostToolUse, PostToolUseFailure, SubagentStart) to pass generated context_ids

## 3. Passive Transcript Matching

- [ ] 3.1 Add `extract_keywords(text)` function to `lib/metrics.py` that extracts significant keywords from memory content (exclude common stopwords, min 3-char words, return top 5 keywords)
- [ ] 3.2 Add `passive_match(injected_content, transcript_entries)` function to `lib/metrics.py` that checks keyword overlap between injected memories and assistant messages (2+ keyword threshold, 5-turn window)
- [ ] 3.3 Extend `scan_transcript_citations()` to accept `injected_content` dict and return passive matches alongside legacy explicit citations
- [ ] 3.4 Update `flush_session()` to accept `mem_matches` list, insert into `mem_matches` table, compute `injected_id_count` from metrics records' `context_ids` arrays, set `matched_id_count` on session

## 4. Stop Hook Integration

- [ ] 4.1 Update `_stop_flush_metrics()` in `bin/wt-hook-memory` to read `_injected_content` from session cache and pass to transcript scanning
- [ ] 4.2 Pass passive match results and injected ID count to `flush_session()`

## 5. Usage Rate Reporting

- [ ] 5.1 Add usage rate queries to `query_report()` in `lib/metrics.py`: compute `total_injected_ids`, `total_matched_ids`, `usage_rate` from sessions table
- [ ] 5.2 Update `format_tui_report()` to display usage rate in the USAGE SIGNALS section
- [ ] 5.3 Update existing `wt-memory metrics` JSON output to include `usage_rate`, `total_injected_ids`, `total_matched_ids`

## 6. TUI Dashboard Command

- [ ] 6.1 Add `cmd_tui()` function to `bin/wt-memory` with `--since` and `--json` argument parsing
- [ ] 6.2 Implement Memory Database section: call `wt-memory stats --json` and format total count, type distribution, noise ratio, top tags
- [ ] 6.3 Implement Hook Overhead section: read from `query_report()` and format per-layer breakdown with count, avg tokens, avg relevance, avg duration
- [ ] 6.4 Implement Usage Signals section: display usage rate (matched/injected), legacy citation rate, relevance distribution histogram (ASCII bars), empty injection rate
- [ ] 6.5 Implement Daily Trend section: ASCII sparklines for token burn, relevance, and usage rate using block characters (▁▂▃▄▅▆▇█)
- [ ] 6.6 Add `tui` to the command dispatch case statement in `bin/wt-memory`
- [ ] 6.7 Implement JSON output mode for `wt-memory tui --json` combining all section data

## 7. Testing

- [ ] 7.1 Test schema migration: verify ALTER TABLE runs cleanly on existing metrics.db with data
- [ ] 7.2 Test context ID generation: verify uniqueness across multiple invocations within a session
- [ ] 7.3 Test passive matching: verify keyword extraction, overlap detection, turn window, and stopword filtering
- [ ] 7.4 Test TUI output: verify all sections render with both real data and empty/missing data
- [ ] 7.5 Test backward compatibility: verify sessions without context_id data display gracefully (N/A usage rate)
