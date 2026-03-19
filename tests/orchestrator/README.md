# Orchestrator Tests

Tests for `set-orchestrate` — the multi-change orchestration layer.

## Test Levels

### Level 1 — Unit Tests (no Claude, no git)

```bash
./tests/orchestrator/test-orchestrate.sh
```

Tests all pure bash functions: brief parsing, directive validation, dependency graph (topological sort, circular detection), state management (init, update, query), and Ralph compatibility verification.

Also available as `set-orchestrate self-test` (subset).

**Cost:** Free (no API calls)
**Time:** < 5 seconds

### Level 2 — Integration Test (plan generation)

```bash
./tests/orchestrator/test-plan.sh
```

Creates a temp project with `sample-brief.md`, runs `set-orchestrate plan`, validates the generated `orchestration-plan.json`: JSON structure, kebab-case names, valid dependency references, no circular dependencies.

**Cost:** ~5-10k tokens (one Claude decomposition call)
**Time:** ~30 seconds

### Level 3 — End-to-End Test (full lifecycle)

```bash
./tests/orchestrator/test-e2e.sh
```

Creates a real git repo with a trivial brief ("create hello.txt"), runs `set-orchestrate plan` + `start`, waits for the change to complete the full lifecycle: pending → dispatched → running → done → merged.

**Cost:** ~20-50k tokens (one Ralph session)
**Time:** 5-10 minutes

### Level 4 — Pilot (real project)

Manual test with a real project. Use a project with 2-3 actual features in the brief. Validates decomposition quality, parallel execution, merge pipeline, and checkpoints.

## Parallel Execution Safety Model

The orchestrator runs multiple worktrees simultaneously. Key safety invariants:

### Worktree Isolation
Each change runs in its own git worktree — separate directory, separate branch, separate `.claude/` state. No shared mutable state between running changes.

### Sequential Merges
The orchestrator merges one change at a time to the target branch. Never concurrent merges. This prevents merge race conditions.

### Dependency Ordering
Changes with `depends_on` relationships are ordered via topological sort (Kahn's algorithm). A dependent change does NOT start until all its dependencies are in "merged" status.

### Conflict Detection
Before each merge, a dry-run check is performed:
```bash
git merge --no-commit --no-ff <branch>
git merge --abort
```
If conflicts are detected, the change is marked as "merge-blocked" and the developer is notified. No automatic conflict resolution.

### Token Budget
The `token_budget` directive provides a soft spending limit. When total tokens across all changes exceed the budget, the orchestrator pauses at a checkpoint and waits for developer approval.

## Test Fixture

`sample-brief.md` contains a 3-feature scenario:
- **Alpha** — independent, can start immediately
- **Beta** — depends on Alpha (tests dependency ordering)
- **Charlie** — independent, can run in parallel with Alpha (tests parallelism)

This covers: independent execution, dependency blocking, parallel dispatch, and the merge pipeline.
