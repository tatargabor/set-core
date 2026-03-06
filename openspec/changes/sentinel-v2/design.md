## Context

The orchestration system (`bin/wt-orchestrate`, 5,220 lines) has been production-tested across multiple consumer project runs. Each run produced detailed diagnostics revealing patterns of failure: orchestrator stalls, merge conflicts from parallel changes touching shared files, no audit trail for post-mortem, excessive context in worktrees, and agents missing cross-cutting concerns. The system works but is a monolith — hard to test, hard to debug, hard to extend.

The current architecture:

```
bin/wt-orchestrate    5,220 lines    ALL orchestration logic
bin/wt-sentinel         146 lines    Crash-restart wrapper
bin/wt-loop           2,248 lines    Ralph agent loop
bin/wt-merge            538 lines    LLM merge resolution
bin/wt-new              459 lines    Worktree creation
bin/wt-common.sh        990 lines    Shared utilities
```

## Goals / Non-Goals

**Goals:**
- Decompose monolith into testable, readable modules without changing external behavior
- Add self-healing capabilities (watchdog, liveness) to eliminate manual SIGKILL interventions
- Add event-sourced audit trail for machine-parseable post-mortem analysis
- Integrate structured project knowledge for merge avoidance and cross-cutting verification
- Reduce worktree context overhead

**Non-Goals:**
- Rewriting in a different language (stays bash, sourced modules)
- Replacing wt-loop or wt-merge internals
- Building a full dependency graph engine (simple flat cross-cutting file list is sufficient)
- Auto-generating project-knowledge from code analysis (bootstrap tool only, human-curated)
- Implementing Claude Code Agent Teams dispatch (abstraction layer only, not the implementation)

## Decision 1: Sourced Library Modules (not separate executables)

**Options considered:**
1. Separate `bin/` executables communicating via JSON/files
2. Sourced bash library files under `lib/orchestration/`
3. Rewrite in Python/Node

**Chosen: Option 2 — Sourced bash libraries**

Rationale:
- Shared state (`STATE_FILENAME`, `PLAN_FILENAME`, `LOG_FILE`, directive variables) stays in global shell scope — no IPC, no serialization, no environment variable passing
- Single process = single PID for sentinel to monitor, single signal handler, no orphan child processes
- Backwards compatible: `bin/wt-orchestrate` remains the entry point, CLI unchanged
- Each module is a self-contained file that can be read and reasoned about independently
- `cmd_self_test()` can test each module's functions after sourcing

**Sourcing chain:**

```bash
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib/orchestration"

source "$SCRIPT_DIR/wt-common.sh"
source "$LIB_DIR/events.sh"      # First: other modules emit events
source "$LIB_DIR/state.sh"       # State CRUD, queries, utilities
source "$LIB_DIR/watchdog.sh"    # Self-healing hooks
source "$LIB_DIR/planner.sh"     # Plan, replan, validation
source "$LIB_DIR/dispatcher.sh"  # Dispatch, resume, pause
source "$LIB_DIR/verifier.sh"    # Poll, test, review, smoke
source "$LIB_DIR/merger.sh"      # Merge, conflict, cleanup
```

## Decision 2: Function-to-Module Mapping

Every function in the current monolith maps to exactly one module:

### `lib/orchestration/state.sh` (~400 lines)

State management, queries, utilities, memory helpers:

| Function | Current Lines |
|---|---|
| `init_state()` | 815-870 |
| `update_state_field()` | 873-879 |
| `update_change_field()` | 882-891 |
| `get_change_status()` | 931-934 |
| `get_changes_by_status()` | 937-940 |
| `count_changes_by_status()` | 943-946 |
| `deps_satisfied()` | 949-966 |
| `topological_sort()` | 971-1022 |
| `generate_summary()` | 4952-4993 |
| `trigger_checkpoint()` | 4902-4950 |
| `brief_hash()` | 566-571 |
| `load_config_file()` | 577-618 |
| `resolve_directives()` | 622-649 |
| `parse_directives()` | 293-563 |
| `parse_next_items()` | 256-290 |
| `find_brief()` | 182-203 |
| `find_input()` | 207-242 |
| `find_openspec_dir()` | 245-253 |
| `parse_duration()` | 107-134 |
| `any_loop_active()` | 139-163 |
| `format_duration()` | 166-177 |
| `send_notification()` | 1178-1199 |
| `orch_remember()` | 1471-1486 |
| `orch_recall()` | 1487-1505 |
| `orch_memory_stats()` | 1506-1518 |
| `orch_memory_audit()` | 1519-1551 |
| `orch_gate_stats()` | 1552-1581 |
| `cmd_status()` | 2303-2505 |
| `cmd_approve()` | 2597-2633 |

### `lib/orchestration/planner.sh` (~600 lines)

Planning, validation, replanning:

| Function | Current Lines | Enhancement |
|---|---|---|
| `cmd_plan()` | 1582-2071 | + project-knowledge merge avoidance |
| `validate_plan()` | 1025-1078 | |
| `check_scope_overlap()` | 1082-1174 | + file-path overlap from project-knowledge |
| `summarize_spec()` | 663-702 | |
| `estimate_tokens()` | 654-659 | |
| `detect_test_infra()` | 708-777 | |
| `auto_detect_test_command()` | 781-810 | |
| `auto_replan_cycle()` | 3429-3552 | + completed change git log injection |
| `cmd_replan()` | 2575-2596 | |

### `lib/orchestration/dispatcher.sh` (~600 lines)

Dispatch, resume, pause, monitor loop:

| Function | Current Lines | Enhancement |
|---|---|---|
| `dispatch_change()` | 2804-2947 | + context pruning, model routing |
| `dispatch_ready_changes()` | 2971-2995 | |
| `resume_stopped_changes()` | 2952-2969 | |
| `resume_change()` | 3021-3102 | |
| `pause_change()` | 2997-3019 | |
| `resume_stalled_changes()` | 4853-4868 | |
| `retry_failed_builds()` | 4872-4898 | |
| `resolve_change_model()` | 895-928 | + complexity-based routing |
| `bootstrap_worktree()` | 1429-1468 | + context pruning |
| `sync_worktree_with_main()` | 1348-1423 | |
| `check_base_build()` | 1211-1255 | |
| `fix_base_build_with_llm()` | 1260-1343 | |
| `cmd_start()` | 2073-2301 | |
| `cmd_pause()` | 2506-2527 | |
| `cmd_resume()` | 2528-2574 | |
| `monitor_loop()` | 3106-3425 | + watchdog hooks |

### `lib/orchestration/verifier.sh` (~500 lines)

Polling, testing, reviewing, smoke gate:

| Function | Current Lines | Enhancement |
|---|---|---|
| `poll_change()` | 3554-3704 | |
| `handle_change_done()` | 3807-4211 | + project-knowledge verification |
| `run_tests_in_worktree()` | 3708-3726 | |
| `review_change()` | 3730-3806 | |
| `verify_merge_scope()` | 4238-4270 | |
| `extract_health_check_url()` | 4272-4279 | |
| `health_check()` | 4283-4305 | |
| `smoke_fix_scoped()` | 4309-4396 | |

### `lib/orchestration/merger.sh` (~400 lines)

Merge, conflict resolution, cleanup:

| Function | Current Lines |
|---|---|
| `merge_change()` | 4398-4707 |
| `cleanup_worktree()` | 4710-4731 |
| `cleanup_all_worktrees()` | 4733-4752 |
| `execute_merge_queue()` | 4754-4764 |
| `retry_merge_queue()` | 4827-4848 |
| `_try_merge()` | 4771-4825 |
| `archive_change()` | 4213-4233 |

### `bin/wt-orchestrate` (thin wrapper, ~300 lines)

Retains only: constants (lines 10-60), logging functions (64-80), `model_id()`, `rotate_log()`, `cmd_self_test()`, `usage()`, `main()`.

## Decision 3: Watchdog Design

The watchdog runs **inside** the orchestrator process, hooked into the monitor loop's poll cycle — not as a separate process.

### Per-change state tracked:

```json
{
  "watchdog": {
    "last_activity_epoch": 1709500000,
    "action_hash_ring": ["abc123", "def456"],
    "consecutive_same_hash": 0,
    "escalation_level": 0
  }
}
```

Stored in `orchestration-state.json` per change, updated by watchdog functions.

### Timeout matrix:

| Status | Timeout | Action |
|---|---|---|
| `running` | 600s (configurable) no loop-state mtime change + PID dead | escalate |
| `verifying` | 300s no state change | escalate |
| `dispatched` | 120s no loop-state.json created | mark failed |

### Action hash loop detection:

Each poll cycle computes MD5 of `(loop-state.json mtime, tokens_used, ralph_status)`. If the same hash appears `watchdog_loop_threshold` (default 5) consecutive times, escalate.

### Escalation chain:

```
Level 0: Normal
Level 1: Log warning + emit WATCHDOG_WARN event
Level 2: resume_change() + emit WATCHDOG_RESUME event
Level 3: Kill Ralph PID + resume_change() + emit WATCHDOG_KILL event
Level 4: Mark failed + emit WATCHDOG_FAILED event + send notification
```

### Integration into monitor_loop:

```bash
# After polling each active change:
while IFS= read -r name; do
    poll_change "$name" ...
    watchdog_check "$name"   # NEW: timeout + loop + velocity
done <<< "$active_changes"

# End of each poll cycle:
watchdog_heartbeat              # NEW: emit heartbeat to events.jsonl
```

## Decision 4: Event Log Design

### Format: JSONL (one event per line)

```json
{"ts":"2026-03-06T10:00:00+01:00","type":"STATE_CHANGE","change":"feature-x","from":"pending","to":"running","data":{}}
{"ts":"2026-03-06T10:05:00+01:00","type":"TOKENS","change":"feature-x","delta":50000,"total":50000}
{"ts":"2026-03-06T10:10:00+01:00","type":"MERGE_ATTEMPT","change":"feature-x","success":true}
{"ts":"2026-03-06T10:10:05+01:00","type":"WATCHDOG_HEARTBEAT","data":{"active_changes":2,"active_seconds":600}}
```

### Event types:

| Type | When emitted |
|---|---|
| `STATE_CHANGE` | Any change status transition |
| `TOKENS` | Token usage delta per change |
| `DISPATCH` | Change dispatched to worktree |
| `MERGE_ATTEMPT` | Merge attempt (success/failure/conflict) |
| `VERIFY_GATE` | Gate result (test/build/review/smoke: pass/fail) |
| `REPLAN` | Replan cycle started/completed |
| `CHECKPOINT` | Checkpoint triggered |
| `WATCHDOG_WARN/RESUME/KILL/FAILED` | Watchdog actions |
| `WATCHDOG_HEARTBEAT` | Periodic orchestrator liveness (every poll) |
| `SENTINEL_RESTART` | Sentinel restarted orchestrator |
| `ERROR` | Any error condition |

### Integration:

`update_change_field()` gains automatic event emission for status changes:

```bash
update_change_field() {
    local change_name="$1" field="$2" value="$3"
    # ... existing jq update ...
    if [[ "$field" == "status" ]]; then
        emit_event "STATE_CHANGE" "$change_name" "{\"from\":\"$old\",\"to\":$value}"
    fi
}
```

### Coexistence with state.json:

| | orchestration-state.json | orchestration-events.jsonl |
|---|---|---|
| Purpose | Current snapshot | History |
| Access | Read-modify-write | Append-only |
| Used by | Monitor loop, CLI | Post-mortem, watchdog, sentinel |
| Rotation | N/A | At 1MB → archive, keep last 3 |

## Decision 5: Project Knowledge System

### Two-layer design:

**Layer 1: `.claude/project-knowledge.yaml`** (planner/verifier, NOT per-turn agent)

```yaml
version: 1

cross_cutting_files:
  sidebar:
    path: "src/components/app-sidebar.tsx"
    description: "Navigation menu — add NavItem for new pages"
  i18n_primary:
    path: "messages/hu.json"
    description: "Primary locale translations"
  i18n_secondary:
    path: "messages/en.json"
    description: "Secondary locale — must mirror primary"
  activity_logger:
    path: "src/lib/activity-logger.ts"
    description: "Activity action enum — extend for new actions"

features:
  companies:
    paths: ["src/app/(dashboard)/companies/**"]
    reference_impl: true
    touches: [sidebar, i18n_primary, i18n_secondary, activity_logger]

verification_rules:
  - name: i18n-parity
    trigger: { file_modified: "messages/hu.json" }
    expect: { file_modified: "messages/en.json" }
    severity: error
  - name: sidebar-for-new-pages
    trigger: { file_created: "src/app/(dashboard)/*/page.tsx" }
    expect: { file_modified: "src/components/app-sidebar.tsx" }
    severity: warning
```

**Layer 2: `.claude/rules/cross-cutting-checklist.md`** (per-turn agent, path-scoped)

A simple checklist rule with `paths:` frontmatter targeting dashboard feature files. Contains the 5-6 cross-cutting checks agents should perform.

### Integration points:

- **Planner**: reads `cross_cutting_files` → if two parallel changes both touch a shared file, marks them sequential
- **Dispatcher**: reads feature `touches` → injects targeted context (not the whole registry)
- **Verifier**: evaluates `verification_rules` against git diff → warnings/errors before merge
- **Agent (per-turn)**: sees only the checklist rule (path-scoped, ~20 lines)

### `wt-project init-knowledge`:

New subcommand that scans project for common patterns (dashboard pages, i18n files, sidebar) and generates a draft `project-knowledge.yaml`. One-time scaffolding, not ongoing sync.

## Decision 6: Enhanced Sentinel

### From crash-restart to liveness-aware:

```bash
# Current: just wait and restart on crash
wait $child_pid

# New: poll with liveness check
while kill -0 "$child_pid" 2>/dev/null; do
    sleep "$SENTINEL_POLL_INTERVAL"
    check_orchestrator_liveness "$child_pid" || {
        # Alive but stuck — controlled restart
        kill -TERM "$child_pid"
        sleep 30
        kill -0 "$child_pid" && kill -KILL "$child_pid"
        # Fix stale state
        jq '.status = "stopped"' "$STATE_FILE" > tmp && mv tmp "$STATE_FILE"
        break  # Outer loop will restart
    }
done
```

### Liveness check:

Monitors `orchestration-events.jsonl` mtime. If no event emitted for `sentinel_stuck_timeout` (default 180s), orchestrator is stuck. The watchdog heartbeat ensures events are emitted every poll cycle (15s), so 180s of silence means the orchestrator is genuinely stuck.

## Decision 7: Worktree Context Pruning

### What to prune (orchestrator-only, never needed by Ralph):

```bash
PRUNE_PATTERNS=(
    ".claude/commands/wt/orchestrate*.md"
    ".claude/commands/wt/sentinel*.md"
    ".claude/commands/wt/manual*.md"
)
```

### What NOT to prune (Ralph needs these):

- `.claude/rules/` — path-scoped conventions, code quality
- `.claude/skills/` — OpenSpec skills for ff→apply
- `.claude/commands/wt/loop*.md` — Ralph loop commands
- `CLAUDE.md` — core project instructions

### Integration: `prune_worktree_context()` called from `bootstrap_worktree()` after worktree setup.

## Decision 8: Per-Change Model Routing

### Enhancement to `resolve_change_model()`:

Three-tier priority:
1. Explicit per-change model from plan (highest)
2. Complexity-based routing (if `model_routing: complexity` in config): S-complexity cleanup/infrastructure → sonnet
3. Directive `default_model` (lowest, default: opus)

### Config directive:

```yaml
model_routing: off          # off | complexity
```

Conservative: `off` by default. When `complexity`, only S-complexity non-feature changes route to sonnet.

## Migration Plan

### Phase 1: Module Extraction (mechanical refactor, zero functional change)

1. Create `lib/orchestration/` directory
2. Extract functions to modules per mapping table
3. Add `source` statements to `bin/wt-orchestrate`
4. Run `cmd_self_test` + existing integration tests
5. Commit: "refactor: extract orchestration modules"

### Phase 2: Events System

1. Implement `events.sh` with `emit_event()`
2. Hook `update_change_field()` for automatic STATE_CHANGE emission
3. Add WATCHDOG_HEARTBEAT in monitor loop
4. Commit: "feat: orchestration event log"

### Phase 3: Watchdog

1. Implement `watchdog.sh` with timeout, loop detection, escalation
2. Hook into monitor loop after poll_change
3. Commit: "feat: orchestration watchdog"

### Phase 4: Planner + Project Knowledge

1. Define `project-knowledge.yaml` schema and template
2. Implement `wt-project init-knowledge` scaffolding
3. Enhance `check_scope_overlap()` with file-path detection
4. Enhance `auto_replan_cycle()` with completed change injection
5. Create cross-cutting checklist rule template
6. Commit: "feat: project knowledge system + planner merge avoidance"

### Phase 5: Sentinel + Context Pruning + Model Routing

1. Enhance sentinel with liveness checking
2. Implement `prune_worktree_context()` in dispatcher
3. Enhance `resolve_change_model()` with complexity routing
4. Commit: "feat: enhanced sentinel, context pruning, model routing"

### Phase 6: Testing

1. Run `cmd_self_test` with all modules
2. Run existing integration tests
3. Deploy to consumer project via `wt-project init`
4. Run a real orchestration to validate

## Risk Analysis

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Module extraction breaks variable scope | Medium | High | Test after each module; bash `source` preserves global scope |
| Watchdog false positives kill healthy changes | Medium | High | Conservative defaults (600s timeout, 5 hash threshold) |
| Sentinel stuck detection during long LLM calls | Medium | Medium | Check events mtime (not state); heartbeat ensures freshness |
| Context pruning removes files Ralph needs | Low | High | Conservative prune list; only orchestrator commands |
| Project-knowledge.yaml maintenance burden | Medium | Low | Graceful degradation; missing features just mean less merge avoidance |
