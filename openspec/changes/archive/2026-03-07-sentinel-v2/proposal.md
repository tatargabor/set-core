## Why

`set-orchestrate` is a 5,220-line monolithic bash script handling planning, dispatch, polling, verification, merging, smoke testing, replanning, and state management in a single file. Four production orchestration runs (v8-v11) on sales-raketa exposed systemic problems: orchestrator stalls requiring SIGKILL (v11 2x), merge conflicts from parallel changes touching shared files (v8, v11), no event audit trail for post-mortem analysis, 370K of unnecessary context files in worktrees, and agents missing cross-cutting concerns (sidebar, i18n, activity-log) when implementing features.

The monolith must be decomposed into testable modules, enhanced with self-healing capabilities, and integrated with a structured project-knowledge system so that both the orchestrator and the agents it supervises produce reliable, complete work.

## What Changes

### Orchestration Modularization
- Extract `bin/set-orchestrate` (5,220 lines) into 7 sourced library modules under `lib/orchestration/`, reducing the main file to ~300 lines of CLI dispatch
- Modules: `state.sh`, `planner.sh`, `dispatcher.sh`, `verifier.sh`, `merger.sh`, `watchdog.sh` (NEW), `events.sh` (NEW)
- All existing CLI commands unchanged (`plan`, `start`, `status`, `pause`, `resume`, `replan`, `approve`)
- All existing state file formats unchanged

### Self-Healing Watchdog (NEW)
- Per-state timeout detection (configurable, default 600s no activity → restart)
- Action hash loop detection (5 consecutive identical poll states → escalation)
- Escalation chain: log → resume → kill → mark-failed
- Orchestrator self-liveness check via event log heartbeat (solves v11 stall problem where PID was alive but orchestrator stuck)

### Event Log (NEW)
- Append-only `orchestration-events.jsonl` alongside existing `orchestration-state.json`
- Every state transition, merge attempt, verify gate result, watchdog action emitted as structured JSON
- Machine-parseable post-mortem analysis (replaces manual run log writing)
- Event-based auto-generated run report at orchestration completion

### Planner Enhancements
- Merge avoidance: file-path overlap detection between parallel changes using `project-knowledge.yaml` cross-cutting file registry
- Replan done-check: inject git log + completed change list into replanner prompt (fixes v10 replan duplication bug)
- Per-change model suggestion: complexity-based routing (S-complexity mechanical → sonnet, architectural → opus)

### Project Knowledge System (NEW)
- `.claude/project-knowledge.yaml`: structured feature-to-dependency map, cross-cutting file registry, verification rules — read by planner (merge avoidance), dispatcher (context assembly), verifier (post-implementation checks)
- `.claude/rules/cross-cutting-checklist.md`: path-scoped rule for agent per-turn guidance — lightweight checklist of cross-cutting concerns (sidebar, i18n, activity-log, tenant-scoping)
- `set-project init-knowledge`: scaffolding command to bootstrap project-knowledge.yaml from code scanning

### Enhanced Sentinel
- Liveness checking: monitor events.jsonl mtime, detect alive-but-stuck orchestrator (3-minute no-activity threshold)
- Controlled restart with state cleanup (SIGTERM → wait → SIGKILL if needed)
- Enhanced from 146 lines to ~300 lines

### Worktree Context Pruning
- `bootstrap_worktree()` removes orchestrator-specific files from worktrees (commands/set-orchestrate, sentinel commands)
- Reduces worktree context from ~370K to ~180K (v11 fix)

### Dispatcher Enhancements
- Agent Teams abstraction layer: dispatch via wt-loop (current) or Claude Code Agent Teams (when available)
- Per-change model routing enforcement from plan
- Targeted context injection from project-knowledge.yaml feature entries

## Capabilities

### New Capabilities
- `orchestration-watchdog`: Self-healing watchdog with timeout detection, loop detection, escalation chain, and orchestrator self-liveness monitoring
- `orchestration-events`: Append-only event log system with structured JSON events, token tracking, and auto-generated run reports
- `project-knowledge`: Structured project knowledge system with feature registry, cross-cutting file map, verification rules, and scaffolding tooling
- `orchestration-context-pruning`: Worktree context optimization removing orchestrator-specific files from agent worktrees

### Modified Capabilities
- `orchestration-engine`: Decomposed from monolith into 7 sourced modules under `lib/orchestration/`; planner enhanced with merge avoidance and replan done-check; dispatcher enhanced with model routing and Agent Teams abstraction
- `sentinel-polling`: Enhanced from crash-restart wrapper to intelligent supervisor with liveness checking and stuck detection
- `per-change-model`: Extended from doc-only heuristic to complexity-based routing with configurable policy
- `verify-gate`: Enhanced with project-knowledge verification rules checking cross-cutting file modifications

## Impact

### Code Changes
- `bin/set-orchestrate`: Reduced from 5,220 to ~300 lines (functions extracted to `lib/orchestration/*.sh`)
- `bin/set-sentinel`: Enhanced from 146 to ~300 lines
- `bin/set-project`: New `init-knowledge` subcommand
- NEW: `lib/orchestration/` directory with 7 module files
- NEW: Template files for `project-knowledge.yaml` and `cross-cutting-checklist.md`

### Configuration (additive, backwards compatible)
- New `orchestration.yaml` directives: `watchdog_timeout`, `watchdog_loop_threshold`, `context_pruning`, `events_log`, `model_routing`, `sentinel_stuck_timeout`
- All new directives have sensible defaults; existing configs work unchanged

### Breaking Changes
- None for CLI interface, state file format, or orchestration.yaml
- **Low risk**: Tools that `source bin/set-orchestrate` directly would need to also source `lib/orchestration/*.sh` modules (unlikely external usage)
- **Low risk**: Worktree context pruning removes orchestrator commands from worktrees — agents relying on these would need adjustment
