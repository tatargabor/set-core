# Spec: E2E Test Enforcement

## Overview

Close the loop between test-plan.json (what tests are needed) and the agent (what tests get written) by injecting test plan into planner, strengthening dispatcher guidance, and adding coverage enforcement at the gate.

## Requirements

### REQ-ENF-001: Test plan injection into planner prompt

The planner LLM receives test-plan.json entries grouped by change requirements when generating scope/tasks.

**Acceptance Criteria:**
- WHEN planner builds scope for a change with requirements THEN test-plan entries are included in the prompt
- WHEN test-plan.json doesn't exist THEN planner proceeds without test context (no error)
- WHEN entries are injected THEN format includes REQ-ID, scenario name, risk, min_tests, categories
- WHEN LLM generates tasks.md THEN E2E section enumerates specific scenarios (not narrative summary)

### REQ-ENF-002: Dispatcher Required Tests made authoritative

The `## Required Tests` section in input.md includes mandatory language, total count, and threshold warning.

**Acceptance Criteria:**
- WHEN Required Tests section is generated THEN it includes "MANDATORY" and "coverage gate will block" language
- WHEN section is generated THEN total test count is shown
- WHEN section is generated THEN 80% threshold is mentioned explicitly

### REQ-ENF-003: Coverage gate enforcement

After E2E tests pass, `validate_coverage()` blocks merge if coverage is below threshold for feature changes.

**Acceptance Criteria:**
- WHEN E2E passes AND coverage < 80% AND change_type is "feature" THEN gate fails with redispatch
- WHEN E2E passes AND coverage >= 80% THEN gate passes
- WHEN change_type is not "feature" (infrastructure, schema, etc.) THEN coverage check is skipped
- WHEN test-plan.json doesn't exist THEN coverage check is skipped (backward compat)
- WHEN gate fails due to coverage THEN retry context lists missing REQ scenarios specifically
- WHEN redispatch for coverage THEN status is "integration-coverage-failed" (distinct from e2e-failed)

### REQ-ENF-004: Configurable coverage threshold

Coverage threshold is configurable via orchestration.yaml directive.

**Acceptance Criteria:**
- WHEN `e2e_coverage_threshold` is set in orchestration.yaml THEN that value is used
- WHEN not set THEN default is 0.8 (80%)
- WHEN set to 0.0 THEN coverage enforcement is disabled (reporting only)
- WHEN threshold value is read THEN it's passed from Directives to the gate

### REQ-ENF-005: Coverage redispatch context

When coverage gate fails, the retry context gives the agent specific, actionable guidance.

**Acceptance Criteria:**
- WHEN coverage fails THEN retry context lists each missing REQ scenario with risk and expected test count
- WHEN coverage fails THEN retry context includes the agent's own spec files
- WHEN coverage fails THEN retry context does NOT include inherited test failures
- WHEN partial coverage THEN retry context shows "covered: N/M" and lists only the gaps
