# Proposal: wt-web-ac-coverage-display

## Why

The backend pipeline now extracts acceptance criteria per requirement (digest.py) and tracks spec coverage with state-aware statuses (planner.py, verifier.py), but the wt-web dashboard does not display any of this data. Users monitoring orchestration runs cannot see AC items for requirements, spec coverage gate results, or the generated coverage report — all of which are already available in the backend JSON/state files.

## What Changes

- **Add acceptance_criteria to frontend DigestReq type** and render AC items as expandable rows in both DigestView and ProgressView requirement tables
- **Add dedicated AC Coverage sub-tab** to DigestView for cross-cutting AC progress view grouped by domain
- **Add spec_coverage_result to frontend ChangeInfo type** and render as a new gate badge (SC) in GateBar/GateDetail
- **Add spec coverage report API endpoint** to serve the generated `spec-coverage-report.md` file
- **Add coverage report viewer** in a new sub-tab or panel showing the rendered markdown report
- **Use coverage-merged.json data** in DigestView overview for accurate merged coverage counts

## Capabilities

### New Capabilities
- `ac-display`: Frontend display of acceptance criteria in requirement tables and cross-cutting AC tab
- `coverage-gate-display`: Frontend display of spec coverage gate result and coverage report

### Modified Capabilities
- `web-dashboard-spa`: Dashboard tabs and layout updated with AC sub-tab and coverage report viewer
- `web-api-server`: New endpoint for spec coverage report

## Impact

- **Frontend**: DigestView.tsx, ProgressView.tsx, GateBar.tsx, GateDetail.tsx, api.ts (type updates + new fetcher)
- **Backend**: api.py (1 new endpoint: coverage report)
- **No breaking changes**: All additions are backward-compatible — missing fields default gracefully
