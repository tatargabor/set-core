## Context

The orchestration pipeline runs: plan → dispatch → apply → verify → merge. Quality enforcement happens primarily at verify time (build, test, E2E, review, spec coverage). The apply skill has no quality guidance — agents implement tasks based on spec/design context but without reference to security patterns, API design rules, or auth middleware requirements. Security rules exist in `.claude/rules/` but are only injected into review **retry** prompts after a CRITICAL is already found — the first review attempt runs without them.

Runtime validation relies on: unit tests (Jest/Vitest via `test_command`), Playwright E2E (via `e2e_command` with random port isolation), and post-merge smoke tests. E2E currently starts Playwright immediately without verifying the dev server is ready — slow starts cause timeout failures. Smoke/E2E results are validated only by exit code, losing structured pass/fail data.

## Goals / Non-Goals

**Goals:**
- Shift quality left: inject relevant patterns during apply, not just during review retries
- Make review content-aware: check for specific patterns based on what the diff actually contains
- Improve E2E reliability: ensure dev server is responding before running Playwright
- Better diagnostics: parse structured test results from smoke/E2E output
- Catch spec coverage gaps at plan time via sentence-level annotation

**Non-Goals:**
- Automated test generation (the acceptance skeleton feature in spec-implementation-fidelity covers this)
- New gate steps in verifier.py (no new steps, just improve existing ones)
- Performance/load testing gates (future work)
- Visual regression testing (future work)
- Accessibility scanning gates (future work)

## Decisions

### Decision 1: Rule injection via dispatcher enrichment, not apply skill modification

Inject relevant rules into the agent's `proposal.md` enrichment (the scope block sent to the agent at dispatch time) based on the change's task content, rather than modifying the apply skill itself. Rationale: the apply skill is generic and schema-independent. The dispatcher already enriches proposal content with design context — adding rule injection follows the same pattern.

Implementation: in `dispatcher.py`'s scope enrichment block (around line 929 where `ctx.design_context` is built), scan the change's scope string for keywords (auth, API, route, middleware, session, database, form, input) and append matching rule file contents from the worktree's `.claude/rules/`.

Alternative considered: Modifying SKILL.md to instruct agents to read `.claude/rules/` — rejected because the apply skill should stay generic, and agents would need to decide which rules are relevant (unreliable).

### Decision 2: Content-aware review via diff classifier in templates.py

Add a `classify_diff_content()` function that scans the diff for patterns and returns a set of categories: `{"auth", "api", "database", "frontend"}`. Then `render_review_prompt()` appends category-specific check instructions.

Categories and triggers:
- `auth`: diff touches files matching `*auth*`, `*session*`, `*middleware*`, `*login*`, `*cookie*`
- `api`: diff contains `router.`, `app.get(`, `app.post(`, `export.*function.*handler`, API route patterns
- `database`: diff contains `prisma.`, `db.`, `query(`, `.findMany`, `.create(`, SQL patterns
- `frontend`: diff touches `*.tsx`, `*.jsx`, `*.vue`, `*.svelte` files

Category-specific instructions:
- `auth` → "Verify auth middleware exists and covers all protected routes. Check for cold-visit protection (unauthenticated access to /admin should redirect to /login)."
- `api` → "Verify every mutation by client-provided ID includes ownership check (IDOR prevention). Check pagination on list endpoints."
- `database` → "Verify queries are scoped by owning entity. Check for missing where-clause conditions on multi-tenant data."

Alternative considered: Loading full security rule files into every review — rejected because it would bloat the review prompt for non-relevant changes. Content-aware injection is more targeted.

### Decision 3: E2E readiness probe before Playwright in verify gate

Add a health check call before running the E2E command in `handle_change_done()` Step 3. The probe:
1. Uses the locally assigned `e2e_port` variable (already computed as `E2E_PORT_BASE + random.randint()`)
2. Polls `http://localhost:{e2e_port}` with 1-second intervals
3. Accepts any 2xx/3xx response as "ready"
4. Times out after 30 seconds (configurable via `E2E_HEALTH_TIMEOUT`)
5. If timeout: skip E2E with a warning (don't fail the gate — server startup issues are infrastructure, not code quality)

The existing `health_check()` function already does this for smoke tests — reuse it for E2E.

Note on sequencing: Playwright projects typically start the dev server via `webServer` config in playwright.config.ts. The E2E command (`e2e_command`) wraps the full Playwright invocation including server startup. The health probe runs BEFORE the E2E command — if the dev server isn't started externally, the probe will timeout and E2E will be skipped with "skip-unhealthy". This is the intended behavior for projects where Playwright manages the server lifecycle: the probe catches cases where an externally-started server isn't ready. For projects using Playwright's `webServer`, the probe is a no-op (skips after timeout, Playwright starts its own server).

Alternative considered: Letting Playwright handle its own retries via `webServer` config — rejected because not all projects configure `webServer` in playwright.config.ts, and the orchestrator should ensure readiness regardless of project config.

### Decision 4: Smoke/E2E output parsing as optional enhancement

Add a `parse_test_output()` function that extracts structured results from test runner output using regex patterns for common frameworks:
- Jest/Vitest: `Tests:\s+(\d+) passed, (\d+) failed`
- Playwright: `(\d+) passed.*(\d+) failed`
- Generic: exit code + output size

Store parsed results in change state as `test_parsed: {passed: N, failed: N, total: N}` alongside existing raw output. This is informational — does not change blocking/passing behavior.

Alternative considered: Requiring structured JSON output from test runners — rejected because it would require project-specific test configuration changes.

### Decision 5: Spec coverage annotation as a post-planning report

After `validate_plan()` succeeds, generate a coverage annotation report that reads the original spec/digest text and marks each requirement/sentence as:
- `[COVERED by change-name]` — requirement ID appears in a change's `requirements[]` or `also_affects_reqs[]`
- `[DEFERRED: reason]` — listed in `deferred_requirements[]`
- `[UNCOVERED]` — not assigned to any change (should not exist if validate_plan passes with spec-implementation-fidelity)

This runs in `planner.py` after `validate_plan()` and writes the annotated report to `wt/orchestration/spec-coverage-report.md`. It's informational — visible to the user/sentinel for review but not blocking.

The report provides the granular "every sentence accounted for" visibility the user requested — complementing the REQ-ID level traceability from spec-implementation-fidelity with human-readable text-level coverage.

Alternative considered: Inline annotation directly in spec files — rejected because it would modify the source specs, creating merge conflicts.

### Decision 6: Rule injection uses keyword matching, not LLM classification

The dispatcher rule injection (Decision 1) uses simple keyword matching on task descriptions, not LLM calls. Rationale: dispatch runs for every change — adding an LLM call would add latency and cost. Keyword matching is fast (~1ms), deterministic, and sufficient because task descriptions are structured text written by the ff-change skill.

Keyword→rule mapping is configured in the profile system, not hardcoded:
```python
# Default mapping (overridable by profile)
RULE_KEYWORDS = {
    "auth": ["auth", "login", "session", "middleware", "cookie", "password", "token"],
    "api": ["api", "route", "endpoint", "handler", "REST", "mutation"],
    "database": ["database", "query", "migration", "schema", "model", "prisma", "drizzle"],
}
```

Alternative considered: LLM-based task classification — rejected due to cost and latency at dispatch time.

## Risks / Trade-offs

- [Risk] Keyword matching for rule injection may miss relevant rules or inject irrelevant ones → Mitigation: use broad keyword sets; irrelevant rules are just extra context (low harm); profile system allows per-project tuning
- [Risk] Content-aware review may increase review prompt size beyond model context → Mitigation: category-specific instructions are short (2-3 sentences each); only inject matching categories; cap total injection at 2000 chars
- [Risk] E2E readiness probe adds 0-30 seconds to verify gate → Mitigation: only waits if server isn't already responding; instant pass if healthy; configurable timeout
- [Risk] Test output parsing regex may not match all frameworks → Mitigation: parser is best-effort; falls back to exit-code-only; add patterns incrementally
- [Risk] Spec coverage report may be stale if plan changes after generation → Mitigation: regenerate on replan; report is informational, not blocking
- [Trade-off] Rule injection at dispatch time means agents get rules even if they don't need them → Acceptable: extra context is low-cost; better to over-inform than under-inform
- [Trade-off] Content-aware review adds complexity to templates.py → Acceptable: classifier is a pure function with no side effects, easy to test
