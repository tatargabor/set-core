## Context

set-core is a bash-heavy CLI toolkit with 7 monolithic scripts (1000-3700 lines each). These grew organically as features were added. The codebase works but is hard to maintain — a single change to set-memory requires understanding 3713 lines of interleaved concerns (CRUD, rules, todos, sync, migration, metrics/UI).

Current structure: main scripts in `bin/`, some shared code in `lib/orchestration/` and `lib/audit/`, shared utilities in `bin/wt-common.sh`.

## Goals / Non-Goals

**Goals:**
- Split monolithic scripts into focused modules under `lib/`
- Each module has a single responsibility and is independently testable
- Main scripts become thin dispatchers (~300 lines) that source lib modules
- Add unit tests for extracted modules
- Zero CLI/behavior changes — purely internal restructuring

**Non-Goals:**
- Rewriting bash to Python or another language
- Changing CLI interfaces or command names
- Refactoring well-structured components (gui/, set-sentinel, events.sh)
- Splitting MCP server (keep as single file for simpler deployment)
- Adding new features or changing behavior

## Decisions

### 1. Source-based modularization (not subcommand binaries)

**Decision:** Extract functions into `lib/<domain>/*.sh` files, sourced by main scripts.

**Why not separate binaries:** Bash function calls within a sourced script are ~1000x faster than spawning subprocesses. Many functions share state (variables, file handles). Source-based splitting preserves this while improving organization.

**Alternative considered:** Git-style subcommand binaries (set-memory-sync, set-memory-rules). Rejected because of subprocess overhead and shared state complexity.

### 2. Directory layout convention

**Decision:** `lib/<domain>/` subdirectories matching the main script name:
```
lib/memory/     ← sourced by bin/set-memory
lib/hooks/      ← sourced by bin/wt-hook-memory
lib/loop/       ← sourced by bin/wt-loop
lib/editor.sh   ← sourced by bin/wt-common.sh (flat, single file)
```

Orchestration already has `lib/orchestration/` — we refactor within that existing directory.

**Why:** Clear 1:1 mapping between bin script and lib directory. Easy to find code.

### 3. Infrastructure stays in main script

**Decision:** Shared infrastructure functions (resolve_project, get_storage_path, run_with_lock, logging) remain in the main bin/ script. Extracted modules can use them because they're sourced after infrastructure setup.

**Why:** These functions are used by ALL modules. Extracting them would create a circular dependency (main sources lib, lib needs infra from main). Keeping infra in main means modules get it "for free" via source order.

### 4. Phase execution order

**Decision:** Phases ordered by risk/impact ratio:
1. wt-common.sh editor extract — lowest risk (self-contained, 4 scripts)
2. set-memory — highest impact (largest monolith)
3. wt-hook-memory — second largest, hooks are critical path
4. orchestration — medium risk, coupling fixes needed
5. wt-loop — well-understood structure
6. set-project — smallest change

Each phase is independently committable and deployable.

### 5. Testing approach

**Decision:** Unit tests source the lib file directly and test functions in isolation. Tests go in `tests/unit/test_<module>.sh`. Use simple assert patterns (no test framework dependency).

**Why:** Bash testing frameworks add complexity. Simple `assert_equals` / `assert_contains` helpers in a shared `tests/unit/helpers.sh` are sufficient and transparent.

## Risks / Trade-offs

**[Risk] Source order dependencies** — Modules may depend on functions defined in other modules or the main script.
→ Mitigation: Document source order in each main script. Infrastructure is always sourced first. Modules declare dependencies in header comments.

**[Risk] Regression during extraction** — Moving code between files could introduce subtle bugs (variable scoping, missing sources).
→ Mitigation: Each phase runs existing integration tests before merging. No behavior changes means existing tests are sufficient for regression detection.

**[Risk] Performance impact of multiple source calls** — Sourcing 7 files instead of 1 adds startup overhead.
→ Mitigation: Measured bash `source` overhead: ~1-2ms per file. Total impact: <15ms. Negligible compared to actual command execution (50-500ms for memory operations).

**[Trade-off] More files to navigate** — 7 monoliths become ~30 focused modules.
→ Accepted: Each file is 100-700 lines instead of 1000-3700. Easier to understand individually. Directory structure provides clear navigation.

## Migration Plan

1. Each phase is a separate commit (or commit series)
2. No rollback needed — if a phase has issues, revert the commit
3. No deployment changes — install.sh copies bin/ and lib/ as before
4. Consumer projects (sales-raketa) get changes via `set-project init` redeploy
5. No migration scripts needed — purely source-level restructuring
