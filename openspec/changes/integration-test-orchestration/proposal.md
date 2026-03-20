# Proposal: Integration Test Orchestration

## Why

The merge/verify/state machine pipeline has no integration tests that exercise real git operations against the Python codebase (merger.py, verifier.py, state.py). The existing bash integration test (`test-orchestrate-integration.sh`) tests the legacy bash orchestrator, not the Python migration. E2E runs (craftbrew, minishop) are the only validation but cost $30-80 and take 1-3 hours. Across 12 E2E runs, 52+ bugs were found — many are regressions of patterns that deterministic integration tests would catch in seconds.

## What Changes

- **New pytest integration test suite** covering the top 10 recurring bug patterns from E2E run logs
- **Stub CLI scripts** (set-merge, openspec, set-close) enabling real git operations without LLM calls
- **Reusable test fixtures** for creating git repos with branches, worktrees, and orchestration state
- **No changes to production code** — this is a test-only addition

## Capabilities

### New Capabilities
- `orchestration-integration-tests`: pytest-based integration tests for merge pipeline, verify gates, state machine transitions, and sentinel/monitor coordination

### Modified Capabilities
_(none)_

## Impact

- **New files**: `tests/integration/conftest.py`, `tests/integration/test_merge_pipeline.py`, `tests/integration/test_verify_gates.py`, `tests/integration/test_state_machine.py`, `tests/integration/fixtures/` (stub scripts)
- **Dependencies**: pytest (already in dev deps), no new dependencies
- **CI**: Tests run in standard `pytest tests/` — auto-included
