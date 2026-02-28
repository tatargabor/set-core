## Why

A sales-raketa v3 orchestration run exposed systemic quality gaps: 0 tests, 0 seed data updates, 5 duplicate changes (24% waste), no build verification, and repeated manual worktree setup pain (.env, pnpm install). This change addresses the most impactful gaps identified in `docs/v3/v3_conclusions.md`.

## What Changes

Four improvements to the orchestrator pipeline:

1. **Worktree bootstrap** — `wt-new` now copies `.env` files and installs dependencies automatically after creating a worktree
2. **Test file existence check** — verify gate warns (non-blocking) when a change has no test files in its diff
3. **Build verification** — verify gate runs the project's build command before merge, with retry on failure
4. **Scope overlap detection** — plan validation compares change scopes using keyword jaccard similarity to detect duplicates before dispatch

## Capabilities

### New Capabilities
- `worktree-bootstrap`: Automatic .env copy and dependency install in new worktrees
- `verify-gate-build`: Build command detection and execution in the verify gate
- `scope-overlap-detection`: Keyword-based duplicate change detection in plan validation

### Modified Capabilities
- `orchestrator-verify-gate`: Added test file existence warning (step 3b) and build verification (step 4)

## Impact

- `bin/wt-new` — two new functions: `bootstrap_env_files`, `bootstrap_dependencies`
- `bin/wt-orchestrate` — `check_scope_overlap` in `validate_plan`, test file check + build step in `handle_change_done`
- Affects all future orchestration runs; running orchestrations pick up changes on next worktree creation / verify gate pass
