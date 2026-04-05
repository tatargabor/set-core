# Design: e2e-test-enforcement

## Core Principle

**Python defines what to test (structured, deterministic). LLM implements how to test (creative, framework-aware).** The test-plan.json is the source of truth — it flows through planner, dispatcher, and gate as structured data, never degraded to narrative.

## Real Data (craftbrew-run22)

| Stage | Expected | Actual | Gap |
|-------|----------|--------|-----|
| test-plan.json entries | 226 scenarios | 226 | ✓ |
| Required Tests in input.md | 226 entries | **10** (foundation only) | 95.6% |
| Agent-written tests | 494 min | **67** | 86.4% |
| Negative/error tests | ~247 | **~5** | 98% |
| Gate enforcement | block if gaps | **pass always** | 100% |

## Design Decisions

### 1. Test plan injection into planner prompt

**Decision:** Before the LLM planner generates changes, inject test-plan.json entries grouped by domain/requirement. The planner sees structured test expectations alongside the feature scope.

**Implementation:** New helper `_build_test_plan_context(digest_dir, change_requirements)` in `planner.py`:

```python
def _build_test_plan_context(digest_dir: str, requirements: list[str]) -> str:
    """Build test plan context for planner from test-plan.json."""
    plan = load_test_plan(digest_dir)
    if not plan:
        return ""
    
    req_set = set(requirements)
    entries = [e for e in plan.entries if e.req_id in req_set]
    if not entries:
        return ""
    
    lines = [
        "\n## Required E2E Tests (from test-plan.json)",
        f"This change must cover {len(entries)} test scenarios:",
    ]
    for e in entries:
        cats = ", ".join(e.categories)
        lines.append(f"- {e.req_id}: {e.scenario_name} [{e.risk}] — {e.min_tests} test(s) ({cats})")
    lines.append("")
    lines.append("Generate E2E tasks that cover ALL scenarios above.")
    lines.append("Each scenario = at least 1 test. MEDIUM risk = happy + negative. HIGH risk = happy + 2 negative.")
    lines.append("Do NOT collapse these into a narrative summary.")
    return "\n".join(lines)
```

**Why planner, not just dispatcher:** The planner generates tasks.md which the agent follows as primary instruction. If tasks.md says "write 7 tests" but input.md says "write 39 tests", the agent follows tasks.md. So the planner must know about the test plan to generate correct tasks.

**Where injected:** Into the planning prompt's per-change scope context (passed to the LLM alongside requirements, domain, and scope text). The planner can then enumerate E2E scenarios in tasks.md instead of narrating them.

### 2. Dispatcher: Required Tests made authoritative

**Decision:** Strengthen the `## Required Tests` section with explicit override language and minimum count instruction.

**Current:**
```
## Required Tests
Name each test with the REQ-* ID prefix.
- REQ-CART-001: Cannot add without variant [MEDIUM] — 2 test(s) (happy, negative)
```

**New:**
```
## Required Tests (MANDATORY — coverage gate will block if incomplete)
You MUST write tests for ALL scenarios below. This list is generated from the test plan
and takes priority over any narrative test descriptions in your tasks.
Name each test with the REQ-* ID prefix.
Minimum test count: 39 (coverage gate blocks below 80%).
- REQ-CART-001: Cannot add without variant [MEDIUM] — 2 test(s) (happy, negative)
```

**Why:** The agent needs to understand that Required Tests is not a suggestion — it's a gate requirement. Adding the total count and threshold makes it concrete.

### 3. Coverage gate: blocking enforcement

**Decision:** After E2E tests pass, run `validate_coverage()`. If coverage drops below 80% of expected test-plan entries for feature-type changes, the gate fails with a specific redispatch context listing missing scenarios.

**Implementation in merger.py:** After E2E gate passes (Phase 2), check coverage:

```python
if e2e_pass and test_plan_entries:
    coverage = validate_coverage(test_plan, actual_results)
    if coverage.coverage_pct < 80.0 and change_type == "feature":
        # Build redispatch context with missing scenarios
        missing = [e for e in coverage.entries if e.status == "missing"]
        ...
        update_change_field(..., "status", "integration-e2e-failed")
        return False  # Block merge
```

**Why 80% and not 100%:** Some test-plan scenarios may not be implementable as E2E tests (API-only, backend-only). 80% catches major gaps (7/39 = 18%) while allowing reasonable flexibility. The threshold is configurable via `orchestration.yaml` directive `e2e_coverage_threshold`.

**Non-feature changes:** infrastructure, schema, foundational, cleanup changes are exempt — they don't have user-facing test requirements.

### 4. Configurable threshold

**Decision:** Add `e2e_coverage_threshold: float = 0.8` to Directives. Default 80%, configurable in `orchestration.yaml`.

**Why:** Different projects may have different test maturity. A new project might start at 50% and increase. The threshold prevents gate-blocking on projects that aren't ready for strict enforcement.

## Data Flow

```
┌─ DIGEST ──────────────────────────────────────┐
│ requirements.json → generate_test_plan()       │
│ OUTPUT: test-plan.json (226 entries)           │
└──────────────┬─────────────────────────────────┘
               ↓
┌─ PLANNER ─────────────────────────────────────┐
│ _build_test_plan_context(digest_dir, reqs)     │
│ → Injects structured scenarios into prompt     │
│ → LLM generates tasks.md with SPECIFIC tests  │
│   "8.1 REQ-CART-001: happy + negative (2)"     │
│   "8.2 REQ-CART-002: happy + negative (2)"     │
│ OUTPUT: tasks.md with structured E2E tasks     │
└──────────────┬─────────────────────────────────┘
               ↓
┌─ DISPATCHER ──────────────────────────────────┐
│ ## Required Tests (MANDATORY)                  │
│ "coverage gate blocks below 80%"               │
│ Lists ALL 39 entries with risk + count         │
│ OUTPUT: input.md (agent's brief)               │
└──────────────┬─────────────────────────────────┘
               ↓
┌─ AGENT ───────────────────────────────────────┐
│ Follows tasks.md (structured E2E tasks)        │
│ + input.md Required Tests (backup list)        │
│ Writes ~39 tests with REQ-* prefixes           │
└──────────────┬─────────────────────────────────┘
               ↓
┌─ GATE ────────────────────────────────────────┐
│ 1. E2E tests pass? (existing)                  │
│ 2. validate_coverage() ≥ 80%? (NEW)            │
│    → Missing REQ-CART-003? Redispatch!          │
│ 3. Merge allowed                               │
└────────────────────────────────────────────────┘
```

## Migration / Backward Compatibility

- **test-plan.json missing:** planner and gate skip test plan injection/enforcement — current behavior preserved
- **Old runs without Required Tests:** gate coverage check only runs when test-plan.json exists AND change has requirements
- **80% threshold:** configurable, can be set to 0.0 to disable enforcement while keeping reporting
