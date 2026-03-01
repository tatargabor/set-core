## Why

The verify gate runs unit tests and build checks, but has no end-to-end smoke testing capability. In production, changes that pass unit tests can still break critical user flows (login, navigation, CRUD) because the tests don't exercise the full stack. Projects need a way to run Playwright/e2e tests as part of the gate pipeline — both locally during verification and optionally against a deployed environment after merge.

## What Changes

- Add `smoke_command` directive — runs e2e tests locally in the worktree during verify gate (blocking, retryable)
- Add `smoke_timeout` directive — configurable timeout for smoke tests (default: 120s)
- Add `deploy_smoke_url` directive — optional remote URL for post-merge smoke testing
- Add `deploy_healthcheck` directive — health endpoint to poll before running deploy smoke (default: `/api/health`)
- Insert smoke step in verify gate between build and LLM review (Step 2c)
- Add post-merge deploy smoke as advisory (non-blocking) step after merge
- Update decomposition prompt to include smoke test awareness when `smoke_command` is configured
- Add smoke test guidance to planning guide

## Capabilities

### New Capabilities
- `smoke-gate`: Smoke/e2e test execution in the verify gate pipeline, supporting both local and deploy targets

### Modified Capabilities
- `verify-gate`: Add smoke test step between build and LLM review
- `orchestration-config`: Add smoke_command, smoke_timeout, deploy_smoke_url, deploy_healthcheck directives
- `orchestration-engine`: Add deploy smoke step after merge, decomposition prompt guidance

## Impact

- `bin/wt-orchestrate`: directive parsing, verify gate pipeline, merge_change(), decomposition prompts
- `docs/planning-guide.md`: smoke test coverage guidance
- `openspec/specs/orchestration-config/spec.md`: new directive definitions
- `openspec/specs/verify-gate/spec.md`: new gate step
