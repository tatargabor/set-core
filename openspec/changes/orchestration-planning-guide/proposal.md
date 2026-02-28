## Why

The orchestrator's plan quality is the single biggest determinant of batch success. Poor plans lead to overlapping changes, missing dependencies, untestable features, and merge conflicts. Users currently have no guidance on how to write effective spec documents or project briefs — they learn through trial and error. A planning guide with concrete patterns, checklists, and web-project-specific advice would significantly reduce wasted orchestration cycles.

## What Changes

- Add a comprehensive planning guide document covering:
  - Input format options (spec mode vs brief mode) with examples
  - Checklist for plan review before execution
  - Web project planning patterns (DB schemas, auth, API routes, persistence, deployment)
  - Design rules: what to specify explicitly vs what to leave to the agent
  - Plan sizing and splitting strategies (when a plan is too large, how to decompose into phases)
  - Common pitfalls and anti-patterns from real orchestration runs
- Add a plan review checklist as a standalone quick-reference

## Capabilities

### New Capabilities
- `planning-guide`: Comprehensive documentation for writing effective orchestration plans — input formats, web project patterns, design rules, sizing strategies, and anti-patterns

### Modified Capabilities

## Impact

- New files in `docs/` directory (documentation only)
- No code changes
- References existing orchestration infrastructure (`wt-orchestrate plan`, `project-brief.md`, spec mode)
