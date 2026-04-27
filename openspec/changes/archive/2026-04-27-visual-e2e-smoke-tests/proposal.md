## Why

The verify gate's E2E check only validates HTTP status codes — it doesn't catch client-side errors (React hydration failures, RSC boundary violations, runtime exceptions). In a recent run, a change passed E2E (HTTP 200) but the page was broken (NotifyMeHandler render prop function passed across RSC/client boundary = Runtime Error visible only after hydration).

Additionally, the E2E gate has no way to verify that the original bug described in the spec was actually fixed. An agent can commit tangential improvements, pass all gates, and merge — while the core bug remains.

## What

Two layers of visual E2E smoke testing:

### 1. Framework level (set-core verifier.py)
- **Console error capture**: Inject `page.on('pageerror')` check into E2E gate — any uncaught runtime error = gate fail
- **Hydration error detection**: Check for React/Next.js error overlay markers in DOM after page load
- **Screenshot on every E2E run**: Configure Playwright `screenshot: 'on'` in the gate, archive results for dashboard review

### 2. Project-type level (set-project-web templates)
- **Route smoke generator**: Auto-generate a Playwright test that visits every `page.tsx` route, waits for hydration (`networkidle`), and asserts: no console errors, no error boundaries in DOM, page renders content
- **Template deployed via `set-project init`**: The test file is generated/updated on deploy based on the app directory structure

## Scope

**set-core (this repo):**
- `lib/set_orch/verifier.py` — E2E gate: add console error capture, hydration error check
- `lib/set_orch/profile_loader.py` — New method: `generate_smoke_e2e()` for project-type plugins to provide auto-generated tests

**set-project-web (separate repo, follow-up):**
- Route smoke test generator template
- Deploy via `set-project init --project-type web`
