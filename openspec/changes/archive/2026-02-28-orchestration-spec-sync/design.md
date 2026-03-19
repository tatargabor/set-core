## Context

The orchestration system (`bin/set-orchestrate`, 4233 lines) was built across 7 changes. Each change created delta specs describing new/modified capabilities, but:
1. Delta specs were never synced to `openspec/specs/` (no main orchestration specs exist)
2. Later changes modified behavior documented in earlier specs without updating them
3. Several production features were added via hotfixes without any spec

The code is the source of truth. Specs must be updated to match.

## Goals / Non-Goals

**Goals:**
- All orchestration capability specs accurately reflect current implementation
- Main specs exist in `openspec/specs/` for all orchestration capabilities
- Dead code removed, minor code inconsistencies fixed
- Single authoritative spec per capability (not scattered across 7 change directories)

**Non-Goals:**
- Refactoring the orchestrator code beyond trivial fixes
- Adding new features
- Changing behavior — this is a documentation-only change (except `init_state` boolean→integer fix and dead code removal)

## Decisions

### D1: Write specs directly in main `openspec/specs/`, not as delta specs
**Rationale:** The orchestration capabilities have no existing main specs to delta against. Creating fresh, complete specs in `openspec/specs/` is cleaner than creating delta specs that reference nonexistent parents. Each spec will be a comprehensive document covering the capability as it exists today.

### D2: One spec per logical capability, not per change
**Rationale:** The 7 changes created overlapping specs (e.g., `orchestration-engine` exists in 3 changes with different content). We consolidate into single authoritative specs:
- `orchestration-engine` — core engine (plan, dispatch, monitor, merge, replan)
- `verify-gate` — quality gate pipeline (test, build, review, verify)
- `orchestrator-memory` — memory integration
- `orchestrator-tui` — terminal dashboard
- `agent-merge-resolution` — NEW: agent-assisted conflict resolution
- `post-merge-verification` — NEW: post-merge build + dep install
- `merge-conflict-fingerprint` — NEW: conflict dedup via fingerprinting

Existing main specs that need updates: `ralph-loop` (stall_count reset behavior).

### D3: Fix `init_state()` verify_retried → verify_retry_count
**Rationale:** Line 727 initializes `verify_retried: false` (boolean) but all code paths use `verify_retry_count` (integer). This is a leftover from the original design before stabilization. Change to `verify_retry_count: 0`.

### D4: Remove or wire `auto_detect_test_command()`
**Rationale:** The function exists (lines 670-700) but is never called. The `test_command` is resolved via directives/config only. Options:
- **Remove it** — simplest, it's dead code
- **Wire it** — call in `resolve_directives()` as fallback when no explicit test_command
Recommend: wire it as lowest-priority fallback in the directive chain, since the spec (`VG-3`) intended this behavior.

## Risks / Trade-offs

- **[Risk] Spec content may not perfectly capture all edge cases** → Mitigation: specs describe documented behavior, implementation remains authoritative for edge cases
- **[Risk] Wiring `auto_detect_test_command` could change behavior for projects that previously had no test gate** → Mitigation: only activates when no explicit `test_command` is set AND a test script exists in package.json — this is the intended behavior per VG-3
