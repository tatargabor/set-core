# Spec: Web Dashboard E2E Tests

## Requirements

### REQ-E2E-SETUP: Playwright infrastructure in web/
- `playwright.config.ts` with `E2E_PROJECT` and `E2E_BASE_URL` env vars
- HTML reporter enabled (output to `web/playwright-report/`)
- No `webServer` — assumes server is already running
- `helpers.ts` with shared navigation, API fetch, project resolution
- `package.json` scripts: `test:e2e` and `test:e2e:report`
- `@playwright/test` in devDependencies

### REQ-E2E-CHANGES: Changes tab data verification
- Each change row displays: name, status text, status color, session count, duration, token values, gate badges
- Gate badges: `[T]` for test, `[B]` for build, `[S]` for smoke, `[R]` for review, `[SC]` for spec_coverage — only when API value is non-null
- Gate badge color: green for pass, red for fail
- Token display: `formatTokens()` format — "Xk" or "X.XM", never "0/0" for merged changes with token data
- Foundation changes without gate data show "—" in gates column
- Change count in table matches API response change count

### REQ-E2E-PHASES: Phases tab data verification
- Changes grouped by phase number
- Phase header shows: phase number, status icon (completed/running/pending), done/total count
- Gate badges render on Phases tab (not just Changes tab)
- Dependency tree indentation visible for child changes
- Phase token/duration aggregation in header

### REQ-E2E-GATES: Gate detail interaction
- Clicking gate badges in Changes tab opens GateDetail panel
- GateDetail shows gate names and results
- ChangeTimeline renders inside expanded panel
- Second click collapses the panel
- Only one change expanded at a time

### REQ-E2E-TOKENS: Tokens chart
- Recharts SVG chart renders (not empty)
- At least one bar with non-zero height for projects with token data
- Change names visible on chart axis

### REQ-E2E-LOG: Log tab
- Log lines render (non-empty for projects with orchestration log)
- ERROR lines styled red
- WARNING lines styled amber/yellow

### REQ-E2E-SESSIONS: Sessions tab
- Session list renders with id, size, label, outcome fields
- Session label (Decompose, Review, etc.) displayed
- Clicking session loads JSONL content

### REQ-E2E-LEARNINGS: Learnings tab
- Gate stats table: per-gate rows (build, test, smoke) with total/pass/fail/pass_rate
- Pass rate is a valid percentage (not NaN, not undefined)
- Total gate time displayed
- Reflections count displayed

### REQ-E2E-DIGEST: Digest tab
- Requirements list renders (when digest exists)
- Domain tabs render
- Coverage data displayed

### REQ-E2E-NAV: Navigation and routing
- Tab switching updates URL query param (?tab=phases)
- Direct URL navigation loads correct tab
- Sidebar shows project name
- Manager page (/) lists registered projects
- Project click navigates to /p/{name}/orch

### REQ-E2E-ACTIONS: Change action buttons
- Merged changes: no action buttons
- Pending changes: Skip button visible
- Running changes: Pause and Stop buttons visible
- Stop requires confirmation (click once → "Sure?", click again → executes)
- Paused changes: Resume button visible

### REQ-E2E-DOCS: Documentation
- CLAUDE.md documents how to run E2E tests
- Instructions cover: prerequisites, running tests, viewing reports, adding new tests
