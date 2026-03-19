## Why

The orchestration planner assumes a single-file specification. When a product spec spans multiple files (30+ files, 3000+ lines) with cross-references, variant systems, and domain-specific detail, the planner either can't read it all or summarizes it — losing the precise details that determine correct change boundaries. There is no way to verify that the generated plan covers every requirement, and implementation agents don't receive the original spec context.

## What Changes

- New **digest phase** in the orchestration pipeline that processes multi-file specs into a structured intermediate representation (requirement IDs, domain summaries, dependency map)
- Planner reads the digest instead of raw spec — sees ~500 structured lines instead of 3000+ raw lines, with nothing lost
- **Coverage tracking**: every requirement gets a unique ID, every change maps to requirements, gaps are detectable at any point
- **Spec context in worktrees**: dispatcher copies relevant raw spec files into each change's worktree so agents can read original detail during implementation
- Planner `find_input()` supports **directory input** (not just single file)
- `set-orchestrate digest` command (explicit) + automatic trigger when planner detects multi-file/large spec without existing digest

## Capabilities

### New Capabilities
- `spec-digest`: Multi-file spec ingestion — scan, classify (convention/feature/data/execution), requirement identification with de-duplication, cross-reference mapping, ambiguity detection, embedded rule extraction from data files, structured output (index.json + conventions.json + data-definitions.md + requirements.json + dependencies.json + ambiguities.json + coverage.json + domains/*.md)
- `coverage-tracking`: Requirement-to-change mapping throughout the pipeline — planner populates coverage at plan time, verified at any point via `set-orchestrate coverage`, final validation before completion
- `spec-context-dispatch`: Dispatcher copies relevant raw spec files to `.claude/spec-context/` in each change's worktree based on `spec_files[]` from plan.json, so implementation agents read original specs

### Modified Capabilities
_(none — no existing specs to modify)_

## Impact

- `lib/orchestration/digest.sh` — new module: scan, API-based digest generation, ID stabilization, coverage population, validation
- `lib/orchestration/utils.sh` — `find_input()` gets directory branch (`INPUT_MODE="digest"`)
- `lib/orchestration/planner.sh` — digest-aware prompt building, `spec_files[]` + `requirements[]` in plan output, auto-digest trigger, `auto_replan_cycle()` digest mode
- `lib/orchestration/dispatcher.sh` — `dispatch_change()` copies spec files to worktree `.claude/spec-context/`, enriches proposal.md with spec refs + requirement IDs
- `lib/orchestration/monitor.sh` — coverage status hook (→ running)
- `bin/set-orchestrate` — new subcommands: `digest`, `coverage`
- `.claude/skills/wt/decompose/SKILL.md` — multi-file spec reading strategy for agent-based planning
- `orchestration-plan.json` schema — new fields per change: `spec_files[]`, `requirements[]`
- `wt/orchestration/digest/` — new directory: `index.json`, `conventions.json`, `data-definitions.md`, `requirements.json`, `dependencies.json`, `ambiguities.json`, `coverage.json`, `domains/*.md`
