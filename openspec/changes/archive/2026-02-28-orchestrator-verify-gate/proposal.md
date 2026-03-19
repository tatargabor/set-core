## Why

set-orchestrate dispatches Ralph loops that implement changes autonomously, but has no quality verification before merge. A Phase 1 run on sales-raketa produced 11 critical bugs (tenant leaks, missing auth guards, crypto corruption) — all found by manual code review *after* orchestration completed. Tests were planned for Phase 2 in the spec, meaning the most security-critical code shipped untested. The orchestrator needs a verify gate and test-aware planning to catch these issues automatically.

## What Changes

- **Planner context scanning**: Before plan decomposition, scan the target project for test infrastructure (vitest/jest config, `*.test.*` file count, test helpers, package.json `test` script). Include findings in the LLM planning prompt.
- **Planner prompt: test requirements**: Instruct the LLM to include test requirements in every change scope. If no test infra exists, plan a `test-infrastructure-setup` change first with all others depending on it.
- **test_command auto-detection**: If no explicit `test_command` directive is set, auto-detect from `package.json` scripts (`test`, `test:unit`, etc.).
- **Verify gate in handle_change_done**: After Ralph finishes, run `test_command` in the worktree. On failure, restart Ralph with test failure context (one retry). On pass, proceed to merge.
- **Model tiering for run_claude**: Support model selection per task — Haiku for spec summarization, Opus for planning + implementation, Sonnet for code review and test failure fixes.
- **Optional LLM code review gate**: Sonnet-based code review before merge (configurable via `review_before_merge: true` directive).

## Capabilities

### New Capabilities
- `verify-gate`: Test execution and optional code review gate between Ralph completion and merge. Includes test_command auto-detection, failure retry, and review integration.
- `model-tiering`: Model selection per orchestration task — cheaper models for summarization/review, expensive models for planning/implementation.
- `test-aware-planning`: Planner scans project test infrastructure and includes test requirements in change scopes.

### Modified Capabilities

## Impact

- `bin/set-orchestrate`: Main implementation target — planner context, verify gate, model tiering, auto-detect
- `bin/wt-merge`: May need `--model` flag for LLM-assisted conflict resolution
- `.claude/orchestration.yaml`: New directives: `review_before_merge`, `verify_model`, `summarize_model`
- Ralph loops: No changes needed — test requirements come through the change scope
