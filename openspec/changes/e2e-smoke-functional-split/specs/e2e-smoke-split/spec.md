# Spec: E2E Smoke/Functional Split

## Overview

Split E2E test execution at merge gate into two phases: inherited tests (non-blocking regression check) and own tests (blocking feature verification). Ownership determined by git diff.

## Requirements

### REQ-SPLIT-001: Git-based spec file ownership detection

New helper `_detect_own_spec_files(wt_path, change_name) -> list[str]` determines which E2E spec files the change branch added.

**Acceptance Criteria:**
- WHEN worktree has git history THEN detect own files via `git diff $(merge-base) --name-only --diff-filter=A | grep .spec.ts`
- WHEN change added `cart.spec.ts` (regardless of change name) THEN it appears in own list
- WHEN change added multiple spec files (e.g. `content.spec.ts` + `wishlist.spec.ts`) THEN all appear
- WHEN `e2e-manifest.json` exists and git diff fails THEN fall back to manifest's `spec_files` list
- WHEN neither git diff nor manifest available THEN return empty list (triggers fallback to run all)

### REQ-SPLIT-002: Two-phase E2E gate in merger.py

The inline E2E execution in `_run_integration_gates()` splits into Phase 1 (inherited, non-blocking) and Phase 2 (own, blocking).

**Acceptance Criteria:**
- WHEN own spec files detected THEN Phase 1 runs inherited files, Phase 2 runs own files
- WHEN Phase 1 (inherited) fails THEN log warning, record in state, but do NOT block merge or trigger redispatch
- WHEN Phase 2 (own) fails THEN use existing blocking/redispatch logic
- WHEN no own spec files detected (empty list) THEN fall back to running all tests as one phase (current behavior)
- WHEN no inherited files exist (first change) THEN skip Phase 1, run only Phase 2
- WHEN e2e gate is non-blocking per gate config THEN both phases are non-blocking (preserve existing config)

### REQ-SPLIT-003: Scoped redispatch context

When Phase 2 fails and triggers redispatch, the retry context contains only own-test output.

**Acceptance Criteria:**
- WHEN agent is redispatched for E2E failure THEN retry_context includes only Phase 2 (own test) output
- WHEN Phase 1 also failed THEN Phase 1 failures are mentioned briefly ("N inherited tests also failed") but full output is NOT included
- WHEN retry_context is built THEN it includes the list of own spec files so the agent knows its scope

### REQ-SPLIT-004: Inherited failure state recording

Phase 1 failures are recorded in change state for sentinel/dashboard visibility.

**Acceptance Criteria:**
- WHEN Phase 1 fails THEN `inherited_e2e_failures` field is set on the change
- WHEN Phase 1 passes THEN `inherited_e2e_result: "pass"` is recorded
- WHEN dashboard shows change details THEN inherited test status is visible separately from own test status

### REQ-SPLIT-005: Test plan type classification

`TestPlanEntry` gains `type: "smoke" | "functional"` field for forward-looking agent guidance.

**Acceptance Criteria:**
- WHEN test plan is generated THEN first happy-path entry per req_id gets type "smoke"
- WHEN test plan is generated THEN all non-first entries get type "functional"
- WHEN loading old test-plan.json without type field THEN default to "functional"

### REQ-SPLIT-006: Dispatcher smoke/functional labels + manifest

Dispatcher labels Required Tests entries and writes e2e-manifest.json to worktree.

**Acceptance Criteria:**
- WHEN input.md is generated THEN smoke entries show `[SMOKE]` with `{ tag: '@smoke' }` instruction
- WHEN change is dispatched THEN `e2e-manifest.json` written to worktree root with change name, spec_files, requirements
- WHEN spec_files can't be determined at dispatch time THEN omit the file (gate uses git diff instead)

### REQ-SPLIT-007: Coverage tracking own/inherited breakdown

`TestCoverage` tracks own and inherited test results separately.

**Acceptance Criteria:**
- WHEN coverage is computed with ownership info THEN own_passed/own_failed and inherited_passed/inherited_failed are populated
- WHEN ownership info is unavailable THEN all tests count as own (backward compat)
- WHEN coverage is serialized/deserialized THEN new fields default to 0

### REQ-SPLIT-008: E2E methodology update

Agent instructions include `@smoke` tag convention.

**Acceptance Criteria:**
- WHEN agent reads methodology THEN it includes `{ tag: '@smoke' }` syntax
- WHEN agent reads methodology THEN it explains "first happy-path test per feature = smoke, tag it"
