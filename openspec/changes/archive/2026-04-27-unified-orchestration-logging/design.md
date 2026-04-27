# Design: unified-orchestration-logging

## Current State

```
WRITERS                          FILES                        READER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set-orchestrate (bash)           .claude/orchestration.log     ❌ nobody
  LOG_FILE=".claude/orch..."     (startup, planning)
  37 log calls
  rotate_log() at 100KB

set-sentinel (bash)              runtime/.../orch.log          ✅ watcher
  LOG_FILE=$WT_ORCH_LOG          (sentinel start/stop)
  ~50 sentinel_log calls

engine.py (Python)               runtime/.../orch.log          ✅ watcher
  setup_logging()                (dispatch/verify/merge)
  RotatingFileHandler 5MB
```

## Target State

```
WRITERS                          FILE                          READER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set-orchestrate (bash)  ─┐
set-sentinel (bash)     ─┼──►  runtime/.../orch.log   ──►   watcher ──► web UI
engine.py (Python)      ─┘     (single file, Python rotation)
```

## Changes

### 1. set-orchestrate LOG_FILE (bin/set-orchestrate)

**Before:**
```bash
LOG_FILE=".claude/orchestration.log"  # line 33
# ...
LOG_FILE="$_root/$LOG_FILE"           # line 787
```

**After:**
```bash
LOG_FILE="$WT_ORCHESTRATION_LOG"      # line 33 — already absolute from set-paths
# line 787: remove the absolute path conversion
```

**Dependency:** `set-paths` is sourced at line 127 (`source "$SCRIPT_DIR/../lib/set-common.sh"` which sources `set-paths`). Verify `WT_ORCHESTRATION_LOG` is set before `LOG_FILE` is used.

### 2. Remove bash rotate_log() (bin/set-orchestrate)

Remove `rotate_log()` (lines 107-118) and the call at line 799. The Python `RotatingFileHandler` (5MB, 3 backups) handles rotation. Having two rotation systems on the same file causes corruption.

Also remove `LOG_MAX_SIZE` and `LOG_KEEP_SIZE` constants (lines 34-35).

### 3. Ensure runtime dirs exist before first log (bin/set-orchestrate)

The bash `log()` function calls `mkdir -p "$(dirname "$LOG_FILE")"` (line 89). With the new path (`~/.local/share/set-core/runtime/{project}/logs/`), this still works. But verify `wt_ensure_runtime_dirs` runs before first log call — in sentinel it does (line 83), but in standalone `set-orchestrate` it may not.

### 4. Update chat_context.py reference

```python
# Before:
"- `tail -50 .claude/orchestration.log` — utolsó log sorok"
# After: reference the runtime path or use set-paths resolution
```

### 5. Update set-e2e-report LOG_FILE

```bash
# Before (line 78):
LOG_FILE=".claude/orchestration.log"
# After:
LOG_FILE="$WT_ORCHESTRATION_LOG"
```

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| `WT_ORCHESTRATION_LOG` not set when `set-orchestrate` runs standalone | `set-paths` is sourced via `set-common.sh` before `main()` — verify |
| Bash `mkdir -p` on runtime path fails | `log()` already does `mkdir -p` on dirname |
| Old `.claude/orchestration.log` files left behind | Harmless — no consumer reads them |
| Log format mismatch in same file | LogPanel only does substring match (ERROR/WARN) — works with both formats |
