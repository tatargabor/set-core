## Why

The orchestration engine is 54% bash (18,000 LOC) with complex logic — state machines, retry loops, JSON manipulation via jq, directive parsing — all in shell scripts that are hard to debug, test, and extend. Python already exists as a thin bridge layer (`lib/wt_orch/` — 7,700 LOC) but handles only templates, state init, and process management. Phase 1 establishes the foundational Python infrastructure (logging, subprocess wrappers, config parsing, event bus) that all subsequent migration phases will build on.

## What Changes

- **New `logging_config.py`**: Structured logging for all orchestration modules — file + stderr output, JSON extras support, rotating file handler, module-level loggers matching the existing `orchestration.log` path
- **New `subprocess_utils.py`**: Type-safe wrappers for `claude`, `git`, and `timeout` subprocess calls — every invocation logged with cmd, duration, exit_code, output_size; replaces ad-hoc `subprocess.run()` scattered across modules
- **New `config.py`**: Migrates directive/config parsing from `utils.sh` — `parse_directives()`, `resolve_directives()`, `load_config_file()`, `parse_duration()`, `format_duration()`, `brief_hash()`, `find_input()`, `auto_detect_test_command()`, `parse_next_items()`
- **New `events.py`**: Event bus with `emit()` / `subscribe()` + JSONL file writer — compatible with existing `events.jsonl` format, replaces `emit_event()` from `events.sh`
- **Pytest test suite**: Unit tests for every migrated function, ensuring 1:1 behavioral parity with bash originals
- **Delete migrated bash functions**: Remove `parse_directives()`, `resolve_directives()`, `load_config_file()`, `parse_duration()`, `format_duration()`, `brief_hash()`, `find_input()`, `parse_next_items()` from `utils.sh`; remove `emit_event()`, `rotate_events_log()`, `query_events()` from `events.sh`; update callers to use `wt-orch-core` CLI

## Capabilities

### New Capabilities
- `orchestration-logging`: Structured logging infrastructure for all Python orchestration modules
- `orchestration-subprocess`: Type-safe subprocess wrappers for claude/git/timeout with automatic logging
- `orchestration-config`: Python-native directive parsing, config loading, duration/hash utilities (migrated from utils.sh)
- `orchestration-events`: Event bus with emit/subscribe pattern and JSONL persistence (migrated from events.sh)

### Modified Capabilities
_(none — these are new Python modules replacing bash functions, no existing spec-level behavior changes)_

## Impact

- **Files added**: `lib/wt_orch/logging_config.py`, `lib/wt_orch/subprocess_utils.py`, `lib/wt_orch/config.py`, `lib/wt_orch/events.py`
- **Files modified**: `lib/wt_orch/cli.py` (new subcommands: `config`, `events`), `lib/orchestration/utils.sh` (remove migrated functions, add Python delegation), `lib/orchestration/events.sh` (remove migrated functions, add Python delegation)
- **Tests added**: `tests/unit/test_config.py`, `tests/unit/test_events.py`, `tests/unit/test_subprocess_utils.py`, `tests/unit/test_logging_config.py`
- **Dependencies**: No new external packages — uses stdlib only (`logging`, `json`, `subprocess`, `hashlib`, `pathlib`, `fcntl`, `re`, `dataclasses`)
- **JSON format**: events.jsonl format unchanged — full backward compatibility
- **Bash callers**: Updated to call `wt-orch-core config parse-directives` etc. instead of sourcing bash functions directly
