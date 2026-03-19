## Context

The `set-memory` CLI uses `mkdir`-based locking (`run_with_lock()`, lines 211-234 in `bin/set-memory`) to serialize RocksDB access. The current implementation has a critical flaw: if the process holding the lock is killed (SIGKILL, OOM, power loss) or the MCP server crashes, the lock directory is never cleaned up. This orphaned lock blocks ALL subsequent write operations permanently.

The MCP server (`mcp-server/wt_mcp_server.py`) calls `set-memory` CLI for all operations. When the lock is stuck, write operations (forget, cleanup, dedup, export) return fallback/empty JSON instead of meaningful errors.

Current `run_with_lock()` flow:
1. Try `mkdir` in a loop (10s timeout)
2. On success: set EXIT trap, run command, cleanup
3. On timeout: return 1 (no cleanup, no staleness check)

## Goals / Non-Goals

**Goals:**
- Auto-recover from orphaned locks without manual intervention
- Track lock owner (PID) for accurate staleness detection
- Keep the fix minimal — only touch `run_with_lock()`

**Non-Goals:**
- Switching locking mechanism (flock, file-based) — mkdir is portable and works
- Changing the MCP server error handling — that's a separate concern
- Adding lock monitoring/alerting

## Decisions

### Decision 1: PID file inside lock directory
Write `$$` to `<lock_dir>/pid` after successful `mkdir`. This enables precise staleness detection: if the PID is dead, the lock is stale regardless of age.

**Alternative considered**: Age-only detection (lock > 60s = stale). Rejected because a legitimately long operation (e.g., large dedup) could exceed 60s and get its lock stolen.

**Approach**: Use PID as primary signal, age as fallback (for cases where pid file is missing or corrupted).

### Decision 2: Check-before-wait and check-on-timeout
Two staleness check points:
1. **Before entering the wait loop**: If lock exists, immediately check PID. If dead → remove and acquire.
2. **On timeout**: If 10s elapsed, check PID one more time. If dead → remove and retry once.

This handles both "lock was stale from the start" and "lock holder died while we were waiting".

### Decision 3: Staleness thresholds
- PID dead → always stale (immediate removal)
- PID file missing + age > 60s → stale (fallback for old-format locks or corrupted state)
- PID alive → never stale (wait or timeout as normal)

## Risks / Trade-offs

- [Race condition: two processes detect stale lock simultaneously] → `mkdir` is atomic; only one will succeed in re-acquiring. The other will loop back and wait normally.
- [PID reuse: OS reassigns PID to different process] → Extremely unlikely within 60s window. The age fallback provides a safety net.
- [Backward compatibility: old locks without pid file] → Handled by the age-only fallback path.
