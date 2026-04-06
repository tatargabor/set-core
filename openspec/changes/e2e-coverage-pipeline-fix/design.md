# Design: E2E Coverage Pipeline Fix

## Architecture

Three independent fixes touching separate code paths. No shared state between them.

```
┌─────────────────────────────────────────────────────────────────┐
│                    E2E Coverage Pipeline                         │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │ Dispatcher    │    │ Merger       │    │ Rules/Templates  │  │
│  │              │    │              │    │                  │  │
│  │ FIX A:       │    │ FIX B:       │    │ FIX C:           │  │
│  │ Append       │    │ Per-change   │    │ REQ-ID naming    │  │
│  │ Required     │    │ coverage in  │    │ enforcement in   │  │
│  │ Tests to     │    │ post-merge   │    │ agent rules      │  │
│  │ input.md     │    │ parser       │    │                  │  │
│  │              │    │              │    │                  │  │
│  │ dispatcher.py│    │ merger.py    │    │ planning_rules   │  │
│  │ L1051-1065   │    │ L2006-2125   │    │ + templates      │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Fix A — Required Tests Injection

**Current bug** (dispatcher.py L1051-1065): `_scope_e2e_postprocess` uses regex to find `E2E:...` in the scope and replace it. The planner never generates this pattern → replacement never matches → debug log "no E2E pattern to replace". The Required Tests section at L1155 IS appended correctly (this works), but the conflicting narrative E2E description in the scope remains, confusing agents.

**Actual problem**: The scope contains narrative test descriptions like "E2E tests/e2e/cart.spec.ts — cold-visit, add product, qty +/-, remove, apply coupon..." which conflict with the structured Required Tests section. Agents follow the narrative (fewer tests) instead of Required Tests (comprehensive list).

**Fix**: Change the regex to also match common narrative patterns: `E2E tests/e2e/...` and `Tests:...` lines. If no match, REMOVE any E2E-like narrative entirely and add a clear note pointing to Required Tests. The goal: agents should ONLY see the Required Tests section, never a conflicting narrative.

**Files**: `lib/set_orch/dispatcher.py` L1051-1065

## Fix B — Per-Change Coverage in Post-Merge Parser

**Current bug** (merger.py L2053-2086): `_parse_test_coverage_if_applicable` collects ALL digest REQ IDs (all 49 requirements across all changes) and checks coverage against ALL of them. Cart has 8 REQs → gate says 100%, but post-merge parser checks 8 against 49 → stores 2/49 = 4.1%.

**Fix**: Use `change.requirements` (the per-change requirement list) instead of `digest_req_ids` when computing coverage. Fall back to digest-level only for acceptance-test type changes that are responsible for cross-cutting coverage.

**Files**: `lib/set_orch/merger.py` L2053-2095

## Fix C — REQ-ID Enforcement in Rules

**Current problem**: checkout.spec.ts has 28 tests with 0 REQ-ID annotations. The Required Tests section tells agents to use REQ-ID prefixes, but there's no rule in the deployed templates enforcing this.

**Fix**: Add explicit REQ-ID naming requirement to:
1. `modules/web/set_project_web/planning_rules.txt` — planner sees it when generating scope
2. `templates/core/rules/set-testing.md` — agent sees it during implementation

The rule: "Every `test()` or `test.describe()` block that tests a requirement MUST include the REQ-XXX-NNN prefix in its name."

**Files**: `modules/web/set_project_web/planning_rules.txt`, `templates/core/rules/set-testing.md`
