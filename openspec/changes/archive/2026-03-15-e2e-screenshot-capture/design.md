## Context

The orchestration pipeline runs Playwright E2E tests at two points: per-change verify gate and phase-end integration test. Both collect `test-results/` contents into `wt/orchestration/e2e-screenshots/`. However, the agent-generated `playwright.config.ts` omits the `screenshot` setting, so Playwright defaults to `'off'` and only writes `error-context.md` text files (accessibility snapshots). The collector counts 0 PNG files.

## Goals / Non-Goals

**Goals:**
- E2E tests produce PNG screenshots automatically via Playwright config
- Existing collector pipeline picks them up without modification

**Non-Goals:**
- Changing the collector or verifier logic (it already works for PNGs)
- Adding a separate screenshot capture step or script
- Visual regression testing or AI-based screenshot review

## Decisions

**1. `screenshot: 'on'` (not `'only-on-failure'`)**
- Rationale: Users want to see what the build looks like after merge — including successful pages, not just failures. `'only-on-failure'` would only capture broken states, which is insufficient for visual verification.
- Trade-off: Slightly more disk usage per test run (~50-200KB per screenshot). Acceptable — E2E suites typically have 10-30 tests.

**2. Instruction in decompose template (not scaffold config file)**
- Rationale: The `playwright.config.ts` is agent-generated per project — there is no scaffold template for it. The decompose planning prompt already instructs agents on config requirements (PW_PORT, webServer). Adding `screenshot: 'on'` to the same instruction is the minimal, consistent approach.
- Alternative: Add a `playwright.config.ts` to the scaffold. Rejected — projects may use different frameworks, ports, test dirs. The prompt-based approach is more flexible.

## Risks / Trade-offs

- [Risk] Agent ignores the prompt instruction → Mitigation: The instruction includes the reason ("without this, Playwright writes error-context.md text files instead of PNG screenshots") to make compliance more likely. If agents still skip it, a future scaffold template could enforce it.
- [Risk] `screenshot: 'on'` increases test duration → Mitigation: Negligible — Playwright screenshot capture adds ~50ms per test. For a 30-test suite, that's 1.5s total.
