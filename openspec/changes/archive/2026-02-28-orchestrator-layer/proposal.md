## Why

The current wt-tools pipeline requires human interaction at every specification step: the developer manually creates proposals, reviews designs, approves specs, and kicks off implementation. While Ralph (wt-loop) automates the implementation phase, the spec-to-implement pipeline is entirely manual. For projects with a clear functional direction, this creates a bottleneck — the developer is the slowest link in a chain that could largely run autonomously. An orchestration layer would allow the developer to express high-level intent (via a living project brief), have the system decompose it into changes, run them through the full OpenSpec pipeline, and only interrupt the developer at meaningful checkpoints.

## What Changes

- **Project Brief format**: Extend `openspec/project.md` into a richer `project-brief.md` that includes a feature roadmap, quality requirements, and orchestrator directives (max parallelism, merge policy, checkpoint frequency). This is the single input document the developer maintains.
- **`wt-orchestrate` CLI**: New bash script that reads the project brief, calls Claude to decompose it into a dependency-ordered change list, dispatches each change to a worktree with Ralph, monitors progress, and handles lifecycle events (pause, resume, replan).
- **Orchestration state tracking**: A `orchestration-state.json` file that tracks the plan version, change statuses (pending/active/paused/done), dependency graph, merge queue, and checkpoint history. This is the orchestrator's source of truth.
- **Decomposition via Claude**: A single `claude -p` call analyzes the brief + existing specs + codebase to produce a change plan with dependency ordering. The developer approves the plan before execution starts.
- **Mid-flight mutation**: Commands to pause individual changes or the entire plan, edit change artifacts, replace changes, and replan from an updated brief — all while preserving completed work.
- **Human checkpoints**: Configurable interruption points where the orchestrator pauses, sends a progress summary (completed changes, active change status, test results, token usage), and waits for developer approval before continuing. Delivered via desktop notifications and the wt-control GUI dashboard.
- **Auto-merge pipeline**: When a change completes and tests pass, the orchestrator can auto-merge (configurable: eager, checkpoint-gated, or manual). Dependency-blocked changes are automatically unblocked when their prerequisites merge.
- **GUI orchestrator view**: Extension to wt-control showing the dependency graph, per-change progress, merge queue, and token consumption. The existing status/Ralph infrastructure is reused.

## Capabilities

### New Capabilities
- `orchestration-engine`: Core orchestrator logic — plan/start/status/pause/resume/replan commands, state machine, change dispatch to worktrees via wt-loop, progress monitoring, auto-merge pipeline, dependency graph resolution
- `project-brief`: Project brief document format extending project.md with feature roadmap (done/in-progress/next/ideas), quality requirements, and orchestrator directives (parallelism, merge policy, checkpoint frequency, notification channel)
- `human-checkpoint`: Developer feedback system — configurable checkpoint triggers (every N changes, on ambiguity, on completion), progress summary generation, desktop notifications via notify-send, GUI dashboard integration, approval gate with timeout

### Modified Capabilities
- `ralph-loop`: External lifecycle control — orchestrator can pause/resume a running loop, query completion status programmatically, and receive structured done/stalled/stuck signals. Currently Ralph only supports manual stop via Ctrl+C or internal stall detection.

## Impact

- **New CLI**: `bin/wt-orchestrate` (~500-800 lines bash) with subcommands: plan, start, status, pause, resume, replan, checkpoint
- **New state file**: `orchestration-state.json` at project root (git-ignored), tracking plan and change lifecycle
- **Project brief**: New `openspec/project-brief.md` format (backwards-compatible extension of project.md)
- **wt-loop modifications**: Add `--signal-file` flag for external done/stall signaling, add `wt-loop pause <worktree>` command for graceful external pause
- **GUI extension**: New orchestrator panel in wt-control showing dependency graph and progress (reuses existing worktree/Ralph status infrastructure)
- **Dependencies**: No new external dependencies. Uses existing `claude` CLI for decomposition, existing `wt-new`/`wt-merge`/`wt-loop` for execution, existing `notify-send` for notifications
- **Token cost**: Each `wt-orchestrate plan` invocation uses one Claude session for decomposition (~5-10k tokens). Execution cost is the same as running Ralph loops manually.
