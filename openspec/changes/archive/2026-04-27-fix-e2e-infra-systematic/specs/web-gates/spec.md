## ADDED Requirements

### Requirement: i18n baseline prevents cascading e2e failures

The nextjs web template SHALL ship with a complete baseline `messages/{hu,en}.json` containing keys used by scaffold components (`home.*`, `nav.*`, `footer.*`, `common.*`). A pre-e2e `i18n_check` gate SHALL scan `src/` for `useTranslations('<ns>')` calls and `t('<ns>.<key>')` usages and fail fast with a listing of any missing keys in the corresponding locale files.

#### Scenario: Homepage uses `useTranslations('home')` but `home.heroTitle` missing from `messages/hu.json`
- **WHEN** `i18n_check` runs during the verify pipeline
- **THEN** the gate SHALL fail with exit code non-zero
- **AND** the output SHALL include the line `Missing key: home.heroTitle in messages/hu.json`
- **AND** the failing gate SHALL block the pipeline BEFORE the full e2e gate runs (saving cascading test-wide failures)

#### Scenario: Template ships with baseline keys mirrored across locales
- **WHEN** `set-project init --project-type web --template nextjs` scaffolds a new project
- **THEN** the generated `messages/hu.json` and `messages/en.json` SHALL both contain the keys `home.heroTitle`, `home.heroSubtitle`, `home.heroCta`, `nav.home`, `nav.account`, `footer.copyright`, `common.loading`, `common.error`, `common.retry` (the baseline set)

#### Scenario: All baseline i18n keys present
- **WHEN** `i18n_check` runs against a project where all `useTranslations(ns)` namespaces are fully populated in both locale files
- **THEN** the gate SHALL pass with exit code 0 in under 2 seconds

### Requirement: Playwright config respects gate timeout

The `playwright.config.ts` shipped in the nextjs template SHALL derive `globalTimeout` from `process.env.PW_TIMEOUT` (seconds), `webServer.port` from `process.env.PW_PORT`, and SHALL disable `reuseExistingServer` when `PW_FRESH_SERVER=1` is set. The web gate runner SHALL construct these env vars from the gate directive and per-worktree port allocation.

#### Scenario: Gate `e2e_timeout=1800` propagates to Playwright
- **GIVEN** the orchestration directive `e2e_timeout: 1800`
- **WHEN** the e2e gate spawns Playwright
- **THEN** the subprocess env SHALL contain `PW_TIMEOUT=1800`
- **AND** `playwright.config.ts` SHALL set `globalTimeout: 1800000` (1800 × 1000 ms)

#### Scenario: Worktree port allocation flows to webServer
- **GIVEN** a change with `extras.assigned_e2e_port=3142`
- **WHEN** the e2e gate spawns Playwright
- **THEN** the subprocess env SHALL contain `PW_PORT=3142`
- **AND** `playwright.config.ts` `webServer.port` SHALL use 3142

#### Scenario: Fresh-server mode
- **GIVEN** `PW_FRESH_SERVER=1` in the gate env
- **WHEN** Playwright starts its webServer
- **THEN** `reuseExistingServer` SHALL be false (always spawn a new server)

### Requirement: Playwright global-setup invalidates stale build

The `tests/e2e/global-setup.ts` shipped in the nextjs template SHALL, before starting `webServer`:
1. Kill any process bound to the assigned `PW_PORT` (cross-platform: `lsof -ti :$PORT | xargs kill -9` on unix; skip on unsupported platforms with a log).
2. Read `.next/BUILD_COMMIT` and compare to the current HEAD SHA. If missing, mismatched, or legacy `.next/BUILD_ID` is present without `BUILD_COMMIT`, remove `.next/` and log the reason.
3. After successful build completion, write the current HEAD SHA to `.next/BUILD_COMMIT`.

#### Scenario: Stale .next from previous worktree
- **GIVEN** `.next/BUILD_COMMIT` contains `abc123` and the current HEAD is `def456`
- **WHEN** `global-setup.ts` runs
- **THEN** `.next/` SHALL be removed
- **AND** a log line SHALL read: `Stale .next cache: BUILD_COMMIT=abc123, HEAD=def456 — invalidating.`

#### Scenario: Zombie next start on PW_PORT
- **GIVEN** a process is bound to `PW_PORT=3142` from a previous session
- **WHEN** `global-setup.ts` runs
- **THEN** the process bound to 3142 SHALL be killed before webServer starts
- **AND** webServer SHALL successfully start on 3142

#### Scenario: Fresh build writes BUILD_COMMIT marker
- **GIVEN** `global-setup.ts` has invalidated `.next/` and rebuilt
- **WHEN** the build completes successfully
- **THEN** `.next/BUILD_COMMIT` SHALL exist and contain the current HEAD SHA

### Requirement: Prisma seed skips when schema unchanged

The nextjs template seed script SHALL compute SHA-256 of `prisma/schema.prisma`, compare it to `.set/seed-schema-hash`, and skip `prisma db push --force-reset` if unchanged. On successful seed, the new hash is written.

#### Scenario: Schema unchanged across gate runs
- **GIVEN** a prior seed wrote `.set/seed-schema-hash` matching the current `prisma/schema.prisma` hash
- **WHEN** the seed script runs
- **THEN** `prisma db push --force-reset` SHALL NOT execute
- **AND** the seed SHALL complete in under 2 seconds
- **AND** a log line SHALL indicate: `Schema unchanged — skipping db reset.`

#### Scenario: Schema changed
- **GIVEN** `prisma/schema.prisma` was modified since the last seed
- **WHEN** the seed script runs
- **THEN** `prisma db push --force-reset` SHALL execute
- **AND** on success, `.set/seed-schema-hash` SHALL be updated to the new hash

#### Scenario: Forced reseed via env var
- **GIVEN** env `PRISMA_FORCE_RESEED=1`
- **WHEN** the seed script runs
- **THEN** the hash check SHALL be bypassed and `prisma db push --force-reset` SHALL run

### Requirement: Worktree port allocation is deterministic

The orchestrator SHALL assign each change a stable E2E port computed from `hash(change.name)` modulo a configurable port range starting at `e2e_port_base`. The assignment is persisted in `change.extras.assigned_e2e_port` and flows to `PW_PORT` in the e2e gate env.

#### Scenario: Same change name produces same port across runs
- **GIVEN** a change name `X` with `e2e_port_base=3100` and `port_range=100`
- **WHEN** the orchestrator assigns a port for this change
- **THEN** the same port SHALL be assigned on every orchestrator restart (deterministic hash)
- **AND** the assigned port SHALL fall in `[3100, 3200)`

#### Scenario: Different changes get non-colliding ports in typical runs
- **GIVEN** two distinct change names
- **WHEN** ports are assigned with `port_range=100`
- **THEN** for a representative set of 20 typical change names in a run, the assigned ports SHALL be pairwise non-colliding (test with a known-good name seed)

### Requirement: Conventions catch anti-patterns

`templates/core/rules/web-conventions.md` and any scaffold-specific conventions SHALL include guidance preventing repeated reviewer-flagged patterns:

- Ban on `navigator.sendBeacon` for cart/order mutations (with fetch+error-handling replacement pattern).
- Upsert unique-key discriminator rule for user-scoped records (e.g., including a distinguishing field in the unique constraint).
- testid naming convention: `data-testid="<feature>-<element>"`, same value in both the component and the e2e spec.
- storageState pattern for admin authentication (referencing a template helper `lib/auth/storage-state.ts`).
- REQ-id commenting convention on spec scenarios (e.g., `// @REQ-A-001`) for future scope-filtered e2e.

#### Scenario: Convention rule present in deployed rules
- **GIVEN** a freshly-scaffolded project
- **WHEN** the user opens `.claude/rules/web-conventions.md`
- **THEN** the file SHALL contain a "Do NOT use `navigator.sendBeacon` for state mutations" section with the fetch+error replacement snippet

#### Scenario: storageState helper is deployed
- **WHEN** `set-project init --project-type web --template nextjs` runs
- **THEN** the scaffold SHALL include `lib/auth/storage-state.ts` (a template file)
- **AND** `web-conventions.md` SHALL reference it for admin e2e tests
