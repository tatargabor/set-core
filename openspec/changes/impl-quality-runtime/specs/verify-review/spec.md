## MODIFIED Requirements

### Requirement: LLM code review
- Generate diff of change branch vs merge-base (origin/HEAD or main)
- Truncate diff to 50000 chars
- Build review prompt via render_review_prompt() template
- Run content-aware diff classification: scan diff for auth, API, database, and frontend patterns; append category-specific review instructions to the prompt
- Inject security rules into the FIRST review attempt (not just retry), loaded via profile or `.claude/rules/` fallback
- Run via run_claude with configurable model
- On failure: escalate from configured model to opus, then skip
- Return `ReviewResult` with has_critical flag
- Detect CRITICAL via regex: `[CRITICAL]`, `severity.*critical`, `CRITICAL:`

#### Scenario: Diff with auth-related changes triggers auth checks
- **WHEN** the review diff contains files matching auth patterns (e.g., `*auth*`, `*session*`, `*middleware*`, `*login*`)
- **THEN** the review prompt SHALL include auth-specific instructions: "Verify auth middleware exists and covers all protected routes. Check for cold-visit protection."

#### Scenario: Diff with API route changes triggers IDOR checks
- **WHEN** the review diff contains API route patterns (e.g., `router.`, `app.get(`, `app.post(`, handler exports)
- **THEN** the review prompt SHALL include API-specific instructions: "Verify every mutation by client-provided ID includes ownership check (IDOR prevention)."

#### Scenario: Diff with database changes triggers data scoping checks
- **WHEN** the review diff contains database patterns (e.g., `prisma.`, `db.`, `query(`, `.findMany`, `.create(`)
- **THEN** the review prompt SHALL include database-specific instructions: "Verify queries are scoped by owning entity. Check for missing where-clause conditions."

#### Scenario: Security rules injected on first review attempt
- **WHEN** a code review runs for the first time (not a retry)
- **THEN** security rules from `.claude/rules/` SHALL be included in the review prompt
- **AND** rules SHALL NOT be deferred to retry-only injection
