# Proposal: unified-orchestration-logging

## Problem

The orchestration system writes logs to **two different files** depending on which component is active:

1. **set-orchestrate (bash)**: writes to `.claude/orchestration.log` — covers startup, planning, initial dispatch (37 log calls)
2. **set-sentinel (bash)**: writes to `~/.local/share/set-core/runtime/{run}/logs/orchestration.log` — covers sentinel start/stop
3. **engine.py (Python monitor)**: writes to same runtime path as sentinel (after recent fix `2a628826f`)

The set-web watcher only reads from the runtime path (via `SetRuntime`), so the bash startup/planning logs are **invisible** in the web UI.

Additionally:
- Bash has its own rotation (100KB) that conflicts with Python's `RotatingFileHandler` (5MB)
- Log formats differ between bash (`[timestamp] [LEVEL] msg`) and Python (`timestamp LEVEL module:func msg`)
- `chat_context.py` references the old `.claude/orchestration.log` path

## Solution

Unify all log writers to the single runtime path: `~/.local/share/set-core/runtime/{run}/logs/orchestration.log`

## Scope

- `bin/set-orchestrate` — change `LOG_FILE` from `.claude/orchestration.log` to `$WT_ORCHESTRATION_LOG`
- `bin/set-orchestrate` — remove line 787 `LOG_FILE="$_root/$LOG_FILE"` (WT path is already absolute)
- `bin/set-orchestrate` — remove `rotate_log()` bash rotation (let Python RotatingFileHandler handle it)
- `lib/set_orch/chat_context.py` — update `.claude/orchestration.log` reference to runtime path
- `bin/set-e2e-report` — update LOG_FILE to use WT_ORCHESTRATION_LOG

## Out of Scope

- Log format unification (bash vs Python) — cosmetic, not blocking
- Sentinel log format changes — works fine as-is
- Legacy `.claude/orchestration.log` cleanup in existing projects

## Size

S — ~5 files, path changes only
