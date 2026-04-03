# Design: Web Dashboard E2E Tests

## Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Real project    │     │  set-orch-core    │     │  Playwright      │
│  (minishop-run10)│────▶│  FastAPI server   │────▶│  browser tests   │
│  state files     │     │  port 7400        │     │                  │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

No mocks. No fixtures. The server reads real project state files and serves the real SPA.

## Test Pattern: API-UI Verification

Every test follows the same pattern:
1. Fetch data from the API (`request.get("/api/{project}/state")`)
2. Navigate to the page in the browser
3. Assert the UI renders the API data correctly

This catches bugs at every layer: Python serialization, API response shape, React rendering, CSS class availability.

```typescript
// Example: verify gate icons match API data
const state = await apiState.json()
const change = state.changes.find(c => c.test_result === 'pass')
const row = page.locator(`tr:has-text("${change.name}")`)
await expect(row.locator('[title="test: pass"]')).toBeVisible()
```

## File Structure

```
web/
├── playwright.config.ts
├── tests/e2e/
│   ├── helpers.ts              ← shared navigation + API helpers
│   ├── changes-data.spec.ts    ← gate badges, tokens, status, duration
│   ├── phases-data.spec.ts     ← phase groups, tree, gate badges
│   ├── gate-detail.spec.ts     ← expand/collapse gate detail panel
│   ├── tokens-chart.spec.ts    ← chart renders, bars have height
│   ├── log-tab.spec.ts         ← log lines, color coding
│   ├── sessions-tab.spec.ts    ← session list, labels, outcomes
│   ├── learnings-tab.spec.ts   ← gate stats, review findings, reflections
│   ├── digest-tab.spec.ts      ← requirements, domains, coverage
│   ├── navigation.spec.ts      ← sidebar, tab switching, URL routing
│   └── change-actions.spec.ts  ← pause/stop/skip/resume buttons
```

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `E2E_PROJECT` | (required) | Registered project name with completed orchestration |
| `E2E_BASE_URL` | `http://localhost:7400` | Server URL |

## Reporter

Use Playwright HTML reporter for readable bug reports:
- Screenshot on failure
- Step-by-step trace
- Filterable by test name
- Output to `web/playwright-report/`

## Key Design Decisions

1. **No webServer config** — server must already be running (same as production)
2. **No fixtures/mocks** — tests run against real data, real server
3. **API-first assertions** — never hardcode expected values, always compare against API
4. **Parametric project** — any completed orchestration run works as test data
5. **HTML report** — `npx playwright show-report` for visual bug diagnosis
