# Capability: e2e-env-drift-guard

## ADDED Requirements

### Requirement: Template `globalSetup` validates DATABASE_URL against schema provider before Prisma init

The scaffolded `tests/e2e/global-setup.ts` (in `modules/web/set_project_web/templates/nextjs/`) SHALL include a `validateDatabaseUrl()` function that runs before `npx prisma db push` and `npx prisma db seed`. The function SHALL:

- Parse `prisma/schema.prisma` to extract the declared `provider` from the first `datasource` block.
- Read `process.env.DATABASE_URL`.
- If `DATABASE_URL` is missing OR mismatches the provider's expected URL prefix (postgresql: `postgres(ql)?://`, mysql: `mysql://`, sqlite: `file:`, sqlserver: `sqlserver://`), attempt recovery from `set/orchestration/config.yaml`:
  - Read the file if it exists.
  - Extract `env_vars.DATABASE_URL` via line-match (no YAML parser dep in TypeScript).
  - If the recovered URL matches the schema provider, set `process.env.DATABASE_URL` to the recovered value and emit a `warn` log entry.
- If after recovery the URL is still missing, throw `Error("[global-setup] DATABASE_URL is not set. ...")`.
- If after recovery the URL still mismatches, throw `Error("[global-setup] DATABASE_URL/schema provider mismatch — ...")`.
- On success, emit a `log` entry: `DATABASE_URL provider OK (schema="<provider>")`.

The function SHALL be invoked once at the top of the default-exported `globalSetup` function, after the port-listener kill but before any Prisma command.

#### Scenario: Stale `.env` recovers from `config.yaml`

- **GIVEN** `prisma/schema.prisma` declares `provider = "postgresql"`
- **AND** `.env` contains `DATABASE_URL="file:./dev.db"`
- **AND** `set/orchestration/config.yaml` contains `env_vars: DATABASE_URL: "postgresql://localhost:5432/db"`
- **WHEN** `validateDatabaseUrl()` runs
- **THEN** `process.env.DATABASE_URL` SHALL be set to `postgresql://localhost:5432/db`
- **AND** a `warn` log SHALL be emitted: `DATABASE_URL in .env (...) does not match schema provider="postgresql". Auto-correcting from set/orchestration/config.yaml.`
- **AND** the function SHALL return without throwing

#### Scenario: `.env` matches schema, no recovery needed

- **GIVEN** `prisma/schema.prisma` declares `provider = "postgresql"`
- **AND** `.env` contains `DATABASE_URL="postgresql://localhost:5432/db"`
- **WHEN** `validateDatabaseUrl()` runs
- **THEN** the function SHALL emit `DATABASE_URL provider OK (schema="postgresql")`
- **AND** SHALL NOT read `set/orchestration/config.yaml`
- **AND** SHALL return without throwing

#### Scenario: Both `.env` and `config.yaml` are wrong → throw

- **GIVEN** `prisma/schema.prisma` declares `provider = "postgresql"`
- **AND** `.env` contains `DATABASE_URL="file:./dev.db"`
- **AND** `set/orchestration/config.yaml` contains `env_vars: DATABASE_URL: "mysql://..."` (also mismatched)
- **WHEN** `validateDatabaseUrl()` runs
- **THEN** the function SHALL throw an `Error` whose message starts with `[global-setup] DATABASE_URL/schema provider mismatch`

#### Scenario: `config.yaml` missing → throw with hint

- **GIVEN** `prisma/schema.prisma` declares `provider = "postgresql"`
- **AND** `.env` does NOT contain `DATABASE_URL`
- **AND** `set/orchestration/config.yaml` does not exist
- **WHEN** `validateDatabaseUrl()` runs
- **THEN** the function SHALL throw an `Error` whose message starts with `[global-setup] DATABASE_URL is not set.`
- **AND** the message SHALL hint at both `.env` and `set/orchestration/config.yaml env_vars` as remediation paths

### Requirement: Gate-runner self-heals on DATABASE_URL/schema provider mismatch

When the e2e gate (`execute_e2e_gate` in `modules/web/set_project_web/gates.py`) sees a non-zero exit with no parseable Playwright failure list, the gate SHALL apply a self-heal probe for env drift, ordered AFTER the existing dep-drift self-heal and gated by the same single-attempt flag.

The probe SHALL match the captured e2e output against any of these signatures:

- Contains `[global-setup] DATABASE_URL/schema provider mismatch` (template self-heal could not recover)
- Contains `Error validating datasource` AND contains `URL must start with the protocol`
- Contains `Command failed: npx prisma db seed` AND contains `PrismaClientInitializationError`

If any signature matches AND `set/orchestration/config.yaml` exists with a parseable `env_vars.DATABASE_URL` whose URL matches the schema provider's expected prefix, the gate SHALL:

1. Rewrite the worktree's `.env`, replacing the first `DATABASE_URL=` line with the recovered URL (or appending if absent), preserving all other lines and using atomic write (`tmpfile + os.replace`).
2. Invoke the e2e command once more in-gate with the corrected `process.env.DATABASE_URL`.
3. NOT increment `verify_retry_count`.
4. NOT restart the agent session.

If the rerun passes (exit 0, no flaky, no runtime errors), the gate SHALL return `pass` with `[self-heal: synced .env from config.yaml]\n` prepended to `GateResult.output`. If the rerun fails or also crashes without a parseable failure list, the gate SHALL return `fail` via the normal fail path.

The probe SHALL run AT MOST ONCE per gate invocation. If `_self_heal_missing_module` already attempted recovery in this invocation, this probe SHALL be skipped.

#### Scenario: Stale `.env` triggers self-heal and recovers

- **GIVEN** `tests/e2e/global-setup.ts` does NOT include the template `validateDatabaseUrl()` (consumer project lagging the template)
- **AND** `prisma/schema.prisma` declares `provider = "postgresql"`
- **AND** `.env` contains `DATABASE_URL="file:./dev.db"`
- **AND** `set/orchestration/config.yaml.env_vars.DATABASE_URL` is `postgresql://localhost:5432/db`
- **WHEN** Playwright runs and crashes with `Error validating datasource ... URL must start with the protocol postgresql:// or postgres://`
- **AND** the e2e gate captures the crash output and detects no parseable failure list
- **THEN** the gate SHALL detect the env-drift signature
- **AND** SHALL rewrite `.env` to set `DATABASE_URL="postgresql://localhost:5432/db"` (preserving other lines)
- **AND** SHALL invoke the e2e command once more
- **AND** if the rerun passes, SHALL return `GateResult("e2e", "pass", ...)` with `[self-heal: synced .env from config.yaml]` as the first line of `GateResult.output`
- **AND** SHALL emit INFO log `e2e_db_env_self_heal_resynced_and_rerun` with `change_name`, `resync_duration_ms`, `rerun_outcome`
- **AND** `verify_retry_count` SHALL remain unchanged

#### Scenario: `config.yaml` missing or unparseable → no self-heal

- **GIVEN** the e2e gate captures a `Error validating datasource` crash
- **AND** `set/orchestration/config.yaml` does not exist OR raises on `yaml.safe_load`
- **WHEN** the gate evaluates the env-drift self-heal probe
- **THEN** the probe SHALL return `None` (no recovery attempted)
- **AND** SHALL log a WARNING with the parse failure reason if applicable
- **AND** the gate SHALL proceed to the normal fail path with the original output

#### Scenario: `config.yaml.env_vars.DATABASE_URL` also mismatches → no self-heal

- **GIVEN** `prisma/schema.prisma` declares `provider = "postgresql"`
- **AND** `.env` has `DATABASE_URL="file:./dev.db"`
- **AND** `config.yaml` has `env_vars.DATABASE_URL: "mysql://..."` (mismatched)
- **WHEN** the env-drift self-heal probe evaluates
- **THEN** the probe SHALL detect that the recovery URL also mismatches the schema provider
- **AND** SHALL return `None` (no rewrite, no rerun)
- **AND** the gate SHALL fail with the original output and an actionable retry context

#### Scenario: Self-heal does not fire when dep-drift self-heal already attempted

- **GIVEN** the e2e crash output contains BOTH `Cannot find module 'X'` (MODULE_NOT_FOUND) AND `Error validating datasource`
- **WHEN** `_self_heal_missing_module` matches and runs install + rerun
- **THEN** the env-drift self-heal probe SHALL be skipped this invocation regardless of rerun outcome
- **AND** at most one `[self-heal: ...]` marker SHALL appear in `GateResult.output`

#### Scenario: Self-heal succeeds at most once per gate invocation

- **GIVEN** the env-drift self-heal probe runs and the rerun ALSO crashes with a `provider mismatch` (e.g. `config.yaml` is also stale)
- **WHEN** the probe evaluates the rerun's output
- **THEN** the probe SHALL NOT recurse — it SHALL return the rerun's failure verdict
- **AND** SHALL NOT attempt a second resync within the same gate invocation

### Requirement: Forensic logging of self-heal events

The gate-runner SHALL emit two structured INFO logs on env-drift self-heal:

- On detection: `e2e_db_env_drift_detected` with fields `change=<name>`, `wt=<wt_path>`, `recovered_url_provider=<provider>`.
- On post-rerun: `e2e_db_env_self_heal_resynced_and_rerun` with fields `change=<name>`, `resync_duration_ms=<int>`, `rerun_outcome=pass|fail_parseable|fail_unparseable`.

These events SHALL appear in `set/orchestration/python.log` and SHALL be surfaced by `set-run-logs` and the web dashboard's gate-output panel alongside the existing `e2e_self_heal_*` events.

#### Scenario: Self-heal pass is distinguishable from real pass in forensics

- **GIVEN** an e2e gate invocation where env-drift self-heal recovered
- **WHEN** an operator runs `set-run-logs <run-id> --gate e2e --change <name>`
- **THEN** the output SHALL include the `e2e_db_env_drift_detected` and `e2e_db_env_self_heal_resynced_and_rerun` events with their full field set
- **AND** the gate verdict line SHALL show the `[self-heal: synced .env from config.yaml]` marker
