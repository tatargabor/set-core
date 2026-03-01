## Why

The orchestrator's plan decomposition has a single dependency rule: "if change B needs code from change A, list A in depends_on." This relies entirely on Claude's general reasoning, which misses semantic ordering patterns like "cleanup before features" or "schema before data layer." The result: changes that should be sequential run in parallel, causing avoidable merge conflicts.

Real example from sales-raketa: `ui-cleanup-pack`, `impersonation`, and `form-submission-unification` all ran in parallel with no dependencies. The cleanup should have run first — it touches the same UI components the other two build on.

The fix is two-layered:
1. **Spec time** — `/wt:plan-review` should detect and suggest dependency annotations before the spec reaches the planner
2. **Plan time** — the decomposition prompt should include ordering heuristics and respect spec-level dependency hints

## What Changes

- The `/wt:plan-review` skill gains dependency analysis: it suggests concrete `depends_on` annotations when it detects ordering issues (cleanup→feature, schema→data, auth→everything)
- The decomposition prompt in `wt-orchestrate` gains ordering heuristics so Claude classifies changes by type and applies foundational-first ordering
- The plan checklist gains a "Dependency Graph" section for the new patterns

## Capabilities

### New Capabilities
- `plan-review-dependencies`: Enhance `/wt:plan-review` to detect and suggest dependency annotations between spec items
- `planner-ordering-heuristics`: Add change-type classification and ordering rules to the decomposition prompt

### Modified Capabilities

## Impact

- `bin/wt-orchestrate` — decomposition prompt text (lines ~1598-1608)
- `.claude/commands/wt/plan-review.md` — review skill gains dependency analysis section
- `docs/planning-guide.md` — dependency section updated with ordering heuristics
- `docs/plan-checklist.md` — new checklist items for ordering
