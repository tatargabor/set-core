## Why

The current pipeline detects most implementation quality issues reactively — security rules only inject into the review retry prompt after a CRITICAL is found, not proactively during apply. The apply skill has zero quality guidance (no pattern awareness, no security references). Meanwhile, runtime correctness depends on E2E tests that lack a readiness probe (Playwright may timeout on slow server starts), smoke output that's validated only by exit code (not parsed results), and acceptance criteria that exist as checkboxes in tasks.md but never become actual runtime tests. These gaps mean quality depends on agent discipline rather than structural guarantees, and runtime bugs (auth bypass, broken routes, data inconsistency) slip through to post-merge.

## What Changes

- **Proactive rule injection during apply**: Inject relevant security/API rules into the apply agent's context based on what the task touches (auth task → auth-middleware rules, API task → api-design + security-patterns rules), so agents follow patterns from the start rather than discovering them in review retries
- **Content-aware review enhancement**: Make the LLM review diff-aware — if diff contains API routes, check IDOR patterns; if auth-related files changed, verify middleware existence and cold-visit test coverage; if new exports/routes added, cross-check against spec scope
- **E2E readiness probe**: Add explicit health check polling (dev server responding) before running Playwright E2E tests in the verify gate, preventing timeout failures from slow server starts
- **Smoke output validation**: Parse smoke/E2E output for structured results (pass/fail counts, test names) rather than relying solely on exit codes, storing parsed results in state for better diagnostics
- **Spec coverage annotation**: After decompose/planning, annotate the original spec text marking which sentences/requirements are covered by which change, making uncovered gaps visible before dispatch — a more granular complement to REQ-ID level traceability

## Capabilities

### New Capabilities
- `proactive-apply-rules`: Task-aware rule injection during apply — match task content against rule categories and inject relevant patterns into agent context
- `e2e-readiness-probe`: Health check polling before Playwright test execution in verify gate
- `smoke-result-parsing`: Structured parsing of smoke/E2E test output beyond exit codes
- `spec-coverage-annotation`: Post-planning spec text annotation showing per-sentence/requirement coverage by change

### Modified Capabilities
- `verify-review`: Content-aware review checks — diff analysis triggers specific verification patterns (IDOR, auth middleware, cold-visit tests)

## Impact

- **apply skill (SKILL.md)**: New instruction block for proactive rule injection — reads task description, matches against rule categories, injects relevant `.claude/rules/` content
- **verifier.py**: E2E readiness probe before Playwright execution, smoke output parsing, enhanced review prompt with content-aware checks
- **templates.py**: Review prompt gains content-aware check sections based on diff analysis
- **planner.py**: Spec coverage annotation in `validate_plan()` — generates coverage report after successful validation
- **No breaking changes**: All additions are backward-compatible — projects without `.claude/rules/` or without E2E degrade gracefully to current behavior
