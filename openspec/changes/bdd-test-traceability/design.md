# Design: BDD Test Traceability

## Context

The digest system (`digest.py`) already parses spec files for requirements. Requirements have `acceptance_criteria: list[str]` — plain strings. The web UI's ACPanel shows these as checkboxes with done/not-done state based on change status.

The acceptance-tests change (from `init-safety-and-acceptance-gate`) produces:
1. `tests/e2e/JOURNEY-TEST-PLAN.md` — REQ → test case mapping with risk levels
2. `tests/e2e/journey-*.spec.ts` — Playwright test files with `// Validates: REQ-*` comments
3. Playwright test results (stdout/JSON)

None of this data flows back into the state or UI.

## Goals / Non-Goals

**Goals:**
- Parse WHEN/THEN scenarios from specs into structured data at digest time
- Parse JOURNEY-TEST-PLAN.md after acceptance-tests merge into state
- Parse Playwright JSON output for per-test results
- Show the full REQ → Scenario → Test → Result chain in report and web UI
- Detect coverage gaps (scenarios without tests)

**Non-Goals:**
- Modifying how the acceptance-tests agent writes tests (that's done in the previous change)
- Full BDD framework integration (Cucumber, SpecFlow) — we use the structure, not tooling
- Per-change test traceability (only the final acceptance-tests change is tracked)
- Real-time test streaming — we parse results post-merge

## Decisions

### D1: Scenario data model

**Choice:** Extend the digest requirement with a `scenarios` field.

```python
@dataclass
class DigestScenario:
    name: str          # "Add single item"
    when: str          # "user clicks add to cart on product detail"
    then: str          # "cart count shows 1 and product appears in cart"
    slug: str          # "add-single-item" (for matching with test plan)
```

Current `acceptance_criteria: list[str]` stays for backward compat. The new `scenarios` field is populated only when spec has proper `#### Scenario:` blocks with WHEN/THEN format.

### D2: Test coverage data model in state

```python
@dataclass
class TestCase:
    scenario_slug: str     # matches DigestScenario.slug
    req_id: str            # "REQ-CART-001"
    risk: str              # "HIGH" | "MEDIUM" | "LOW"
    test_file: str         # "journey-purchase.spec.ts"
    test_name: str         # "add product to cart"
    category: str          # "journey-step" | "standalone" | "negative"
    result: str | None     # "pass" | "fail" | None (not yet run)

@dataclass
class TestCoverage:
    plan_file: str                           # "tests/e2e/JOURNEY-TEST-PLAN.md"
    test_cases: list[TestCase]
    covered_reqs: list[str]                  # REQ IDs with at least one test
    uncovered_reqs: list[str]                # REQ IDs with zero tests
    non_testable_reqs: list[str]             # REQ IDs marked exempt
    total_tests: int
    passed: int
    failed: int
    coverage_pct: float                      # covered / (covered + uncovered)
    parsed_at: str                           # ISO timestamp
```

Stored in `state.extras["test_coverage"]`.

### D3: JOURNEY-TEST-PLAN.md format (contract)

The acceptance-tests agent writes this in Phase 0. The parser expects this format:

```markdown
## REQ-CART-001: Add to cart [HIGH]
- [x] Happy: Given logged in → When add Ethiopia 250g → Then cart count=1, product visible
  → journey-purchase.spec.ts: "add product to cart"
- [x] Negative: Given not logged in → When add item → Then redirect to login
  → journey-purchase.spec.ts: "anonymous add redirects to login"
- [ ] Boundary: Given cart has 99 items → When add 1 more → Then max limit error

## REQ-EMAIL-001: Order confirmation email [NON-TESTABLE]
Exempt: email delivery cannot be verified via Playwright
```

Parser extracts:
- REQ-ID from `## REQ-XXX:` header
- Risk level from `[HIGH]`, `[MEDIUM]`, `[LOW]`, `[NON-TESTABLE]`
- Test cases from `- [x]`/`- [ ]` lines
- Test file + name from `→ file: "name"` lines
- Category from prefix (Happy/Negative/Boundary)

### D4: Playwright JSON parsing

**Choice:** Enable Playwright JSON reporter alongside default.

The acceptance-tests agent's merge gate runs `npx playwright test`. We add `--reporter=json` to capture structured results. The JSON output contains per-test results that we match to test names from the plan.

Alternatively, parse the Playwright stdout which already contains test names and pass/fail. This is simpler and doesn't require reporter config changes.

**Decision:** Parse stdout first (simpler, no config change needed). If inadequate, add JSON reporter later.

Pattern to match in stdout:
```
✓  12 journey-purchase.spec.ts:15:7 › Full purchase flow › add product to cart (2.3s)
✗  13 journey-purchase.spec.ts:25:7 › Full purchase flow › apply coupon (5.1s)
```

### D5: When to parse — post-merge hook

**Choice:** In `merger.py:merge_change()`, after the acceptance-tests change merges successfully, run the test coverage parser.

Detection: `change.name == "acceptance-tests"` or `change.change_type == "test"` with requirements covering all REQs.

The parser:
1. Reads `tests/e2e/JOURNEY-TEST-PLAN.md` from the project root (now on main)
2. Reads the E2E gate output (change.test_stats + stdout)
3. Cross-references plan entries with test results
4. Stores `TestCoverage` in `state.extras["test_coverage"]`

### D6: Web UI — extend AC panel

The current ACPanel iterates requirements and shows ACs as checkboxes. Extend to show:

```
REQ-CART-001  Add to cart    ✅ merged    3/3 ✅
  ├── Scenario: Add single item                    [HIGH]
  │   WHEN clicks add to cart
  │   THEN cart count = 1
  │   └── journey-purchase.spec.ts:test#2  ✅
  │
  ├── Scenario: Add out-of-stock                   [HIGH]
  │   WHEN clicks add on out-of-stock
  │   THEN error message
  │   └── journey-purchase.spec.ts:test#4  ✅
  │
  └── Scenario: Anonymous add                      [MEDIUM]
      WHEN anonymous user adds item
      THEN redirect to login
      └── ⚠️ NO TEST
```

The data comes from two sources:
- Scenarios: digest API (DigestScenario from spec parsing)
- Test coverage: state extras (TestCoverage from post-merge parsing)

Frontend matches them by `scenario_slug` ↔ `DigestScenario.slug`.

### D7: Report.html — test coverage section

New section after the execution table:

```html
<h2>Test Coverage</h2>
<div class="coverage-summary">
  <p>Covered: 42/47 (89%) — 3 non-testable, 2 gaps</p>
  <div class="coverage-bar">...</div>
</div>
<table>
  <tr><th>REQ</th><th>Scenarios</th><th>Tests</th><th>Result</th></tr>
  <tr>
    <td>REQ-CART-001</td><td>3</td><td>3/3</td><td class="gate-pass">✓</td>
  </tr>
  ...
</table>
```

## Risks / Trade-offs

- **[Risk] JOURNEY-TEST-PLAN.md format not followed** → Mitigation: parser is lenient, extracts what it can, logs warnings for unparseable lines
- **[Risk] Playwright stdout format changes** → Mitigation: regex patterns are versioned, fallback to binary pass/fail if parse fails
- **[Risk] Scenario slug matching fails** → Mitigation: fuzzy matching (lowercase, strip punctuation), log mismatches
- **[Risk] Digest re-run loses scenario data** → Mitigation: scenarios are re-parsed from specs each time, no persistence needed

## Open Questions

None.
