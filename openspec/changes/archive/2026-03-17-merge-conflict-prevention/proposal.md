# Merge Conflict Prevention

## Problem

Merge conflicts are the #1 cause of sentinel interventions across E2E runs #13–#17. In run #17, 10/11 changes required manual merge — every single one due to lockfile/runtime file conflicts that the pipeline couldn't auto-resolve.

Root causes identified through 5 E2E runs:
1. `pnpm-lock.yaml` conflicts when parallel changes both modify dependencies
2. `.claude/*` runtime files (activity.json, loop-state.json, logs/) committed by agents
3. `partial_mode=false` prevented auto-resolution when mixed (lockfile + app code) conflicts existed
4. Engine dispatches new changes while merge queue still draining — archive race (Bug #38)
5. No conflict classification — LLM receives 4000-line lockfiles it can't resolve

## Solution

Multi-layer conflict prevention:

**Layer 1 (git-level): `.gitattributes merge=ours`** — prevents lockfile and runtime file conflicts from ever appearing as git conflicts. Experimentally validated: eliminates 100% of lockfile conflicts with zero side effects.

**Layer 2 (wt-merge): `partial_mode=true` always** — when gitattributes isn't configured (older projects), auto-resolve generated files even in mixed-conflict scenarios. LLM only receives app code conflicts (~50-200 lines instead of ~4000).

**Layer 3 (engine): merge-before-dispatch serialization** — drain merge queue completely before dispatching new changes. Eliminates archive race (Bug #38) where new worktrees miss archive commits.

## Scope

- `bin/wt-merge`: generated file pattern coverage expansion
- `lib/set_orch/engine.py`: merge-before-dispatch serialization
- `lib/set_orch/dispatcher.py`: gitattributes setup in bootstrap_worktree()
- `tests/e2e/run.sh`, `tests/e2e/run-complex.sh`: scaffold gitattributes (already committed)

## Already Committed (pre-change)

- `8144b8d4f`: partial_mode=true in wt-merge
- `21f4e72dd`: .gitattributes in scaffold + benchmark framework

## Out of Scope

- DB/Frontend separation in planner (analysis showed not beneficial)
- Post-merge git hook (experimentally proven harmful — leaves 49 dirty files)
- `@pnpm/merge-driver` (adds global dependency, merge=ours is simpler and sufficient)
