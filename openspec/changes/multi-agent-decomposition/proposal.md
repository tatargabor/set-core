## Why

The orchestration planner currently runs as a single LLM API call — one prompt with spec + context, one JSON response. This means no codebase exploration, no iterative refinement, no memory-aware reasoning, and context overflow on large specs. The planning phase should be an agent-based process (like execution already is with Ralph loops), using sub-agents for code exploration and memory for accumulated knowledge.

Additionally, there's no clear separation between the initial spec decomposition and iteration-cycle replanning, no memory hygiene before planning, and no spec reference mechanism for worker agents to consult the original spec during execution.

## What Changes

- **Agent-based decomposition**: `cmd_plan()` gains an agent-based path alongside the existing API call path. A planning worktree with Ralph loop runs a decomposition skill that uses Agent tool sub-agents for codebase exploration, requirements analysis, and spec processing. Output remains `orchestration-plan.json` — the dispatch pipeline is unchanged.
- **Plan metadata**: New fields `plan_phase` (initial|iteration) and `plan_method` (api|agent) in `orchestration-plan.json` to distinguish how and when a plan was created.
- **Decomposition skill**: New `/wt:decompose` skill prompt that guides the planning agent through spec analysis, code exploration (via Agent tool), memory recall, and plan generation.
- **Spec reference in proposals**: `proposal.md` includes a `## Source Spec` section with path and relevant section, so worker agents can consult the original spec during execution.
- **Memory tag convention**: Introduce `phase:planning`, `phase:execution`, `phase:verification`, `phase:orchestration` tags for memory segmentation. Recall calls filter by phase to prevent cross-contamination.
- **Memory hygiene**: Pre-decomposition cleanup — stale detection, dedup check, phase-filtered recall instead of unfiltered.
- **Project type injection**: The decomposition agent receives project type context (verification rules, conventions) to make better decomposition decisions.

## Capabilities

### New Capabilities
- `decomposition-agent`: Agent-based planning path in `cmd_plan()` — worktree creation, Ralph loop dispatch, result collection for the planning phase
- `decomposition-skill`: The `/wt:decompose` skill that guides the planning agent through spec → execution plan conversion
- `memory-phase-tags`: Phase-based memory tagging and filtered recall for planning, execution, verification, orchestration
- `spec-reference`: Spec path and section reference in proposal.md for worker agent access during execution

### Modified Capabilities
- `orchestration-engine`: `cmd_plan()` and `auto_replan_cycle()` gain agent-based path, plan metadata fields (`plan_phase`, `plan_method`)
- `orchestrator-memory`: Recall calls become phase-tag-filtered; memory hygiene step before decomposition

## Impact

- **lib/orchestration/planner.sh**: Major — new agent-based planning path, plan metadata, memory hygiene
- **lib/orchestration/dispatcher.sh**: Minor — spec reference injection into proposal.md, phase-tagged memory recall at dispatch
- **.claude/skills/wt/decompose/**: New skill directory with SKILL.md
- **.claude/commands/wt/decompose.md**: New command for manual decomposition trigger
- **wt-project init**: Deploy new skill and command to consumer projects
- **Memory system**: Tag convention documentation, recall filtering guidance
- **orchestration-plan.json format**: Additive — new optional fields, backward compatible
