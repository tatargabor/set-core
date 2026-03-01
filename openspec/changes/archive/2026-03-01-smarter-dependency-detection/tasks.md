# Tasks: smarter-dependency-detection

## Planner Ordering Heuristics

- [x] Add ordering heuristic rules to spec-mode decomposition prompt in `bin/wt-orchestrate` (~line 1598). Add after existing dependency rule: change-type classification (infrastructure, schema, foundational, feature, cleanup-before, cleanup-after), cleanup-before→feature ordering, schema→data ordering, foundational→consumer ordering.
- [x] Add the same ordering heuristic rules to brief-mode decomposition prompt (~line 1655).
- [x] Add "respect spec-level dependency hints" instruction to both prompts: if spec contains `depends_on:` or "requires X" or "after X", preserve in output JSON.

## Output Schema

- [x] Add `change_type` field to the JSON output schema in both spec-mode and brief-mode decomposition prompts. Values: `infrastructure`, `schema`, `foundational`, `feature`, `cleanup-before`, `cleanup-after`. Update `plan --show` display to show the type alongside each change.

## Plan Review Dependencies

- [x] Add "Dependency Graph Analysis" section to `/wt:plan-review` (`.claude/commands/wt/plan-review.md`). The review should classify each spec item by change type, detect ordering issues (cleanup-before→feature, schema→data, auth→features, shared-types→consumers), and output a "Suggested Dependencies" section with concrete `depends_on:` text to add to the spec.

## Documentation

- [x] Update `docs/planning-guide.md` section 3 (Dependencies) to document change-type ordering heuristics and the fact that the planner now recognizes them.
- [x] Update `docs/plan-checklist.md` to add ordering-related checklist items: "Cleanup/refactor changes run before feature changes in same area", "Change types classified (infrastructure, schema, foundational, feature, cleanup)".

## Deploy

- [x] Run `wt-project init` on all registered projects to deploy updated plan-review skill.
