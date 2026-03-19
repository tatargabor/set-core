## Why

E2E orchestration runs consistently expose the same failure pattern: agents complete work but the pipeline can't detect incomplete or broken state. In the latest run, an agent created 7 test files without committing any of them, yet the done-check and verify gate both passed because they only ran `pnpm test` (Jest unit tests) — not the actual E2E test command. The agent's worktree had uncommitted changes that nobody checked for.

Three root causes need fixing together:
1. **No uncommitted work detection** — the Ralph loop and verify gate don't check for dirty worktrees
2. **No startup documentation for agents** — agents entering a worktree mid-project don't know how to start the app, seed the DB, or install test dependencies
3. **smoke_command too weak** — `pnpm test` alone misses build/type errors that mocked unit tests hide

## What Changes

- **Uncommitted work guard**: Ralph loop's `is_done()` and the verify gate's pipeline SHALL check for uncommitted changes (tracked modified + untracked non-ignored files) before declaring success. If uncommitted work exists, done-check returns False and verify gate fails with a clear message.
- **Startup guide in CLAUDE.md**: The planner/dispatcher SHALL append an `## Application Startup` section to the worktree's CLAUDE.md as the project evolves. This section documents how to start the dev server, reset the DB, install test browsers, and run E2E tests. Each infrastructure/foundational change updates it. Template and planner rules updated accordingly.
- **Build-inclusive smoke**: The default smoke_command resolution SHALL prefer `build && test` over `test` alone when a build script exists. This catches TypeScript/compilation errors that mock-based unit tests miss.

## Capabilities

### New Capabilities
- `uncommitted-work-guard`: Detection and blocking of uncommitted changes in Ralph loop done-check and verify gate pipeline
- `startup-guide`: Auto-maintained `## Application Startup` section in worktree CLAUDE.md documenting dev server, DB, E2E setup

### Modified Capabilities
- `verify-gate`: Add uncommitted work check as a pre-condition before running the gate pipeline
- `test-done-criteria`: Add uncommitted work check before declaring test-based done
- `dispatch-core`: Dispatcher appends startup guide context to worktree CLAUDE.md on dispatch

## Impact

- **lib/set_orch/loop_tasks.py**: `is_done()` gains uncommitted work pre-check across all done_criteria modes
- **lib/set_orch/verifier.py**: `handle_change_done()` gains uncommitted work gate step before build/test/review
- **lib/set_orch/dispatcher.py**: Dispatch writes/appends startup guide section to worktree CLAUDE.md
- **lib/set_orch/config.py**: `auto_detect_smoke_command()` prefers `build && test` when build script exists
- **set-project-web templates**: Planning rules and testing conventions updated with startup guide pattern and build-inclusive smoke defaults
- **No breaking changes** — all additions are additive guards that improve existing pipeline behavior
