## Why

The orchestrator currently hardcodes `--model opus` for all dispatch and resume operations. This wastes expensive tokens on simple tasks (doc sync, cleanup, small fixes) that sonnet handles equally well. Users have no way to control model selection per change — either in the plan JSON, in directives, or via complexity-based heuristics.

## What Changes

- Add `model` field to plan JSON per-change schema (optional, overrides default)
- Add `default_model` directive for global model selection (default: opus)
- Implement complexity-based model heuristic: S-complexity doc/cleanup changes default to sonnet
- Add `skip_review` and `skip_test` per-change flags for doc-only changes that don't need code review or test gates
- `dispatch_change()` and `resume_change()` read the effective model instead of hardcoding opus
- Update planner LLM prompt to optionally suggest model per change
- Update `docs/plan-checklist.md` and `docs/planning-guide.md` with model selection guidance

## Capabilities

### New Capabilities
- `per-change-model`: Per-change model override in plan JSON, default_model directive, complexity-based heuristic fallback
- `per-change-gate-skip`: Per-change skip_review and skip_test flags to bypass verify gate steps for doc-only or trivial changes

### Modified Capabilities

## Impact

- `bin/set-orchestrate`: plan JSON schema, init_state, dispatch_change, resume_change, planner prompt, verify gate logic
- `docs/plan-checklist.md`: new checklist items for model and gate skip
- `docs/planning-guide.md`: new section on model selection strategy
