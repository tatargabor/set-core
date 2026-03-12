## Why

The orchestration pipeline runs Playwright E2E tests at two points (pre-merge per-change gate, post-merge smoke on main) but never saves visual artifacts (screenshots, traces). When smoke tests pass, there's no visual evidence for the report. When they fail, the fix agent and sentinel have no visual context for diagnosis. Additionally, the post-merge smoke often runs after multiple merges (checkpoint mode), but the fix agent only receives context about the last change — making multi-change regression diagnosis blind.

## What Changes

- **Smoke pipeline saves Playwright artifacts**: After post-merge smoke runs on main, collect `test-results/` directory contents (screenshots, traces) into `wt/orchestration/smoke-screenshots/{change-name}/` and record `screenshot_dir` + `screenshot_count` in state.json
- **Per-change E2E gate saves Playwright artifacts**: After pre-merge E2E runs in worktree, collect artifacts into `wt/orchestration/e2e-screenshots/{change-name}/` and record in state.json
- **Report displays screenshot galleries**: Smoke and E2E columns link to screenshot directories; expandable inline gallery for latest results
- **Multi-change smoke context**: When smoke fails after a checkpoint (multiple merges), the fix agent receives the list of ALL changes merged since last successful smoke — not just the last one
- **Already-merged changes get `smoke_result: "skip_merged"`**: Changes that skip the smoke pipeline (already on main from previous phase) get an explicit skip status instead of null, distinct from `"skip"` (no smoke configured)

## Capabilities

### New Capabilities
- `smoke-screenshot-collection`: Playwright artifact collection and storage for both smoke and per-change E2E pipelines

### Modified Capabilities
- `orchestration-html-report`: Add screenshot gallery display for smoke and per-change E2E results
- `orchestration-smoke-blocking`: Add artifact collection after smoke runs, multi-change context on failure, skip status for already-merged

## Impact

- `lib/orchestration/merger.sh` — artifact collection after smoke, multi-change context in fix prompt, skip status
- `lib/orchestration/verifier.sh` — artifact collection after per-change E2E gate
- `lib/orchestration/reporter.sh` — screenshot gallery rendering in execution table
- `lib/orchestration/state.sh` — new fields: `screenshot_dir`, `screenshot_count` per change
- `tests/e2e/run-complex.sh` — update smoke_command documentation/example
