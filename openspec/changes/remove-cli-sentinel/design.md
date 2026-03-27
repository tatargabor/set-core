# Design: Remove CLI set-sentinel

## Context

Three sentinel execution paths exist:
1. **`bin/set-sentinel`** (bash, 1135 lines) — supervised `set-orchestrate start` with crash recovery
2. **`/set:sentinel`** (Claude skill, 480 lines) — intelligent supervisor with Tier 1-3 authority
3. **`set-orchestrate start`** (Python) — raw orchestration engine, single run

Path 1 is redundant. Path 2 (launched via supervisor.py from web UI) is strictly superior. Path 3 exists for direct/scripted use.

## Goals
- Remove the bash `set-sentinel` script and its sole dependent (`set-sentinel-rotate`)
- Update all docs/scripts that reference `set-sentinel` CLI usage
- Zero impact on web UI, supervisor.py, or the Claude skill

## Non-Goals
- Changing the `/set:sentinel` skill behavior
- Removing sentinel helper scripts used by the skill (`-finding`, `-inbox`, `-log`, `-status`)
- Modifying supervisor.py or web API endpoints

## Decisions

### D1: Remove only `bin/set-sentinel` and `bin/set-sentinel-rotate`
**Why:** The other 4 helper scripts (`-finding`, `-inbox`, `-log`, `-status`) are actively used by the Claude skill (`sentinel.md`). Removing them would break the skill.

### D2: Keep `tests/graceful-shutdown/` and `tests/orchestrator/test-sentinel-v2.sh` but update them
**Why:** These tests validate sentinel behavior. They should point to the skill-based flow, or be removed if they only test the bash script.

### D3: Don't modify openspec/specs/ or archived changes
**Why:** Specs describe what the system should do (requirements), not implementation. The sentinel capability remains — only the CLI entry point is removed. Archive is immutable history.

## Risks / Trade-offs

- **[Risk]** Users scripting `set-sentinel` in CI/cron → **Mitigation:** Document `set-orchestrate start` as replacement for non-interactive use
- **[Risk]** Test scripts reference `set-sentinel` → **Mitigation:** Update or remove test scripts that only tested the bash wrapper
