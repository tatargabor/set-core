import "dotenv/config";
import { randomBytes } from "node:crypto";
import { defineConfig, devices } from "@playwright/test";

const port = Number(process.env.PW_PORT) || 3000;

// Global suite cap. Driven by PW_TIMEOUT (seconds) so the orchestrator can
// pass the effective gate budget down — otherwise a gate with a 600s directive
// would be killed at 600s but playwright would still be in minute-40 of 60,
// burning the whole gate budget without a useful failure list.
const globalTimeoutMs = process.env.PW_TIMEOUT
  ? parseInt(process.env.PW_TIMEOUT, 10) * 1000
  : 3_600_000;

// When the gate asks for a fresh server (zombie-proof, stale-build-proof),
// disable Playwright's reuseExistingServer optimization.
const freshServer = !!process.env.PW_FRESH_SERVER;

// NEXTAUTH_SECRET for the E2E webServer.
//
// This MUST be set at config load time (before `webServer.env` spreads
// process.env below) because globalSetup runs AFTER the webServer child
// process is spawned — too late for it to inherit the value.
//
// Precedence:
//   1. Real `.env` / `NEXTAUTH_SECRET` set in the environment (e.g. CI secret).
//   2. Otherwise: a cryptographically random secret generated per test run.
//
// Safe because playwright.config.ts is never loaded by production builds —
// it only runs when `npx playwright test` invokes it. This does NOT violate
// security-patterns.md § 10 (which bans fallbacks in *production* code).
if (!process.env.NEXTAUTH_SECRET) {
  process.env.NEXTAUTH_SECRET = randomBytes(32).toString("base64");
}

export default defineConfig({
  testDir: "./tests/e2e",
  // Single worker: SQLite has writer contention under concurrent connections,
  // and stateful auth tests reuse the same test user. Override only when the
  // app uses Postgres/MySQL with per-worker database isolation.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  // Retries hide flakiness. Orchestration gates set PW_FLAKY_FAILS=1 so the
  // suite runs with 0 retries — any failure is a REAL bug, not hardware jitter.
  // Local dev keeps the 1-retry comfort; CI (outside orchestration) keeps 2.
  retries: process.env.PW_FLAKY_FAILS ? 0 : process.env.CI ? 2 : 1,
  // Per-test cap. 30s is enough for typical interactions; assertion-heavy
  // tests can override locally with test.setTimeout().
  timeout: 30_000,
  // Global suite cap. Driven by PW_TIMEOUT env (seconds) when set by the gate
  // runner; defaults to 1h. Sized for ~150-200 tests at ~3-5s each + login per
  // test (~3s) + webServer cold start (Next.js prod build can be 30s+) +
  // prisma seed. The set-orch e2e gate timeout is the outer kill switch
  // (3600s default, see verifier.DEFAULT_E2E_TIMEOUT).
  globalTimeout: globalTimeoutMs,
  // Reporter choice has real memory impact. "html" buffers every screenshot +
  // trace + result in memory until suite end, which caused SIGKILL (exit 137)
  // on realistic suites when combined with screenshot: "on". "list" streams
  // to stdout — parseable by the orchestrator's failure extractor, minimal
  // memory. Harvested from craftbrew-run-20260415-0146 (agent hit OOM at
  // 26 tests, fixed it, the fix is now in the template).
  reporter: "list",
  use: {
    baseURL: `http://localhost:${port}`,
    headless: true,
    locale: "en-US",
    // ALWAYS capture screenshots + trace — pass and fail alike. These are the
    // primary forensic artifact when review gates debate whether "this test
    // passed because the fix worked" vs "this test passed because it never
    // actually rendered the change". Skipping green captures hides that from
    // the dashboard's per-attempt gallery. Memory pressure is mitigated by
    // `reporter: "list"` above — the OOM incident (craftbrew-run-20260415-0146)
    // was `html` reporter buffering everything, not the capture mode itself.
    // Do NOT downgrade to "only-on-failure" — the per-attempt archive relies
    // on every run having artifacts so the user can verify tests re-executed.
    screenshot: "on",
    // Trace every test in memory but only write .zip for failures.
    // Saves ~200 MB/attempt in gate archives (140 passing trace.zip's)
    // while preserving full trace forensics for any failing test.
    trace: "retain-on-failure",
    // Action and navigation defaults — Playwright's defaults (no timeout)
    // cause hung tests to consume globalTimeout instead of failing fast.
    // navigationTimeout is 30s (not the Playwright default 15s) because the
    // first few page.goto calls in a fresh gate run hit the Next.js dev
    // server BEFORE it has on-demand-compiled the requested route. 15s
    // worked on hot caches but reliably blew up on cold compile under
    // single-worker orchestration runs (observed across multiple consumer
    // E2E runs; agents otherwise hand-bumped this on first failure).
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: `npx next dev -p ${port}`,
    port,
    // 120s instead of Playwright's 60s default. A cold `next dev` compile on
    // a realistic app (~17 routes, server components, Prisma client gen) can
    // take 80-100s on first run after a `.next/` invalidation. The default
    // 60s was hitting webServer timeout BEFORE any test ran — the gate then
    // exited with no parseable failure list. Harvested from
    // craftbrew-run-20260415-0146 ab085c99.
    timeout: 120_000,
    // Reuse the dev server only in local dev (no CI, no PW_FRESH_SERVER).
    // Orchestrated gate runs set PW_FRESH_SERVER=1 for zombie/stale-cache
    // invulnerability; CI sets CI=1. Local iteration (`pnpm test:e2e` in
    // VSCode while `pnpm dev` is already running) gets the fast path.
    reuseExistingServer: !process.env.CI && !freshServer,
    env: {
      ...process.env,
      // NextAuth v4 (legacy) — kept for back-compat with apps still on v4.
      NEXTAUTH_URL: `http://localhost:${port}`,
      // NextAuth v5 (Auth.js) — required for the dynamic test ports
      // (3xxx/4xxx) the e2e gate assigns per worktree. Without these,
      // every /api/auth/* call throws `UntrustedHost`, which causes
      // auth-dependent tests to hang waiting for a session that never
      // arrives — the gate then hits its outer timeout. Setting both
      // here is safe: playwright.config.ts is never loaded in production.
      AUTH_URL: `http://localhost:${port}`,
      AUTH_TRUST_HOST: "true",
    },
  },
  globalSetup: "./tests/e2e/global-setup.ts",
});
