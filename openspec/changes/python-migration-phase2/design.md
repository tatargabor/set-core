## Context

Phase 1 delivered the Python infrastructure layer (`lib/wt_orch/`) with typed state schema (`state.py`: dataclasses for `OrchestratorState`, `Change`, `WatchdogState`), structured logging, event bus, config parsing, and subprocess utilities. The state module currently handles only serialization/deserialization — all runtime mutations (field updates, dependency checks, phase management, crash recovery) remain in `lib/orchestration/state.sh` (997 lines of bash+jq).

The bash state functions are the most fragile orchestrator component: jq filter injection, quoting bugs, `set -e` traps with arithmetic, and race conditions on concurrent writes. Phase 2 migrates these to Python, extending `state.py` with mutation methods and adding CLI bridge commands.

## Goals / Non-Goals

**Goals:**
- Migrate all state mutation functions from `state.sh` to Python with 1:1 function mapping
- Add `fcntl.flock`-based file locking (consistent with the project's existing locking pattern)
- Provide `wt-orch-core state <subcommand>` CLI bridge so bash callers work during transition
- Maintain backward compatibility — bash wrappers call Python, JSON format unchanged
- Full pytest coverage for mutations, locking, deps, phases, recovery

**Non-Goals:**
- Migrating `monitor_loop` or `dispatcher` (those are Phase 7 and Phase 5)
- Changing the JSON state schema (must remain compatible with existing state files)
- Removing `state.sh` entirely (it keeps thin bash wrappers that call `wt-orch-core`)
- Migrating `cmd_status` display (complex formatting, low risk, can stay bash for now)
- Adding new state features not in the current bash implementation

## Decisions

### D1: Extend state.py vs separate mutations module
**Choice:** Extend `state.py` with mutation methods on the dataclasses + module-level functions.
**Rationale:** The mutations operate directly on `OrchestratorState` and `Change` — they are inherently part of the state module. A separate file would require importing everything from state.py anyway. The file grows from ~350 to ~750 LOC, which is manageable for a single-concern module.
**Alternative:** Separate `state_mutations.py` — rejected because it splits a cohesive concern and requires cross-module imports.

### D2: Locking strategy — fcntl.flock per-file
**Choice:** Use `fcntl.flock` with a `.lock` file adjacent to the state file (e.g., `orchestration-state.json.lock`), consistent with the project's existing locking pattern (wt-memory uses flock with `--timeout 10`).
**Rationale:** `flock` is process-safe, automatically releases on crash, and has negligible overhead. The bash `with_state_lock` already uses flock — Python just does the same natively.
**Alternative:** `filelock` pip package — rejected to avoid external dependency for a stdlib-solvable problem.

### D3: Event emission integration
**Choice:** Mutation functions accept an optional `EventBus` instance. When provided, status transitions emit `STATE_CHANGE` events, token updates emit `TOKENS` events — matching the exact event format from bash.
**Rationale:** The event bus was built in Phase 1. Mutations are the primary event source. Optional parameter keeps pure unit tests simple (no bus needed).

### D4: CLI bridge subcommands
**Choice:** Add to `wt-orch-core state` these subcommands: `update-field`, `update-change`, `get-status`, `count-by-status`, `deps-satisfied`, `cascade-failed`, `topo-sort`, `advance-phase`, `reconstruct`.
**Rationale:** During transition, bash still calls these functions. The CLI bridge pattern (`wt-orch-core state init`) was established in Phase 1 and works well.

### D5: Notification dispatch
**Choice:** Implement `send_notification()` in a new `notifications.py` module with `notify-send` (desktop) and Resend API (email) backends.
**Rationale:** Notifications are a distinct concern from state — separating them keeps state.py focused. The function signature matches bash: `send_notification(title, body, urgency)`.

### D6: Hook runner
**Choice:** Implement `run_hook()` in state.py alongside mutations (it's called during status transitions).
**Rationale:** Hooks are tightly coupled to state transitions (`on_fail` triggers on status→failed). Keeping it in state.py matches the bash structure where hooks are in state.sh.

## Risks / Trade-offs

**[Risk] Concurrent bash and Python writers during transition** → Both use the same flock file, so mutual exclusion is guaranteed. Python `flock` and bash `flock` are compatible (same syscall).

**[Risk] Event format divergence** → Python emitter must produce identical JSONL to bash `emit_event`. Mitigated by using the same field names and JSON structure, validated by test comparisons.

**[Risk] Notification failures silently swallowed** → Match bash behavior: log warning, don't crash. Notifications are best-effort.

**[Trade-off] state.py grows large (~750 LOC)** → Acceptable for a single-concern module. If it grows beyond Phase 2, refactoring to sub-modules is straightforward.
