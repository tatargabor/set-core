## Context

`set-memory` is a bash wrapper around the shodh-memory Python/Rust library. Each invocation spawns a new `python3` process that opens a RocksDB database at `~/.local/share/set-core/memory/<project>/`. RocksDB uses an exclusive `LOCK` file — only one process can open a directory at a time.

The GUI's `FeatureWorker` (in `gui/workers/feature.py`) polls `set-memory status --json` every 15 seconds, briefly opening the database. Agent sessions call `set-memory remember` during OpenSpec hooks and proactive memory saves. When these overlap, the second process fails with `RuntimeError: Failed to create memory system`, which is silently swallowed.

The `run_shodh_python` helper compounds the problem:
1. `2>/dev/null` discards all Python stderr (including errors)
2. `| grep -v "^⭐"` filters the shodh-memory import banner from stdout, but returns exit code 1 when no lines pass through (i.e., on every successful `remember` call that produces no output)
3. `|| true` catches everything, making success and failure indistinguishable

## Goals / Non-Goals

**Goals:**
- Prevent silent data loss from concurrent `set-memory` access
- Make errors visible and diagnosable
- Zero behavior change for callers — same CLI interface, same exit codes on success

**Non-Goals:**
- Switching shodh-memory to server mode (client.py) — too invasive for this fix
- Adding retry logic — flock serialization eliminates the need
- Changing the GUI poll interval or mechanism
- Fixing shodh-memory's RocksDB locking upstream

## Decisions

### Decision 1: `flock` for serialization (over retry logic)

Use `flock` (POSIX file locking) on a per-project lock file to serialize all `set-memory` operations that touch RocksDB.

**Lock file path**: `/tmp/set-memory-<project>.lock`

**Why flock over retry:**
- Retry adds complexity (how many retries? what delay? still might fail)
- flock guarantees correctness — the OS handles queuing
- flock adds negligible latency (microseconds for uncontended lock)
- Available on all Linux distros and macOS (part of util-linux / BSD)

**Why NOT shared/exclusive (flock -s/-x):**
- RocksDB itself doesn't support shared readers — even two read-only opens contend
- Shared locks would give false safety; exclusive-only is correct and simpler

**Timeout**: `flock --timeout 10` — fail after 10 seconds rather than block forever.

### Decision 2: Python-level banner suppression (over grep filtering)

Set `sys._shodh_star_shown = True` before importing shodh_memory. This prevents the `⭐ Love shodh-memory?` banner from being printed at all, eliminating the need for `grep -v "^⭐"` in the pipe.

**Why this matters:**
- Without grep, the pipe is gone, so python3's exit code flows through directly
- `run_shodh_python` can now return the actual Python exit code
- No more grep returning exit 1 on successful calls

### Decision 3: Stderr to log file (over /dev/null)

Replace `2>/dev/null` with `2>>"$log_file"` where the log file is at `${SHODH_STORAGE}/<project>/set-memory.log`. This preserves the quiet CLI behavior while making errors diagnosable.

**Why a log file:**
- Users don't want Python tracebacks on every `set-memory` call
- But invisible errors led to the original bug — need a middle ground
- Log file lives next to the memory storage, easy to find

**Exit code propagation**: After removing the grep pipe and 2>/dev/null, the actual Python exit code propagates. `cmd_remember` keeps `|| true` for graceful degradation (shodh-memory not installed), but logs the error first.

## Risks / Trade-offs

- **[flock on macOS]** → macOS has `flock` via Homebrew or BSD `flock`. The `util-linux` `flock` and BSD `flock` have slightly different flags. Use POSIX-compatible syntax only. Test on macOS.
- **[Lock file cleanup]** → `/tmp/set-memory-*.lock` files persist after use. They're empty files in /tmp, cleaned on reboot. Acceptable.
- **[10s timeout]** → If a process hangs holding the lock, other callers wait up to 10s then fail. This is better than the current behavior (immediate silent failure), and 10s is generous for any normal operation.
- **[Log file growth]** → `set-memory.log` could grow unbounded in error-heavy scenarios. Not adding log rotation — the file only grows on errors, which should be rare after this fix.
