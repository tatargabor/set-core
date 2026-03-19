# Tasks — python-migration-phase8

## Phase 8: Orchestration Engine Completion

### 1. Digest Engine Migration

- [x] Create `lib/set_orch/digest.py` with `scan_spec_directory()` — recursive spec file finder with ignore patterns
- [x] Add `build_digest_prompt()` — assemble LLM prompt from spec files and project context
- [x] Add `call_digest_api()` — Claude CLI call with retry, parse `DigestResult` dataclass
- [x] Add `write_digest_output()` — write `index.yaml`, `requirements.yaml`, `dependencies.yaml`, `coverage.yaml`, `domains/*.md`
- [x] Add `stabilize_ids()` — preserve requirement IDs across re-digests by content similarity matching
- [x] Add `validate_digest()` — check structural integrity (files exist, unique IDs, valid refs)
- [x] Add `populate_coverage()`, `check_coverage_gaps()`, `update_coverage_status()` — coverage tracking
- [x] Add `generate_triage_md()`, `parse_triage_md()`, `merge_triage_to_ambiguities()`, `merge_planner_resolutions()` — triage pipeline
- [x] Add `check_digest_freshness()` — compare spec mtime vs digest mtime
- [x] Register CLI subcommands: `set-orch-core digest run|validate|coverage|freshness`
- [x] Create `tests/unit/test_digest.py` — scanning, ID stabilization, validation, coverage, freshness tests

### 2. Watchdog Migration

- [x] Create `lib/set_orch/watchdog.py` with `WatchdogResult` dataclass and `watchdog_check()` — per-change health evaluation
- [x] Add `watchdog_init_state()` — create initial baseline (file count, test count, iteration)
- [x] Add `detect_hash_loop()` — ring buffer analysis for action hash repetition
- [x] Add escalation logic — levels 0-3 (ok → restart → redispatch → fail), reset on progress
- [x] Register CLI subcommands: `set-orch-core watchdog check|status`
- [x] Create `tests/unit/test_watchdog.py` — timeout, hash loop, escalation, progress reset tests

### 3. Auditor Migration

- [x] Create `lib/set_orch/auditor.py` with `build_audit_prompt()` — collect merged changes with scopes and file lists
- [x] Add `run_audit()` — Claude CLI call, parse gaps/recommendations/coverage_score
- [x] Add `parse_audit_result()` — structured finding extraction with severity levels
- [x] Register CLI subcommands: `set-orch-core audit run|prompt`
- [x] Create `tests/unit/test_auditor.py` — prompt construction, result parsing, severity tests

### 4. Builder + Server-Detect + Orch-Memory Migration

- [x] Create `lib/set_orch/builder.py` with `check_base_build()` — auto-detect PM, run build, cache result
- [x] Add `fix_base_build()` — LLM-assisted build fix with single attempt guard
- [x] Add `detect_dev_server()` and `detect_package_manager()` to `lib/set_orch/config.py` (from server-detect.sh)
- [x] Add `install_dependencies()` to `config.py` — run PM install command
- [x] Add `orch_remember()`, `orch_recall()`, `orch_gate_stats()` to `lib/set_orch/events.py` or new `orch_memory.py`
- [x] Register CLI subcommands: `set-orch-core build check|fix|detect-server|detect-pm`
- [x] Create `tests/unit/test_builder.py` — PM detection, dev server cascade, build caching tests

### 5. Wrapper Elimination

> **Deferred**: `bin/set-orchestrate` stays bash (design non-goal to migrate it). The bash files in
> `lib/orchestration/` are sourced by `set-orchestrate` and call functions across each other (monitor.sh
> calls watchdog_check, merger.sh calls orch_remember, etc.). Deleting them requires migrating
> `set-orchestrate` itself to Python. The Python modules + CLI endpoints are ready for that cutover.

- [x] All 6 Python modules created with `set-orch-core` CLI subcommands (digest, watchdog, audit, build)
- [x] All unit tests passing (517/517)
- [ ] ~~Update `bin/set-orchestrate` — remove all `source lib/orchestration/*.sh` lines~~ (deferred: requires migrating set-orchestrate to Python)
- [ ] ~~Delete `lib/orchestration/` bash files~~ (deferred: set-orchestrate still sources them)
