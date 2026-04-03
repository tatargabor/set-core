# Proposal: BDD Test Traceability

## Why

The system already has a BDD-like chain: Spec Scenarios (WHEN/THEN) → Digest REQs → ACs → Changes. But this chain breaks at the test layer — there's no visibility into which ACs have test coverage, which tests map to which scenarios, or whether journey tests actually verify what the spec defines.

Current state:
- Digest extracts `acceptance_criteria` as **plain string arrays** — WHEN/THEN structure is lost
- Web UI AC tab shows checkboxes (done/not done) but **no test info**
- E2E gate result is binary pass/fail — **no per-test breakdown**
- `JOURNEY-TEST-PLAN.md` will exist (from the acceptance-gate change) but **nothing parses it**

The full BDD traceability chain should be:
```
Spec Scenario → Digest AC (with WHEN/THEN) → Test Case → Test Result
```

All visible on the web UI and report.

## What Changes

- **Digest scenario extraction**: Parse `#### Scenario:` blocks from specs, extracting WHEN/THEN structure into structured data (not plain strings)
- **JOURNEY-TEST-PLAN.md parser**: Parse the test plan that the acceptance-tests agent writes, linking REQ-IDs to test files and test names
- **Playwright JSON result parser**: Parse Playwright's JSON reporter output to get per-test pass/fail results
- **State model extension**: `state.extras["test_coverage"]` with REQ → scenario → test case → result mapping
- **Post-merge hook**: After acceptance-tests merge, parse plan + results, store in state
- **Report extension**: Test Coverage section in report.html showing REQ → scenario → test → result
- **Web UI extension**: AC tab enhanced with test coverage data per scenario

## Capabilities

### New Capabilities
- `bdd-scenario-extraction` — Digest parses WHEN/THEN scenarios as structured data
- `test-coverage-tracking` — Post-merge parsing of test plan and results into state
- `test-coverage-display` — Web UI and report visualization of BDD → test chain

### Modified Capabilities
- `spec-digest` — Scenario extraction added to requirement parsing
- `orchestration-html-report` — Test coverage section added
- `ac-display` — Web UI AC panel shows test coverage per scenario

## Impact

- `lib/set_orch/digest.py` — Scenario extraction in requirement parsing
- `lib/set_orch/state.py` — TestCoverage dataclass
- `lib/set_orch/merger.py` — Post-merge test plan + result parsing
- `lib/set_orch/reporter.py` — Test coverage section in HTML report
- `lib/set_orch/api/orchestration.py` — Test coverage in digest API response
- `web/src/components/DigestView.tsx` — AC panel enhanced with test data
- `web/src/lib/api.ts` — TypeScript types for test coverage
