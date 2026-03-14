## Tasks

### 1. Create logging_config.py
- [x] Create `lib/wt_orch/logging_config.py` with `setup_logging(log_path=None)` function
- [x] Implement `ExtraFormatter` that appends extra dict keys as `key=value` pairs
- [x] Configure rotating file handler (5MB, 3 backups) for DEBUG+ and stderr handler for WARNING+
- [x] Add `STATE_FILENAME` env var detection for backward-compatible log path
- [x] Create `tests/unit/test_logging_config.py` with tests for all scenarios

### 2. Create subprocess_utils.py
- [x] Create `lib/wt_orch/subprocess_utils.py` with `CommandResult`, `ClaudeResult`, `GitResult` dataclasses
- [x] Implement `run_command(cmd, timeout, cwd, max_output_size)` with timeout and output truncation
- [x] Implement `run_claude(prompt, timeout, model, extra_args)` wrapping claude CLI
- [x] Implement `run_git(*args)` wrapping git CLI
- [x] Log every invocation with structured extras: cmd, duration_ms, exit_code, output_size
- [x] Create `tests/unit/test_subprocess_utils.py` with tests for all scenarios

### 3. Create config.py
- [x] Create `lib/wt_orch/config.py` with `Directives` dataclass (all 50+ fields with defaults)
- [x] Implement `parse_duration(input_str) -> int` — Migrated from: utils.sh:parse_duration() L46-73
- [x] Implement `format_duration(secs) -> str` — Migrated from: utils.sh:format_duration() L119-130
- [x] Implement `brief_hash(path) -> str` — Migrated from: utils.sh:brief_hash() L732-737
- [x] Implement `parse_next_items(brief_path) -> list[str]` — Migrated from: utils.sh:parse_next_items() L227-261
- [x] Implement `parse_directives(doc_path) -> dict` with full validation for all directive keys — Migrated from: utils.sh:parse_directives() L266-729
- [x] Implement `load_config_file(config_path) -> dict` with PyYAML + fallback parser — Migrated from: utils.sh:load_config_file() L743-784
- [x] Implement `resolve_directives(input_file, cli_overrides) -> dict` with 4-level precedence — Migrated from: utils.sh:resolve_directives() L788-819
- [x] Implement `find_input(spec_override, brief_override) -> tuple[str, str]` returning (mode, path) — Migrated from: utils.sh:find_input() L160-213
- [x] Implement `find_openspec_dir() -> str` — Migrated from: utils.sh:find_openspec_dir() L216-224
- [x] Implement `auto_detect_test_command(directory) -> str`
- [x] Create `tests/unit/test_config.py` with tests for all functions, including edge cases from bash

### 4. Create events.py
- [x] Create `lib/wt_orch/events.py` with `EventBus` class
- [x] Implement `emit(type, change, data)` appending JSONL lines — Migrated from: events.sh:emit_event() L19-61
- [x] Implement `rotate_log()` with size check and 3-archive retention — Migrated from: events.sh:rotate_events_log() L66-86
- [x] Implement periodic rotation check every 100 emissions
- [x] Implement `query_events(type, change, since, last_n)` with filter support — Migrated from: events.sh:query_events() L92-139
- [x] Implement `subscribe(type, handler)` and `"*"` wildcard for in-process event bus
- [x] Verify JSONL output byte-compatibility with bash version
- [x] Create `tests/unit/test_events.py` with tests for all scenarios

### 5. Extend cli.py with config and events subcommands
- [x] Add `config` subcommand group to `cli.py` with `parse-directives` and `resolve-directives` actions
- [x] Add `events` subcommand to `cli.py` with `--type`, `--change`, `--last`, `--since`, `--json` flags
- [x] Test CLI dispatch end-to-end

### 6. Update bash callers to use wt-orch-core
- [x] Replace `parse_directives()` call in `bin/wt-orchestrate` with `wt-orch-core config parse-directives`
- [x] Replace `resolve_directives()` call with `wt-orch-core config resolve-directives`
- [x] Replace `load_config_file()` call with `wt-orch-core config load-config`
- [x] Replace `parse_duration()` calls across orchestration modules with `wt-orch-core config parse-duration`
- [x] Replace `format_duration()` calls across orchestration modules with `wt-orch-core config format-duration`
- [x] Replace `brief_hash()` call with `wt-orch-core config brief-hash`
- [x] Replace `parse_next_items()` call with `wt-orch-core config parse-next-items`
- [x] Replace `find_input()` call with `wt-orch-core config find-input`
- [x] Update `cmd_events()` in `bin/wt-orchestrate` to delegate to `wt-orch-core events`

### 7. Delete migrated bash functions
- [x] Replace `parse_duration()`, `format_duration()`, `find_brief()`, `find_input()`, `find_openspec_dir()`, `parse_next_items()`, `parse_directives()`, `brief_hash()`, `load_config_file()`, `resolve_directives()` in `lib/orchestration/utils.sh` with thin Python-delegating wrappers
- [x] Replace `cmd_events()` in `lib/orchestration/events.sh` with Python delegation
- [x] Keep `safe_jq_update()`, `with_state_lock()`, `update_progress_ts()`, `any_loop_active()` in utils.sh (needed by non-migrated modules)
- [x] Keep `emit_event()`, `rotate_events_log()`, `query_events()` in events.sh (needed by non-migrated modules)

### 8. Verify parity and run full test suite
- [x] Run pytest for all new Python tests (117/117 passing)
- [x] Run existing bash self-test functions via delegated wrappers (parse_duration, format_duration, brief_hash, parse_directives all verified)
- [x] Verify directive output parity: JSON output matches expected structure (milestones nested, hooks conditional, types correct)
- [x] Verify events.jsonl format parity: compact JSON, correct field order, change field omission verified
