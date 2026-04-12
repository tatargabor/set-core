# Proposal: E2E Coverage Pipeline Fix

## Problem

The E2E test coverage pipeline has three broken links that result in misleading metrics (dashboard shows 4.1% when real coverage is 69%) and agents not receiving test plan guidance:

1. **Required Tests injection dead code** — dispatcher's `_scope_e2e_postprocess()` searches for an "E2E" line in the scope to replace. The planner never generates such a line, so Required Tests are never injected into input.md. Validated broken in both run22 and run23 (0/16 changes received Required Tests).

2. **Coverage aggregation bug** — the coverage gate correctly checks per-change requirements (cart: 8/8 = 100%), but the state stores coverage against ALL 49 requirements (cart: 2/49 = 4.1%). The dashboard displays this wrong number.

3. **Missing REQ-ID enforcement** — checkout.spec.ts has 28 tests with 0 REQ-ID annotations. Without REQ-IDs, the coverage system can't match tests to requirements. No rule or prompt enforces REQ-ID naming.

## Solution

**Fix A — Required Tests as append, not replace**: Instead of searching for an E2E line in the scope, always append a `## Required Tests` section to input.md when a test plan exists for the change. This guarantees every agent sees its test requirements.

**Fix B — Per-change coverage in state**: Store `coverage_pct` as the per-change ratio (covered own-REQs / total own-REQs), not the global ratio. The dashboard aggregates across changes for the global view.

**Fix C — REQ-ID enforcement in agent rules**: Add a rule to the E2E test template/rules that mandates `REQ-XXX-NNN:` prefix in test describe/test blocks. The coverage gate already parses these — agents just need to be told to use them.

## Scope

- `lib/set_orch/dispatcher.py` — Fix A: rewrite Required Tests injection
- `lib/set_orch/merger.py` — Fix B: per-change coverage calculation
- `lib/set_orch/test_coverage.py` — Fix B: store per-change coverage correctly
- `templates/core/rules/set-e2e-testing.md` or equivalent — Fix C: REQ-ID rule
- `modules/web/set_project_web/planning_rules.txt` — Fix C: REQ-ID in planning rules

## Impact

- Agents receive explicit test requirements with counts and risk levels
- Dashboard shows accurate per-change and aggregate coverage
- Coverage gate can block changes missing REQ-ID annotations
- Expected improvement: 69% → 90%+ measured coverage (tests already exist, just not tracked)
