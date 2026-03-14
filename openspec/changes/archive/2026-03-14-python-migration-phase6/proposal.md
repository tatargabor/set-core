## Why

Phase 6 of the 8-phase Python migration (per master plan). `verifier.sh` (1453 lines) is the largest remaining bash module — it owns the entire verify gate pipeline, test running, code review, smoke testing, E2E, and change polling. Migrating it to Python enables structured data flow, proper error handling, and testability for the most complex orchestration logic.

## What Changes

- New `lib/wt_orch/verifier.py` (~800 LOC) with 1:1 function mapping from verifier.sh
- 12 functions migrated: test runner, requirement review builder, LLM code review, verification rules, scope checks, health check, smoke fix, phase-end E2E, poll_change, handle_change_done
- New CLI subcommands under `wt-orch-core verify *` for all functions
- `lib/orchestration/verifier.sh` replaced with thin bash wrappers (~50 LOC)
- Unit tests for all pure-logic functions

## Capabilities

### New Capabilities
- `verify-gate`: Test runner, scope checks, verification rule evaluation, gate pipeline orchestration
- `verify-review`: LLM code review with model escalation, requirement-aware prompting
- `verify-smoke`: Health checks, scoped smoke fix agent, phase-end E2E orchestration
- `verify-poll`: Change polling, loop-state parsing, status transitions

### Modified Capabilities
<!-- No existing spec requirements change — this is a 1:1 reimplementation -->

## Impact

- `lib/orchestration/verifier.sh` — rewritten to thin wrappers
- `lib/wt_orch/cli.py` — new `verify` subcommand group
- `lib/wt_orch/verifier.py` — new module
- `tests/unit/test_verifier.py` — new test file
- Dependencies: existing `subprocess_utils`, `state`, `events`, `process`, `notifications`, `dispatcher` modules
