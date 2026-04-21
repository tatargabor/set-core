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
## Requirements
### Requirement: E2E manifest history append on merge
When a change merges successfully, the merger SHALL append the change's current `e2e-manifest.json` contents to `e2e-manifest-history.jsonl` in the project root as a single JSON line annotated with the change name, plan version, session id, and merge timestamp.

#### Scenario: Merge with passing E2E manifest
- **WHEN** change "foundation-setup" merges and its worktree `e2e-manifest.json` lists 15 passing tests
- **THEN** a line `{ "change": "foundation-setup", "plan_version": <V>, "sentinel_session_id": <UUID>, "merged_at": "<iso>", "manifest": <full e2e-manifest.json object> }` SHALL be appended to `e2e-manifest-history.jsonl`
- **AND** the per-worktree `e2e-manifest.json` SHALL remain in place for the current test-run view (unchanged)

#### Scenario: Merge with missing manifest
- **WHEN** a change merges but its worktree never generated an `e2e-manifest.json`
- **THEN** no line SHALL be appended
- **AND** the merger SHALL log at DEBUG that the manifest was missing (not WARNING — absence is legitimate for changes that skip tests)

### Requirement: E2E manifest history carries lineage
Every `e2e-manifest-history.jsonl` line SHALL carry `spec_lineage_id`, and the Digest/E2E endpoint SHALL accept `?lineage=<id>` to filter the aggregation to a single lineage.

#### Scenario: v1 e2e manifest while v2 is running
- **WHEN** the client calls `GET /api/<project>/digest/e2e?lineage=docs/spec-v1.md`
- **THEN** only v1-tagged manifest history lines SHALL contribute to the returned blocks
- **AND** v2's live manifests SHALL NOT appear in the v1 response

### Requirement: Digest E2E aggregates across cycles
The Digest/E2E API SHALL combine the live per-change manifests with every entry in `e2e-manifest-history.jsonl`, so archived test blocks are visible alongside current ones.

#### Scenario: Archived + live blocks
- **WHEN** live plan has change "promotions-engine" with a current manifest of 28 tests
- **AND** `e2e-manifest-history.jsonl` has three archived entries (foundation-setup: 15 tests, auth-and-accounts: 12 tests, product-catalog: 20 tests)
- **THEN** the Digest/E2E response SHALL include all four blocks, each labelled with its originating change name
- **AND** the header SHALL read "75 tests across 4 change(s)" (or equivalent aggregated wording)
- **AND** archived blocks SHALL carry an `archived = true` flag so the UI can style them distinctly

#### Scenario: Legacy archive without history
- **WHEN** `e2e-manifest-history.jsonl` does not exist (legacy run)
- **THEN** the API SHALL fall back to current behaviour (live manifests only) without raising

