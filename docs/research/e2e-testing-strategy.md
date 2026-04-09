# E2E Testing Strategy Research

Research conducted during MiniShop E2E Run #2 analysis (2026-03-09). Findings informed the `fix-jest-playwright-coexistence` change — pre-merge Playwright E2E in worktrees with port/DB isolation.

## Problem Statement

The orchestrator's original testing architecture:
- `test_command` (Jest unit tests) — pre-merge in worktree
- `smoke_command` (Playwright E2E) — post-merge on main

This caused three failures:
1. **Jest/Playwright collision**: Jest picks up `.spec.ts` files and crashes on Playwright imports in jsdom (`TypeError: Class extends value undefined`)
2. **No pre-merge E2E**: Broken code lands on main, no change attribution for the fix
3. **Consolidation anti-pattern**: Planner defers all E2E to one agent — too complex, single point of failure

## Testing Models

### Testing Pyramid (Traditional)

```
    /  E2E  \        ~10%
   / Integr. \       ~20%
  /   Unit    \      ~70%
```

Originated: Mike Cohn, "Succeeding with Agile" (2009). Optimizes for speed and isolation. Works well for backend services with stable APIs. Under-tests runtime interactions critical in web applications.

### Testing Diamond (Modern — Preferred for Web)

```
    /  E2E  \        ~10%  — critical user flows
   /=========\
  / Integr.   \      ~50%  — API, DB, component interactions (FOCUS)
   \==========/
    \  Unit  /       ~40%  — pure logic, utilities, validation
```

Popularized by Guillermo Rauch: "Write tests. Not too many. Mostly integration." Endorsed by web.dev testing strategy guides and code4it.dev.

**Why Diamond fits web apps:** Web applications fail primarily at runtime boundaries — `cookies()`, `headers()`, `redirect()`, middleware chains, DB queries, session management. Mock-based unit tests hide these failures because the mocks pass even when the real runtime would crash. The MiniShop run proved this: all 81 Jest unit tests passed while the app had critical bugs (admin visible without auth, session.ts crash, dead routes).

### ISTQB Test Levels

The ISTQB CT-TAS v1.0 (2024) and CTAL-TAE v2.0 syllabi define four test levels mapped to automation:

| ISTQB Level | Description | Our Mapping | When |
|---|---|---|---|
| Component (unit) | Code quality, pure logic | Jest/Vitest via `test_command` | Pre-merge |
| Component Integration | UI/API with test doubles | Jest/Vitest via `test_command` | Pre-merge |
| Contract | Service contract validation | N/A (single-service) | — |
| UI (E2E) | Full system via GUI | Playwright via `e2e_command` | Pre-merge |

The CTAL-TAE v2.0 extends with automation architecture patterns:
- **Keyword-driven**: Maps to Playwright's page object pattern
- **Data-driven**: Maps to env var configuration (`PW_PORT`, `DATABASE_URL`)
- **Model-based**: Maps to spec-driven test generation in planner

## Pre-Merge E2E — "Shift Left" Industry Consensus

Running E2E tests pre-merge in ephemeral environments is the established industry best practice:

### Shipyard — "E2E Testing Before Merge"
- Ephemeral preview environments per PR
- Each PR gets isolated runtime (server, DB, filesystem)
- **Our analog**: Git worktrees are ephemeral environments — isolated filesystem, branch, and database per change

### Aviator — "Pre and Post-Merge Tests Using a Merge Queue"
- Two-step CI: fast tests on every commit, thorough tests before merge
- Fast: lint, type check, unit tests (~30s)
- Thorough: E2E, integration, performance (~2min)
- **Our analog**: Step 1 (`test_command` + build) / Step 2 (`e2e_command`) in verify gate

### Conf42 — Shift-Left Testing
- Catching bugs earlier is exponentially cheaper
- Post-merge E2E = broken code on main with no change attribution
- Pre-merge E2E = bugs caught per-change, fix is targeted

### Microsoft Engineering Playbook — Smoke Testing
- Smoke tests = post-deploy verification of critical paths
- Distinct from E2E: smoke is "does it run?", E2E is "does it work correctly?"
- **Our analog**: `smoke_command` (optional post-merge) vs `e2e_command` (required pre-merge)

## Playwright Isolation Patterns

### Port Isolation

Playwright natively supports per-worker isolation via `workerIndex` for ports and databases (documented in Parallelism, WorkerInfo, and Fixtures docs).

For our simpler case — one Playwright run per worktree — a `PW_PORT` environment variable suffices:

```typescript
// playwright.config.ts
const PORT = process.env.PW_PORT ? parseInt(process.env.PW_PORT) : 3100;
export default defineConfig({
  use: { baseURL: `http://localhost:${PORT}`, headless: true, screenshot: 'on' },
  webServer: {
    command: `pnpm dev --port ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: false,  // fail fast on port collision
    timeout: 120_000,
  },
});
```

- Port range: 3100-3999 (avoids default dev port 3000)
- Assignment: `PW_PORT=$((3100 + RANDOM % 900))` per worktree
- Collision probability: ~0.1% per pair of concurrent runs (900 ports)
- Detection: `reuseExistingServer: false` makes Playwright error immediately on collision

### Browser Cache

Browser binaries at `~/.cache/ms-playwright/` are shared across all worktrees. Install once via `npx playwright install chromium` in the infrastructure change.

## DB Isolation for Parallel E2E

Per Playwright GitHub issue #33699, database isolation is the hardest problem in parallel E2E testing.

### Tier 1 — SQLite (Zero Config)

File-based databases are naturally isolated per worktree:
- Each worktree has its own `prisma/dev.db` file
- `prisma db push` + `prisma db seed` operates on the local file
- No shared state, no conflicts
- Schema divergence between worktrees (different changes adding different models) is naturally isolated

This covers most orchestrated web projects.

### Tier 2 — PostgreSQL/MySQL (Future)

Server-based databases require per-worktree database names:

```
cart-feature  → DATABASE_URL=postgres://.../ app_wt_cart_feature
admin-auth    → DATABASE_URL=postgres://.../ app_wt_admin_auth
```

Implementation: `e2e_db_setup` / `e2e_db_teardown` hooks in orchestrator. Deferred — most orchestrated projects use SQLite.

### Tier 3 — Clean State via globalSetup

Regardless of database type, the Playwright `globalSetup` must ensure clean state:

```typescript
// tests/e2e/global-setup.ts
async function globalSetup() {
  execSync('npx prisma generate', { stdio: 'inherit' });
  execSync('npx prisma db push --force-reset', { stdio: 'inherit' });
  execSync('npx prisma db seed', { stdio: 'inherit' });
}
```

**Critical**: `prisma generate` must run before `prisma db push`. Without it, the Prisma client doesn't know about models added by the current change, causing seed/test failures. This was identified during MiniShop analysis.

## Jest/Playwright Coexistence

### The Problem

Jest's default `testRegex` matches `.spec.ts` files. When Playwright test files (`tests/e2e/*.spec.ts`) exist, Jest picks them up and tries to run them in jsdom. Playwright imports (`@playwright/test`) reference browser APIs unavailable in jsdom, causing:

```
TypeError: Class extends value undefined is not a constructor or null
```

In MiniShop Run #2, the agent wasted 1.57M tokens trying to fix this without identifying the root cause.

### The Fix

One line in `jest.config.ts`:

```typescript
testPathIgnorePatterns: ["/node_modules/", "/tests/e2e/"],
```

This must be set up in the infrastructure/foundation change (first in dependency order), not in individual feature changes.

### Planner Implications

- Scope must say `Create tests/e2e/cart.spec.ts` (explicit file deliverable), not `Functional test scenarios: ...` (description)
- Each feature change owns its own `.spec.ts` file
- No consolidation "e2e" change that writes all tests at once (anti-pattern: overloads one agent)

## Two-Step Verify Gate Architecture

```
Step 1 — Fast feedback (~30s):        Step 2 — Thorough validation (~2min):
┌─────────────────────────┐            ┌─────────────────────────────┐
│ test_command (Jest)      │            │ e2e_command (Playwright)    │
│ build (pnpm build)       │            │  ├─ auto-start dev server   │
│                          │            │  ├─ per-worktree DB         │
│ → catches type errors,   │            │  ├─ isolated port           │
│   import errors, logic   │            │  └─ real runtime validation │
└─────────────────────────┘            └─────────────────────────────┘
```

| Level | When | What | Gate |
|---|---|---|---|
| `test_command` | Pre-merge | Jest unit tests | Blocking |
| `build` | Pre-merge | TypeScript/Next build | Blocking |
| `e2e_command` | Pre-merge | Playwright per-change | Blocking (NEW) |
| `smoke_command` | Post-merge | Cross-feature integration | Optional |

## References

- ISTQB CT-TAS v1.0 Syllabus (2024) — test automation strategy, CI/CD integration
- ISTQB CTAL-TAE v2.0 — test automation architecture, test levels mapping
- Guillermo Rauch — "Write tests. Not too many. Mostly integration."
- web.dev — Testing strategy guides (Testing Diamond)
- code4it.dev — Testing Diamond model explanation
- Playwright docs — Parallelism, WorkerInfo, Fixtures (per-worker isolation)
- Playwright GitHub #33699 — DB isolation patterns for parallel E2E
- Shipyard — "E2E Testing Before Merge" (ephemeral environments per PR)
- Aviator — "Pre and Post-Merge Tests Using a Merge Queue" (two-step CI)
- Conf42 — Shift-left testing conference talks
- Microsoft Engineering Playbook — Smoke Testing (post-deploy verification)
