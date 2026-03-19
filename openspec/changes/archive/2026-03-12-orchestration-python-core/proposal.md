## Why

After the bash-hardening change (safe_jq_update, flock locking), JSON state writes are safe. But three critical fragility areas remain that Bash cannot solve well:

1. **Process management** — PID tracking uses `kill -0` without verifying the process is still `wt-loop` (PID recycling risk). No SIGCHLD handling. Orphan detection relies on 5-minute watchdog timeout instead of immediate notification. Known production incidents: orphaned agent process after orchestrator stop, merge conflict loops caused by stale PID references.

2. **441 jq invocations** for JSON manipulation — ~12 are multi-stage pipelines and ~15 are complex filters (>40 chars) with embedded variables. No type safety, no validation between stages. Silent empty returns on missing fields hide state corruption.

3. **Structured text generation** — 18 heredocs build proposal.md, review prompts, and event JSON. If variables contain EOF markers or special characters, output is corrupted. No escaping.

Python is the right choice: psutil is already installed (via install.sh for the GUI), pyproject.toml and pytest infrastructure exist, and 7 inline `python3 -c` scripts in the orchestration code already prove the pattern works.

## What Changes

- Create `lib/set_orch/` Python package with three modules:
  - `process.py` — PID lifecycle management with `/proc/cmdline` verification, psutil-based orphan detection, safe kill sequences
  - `state.py` — Typed JSON state management with dataclasses, atomic file operations, validation on read/write
  - `templates.py` — Proposal.md, review prompts, event JSON generation with proper escaping
- Create `bin/set-orch-core` CLI entry point that exposes Python functions to bash scripts
- Migrate dispatcher.sh PID operations to call `set-orch-core process ...`
- Migrate state.sh complex jq queries to call `set-orch-core state ...`
- Migrate dispatcher.sh proposal generation to call `set-orch-core template ...`
- Bash scripts remain as entry points and git/worktree orchestration — Python handles the fragile internals

## Capabilities

### New Capabilities
- `process-lifecycle`: Safe PID tracking, verification, kill sequences, and orphan detection via Python/psutil
- `typed-state`: Python dataclass-based JSON state management with validation, replacing complex jq pipelines
- `template-engine`: Safe structured text generation for proposals, prompts, and event payloads

### Modified Capabilities
- `orchestration-engine`: dispatcher.sh, watchdog.sh, and state.sh will delegate process/state/template operations to the new Python modules
- `orchestration-watchdog`: Watchdog will use Python process module for immediate dead-process detection instead of timeout-based polling

## Impact

- **New files:** `lib/set_orch/__init__.py`, `process.py`, `state.py`, `templates.py`, `bin/set-orch-core`
- **Modified:** `lib/orchestration/dispatcher.sh` (PID ops → Python), `lib/orchestration/state.sh` (complex queries → Python), `lib/orchestration/watchdog.sh` (process checks → Python)
- **Dependencies:** psutil (installed by install.sh for GUI, to be added to pyproject.toml main deps)
- **Tests:** `tests/unit/test_process.py`, `test_state.py`, `test_templates.py`
- **No breaking changes** to CLI interface or external behavior — bash scripts call Python internally
