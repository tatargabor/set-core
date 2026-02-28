## Why

The orchestrator (wt-orchestrate) has near-zero memory integration. While agents running inside worktrees get full memory support via hooks, the orchestrator layer itself neither saves its operational decisions nor recalls past experience when planning, dispatching, or replanning. This means merge conflicts, test failures, and review outcomes are lost between cycles — the orchestrator repeats the same mistakes instead of learning from them.

## What Changes

- **Event saving**: The orchestrator saves key operational events (merge conflicts, test failures, review outcomes, successful merges) as memories with `source:orchestrator` tags
- **Dispatch enrichment**: When dispatching a change to a worktree, recall change-specific memories and inject relevant context into the proposal.md
- **Replan recall**: `auto_replan_cycle()` recalls orchestrator memories (past merge conflicts, test failures) to inform better replanning decisions
- **Per-change planning recall**: During `cmd_plan()`, recall memories specific to each roadmap item scope instead of using a single generic query

- **Quality gate cost tracking**: Time every quality gate step (tests, LLM review, verify), track retry token cost, store per-change gate costs in state JSON, log aggregate summaries, show in `cmd_status`

Not included: loop prompt memory injection (redundant — agent hooks already provide memory context inside each Claude session).

## Capabilities

### New Capabilities
- `orchestrator-memory`: Memory integration for the wt-orchestrate orchestration layer — saving operational events, recalling past experience during planning/dispatch/replan

### Modified Capabilities
<!-- None — dispatch_change lives in wt-orchestrate, covered by orchestrator-memory -->

## Impact

- **Code**: `bin/wt-orchestrate` (plan, dispatch, replan, merge/test/review functions), `bin/wt-loop` (dispatch_change proposal writing)
- **Dependencies**: Requires `wt-memory` CLI available on PATH (already a prerequisite for memory-enabled projects)
- **Systems**: shodh-memory database receives additional `source:orchestrator` tagged memories; projects using wt-orchestrate get richer memory context over time
