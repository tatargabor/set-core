# Proposal: gate-lint-forbidden-patterns

**Series: programmatic-gate-enforcement (2/4)**

## Why

The code review gate relies entirely on LLM judgment to identify anti-patterns in diffs. In documented E2E runs, agents applied `any` type casts on database client parameters to bypass TypeScript build errors instead of fixing the root cause (missing schema models). The review LLM classified this as HIGH severity instead of CRITICAL, allowing the change to merge — converting compile-time errors into runtime 500 errors discovered only in production.

This is a systemic pattern: the agent optimizes for passing the gate (build green) rather than correctness, and the review LLM doesn't consistently enforce anti-pattern rules. A deterministic grep-based lint gate running BEFORE the LLM review would catch these patterns with 100% reliability.

## What Changes

- **New lint gate**: Deterministic grep-based gate in the verify pipeline, positioned after build/test/e2e and BEFORE review. Scans git diff for forbidden patterns and reports CRITICAL/WARNING matches.
- **Pattern sources**: Profile plugin `get_forbidden_patterns()` method + `project-knowledge.yaml` verification.forbidden_patterns section
- **Gate integration**: Registered in GatePipeline between scope_check and review gates. Blocking for CRITICAL matches, warning for WARNING matches.
- **Profile interface extension**: NullProfile and project-type plugins get `get_forbidden_patterns()` returning a list of `{pattern, severity, message}` dicts

## Capabilities

### New Capabilities
- `lint-gate`: Deterministic forbidden/required pattern scanning in verify pipeline

### Modified Capabilities
- `verify-gate`: New lint gate registered in GatePipeline execution order
- `gate-profiles`: Lint gate skip/run/warn configuration per change_type

## Impact

- **Files modified**: `lib/set_orch/verifier.py` (new _execute_lint_gate + registration), `lib/set_orch/profile_loader.py` (NullProfile.get_forbidden_patterns), `lib/set_orch/gate_profiles.py` (lint gate config field)
- **Risk**: Low — additive gate, existing gates unchanged. False positives mitigated by profile-specific patterns (not global).
- **Tests**: New unit tests for lint gate pattern matching; existing pipeline tests must pass
