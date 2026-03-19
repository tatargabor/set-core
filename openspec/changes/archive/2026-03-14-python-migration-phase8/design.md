## Context

Phases 1-7 migrated all core orchestration logic to Python (`lib/set_orch/`) but left bash wrappers in `lib/orchestration/*.sh` that call `set-orch-core` CLI. Six modules remain unmigrated: `digest.sh` (1,311 LOC), `watchdog.sh` (424), `auditor.sh` (298), `builder.sh` (151), `orch-memory.sh` (145), `server-detect.sh` (113). The wrapper pattern adds ~50ms per call (bash→CLI→Python) and makes debugging harder (two stack traces).

## Goals / Non-Goals

**Goals:**
- Migrate remaining 6 bash modules to Python in `lib/set_orch/`
- Eliminate all bash wrapper functions — callers use `set-orch-core` CLI directly
- Delete `lib/orchestration/` directory entirely
- Maintain 1:1 behavioral parity with bash originals
- Unit tests for all new modules

**Non-Goals:**
- Refactoring or improving migrated logic (1:1 migration only)
- Migrating `bin/set-orchestrate` itself (stays bash, calls `set-orch-core`)
- Migrating `lib/loop/` or `lib/hooks/` (Phase 9)
- Changing output formats (JSON, events.jsonl, digest YAML)

## Decisions

1. **digest.sh → digest.py**: Largest remaining module. Key functions: `cmd_digest()`, `scan_spec_directory()`, `build_digest_prompt()`, `call_digest_api()`, `write_digest_output()`, `validate_digest()`, `stabilize_ids()`, `check_digest_freshness()`, `populate_coverage()`, `check_coverage_gaps()`, `update_coverage_status()`, `generate_triage_md()`, `parse_triage_md()`, `merge_triage_to_ambiguities()`, `merge_planner_resolutions()`. CLI subcommand group: `set-orch-core digest *`.

2. **watchdog.sh → watchdog.py**: Per-change health monitoring. Functions: `watchdog_check()`, `watchdog_init_state()`, `detect_hash_loop()`, `escalate_stuck_change()`. CLI: `set-orch-core watchdog *`.

3. **auditor.sh → auditor.py**: Post-phase audit prompt builder. Functions: `build_audit_prompt()`, `run_audit()`, `parse_audit_result()`. CLI: `set-orch-core audit *`.

4. **builder.sh → builder.py**: Build health check. Functions: `check_base_build()`, `fix_base_build()`. CLI: `set-orch-core build *`.

5. **orch-memory.sh absorption**: `orch_remember()`, `orch_recall()`, `orch_gate_stats()` — thin wrappers around `set-memory` CLI. Absorb into existing `events.py` (remember is event-like) or keep as standalone `orch_memory.py` helper.

6. **server-detect.sh absorption**: `detect_dev_server()`, `detect_package_manager()`, `install_dependencies()` — config/environment detection. Absorb into `config.py`.

7. **Wrapper elimination strategy**: After all modules migrated, update `bin/set-orchestrate` to remove all `source lib/orchestration/*.sh` lines. Functions that were called directly in bash now go through `set-orch-core` CLI. The `bin/set-orchestrate` main script stays bash but becomes a thin orchestrator that delegates everything to Python.

8. **CLI subcommand registration**: New groups added to `lib/set_orch/cli.py`: `digest`, `watchdog`, `audit`, `build`. Each follows existing pattern (click group + subcommands).

## Risks / Trade-offs

- **digest.sh complexity**: The digest module has heavy text processing (spec scanning, YAML generation, ID stabilization). Python's `pathlib`, `yaml`, and string processing are actually better suited for this than bash.
- **set-orchestrate coupling**: The main orchestrate script sources all `lib/orchestration/*.sh` files and calls functions directly. After migration, it must call `set-orch-core` for everything — this is more subprocess calls but cleaner separation.
- **Testing the elimination**: Must verify that `bin/set-orchestrate` still works end-to-end after removing all bash sources. The existing E2E test infrastructure can validate this.
