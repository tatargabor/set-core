## Purpose

Migrate `lib/hooks/session.sh` (134 LOC) and `lib/hooks/util.sh` (148 LOC) to `lib/set_hooks/session.py` and `lib/set_hooks/util.py`. Session-level dedup cache, context ID generation, debug logging, timing helpers, and cache I/O.

## Requirements

### SESSION-01: Dedup Cache
- `dedup_clear()` clears dedup hashes while preserving persistent keys (turn_count, metrics, frustration_history)
- `dedup_check(content_hash)` returns True if already surfaced
- `dedup_add(content_hash)` marks as surfaced
- Storage: JSON cache file at predictable path per session

### SESSION-02: Content Hash Generation
- `content_hash(text)` generates stable hash for dedup comparison
- Use first 50 chars as key (matches existing bash behavior)
- Fast — called on every memory before surfacing

### SESSION-03: Turn Counter
- `increment_turn(cache_file)` bumps turn count
- `get_turn_count(cache_file)` reads current count
- Used for checkpoint triggering and metrics

### SESSION-04: Debug Logging (util)
- `_dbg(message)` writes to stderr when debug mode enabled
- `_metrics_timer_start()` / `_metrics_timer_end(label)` timing helpers
- Controlled by `WT_HOOKS_DEBUG` environment variable

### SESSION-05: Cache I/O (util)
- `read_cache(path)` reads JSON cache file, returns dict (empty dict if missing)
- `write_cache(path, data)` writes JSON atomically (write to tmp, rename)
- `CACHE_FILE` path resolution from environment or default

### SESSION-06: Unit Tests
- Test dedup cycle: clear → check (miss) → add → check (hit)
- Test cache round-trip with atomic write
- Test turn counter increment
