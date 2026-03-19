## Why

Phase 8 of the Python migration. Phases 1-7 created Python modules for all core orchestration logic but left behind ~4,200 LOC of bash wrappers (thin shell functions that call `set-orch-core` CLI) plus ~2,400 LOC of unmigrated modules (digest, watchdog, auditor, builder, orch-memory, server-detect). This phase eliminates the wrapper layer entirely and migrates the remaining modules, making the orchestration engine 100% Python with zero bash dependency.

## What Changes

- **Wrapper elimination**: Remove bash wrapper functions from `state.sh`, `planner.sh`, `dispatcher.sh`, `verifier.sh`, `merger.sh`, `monitor.sh`, `events.sh`, `config.sh`, `utils.sh`, `reporter.sh`, `milestone.sh`. All callers (`bin/set-orchestrate`, `bin/wt-loop`) updated to call Python directly via `set-orch-core` CLI or Python imports
- **New `lib/set_orch/digest.py`** (~600 LOC): 1:1 migration of `digest.sh` (1,311 LOC) — spec scanning, classification, requirement extraction, coverage tracking, triage generation, digest validation, ID stabilization
- **New `lib/set_orch/watchdog.py`** (~250 LOC): 1:1 migration of `watchdog.sh` (424 LOC) — per-change timeout detection, action hash loop detection, escalation levels, progress baseline tracking
- **New `lib/set_orch/auditor.py`** (~180 LOC): 1:1 migration of `auditor.sh` (298 LOC) — post-phase LLM audit prompt building, spec-vs-implementation gap detection
- **New `lib/set_orch/builder.py`** (~100 LOC): 1:1 migration of `builder.sh` (151 LOC) — base build health check, LLM-assisted build fix
- **Extend existing modules**: `orch-memory.sh` (145 LOC) functions absorbed into existing `state.py`/`events.py`; `server-detect.sh` (113 LOC) absorbed into `config.py`
- **Delete all `lib/orchestration/*.sh` files** after migration — the directory becomes empty/removable
- Unit tests for all new modules

## Capabilities

### New Capabilities
- `spec-digest-engine`: Spec directory scanning, classification, requirement extraction, digest validation, ID stabilization, coverage tracking, triage generation — full digest pipeline
- `orchestration-watchdog`: Per-change timeout detection, action hash ring loop detection, escalation levels (restart → redispatch → fail), progress baseline tracking
- `post-phase-auditor`: Post-phase LLM audit prompt construction, spec-vs-implementation gap analysis, merged change scope collection
- `build-health-check`: Base build verification, package manager detection, LLM-assisted build fix agent

### Modified Capabilities
- `orchestration-config`: Add dev server detection and package manager detection (from server-detect.sh absorption)

## Impact

- **Deleted**: All 17 files in `lib/orchestration/*.sh` (~6,684 LOC total)
- **New**: `lib/set_orch/digest.py`, `watchdog.py`, `auditor.py`, `builder.py`
- **Modified**: `lib/set_orch/config.py` (server-detect), `lib/set_orch/state.py` (orch-memory), `lib/set_orch/cli.py` (new subcommand groups)
- **Modified**: `bin/set-orchestrate` — remove `source lib/orchestration/*.sh` lines, call Python directly
- **Tests**: `test_digest.py`, `test_watchdog.py`, `test_auditor.py`, `test_builder.py`
- **Dependencies**: No new external deps — uses existing `jinja2`, `dataclasses`, `fcntl`
