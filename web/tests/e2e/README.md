# Web Dashboard E2E Tests

Playwright tests that verify the set-core web dashboard renders data correctly.

## How It Works

Every test follows the **API-UI verification** pattern:

1. Fetch data from the REST API (`/api/{project}/state`)
2. Navigate to the dashboard page in a real browser
3. Assert the UI renders the API data correctly

No mocks. No fixtures. Tests run against the **live server** with a **real project**.

This catches bugs at every layer:
- Python `state.py` → `to_dict()` serialization
- FastAPI response shape
- React component rendering
- Tailwind CSS class availability (not purged)
- Vite build correctness

## Prerequisites

1. `set-orch-core` server running on port 7400 (or custom `E2E_BASE_URL`)
2. At least one registered project with completed orchestration (e.g., `minishop-run-20260315-0930`)
3. Chromium installed: `npx playwright install chromium`

## Running

```bash
cd web/

# Run all tests against a specific project
E2E_PROJECT=minishop-run-20260315-0930 pnpm test:e2e

# View the HTML report
pnpm test:e2e:report

# Run a specific test file
E2E_PROJECT=minishop-run-20260315-0930 npx playwright test changes-data

# Run with headed browser (debug)
E2E_PROJECT=minishop-run-20260315-0930 npx playwright test --headed
```

## Test Structure

| File | What it tests |
|------|--------------|
| `changes-data.spec.ts` | Gate badges, tokens, status, duration, session count |
| `phases-data.spec.ts` | Phase groups, tree layout, gate badges on phases tab |
| `gate-detail.spec.ts` | Expand/collapse gate detail panel |
| `tokens-chart.spec.ts` | Recharts renders, bars have height |
| `log-tab.spec.ts` | Log lines display, error color coding |
| `sessions-tab.spec.ts` | Session list, labels |
| `learnings-tab.spec.ts` | Gate stats, pass rates, reflections |
| `digest-tab.spec.ts` | Requirements, domains, coverage |
| `navigation.spec.ts` | Tab switching, URL routing, sidebar |
| `change-actions.spec.ts` | Pause/Stop/Skip buttons per status |

## Adding New Tests

1. Create `web/tests/e2e/<name>.spec.ts`
2. Import helpers: `import { getApiState, navigateToTab } from './helpers'`
3. Follow the API-UI pattern: fetch from API, assert in browser
4. Use `test.skip()` when the project doesn't have the required data (graceful skip)

## Interpreting Results

After a run, open the HTML report:

```bash
pnpm test:e2e:report
```

- **Green**: All assertions pass — UI matches API data
- **Red with screenshot**: Something broke — the screenshot shows what the user would see
- **Skipped**: The test project doesn't have the required data (e.g., no pending changes)

## Common Failures and What They Mean

| Failure | Likely Cause |
|---------|-------------|
| Gate badge not visible | `GateBar` component not receiving prop, or `to_dict()` not including field |
| Token shows "—" for merged change | `_final_token_collect()` not called, or `loop-state.json` missing |
| Tab doesn't load | Route change in `App.tsx`, or component import error |
| "NaN" in learnings | Division by zero in gate stats calculation |
