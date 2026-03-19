## verify-poll

Change polling, loop-state parsing, and status transitions.

### Requirements

#### VP-POLL — Poll change loop-state
- Read loop-state.json from worktree .claude/ directory
- Extract status, token counts (total, input, output, cache_read, cache_create)
- Fallback: if tokens=0 in loop-state, query set-usage with loop started_at
- Accumulate tokens with _prev counters from state
- Handle missing worktree: skip if already merged+archived
- Handle missing loop-state: check if ralph_pid is dead, mark failed

#### VP-STATUS — Status dispatch
- `done` → call handle_change_done with full parameter set
- `running` → check staleness (>300s mtime + dead PID → mark stalled)
- `waiting:human` → update status, log manual task summary, send notification; resume if tasks resolved (status=dispatched)
- `budget_exceeded`/`waiting:budget` → update status, log budget checkpoint, send notification
- `stopped`/`stalled`/`stuck` → re-read loop-state (race window check for done), mark stalled for watchdog

#### VP-TOKENS — Token accumulation
- Current loop tokens from loop-state.json or set-usage fallback
- Add tokens_used_prev, input_tokens_prev, output_tokens_prev, cache_read_tokens_prev, cache_create_tokens_prev
- Update all 5 token fields in state per poll cycle
