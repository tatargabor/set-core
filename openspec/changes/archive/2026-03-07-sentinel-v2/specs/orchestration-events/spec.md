# Orchestration Events

Append-only event log system providing structured audit trail for every orchestration state transition, enabling machine-parseable post-mortem analysis and auto-generated run reports.

## Requirements

### R1: Event Emission
- `emit_event(type, change_name, data)` appends a single JSON line to `orchestration-events.jsonl`
- Format: `{"ts":"ISO8601","type":"EVENT_TYPE","change":"name","data":{...}}`
- Timestamp uses `date -Iseconds`
- The `change` field is omitted for orchestrator-level events (heartbeat, replan, sentinel)

### R2: Event Types
- `STATE_CHANGE`: Any change status transition (includes `from` and `to` fields)
- `TOKENS`: Token usage delta per change
- `DISPATCH`: Change dispatched to worktree
- `MERGE_ATTEMPT`: Merge attempt with success/failure/conflict result
- `VERIFY_GATE`: Gate result (test/build/review/smoke: pass/fail/skip)
- `REPLAN`: Replan cycle started/completed with novel change count
- `CHECKPOINT`: Checkpoint triggered with reason
- `WATCHDOG_WARN`, `WATCHDOG_RESUME`, `WATCHDOG_KILL`, `WATCHDOG_FAILED`: Watchdog actions
- `WATCHDOG_HEARTBEAT`: Periodic orchestrator liveness signal
- `SENTINEL_RESTART`: Sentinel restarted the orchestrator
- `ERROR`: Any error condition with message

### R3: Automatic Emission
- `update_change_field()` automatically emits `STATE_CHANGE` when the `status` field changes
- Token tracking emits `TOKENS` events when `tokens_used` is updated
- No manual `emit_event` calls needed for status transitions — they happen via the existing `update_change_field()` wrapper

### R4: Event Log Rotation
- When `orchestration-events.jsonl` exceeds `events_max_size` (default 1MB), archive to `orchestration-events-{timestamp}.jsonl`
- Keep last 3 archives, delete older ones
- Rotation checked at orchestrator startup and periodically (every 100 poll cycles)

### R5: Event Query
- `set-orchestrate events` subcommand for querying the event log
- Filters: `--type`, `--change`, `--since`, `--last N`
- Output: formatted table or raw JSON (`--json`)

### R6: Auto Run Report
- At orchestration completion (status=done), generate a markdown summary from events
- Contents: change list with status/tokens/duration, verify gate results, watchdog interventions, token totals
- Written to `orchestration-summary.md` (extends existing summary generation)

### R7: Coexistence with State File
- `orchestration-state.json` remains the mutable current-state snapshot (unchanged format)
- `orchestration-events.jsonl` is the append-only history
- Both files live in the project root alongside each other

### R8: Configuration
- `events_log`: Enable/disable event logging (default: true)
- `events_max_size`: Rotation threshold in bytes (default: 1048576 = 1MB)
