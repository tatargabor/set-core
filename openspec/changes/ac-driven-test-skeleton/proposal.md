# Proposal: AC-Driven Test Skeleton

## Why

The test-to-acceptance-criteria binding is broken. The current system relies on fuzzy slug matching between agent-written test names and digest-generated scenario slugs. In run36 simulation, only 20/46 scenarios bound correctly — the rest failed because agents use different wording than the digest ACs. The root cause: **AC-IDs don't exist as explicit identifiers anywhere in the pipeline**. ACs are tracked only as array positions in `requirements.json` and slugified text in `test-plan.json`. There's no stable identifier that survives from digest through skeleton through test execution through coverage binding through dashboard display.

## What Changes

**Introduce explicit AC-IDs (`REQ-XXX-NNN:AC-M`) throughout the entire pipeline:**

1. **Digest**: `requirements.json` gets `ac_id` field per acceptance criterion (e.g., `REQ-NAV-001:AC-1`)
2. **Test plan**: `test-plan.json` entries get `ac_id` field (replaces reliance on `scenario_slug` for identity)
3. **Skeleton**: Generated test blocks use AC-ID as the stable identifier: `test('REQ-NAV-001:AC-1 — Header visible', ...)`
4. **Coverage binding**: `extract_req_ids()` extended to also extract AC-IDs; `build_test_coverage()` matches by AC-ID first, slug fallback second
5. **Dashboard**: ACPanel matches by AC-ID instead of scenario_slug; E2E tab shows AC-ID prefix

**The skeleton becomes the single source of truth** for test-to-AC mapping. The agent fills in the body but cannot change the identity.

## Capabilities

### Modified Capabilities

- `spec-digest`: requirements.json acceptance_criteria entries get `ac_id` field
- `e2e-coverage-check`: coverage binding uses AC-ID matching
- `acceptance-skeleton`: skeleton generates AC-ID-prefixed test blocks

## Impact

- **Digest** (`lib/set_orch/digest.py`): AC-ID generation when extracting acceptance criteria
- **Test plan** (`lib/set_orch/test_coverage.py`): `TestPlanEntry` gets `ac_id` field, `generate_test_plan()` populates it
- **Skeleton** (`lib/set_orch/test_scaffold.py` + `modules/web/project_type.py`): skeleton uses AC-ID in test names
- **Coverage** (`lib/set_orch/test_coverage.py`): `build_test_coverage()` Phase 0 AC-ID binding before slug fallback
- **Dispatcher** (`lib/set_orch/dispatcher.py`): AC display already uses AC-N numbering (done), test injection uses AC-IDs
- **Dashboard** (`web/src/components/DigestView.tsx`): ACPanel matches by `ac_id`, E2E tab highlights AC-IDs
- **No behavioral change** for agents — the skeleton provides the structure, agents only fill test bodies
- **Backwards compatible** — old test plans without `ac_id` fall back to current slug matching
