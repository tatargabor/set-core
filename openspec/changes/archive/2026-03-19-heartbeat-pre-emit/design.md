# Design: heartbeat-pre-emit

## Context

The monitor loop in `engine.py` is single-threaded. The current heartbeat is emitted every 8th poll (`poll_count % 8 == 0`), which assumes each poll cycle completes in ~15 seconds. When a blocking call (dispatch, merge, replan) takes minutes, no heartbeat is emitted, and the sentinel kills the process after 180s of inactivity.

The sentinel checks both the events JSONL file mtime and the state file mtime to determine if the orchestrator is alive.

## Goals / Non-Goals

**Goals:**
- Eliminate false-positive sentinel kills during long operations
- Zero-risk change — only add timing signals, no behavioral changes

**Non-Goals:**
- Threading or async patterns (too much complexity for this fix)
- Changing sentinel timeout values
- Removing the existing periodic heartbeat (kept as fallback)

## Decisions

### 1. Bracket pattern: heartbeat before AND after blocking calls

Rather than a background thread, emit heartbeat _around_ each long-running call:

```python
_signal_alive(state_file, event_bus)
_dispatch_ready_safe(state_file, d, event_bus)
_signal_alive(state_file, event_bus)
```

**Why not threading?** Python's GIL + `fcntl.flock` + signal handlers interact poorly. A threading bug in the monitor loop would be much harder to debug than a missing heartbeat. The bracket pattern is simple, deterministic, and sufficient — even a 10-minute dispatch only needs one pre-emit to reset the 180s timer.

**Why not just pre-emit?** If two long operations run back-to-back (e.g., merge then dispatch), the gap between the first pre-emit and the second operation's start could exceed 180s. Post-emit closes that gap.

### 2. Dual signal: event bus emit + state file mtime touch

The sentinel checks two indicators: events file and state file mtime. Touch both:

```python
def _signal_alive(state_file: str, event_bus: EventBus | None) -> None:
    if event_bus:
        event_bus.emit("WATCHDOG_HEARTBEAT")
    try:
        os.utime(state_file, None)
    except OSError:
        pass
```

**Why `os.utime`?** It's a single syscall, no locking needed, and directly updates what the sentinel checks. Even if the event bus is broken, the mtime touch keeps the sentinel happy.

### 3. Which calls to bracket

Only calls that empirically block for >30 seconds in E2E runs:

| Call site | Max observed duration | Bracket? |
|-----------|----------------------|----------|
| `_poll_active_changes()` | ~2 min (many changes) | Yes |
| `_drain_merge_then_dispatch()` | ~5 min (multiple merges + dispatch) | Yes |
| `_dispatch_ready_safe()` | ~10 min (worktree create + agent init) | Yes |
| `_resume_stalled_safe()` | ~30s | No (within margin) |
| `_generate_report_safe()` | ~5s | No |
| `_periodic_memory_ops_safe()` | ~5s | No |

## Risks / Trade-offs

- **[Risk] Heartbeat masks a truly stuck process** → Mitigated: the self-watchdog (`_self_watchdog()`) independently tracks progress via change status transitions, not heartbeat. A stuck process with heartbeat will still be caught by idle escalation.
- **[Risk] Extra event bus writes increase disk I/O** → Negligible: ~6 extra JSONL appends per poll cycle, <1KB total.

## Open Questions

_(none)_
