# Tasks: Web Dashboard E2E Tests

## 1. Playwright Setup

- [x] Add `@playwright/test` to `web/package.json` devDependencies
- [x] Create `web/playwright.config.ts` — baseURL from `E2E_BASE_URL` env (default `http://localhost:7400`), HTML reporter, no webServer, screenshot on failure
- [x] Add scripts to `web/package.json`: `"test:e2e": "playwright test"`, `"test:e2e:report": "playwright show-report"`
- [x] Add `playwright-report/` and `test-results/` to `web/.gitignore`
- [x] Create `web/tests/e2e/helpers.ts` — `PROJECT` from env, `navigateToTab()`, `getApiState()`, `formatTokens()` mirror

## 2. Changes Tab Tests

- [x] Create `web/tests/e2e/changes-data.spec.ts`
- [x] Test: change row count matches API changes count
- [x] Test: merged change with `test_result=pass` shows `[T]` badge with `title="test: pass"`
- [x] Test: merged change with `build_result=pass` shows `[B]` badge
- [x] Test: merged change with `smoke_result=pass` shows `[S]` badge
- [x] Test: change with `review_result=null` does NOT show `[R]` badge
- [x] Test: change with no gate results (all null) shows "—" in gates column
- [x] Test: merged change with `output_tokens > 0` does NOT show "—/—" in token column
- [x] Test: `session_count` value displayed in Sess column (when present)
- [x] Test: duration column shows time format (Xm Ys or Xs) for changes with started_at+completed_at

## 3. Phases Tab Tests

- [x] Create `web/tests/e2e/phases-data.spec.ts`
- [x] Test: phase groups render — at least one "Phase N" header visible
- [x] Test: phase header shows done/total count (matches filtered changes)
- [x] Test: gate badges appear on phases tab (same as changes tab)
- [x] Test: phase status icon: ✅ for completed phases, 🔄 for running
- [x] Test: dependency tree — child changes indented (padding-left > 0)

## 4. Gate Detail Tests

- [x] Create `web/tests/e2e/gate-detail.spec.ts`
- [x] Test: clicking gate badges in Changes tab opens detail panel (new row appears)
- [x] Test: detail panel contains gate result text
- [x] Test: clicking again collapses the panel

## 5. Tokens Chart Tests

- [x] Create `web/tests/e2e/tokens-chart.spec.ts`
- [x] Test: SVG chart element exists (Recharts renders)
- [x] Test: at least one rect/bar element with height > 0

## 6. Log Tab Tests

- [x] Create `web/tests/e2e/log-tab.spec.ts`
- [x] Test: log content area is not empty (when orchestration.log exists)
- [x] Test: lines containing "ERROR" have red text color class

## 7. Sessions Tab Tests

- [x] Create `web/tests/e2e/sessions-tab.spec.ts`
- [x] Test: session list renders entries (when sessions exist via API)
- [x] Test: session entry shows label (Decompose, Review, etc.)

## 8. Learnings Tab Tests

- [x] Create `web/tests/e2e/learnings-tab.spec.ts`
- [x] Test: gate stats section renders per-gate rows (build, test, smoke)
- [x] Test: pass rate values are valid numbers (not NaN)
- [x] Test: reflections count is displayed

## 9. Digest Tab Tests

- [x] Create `web/tests/e2e/digest-tab.spec.ts`
- [x] Test: when digest exists, requirements section renders
- [x] Test: domain tabs are clickable
- [x] Test: coverage data is displayed

## 10. Navigation Tests

- [x] Create `web/tests/e2e/navigation.spec.ts`
- [x] Test: clicking tab updates URL to include `?tab=<name>`
- [x] Test: navigating directly to `?tab=phases` loads Phases tab
- [x] Test: sidebar contains project name text
- [x] Test: manager page (/) lists at least one project
- [x] Test: clicking project navigates to /p/{name}/orch

## 11. Change Actions Tests

- [x] Create `web/tests/e2e/change-actions.spec.ts`
- [x] Test: merged change row has no action buttons
- [x] Test: pending change row shows "Skip" button (if project has pending changes)
- [x] Test: running change row shows "Pause" and "Stop" buttons (if project has running changes)

## 12. Documentation

- [x] Add "## Web Dashboard E2E Tests" section to CLAUDE.md with: prerequisites, run command, view report command, how to add new tests
- [x] Add `web/tests/e2e/README.md` with test architecture explanation and the API-UI verification pattern
