# Tasks: wt-web-ac-coverage-display

## 1. TypeScript Type Updates

- [x] 1.1 Add `acceptance_criteria?: string[]` to `DigestReq` interface in `web/src/lib/api.ts` [REQ: digestreq-type-includes-acceptance_criteria]
- [x] 1.2 Add `spec_coverage_result?: string` to `ChangeInfo` interface in `web/src/lib/api.ts` [REQ: changeinfo-type-includes-spec_coverage_result]
- [x] 1.3 Add `coverage_merged` field to `DigestData` interface in `web/src/lib/api.ts` with same shape as `coverage` [REQ: coverage-merged-data-in-digestview-overview]
- [x] 1.4 Add `getCoverageReport(project: string)` fetch function in `web/src/lib/api.ts` [REQ: coverage-report-endpoint]

## 2. Backend API Endpoint

- [x] 2.1 Add `GET /api/{project}/coverage-report` endpoint in `lib/set_orch/api.py` that reads `wt/orchestration/spec-coverage-report.md` and returns `{exists, content}` [REQ: coverage-report-endpoint]

## 3. GateBar — Spec Coverage Badge

- [x] 3.1 Add `spec_coverage_result` prop to GateBar component in `web/src/components/GateBar.tsx` [REQ: spec-coverage-gate-badge-in-gatebar]
- [x] 3.2 Render "SC" badge when `spec_coverage_result` is present, using existing `statusStyle` map (pass=green, fail/timeout=red) [REQ: spec-coverage-gate-badge-in-gatebar]
- [x] 3.3 Pass `spec_coverage_result` from ChangeTable to GateBar in both mobile and desktop layouts [REQ: spec-coverage-gate-badge-in-gatebar]

## 4. GateDetail — Spec Coverage Section

- [x] 4.1 Add "Spec Coverage" entry to the `gates` array in GateDetail component in `web/src/components/GateDetail.tsx` using `change.spec_coverage_result` [REQ: spec-coverage-in-gatedetail]
- [x] 4.2 Map timeout result to fail styling in GateDetail [REQ: spec-coverage-in-gatedetail]

## 5. DigestView — Inline AC Display

- [x] 5.1 Make requirement rows expandable in DigestView `OverviewPanel` — add click handler and expanded state tracking per requirement ID [REQ: inline-ac-display-in-requirement-tables]
- [x] 5.2 Render AC items as checkbox-style lines below expanded requirement row: checked when associated change status is done/merged/completed/skip_merged, unchecked otherwise [REQ: inline-ac-display-in-requirement-tables]
- [x] 5.3 Make requirement rows expandable in DigestView `RequirementsPanel` with same AC rendering [REQ: inline-ac-display-in-requirement-tables]
- [x] 5.4 Skip AC rendering when `acceptance_criteria` is empty or absent (no empty state) [REQ: inline-ac-display-in-requirement-tables]

## 6. DigestView — AC Sub-Tab

- [x] 6.1 Add `'ac'` to the `DigestTab` union type and tabs array in DigestView [REQ: ac-coverage-sub-tab-in-digestview]
- [x] 6.2 Create `ACPanel` component: aggregate progress bar (checked/total AC count), requirements grouped by domain, each AC item showing req ID + AC text + check state [REQ: ac-coverage-sub-tab-in-digestview]
- [x] 6.3 Add domain filter dropdown to ACPanel [REQ: ac-coverage-sub-tab-in-digestview]
- [x] 6.4 Show "No acceptance criteria extracted" when all requirements have empty AC [REQ: ac-coverage-sub-tab-in-digestview]

## 7. ProgressView — Inline AC in Digest Fallback

- [x] 7.1 Make requirement rows expandable in `DigestDomainGroup` component (ProgressView digest fallback) with same AC rendering as DigestView [REQ: inline-ac-display-in-requirement-tables]

## 8. DigestView — Coverage-Merged Data

- [x] 8.1 In DigestView `OverviewPanel`, prefer `data.coverage_merged.coverage` over `data.coverage.coverage` when available [REQ: coverage-merged-data-in-digestview-overview]
- [x] 8.2 Same preference in the `uncovered` array: use merged data when present [REQ: coverage-merged-data-in-digestview-overview]

## 9. Coverage Report Viewer

- [x] 9.1 Add coverage report fetch and render in an appropriate location — either as a section in DigestView overview or in GateDetail spec coverage section, using existing `MarkdownPanel` [REQ: coverage-report-viewer]
- [x] 9.2 Show "No coverage report generated yet" fallback when report does not exist [REQ: coverage-report-viewer]

## 10. Integration Verification

- [x] 10.1 Verify that old state files (without spec_coverage_result or acceptance_criteria) render correctly with no errors — graceful fallback to current behavior [REQ: digestreq-type-includes-acceptance_criteria]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN digest API returns a requirement with acceptance_criteria array THEN DigestReq object has acceptance_criteria populated [REQ: digestreq-type-includes-acceptance_criteria, scenario: ac-field-present-in-digest-response]
- [x] AC-2: WHEN digest API returns a requirement without acceptance_criteria THEN frontend treats it as empty array [REQ: digestreq-type-includes-acceptance_criteria, scenario: ac-field-missing-old-digest]
- [x] AC-3: WHEN user expands a requirement row with 3 AC items THEN 3 AC items render with check indicators based on change status [REQ: inline-ac-display-in-requirement-tables, scenario: expand-requirement-with-ac-items]
- [x] AC-4: WHEN user expands a requirement with empty acceptance_criteria THEN no AC section renders [REQ: inline-ac-display-in-requirement-tables, scenario: requirement-with-no-ac-items]
- [x] AC-5: WHEN user navigates to AC sub-tab THEN progress bar and domain-grouped AC items render [REQ: ac-coverage-sub-tab-in-digestview, scenario: ac-tab-shows-aggregate-progress]
- [x] AC-6: WHEN all requirements have empty AC THEN AC tab shows "No acceptance criteria extracted" [REQ: ac-coverage-sub-tab-in-digestview, scenario: ac-tab-with-no-ac-data]
- [x] AC-7: WHEN change has spec_coverage_result "pass" THEN GateBar renders green SC badge [REQ: spec-coverage-gate-badge-in-gatebar, scenario: sc-badge-shows-pass]
- [x] AC-8: WHEN change has spec_coverage_result "fail" THEN GateBar renders red SC badge [REQ: spec-coverage-gate-badge-in-gatebar, scenario: sc-badge-shows-fail]
- [x] AC-9: WHEN change has no spec_coverage_result THEN no SC badge renders [REQ: spec-coverage-gate-badge-in-gatebar, scenario: sc-badge-hidden-when-absent]
- [x] AC-10: WHEN spec-coverage-report.md exists THEN coverage-report endpoint returns exists:true with content [REQ: coverage-report-endpoint, scenario: report-file-exists]
- [x] AC-11: WHEN spec-coverage-report.md is missing THEN coverage-report endpoint returns exists:false [REQ: coverage-report-endpoint, scenario: report-file-missing]
- [x] AC-12: WHEN digest API returns both coverage and coverage_merged THEN overview uses coverage_merged [REQ: coverage-merged-data-in-digestview-overview, scenario: merged-coverage-available]
- [x] AC-13: WHEN digest API returns only coverage (no merged) THEN overview uses coverage [REQ: coverage-merged-data-in-digestview-overview, scenario: only-base-coverage-available]
