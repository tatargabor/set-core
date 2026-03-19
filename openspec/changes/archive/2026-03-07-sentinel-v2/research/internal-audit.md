# Sentinel-v2 OpenSpec Change: Internal Completeness Audit

## 1. PROPOSAL-TO-SPEC COVERAGE

The proposal lists **4 new capabilities** and **4 modified capabilities** (8 total).

### New Capabilities (4/4 have specs)

| Capability | Spec File | Status |
|---|---|---|
| `orchestration-watchdog` | `specs/orchestration-watchdog/spec.md` | COVERED |
| `orchestration-events` | `specs/orchestration-events/spec.md` | COVERED |
| `project-knowledge` | `specs/project-knowledge/spec.md` | COVERED |
| `orchestration-context-pruning` | `specs/orchestration-context-pruning/spec.md` | COVERED |

### Modified Capabilities (0/4 have delta specs)

| Capability | Delta Spec | Tasks Coverage | Status |
|---|---|---|---|
| `orchestration-engine` (module decomposition) | NONE | Tasks 1.1-1.8 | Covered by tasks only |
| `sentinel-polling` (liveness checking) | NONE | Tasks 9.1-9.5 | Covered by tasks only |
| `per-change-model` (complexity routing) | NONE | Tasks 7.1-7.3 | Covered by tasks only |
| `verify-gate` (project-knowledge rules) | NONE | Tasks 8.1-8.4 | Covered by tasks only |

**GAP: No delta specs exist for any of the 4 modified capabilities.** The tasks cover these, but there is no spec-level requirements document that a future developer or auditor can reference for the modified behaviors. This is a soft gap -- the tasks are detailed enough to serve as requirements, but it deviates from OpenSpec best practice.

---

## 2. DESIGN-TO-TASK COVERAGE

The design contains **8 decisions**. Each should map to at least one task.

| Decision | Description | Task Mapping | Status |
|---|---|---|---|
| D1 | Sourced Library Modules | 1.1-1.8 (module extraction) | COVERED |
| D2 | Function-to-Module Mapping | 1.2-1.7 (exact function lists per module) | COVERED |
| D3 | Watchdog Design | 3.1-3.10 | COVERED |
| D4 | Event Log Design | 2.1-2.13 | COVERED |
| D5 | Project Knowledge System | 5.1-5.4, 6.1-6.3, 8.1-8.4, 10.1-10.2 | COVERED |
| D6 | Enhanced Sentinel | 9.1-9.5 | COVERED |
| D7 | Worktree Context Pruning | 4.1-4.4 | COVERED |
| D8 | Per-Change Model Routing | 7.1-7.3 | COVERED |

All 8 design decisions have corresponding tasks.

---

## 3. SPEC-TO-TASK COVERAGE MATRIX

### orchestration-watchdog/spec.md

| Requirement | Task(s) | Status |
|---|---|---|
| R1: Per-State Timeout Detection | 3.2 | COVERED |
| R2: Action Hash Loop Detection | 3.3 | COVERED |
| R3: Orchestrator Self-Liveness | 3.5 (heartbeat), 9.2 (sentinel check) | COVERED |
| R4: Escalation Chain | 3.4, 3.6 | COVERED |
| R5: Watchdog State Storage | 3.7 | COVERED |
| R6: Configuration | 3.10 | COVERED |

### orchestration-events/spec.md

| Requirement | Task(s) | Status |
|---|---|---|
| R1: Event Emission | 2.1 | COVERED |
| R2: Event Types | 2.3-2.10 | COVERED |
| R3: Automatic Emission | 2.3, 2.4 | COVERED |
| R4: Event Log Rotation | 2.2 | COVERED |
| R5: Event Query | 2.12 | COVERED |
| R6: Auto Run Report | 2.13 | COVERED |
| R7: Coexistence with State File | Implicit (no state format changes) | COVERED (implicitly) |
| R8: Configuration | 2.11 | COVERED |

### project-knowledge/spec.md

| Requirement | Task(s) | Status |
|---|---|---|
| R1: Project Knowledge File | 5.1 | COVERED |
| R2: Cross-Cutting Files Section | 5.1 (template) | COVERED |
| R3: Features Section | 5.1 (template) | COVERED |
| R4: Verification Rules Section | 5.1 (template), 8.1-8.3 | COVERED |
| R5: Cross-Cutting Checklist Rule | 5.2 | COVERED |
| R6: Scaffolding Tool | 5.3, 5.4 | COVERED |
| R7: Planner Integration | 6.1, 6.2 | COVERED |
| R8: Dispatcher Integration | 10.1, 10.2 | COVERED |
| R9: Verifier Integration | 8.1, 8.2, 8.3 | COVERED |
| R10: Graceful Degradation | 8.4 | COVERED |

### orchestration-context-pruning/spec.md

| Requirement | Task(s) | Status |
|---|---|---|
| R1: Prune Orchestrator Commands | 4.1 | COVERED |
| R2: Preserve Agent-Essential Files | 4.1 (implicit in implementation) | PARTIALLY -- no explicit negative test task |
| R3: Configurable | 4.2 | COVERED |
| R4: Logging | 4.4 | COVERED |
| R5: Integration Point | 4.3 | COVERED |

---

## 4. GAPS FOUND

### GAP-1: Agent Teams Abstraction Layer -- MISSING from specs AND tasks
The proposal (line 47) mentions "Agent Teams abstraction layer: dispatch via wt-loop (current) or Claude Code Agent Teams (when available)." The design (D2, dispatcher.sh) does not mention it except as a non-goal for implementation. However, the proposal's `orchestration-engine` modified capability description explicitly says "dispatcher enhanced with model routing and Agent Teams abstraction."

**Status:** The abstraction layer itself has zero tasks. The design says "not the implementation" is a non-goal, but the abstraction interface (e.g., a dispatch function that could be swapped) is implied as in-scope. There is no task to create this abstraction point.

**Recommendation:** Either add a task "10.3: Add dispatch abstraction point in `dispatch_change()` for future Agent Teams support" or remove the Agent Teams mention from the proposal's modified capabilities.

### GAP-2: No delta specs for modified capabilities
As noted in section 1, the 4 modified capabilities (`orchestration-engine`, `sentinel-polling`, `per-change-model`, `verify-gate`) lack delta spec documents. While the tasks are sufficient for implementation, delta specs would capture the "before/after" contract for each modified behavior.

**Recommendation:** At minimum, add a one-paragraph delta note in the design.md or create lightweight `specs/<name>/delta.md` files documenting the behavioral changes.

### GAP-3: Replan done-check -- partially covered
The proposal says "Replan done-check: inject git log + completed change list into replanner prompt (fixes v10 replan duplication bug)." Task 6.3 covers "inject git log of completed changes and their file lists." However, the current `auto_replan_cycle()` code already injects `_REPLAN_COMPLETED` (completed roadmap items). The delta is specifically "git log of completed changes" -- their actual file-level diffs. Task 6.3 mentions this but the spec for project-knowledge does not cover it (it is planner behavior, not project-knowledge).

**Status:** Covered by task 6.3, but no spec formalizes this requirement. Minor gap.

### GAP-4: No task for the thin wrapper's sourcing chain validation
Design D1 specifies a precise sourcing order: `events.sh` first (other modules emit events), then `state.sh`, `watchdog.sh`, `planner.sh`, `dispatcher.sh`, `verifier.sh`, `merger.sh`. Task 1.7 says "add source statements for all modules" but does not emphasize the **ordering constraint** that events.sh must be sourced first. If this order is wrong, emit_event calls from state.sh would fail at runtime.

**Recommendation:** Add a note to task 1.7 or a new sub-task: "1.7a: Verify source order matches design D1 -- events.sh must be sourced before all other modules."

### GAP-5: No task for SENTINEL_RESTART event emission
The events spec (R2) lists `SENTINEL_RESTART` as an event type. Task 9.4 says "Emit SENTINEL_RESTART event when restarting orchestrator." However, `set-sentinel` is a standalone script that does NOT source `lib/orchestration/events.sh`. The sentinel currently uses its own `sentinel_log()` function. There is no task for how the sentinel will emit a JSONL event to the events file.

**Recommendation:** Add a sub-task under 9.4: "Implement JSONL append in set-sentinel (either inline or source events.sh) to emit SENTINEL_RESTART events."

### GAP-6: Existing stall detection overlap with watchdog
The current `poll_change()` (lines 3596-3641) already implements stall detection: tracking `stall_count`, checking loop-state mtime staleness, verifying PID liveness, auto-resuming up to 3 times, then marking failed. The watchdog spec (R1, R4) proposes a very similar but different mechanism: `last_activity_epoch`, `escalation_level` 0-4, with different thresholds.

**No task addresses migrating or decommissioning the existing stall detection code.** If both run, the old stall_count system and the new watchdog will conflict -- potentially double-resuming or double-killing changes.

**Recommendation:** Add a task: "3.11: Migrate existing stall detection in `poll_change()` to use watchdog infrastructure -- remove `stall_count` logic, replace with `watchdog_check()` calls."

---

## 5. RISKS

### RISK-1: Variable scope breakage during module extraction (HIGH)
The current monolith uses global variables extensively: `STATE_FILENAME`, `PLAN_FILENAME`, `LOG_FILE`, `DEFAULT_IMPL_MODEL`, `BASE_BUILD_STATUS`, `_MEM_OPS_COUNT`, etc. When functions are moved to separate `.sh` files and sourced back, `local` variables in the calling function are not visible to the called function across files. This is fine for `source`d files (they share the global scope), but any function declared `local` in the wrapper that is used by a module function will break.

**Specific example:** `monitor_loop()` declares many `local` variables (`smoke_command`, `smoke_timeout`, `smoke_blocking`, etc.) that are passed as arguments to `poll_change()` and `handle_change_done()`. If these functions move to `verifier.sh`, the argument passing is preserved. BUT the `smoke_command` etc. variables in `poll_change()` at line 3594 are NOT passed as arguments -- they are accessed as **closure-like** variables from `monitor_loop()`'s scope. After extraction, `poll_change()` in `verifier.sh` will not see these locals.

**Mitigation:** Task 1.8 covers self-test validation, but a more thorough approach is needed. Each extracted module needs an explicit contract for which globals it reads. The smoke-related variables being passed through `poll_change` to `handle_change_done` rely on shell closure behavior that breaks across files.

### RISK-2: Dual stall detection (MEDIUM)
As described in GAP-6, running both the existing `stall_count` system and the new watchdog simultaneously could cause: double-resume (two resume_change calls for the same stuck change), or the watchdog marking a change as failed while the old system is still trying to resume it.

### RISK-3: Event emission performance impact (MEDIUM)
Every `update_change_field()` call for a status change will now also call `emit_event()`, which does a `date -Iseconds`, JSON construction, and file append. In the monitor loop, `update_change_field()` is called many times per poll cycle (token updates, status updates, retry counts). The design says tokens_used updates also emit TOKENS events (task 2.4). With 3-5 active changes polled every 15s, each emitting 1-2 events, this adds file I/O overhead.

**Mitigation:** Consider batching events or only emitting TOKENS events on significant deltas (e.g., >10K tokens change).

### RISK-4: Sentinel sourcing events.sh (LOW-MEDIUM)
The sentinel (`bin/set-sentinel`) is a 146-line standalone script. To emit `SENTINEL_RESTART` events, it needs access to `emit_event()`. Sourcing all of `lib/orchestration/events.sh` is one option, but if events.sh depends on globals set by the orchestrator (like `LOG_FILE`), this could fail.

### RISK-5: Context pruning false positives (LOW)
The prune patterns (`.claude/commands/wt/orchestrate*.md`, `sentinel*.md`, `manual*.md`) are glob-based. If a consumer project creates a file like `.claude/commands/wt/manual-testing-guide.md`, it would be pruned. The spec does not address user-defined files that match the glob.

---

## 6. RECOMMENDATIONS

1. **Add task 3.11** to migrate existing `stall_count`/stale detection in `poll_change()` to the new watchdog system, preventing dual-detection conflicts.

2. **Add task 1.7a** to explicitly validate the source ordering constraint from design D1, with a comment in the wrapper explaining why `events.sh` must be first.

3. **Clarify task 9.4** to specify HOW `set-sentinel` emits JSONL events -- either inline JSONL append (simple, no dependencies) or sourcing a minimal events helper.

4. **Address smoke variable closure** in task 1.5 or 1.4: the `smoke_command`, `smoke_timeout`, `smoke_blocking` variables used by `poll_change()` / `handle_change_done()` in verifier.sh are currently local to `monitor_loop()` in dispatcher.sh. After extraction, these must either become globals or be explicitly passed as function arguments. This is the highest-risk extraction detail.

5. **Decide on Agent Teams abstraction**: either add a minimal task or remove from the proposal's modified capabilities list. Currently it is promised but unplanned.

6. **Add a negative-test task for context pruning** (e.g., "4.5: Verify `.claude/rules/`, `.claude/skills/`, `CLAUDE.md`, and `loop*.md` are preserved after pruning").

7. **Consider adding delta specs** for the 4 modified capabilities, even if lightweight (1-page each). This makes the change self-documenting for future reference.

---

## Summary

| Category | Count | Details |
|---|---|---|
| Proposal capabilities | 8 | 4 new (all have specs), 4 modified (none have delta specs) |
| Design decisions | 8 | All mapped to tasks |
| Spec requirements | 30 total | 29 mapped to tasks, 1 partially covered (context pruning R2 negative test) |
| Gaps found | 6 | Agent Teams missing, no delta specs, source ordering, SENTINEL_RESTART emission, stall detection overlap, replan done-check |
| Risks identified | 5 | Variable scope breakage (HIGH), dual stall detection (MED), event I/O (MED), sentinel sourcing (LOW-MED), prune false positives (LOW) |

The change is **substantially complete** in its spec/task coverage. The most critical finding is **RISK-1** (variable scope breakage during extraction, specifically the smoke-related variables accessed as closures) and **GAP-6** (existing stall detection conflicting with the new watchdog). Both need explicit tasks added before implementation begins.
