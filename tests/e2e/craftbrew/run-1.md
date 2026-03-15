# CraftBrew E2E — Run #1

**Date**: 2026-03-15 ~ 2026-03-16 (overnight)
**wt-tools commit**: 58f63afa2 (master)
**Project dir**: `/tmp/craftbrew-run1`
**Spec**: CraftBrew multi-file spec (15 changes, 5 phases, 50 REQs, 10 domains)

## Bugs Found

### 1. PyYAML not available in linuxbrew Python 3.14
- **Type**: framework (non-blocking)
- **Severity**: noise
- **Root cause**: `wt-orch-core` runs under linuxbrew Python 3.14 which doesn't have PyYAML. `profile_loader.py` falls back to NullProfile.
- **Fix**: N/A — fallback works, just a warning in logs
- **Recurrence**: known, not worth fixing

### 2. Stall detection during initial dispatch
- **Type**: framework
- **Severity**: noise (auto-recovers)
- **Root cause**: Agent dispatched to worktree, starts working but initial commits are doc-only (README, config). Stall detector flags as "no implementation progress".
- **Fix**: Stall cooldown (300s) allows recovery automatically. Working as designed.
- **Recurrence**: expected pattern

### 3. Figma MCP blocks claude -p mode
- **Type**: framework (blocking)
- **Severity**: blocking
- **Root cause**: Figma HTTP MCP (`https://mcp.figma.com/mcp`) requires interactive OAuth browser auth. When registered in `.claude/settings.json`, `claude -p` (pipe mode) hangs indefinitely waiting for auth.
- **Fix**: `ee8529342` — removed Figma MCP registration from both E2E scaffold scripts. Design data available via static `design-snapshot.md` + `figma-raw/` files.
- **Deployed**: yes
- **Recurrence**: new

### 4. Python monitor crashes with JSONDecodeError on sentinel restart
- **Type**: framework (blocking)
- **Severity**: blocking
- **Root cause**: Bash dispatcher creates directives via `mktemp /tmp/orch-directives-XXXXXX.json`. On sentinel restart, a new bash process creates a NEW temp file, but the old path (stored nowhere) is gone. The Python monitor receives the deleted file path via `--directives`, `os.path.isfile()` returns False, falls through to `json.loads(path_string)` which crashes: `JSONDecodeError: Expecting value`.
- **Compound issue**: Python's atexit handler sets `status="stopped"`. Sentinel sees `exit_code=1 + status=stopped` → `is_transient_failure` returns true (exit_code != 0) → restarts → same crash → 5 rapid crashes → sentinel gives up.
- **Fix**: `58f63afa2` — two changes:
  1. `dispatcher.sh`: use stable path `wt/orchestration/directives.json` instead of `mktemp`
  2. `engine.py` + `cli.py`: fall back to directives persisted in state file when file is missing
- **Deployed**: yes
- **Recurrence**: new

### 5. Sentinel kills monitor during stall cooldown (heartbeat too slow)
- **Type**: framework (blocking)
- **Severity**: blocking
- **Root cause**: Monitor emits WATCHDOG_HEARTBEAT every 20 polls (20*15s = 300s). Sentinel stuck timeout is 180s. During stall recovery, the monitor waits for the 300s cooldown without writing to the state file or events — sentinel sees no activity for 180s and kills it.
- **Fix**: `b1b5d1a29` — reduce heartbeat interval to every 8 polls (8*15s = 120s), well within the 180s threshold.
- **Deployed**: yes
- **Recurrence**: new (existed latently, first triggered by stall + no other activity)

## Timeline

| Time | Event |
|------|-------|
| ~22:30 | Scaffold script run, project created |
| ~22:35 | Sentinel started, planning + decomposition |
| ~22:50 | Planning complete: 15 changes, 5 phases |
| ~22:55 | First dispatch: test-infrastructure-setup |
| ~23:10 | Bug #3 discovered: Figma MCP blocking agent |
| ~23:20 | Bug #3 fixed, restarted |
| ~23:30 | Bug #4 discovered: JSONDecodeError crash loop |
| ~00:27 | Bug #4 fixed, restarted successfully |
| ~00:27 | Orchestration running, test-infrastructure-setup dispatched |
| ~00:31 | Bug #5: sentinel kills monitor (heartbeat too slow) |
| ~00:33 | Bug #5 fixed, deployed, restarted |

## Status (in progress)

| Change | Phase | Status | Notes |
|--------|-------|--------|-------|
| test-infrastructure-setup | 1 | running | dispatched |
| ... (14 more) | 1-5 | pending | waiting |
