# Spec: worktree-e2e-lifecycle

## IN SCOPE
- Deterministic port allocation per worktree (bootstrap time)
- PORT + PW_PORT injection into worktree .env
- Verify gate e2e port isolation (execute_e2e_gate)
- Pre-gate hook: Prisma db push + seed (SQLite)
- Post-gate hook: placeholder for cleanup
- ABC methods on ProjectType for extensibility

## OUT OF SCOPE
- Postgres per-worktree DB creation (future — placeholder only)
- Container-based DB isolation
- Integration gate port changes (already done)
- Phase-end e2e port changes (already done)
- Agent-internal port management (agent reads .env)

## ADDED Requirements

### Requirement: Worktree port allocation

The system SHALL assign a deterministic unique port to each worktree during bootstrap, based on the change name.

#### Scenario: Port injected at bootstrap
- WHEN `bootstrap_worktree()` runs for change `contact-form`
- THEN the worktree `.env` file SHALL contain `PORT=<N>` and `PW_PORT=<N>` where N is derived from `profile.worktree_port("contact-form")`
- AND N SHALL be in range 3100-4099

#### Scenario: Port is idempotent
- WHEN `bootstrap_worktree()` runs twice for the same worktree
- THEN PORT and PW_PORT values SHALL NOT be duplicated in `.env`

#### Scenario: No port when profile returns 0
- WHEN the profile `worktree_port()` returns 0
- THEN no PORT or PW_PORT SHALL be written to `.env`

### Requirement: Verify gate port isolation

The verify gate e2e runner SHALL use the worktree's assigned port via `profile.e2e_gate_env()`.

#### Scenario: Verify e2e uses isolated port
- WHEN `execute_e2e_gate()` runs for a worktree with `PORT=3247` in `.env`
- THEN the Playwright command SHALL receive `PW_PORT=3247` in its environment
- AND the dev server SHALL start on port 3247

### Requirement: Pre-gate DB setup

The system SHALL run profile-defined setup before e2e tests execute.

#### Scenario: Prisma SQLite push before e2e
- WHEN `prisma/schema.prisma` exists in the worktree
- AND DATABASE_URL uses SQLite (`file:` prefix)
- THEN `npx prisma db push --skip-generate` SHALL run before e2e tests

#### Scenario: Prisma seed before e2e
- WHEN `prisma/seed.ts` or `prisma/seed.js` exists in the worktree
- THEN `npx prisma db seed` SHALL run after db push and before e2e tests

#### Scenario: No Prisma schema
- WHEN `prisma/schema.prisma` does NOT exist
- THEN pre-gate SHALL be a no-op

### Requirement: Post-gate cleanup hook

The system SHALL call `profile.e2e_post_gate()` after e2e tests complete, regardless of pass/fail.

#### Scenario: Post-gate called on success
- WHEN e2e tests pass
- THEN `e2e_post_gate()` SHALL be called

#### Scenario: Post-gate called on failure
- WHEN e2e tests fail
- THEN `e2e_post_gate()` SHALL still be called

### Requirement: ABC extensibility

`ProjectType` ABC SHALL define `worktree_port()`, `e2e_pre_gate()`, and `e2e_post_gate()` with no-op defaults.

#### Scenario: Default profile has no port
- WHEN a non-web project type does not override `worktree_port()`
- THEN it SHALL return 0
- AND no port injection SHALL occur
