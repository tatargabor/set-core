# Design: ac-test-coverage-binding

## Context

The orchestration system already has a complete spec-to-test chain:
- Digest extracts requirements with acceptance criteria (`requirements.json`)
- Planner maps requirements to changes (`coverage.json`)
- Dispatcher injects requirements + AC into agent input (`_build_input_content`)
- Agent writes JOURNEY-TEST-PLAN.md manually and test files
- `build_test_coverage()` fuzzy-matches test results to test plan entries
- Coverage stored in `state.extras["test_coverage"]`

The chain breaks at two points: (1) agent writes JOURNEY-TEST-PLAN.md freely with no structural constraint, and (2) the coverage matcher uses fuzzy text comparison (`_fuzzy_match`) which fails when agent-chosen test names don't align with spec scenario names.

## Core Principle: Python Frame, LLM Content

**Python enforces the structure — LLM fills in the content.** The LLM must not be able to skip, override, or lose focus on testing requirements. Python provides:
- **Generated test plan** (deterministic from digest, not LLM-authored)
- **REQ-ID naming validation** (post-execution check, warns on missing IDs)
- **Minimum test count per risk level** (Python sets floor, agent can exceed but not go below)
- **Structured dispatch input** (test plan entries injected as structured data, not prose)
- **Post-gate coverage audit** (Python compares actual vs expected, no LLM interpretation)

The LLM operates within this frame:
- Writes actual test code (assertions, setup, teardown)
- Chooses locator strategies and interaction patterns
- Handles implementation-specific edge cases
- May add tests beyond the minimum count

If a constraint can be expressed as a Python check, it MUST NOT rely on LLM compliance.

## Goals / Non-Goals

**Goals:**
- Deterministic AC-to-test binding via REQ-ID in test names
- Python-generated test plan from digest scenarios (not LLM-written)
- ISTQB-inspired risk classification driving test case count
- Post-gate coverage validation against the generated plan
- Dispatch injects structured test plan entries per change

**Non-Goals:**
- Changing the Playwright runner or gate pipeline
- Removing JOURNEY-TEST-PLAN.md (agent still writes it, but now validates against generated plan)
- Blocking gates on coverage gaps (warning only, not failure)
- Modifying existing digest or planning phases

## Decisions

### D1: Test plan generation in Python, not LLM

**Choice:** `generate_test_plan(requirements_json_path) -> test-plan.json` in `lib/set_orch/test_coverage.py`

**Alternative considered:** Keep LLM-written JOURNEY-TEST-PLAN.md as source of truth.

**Why:** The current approach lets LLMs freely structure test plans with inconsistent naming, varying granularity, and no guaranteed REQ-ID mapping. A Python generator produces a deterministic, auditable plan from the same `requirements.json` that digest already creates. The scenarios are already parsed into structured `DigestScenario` objects — the data is there, we just need to transform it.

### D2: REQ-ID as the binding key in test names

**Choice:** Test naming convention `test('REQ-HOME-001: Hero heading visible', ...)`

**Alternative considered:** Annotation comments, test metadata, separate mapping file.

**Why:** Simplest approach — test names are already visible in Playwright output. `parse_test_results()` already extracts `(file, test_name)` tuples. Adding regex extraction `REQ-[A-Z]+-\d+` to `build_test_coverage()` is a 10-line change. No toolchain changes needed. grep-able in CI output.

### D3: ISTQB risk classification — core/web split via profile

**Choice:**
- Core defines `classify_test_risk(scenario, requirement) -> str` in `ProjectType` ABC, default: `LOW`
- Web module implements with domain + keyword matching:
  - Domain-first: `{"auth": "HIGH", "payment": "HIGH", "admin": "HIGH", "forms": "MEDIUM", "navigation": "MEDIUM", "search": "MEDIUM"}`
  - Keyword fallback: `{"delete", "password", "token", "checkout"}` → HIGH, `{"submit", "validate", "filter", "edit"}` → MEDIUM
- Risk → min_tests: HIGH=3 (1 happy + 2 negative), MEDIUM=2 (1 happy + 1 negative), LOW=1 (1 happy)

**Alternative considered:** Risk classification in core with hardcoded keywords.

**Why:** "auth → HIGH" is web-specific knowledge. A dungeon-builder plugin might classify "combat" as HIGH and "inventory display" as LOW. The profile system already handles this pattern (`parse_test_results()`, `detect_e2e_command()`). Core provides the frame (risk→min_tests mapping), module provides the content (domain/keyword knowledge).

### D4: Dispatch injects per-change test plan entries

**Choice:** `_build_input_content()` adds `## Required Tests` section from `test-plan.json` filtered by the change's `requirements[]`.

**Alternative considered:** Separate test-plan file in worktree.

**Why:** Inline in `input.md` is how all other structured data reaches agents (requirements, cross-cutting, retry context). Adding another file creates discovery problems. The section format mirrors existing `## Assigned Requirements` — agents already know to read these.

### D5: Coverage validation is non-blocking (warning only)

**Choice:** Post-gate validation compares expected vs actual REQ-IDs. Missing → warning log + dashboard indicator, not gate failure.

**Alternative considered:** Fail the gate on coverage gaps.

**Why:** Gradual adoption. Existing consumer projects have tests without REQ-IDs. A blocking gate would break all running orchestrations. Dashboard visibility is sufficient to drive adoption — the AC panel will show green/red per-scenario coverage.

## Risks / Trade-offs

**[Risk] Agents ignore REQ-ID naming convention** → Mitigation: The `## Required Tests` section in input.md uses imperative language ("Name each test with the REQ-* ID prefix"). Agent non-compliance results in "unbound test" warning, visible in dashboard. Over time, rules can escalate to blocking.

**[Risk] Risk classifier miscategorizes scenarios** → Mitigation: Classification uses keyword matching (configurable), not ML. Default keywords are conservative. Override possible via `risk_overrides` in `test-plan.json`. Wrong risk level only affects test count recommendation, not correctness.

**[Risk] Test name length increases** → Mitigation: REQ-ID prefix adds ~15 chars. Playwright truncates display but preserves full name in JSON output. No functional impact.

## Migration Plan

1. Generate `test-plan.json` after digest (additive, no existing behavior changes)
2. Add `## Required Tests` to dispatch input (additive to input.md)
3. Add REQ-ID extraction to `build_test_coverage()` (additive, fuzzy match kept as fallback)
4. Add post-gate coverage validation (additive, warning only)
5. Existing consumer projects continue working — new naming convention adopted on next orchestration run

No rollback needed — all changes are additive with fallback to existing behavior.

## Open Questions

None — scope is well-defined from the proposal and existing code analysis.
