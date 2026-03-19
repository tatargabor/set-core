## Purpose

Migrate `lib/loop/state.sh` (255 LOC) to `lib/set_orch/loop_state.py`. Loop state file management, token tracking, and date parsing utilities.

## Requirements

### STATE-01: State File I/O
- `init_loop_state(wt_path)` creates initial `loop-state.json`
- `read_loop_state(wt_path)` returns `LoopState` dataclass
- `update_loop_state(wt_path, updates)` merges updates atomically (file lock)
- Fields: iteration, tokens_used, status, start_time, last_activity, change_name

### STATE-02: Token Tracking
- `add_tokens(state, count)` increments cumulative token counter
- Parse token count from Claude CLI output (regex on "tokens used" line)
- Track per-iteration and cumulative totals

### STATE-03: Date Parsing
- `parse_date_to_epoch(date_str)` cross-platform ISO 8601 → epoch
- Handle timezone offsets
- Return integer epoch seconds

### STATE-04: Activity File
- `write_activity(wt_path, activity)` writes `activity.json` for monitoring
- Fields: skill, skill_args, iteration, tokens, timestamp, pid
- Read by `wt-status` and MCP `get_activity` tool

### STATE-05: Unit Tests
- Test state file round-trip (write → read)
- Test token parsing from various Claude output formats
- Test date parsing with various ISO 8601 formats
