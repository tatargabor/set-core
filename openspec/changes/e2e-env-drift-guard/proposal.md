# Change: e2e-env-drift-guard

## Why

When a change modifies `prisma/schema.prisma` to switch the database `provider` (commonly SQLite → PostgreSQL during foundation work), the worktree's `.env` carries the previous `DATABASE_URL` from the orchestrator's bootstrap. Playwright's `globalSetup` then hits `npx prisma db push` which dies inside Prisma with a non-Playwright-parseable error. The e2e gate captures `exit_code=1` with no `failedTests[]` block and reports "fail" — burning one `verify_retry_count` slot and dispatching the agent to fix something the agent already fixed (the schema is correct; only `.env` is stale).

Empirical evidence from a recent project run with five changes that hit the foundation→feature lifecycle:

- The first foundation change lost retry slot 1/4 to this pattern when its first e2e run ran against the bootstrap `.env` carrying the previous provider's URL.
- A downstream feature change lost retry slots 1/4 and 2/4 plus two stall-cooldowns before the agent diagnosed the orchestrator-side env_vars sync gap and worked around it with an empty cache-buster commit.
- A second foundation change lost retry slot 1/4 to the same `[global-setup] DATABASE_URL/schema provider mismatch` signature.
- A later admin change introduced a separate build-time crash class that the existing `_self_heal_missing_module` does not cover but follows the same retry-budget waste pattern.

During that run the agent itself committed a worktree-resident `validateDatabaseUrl()` pre-flight in `tests/e2e/global-setup.ts` that reads `set/orchestration/config.yaml` and overrides stale `process.env.DATABASE_URL`. Downstream changes that branched from main after the agent's fix landed inherited the recovery and stopped burning the first retry slot. **But that fix is in the runtime worktree only** — the set-core template (`modules/web/set_project_web/templates/nextjs/tests/e2e/global-setup.ts`) does not have it, so the next freshly scaffolded project starts the cycle over.

The MODULE_NOT_FOUND self-heal already specified by `e2e-dep-drift-guard` proves the pattern works: detect a known crash signature, recover in-gate without consuming a retry slot, and prepend a `[self-heal: ...]` marker to `GateResult.output` so forensics can distinguish healed runs from real passes. This change extends that pattern to env-drift.

## What Changes

Two layers of defense, mirroring the dep-drift change:

**Layer 2a — Pre-flight in template (`modules/web/set_project_web/templates/nextjs/tests/e2e/global-setup.ts`):**

- Forward-port the `validateDatabaseUrl()` function from the agent's harvest commit (worktree-resident fix harvested from a recent project run) into the scaffolded template. New consumer projects ship with the pre-flight from day one.
- Cheap on the common case: schema parse + regex match + URL provider check. Reads `set/orchestration/config.yaml` only on mismatch (recovery path).

**Layer 2b — Gate-runner self-heal (`modules/web/set_project_web/gates.py`):**

- Add `_extract_db_env_drift(e2e_output)` that returns `True` on any of these signatures (handles consumer projects that have not yet picked up the template self-heal, or projects where the template self-heal failed to recover for any reason):
  - `[global-setup] DATABASE_URL/schema provider mismatch`
  - `Error validating datasource` + `URL must start with the protocol`
  - `Command failed: npx prisma db seed` + `PrismaClientInitializationError`
- Add `_resolve_database_url_from_config(project_root)` that parses `set/orchestration/config.yaml` (`yaml.safe_load`, already a dep) and returns `env_vars.DATABASE_URL` or `None`.
- Add `_resync_dotenv_database_url(wt_path, new_url)` that rewrites or appends the `DATABASE_URL=` line in the worktree's `.env`, preserving all other lines.
- Add `_self_heal_db_env_drift(...)` that runs detection + resync + one in-gate rerun with the corrected `process.env.DATABASE_URL`, mirroring `_self_heal_missing_module`'s contract: returns `(healed: bool, recovered_url: str, rerun_result)` or `None` if the signature didn't match.
- Wire the new self-heal into `execute_e2e_gate` on the unparseable-fail path, **after** `_self_heal_missing_module`. Both are gated by the same `self_heal_attempted` flag — at most one self-heal per gate invocation.
- New INFO logs: `e2e_db_env_drift_detected`, `e2e_db_env_self_heal_resynced_and_rerun`. New `GateResult.output` marker: `[self-heal: synced .env from config.yaml]`.

**No core (Layer 1) changes.** The existing `verify_retry_count` invariant from `e2e-dep-drift-guard` carries forward — self-heal does not increment.

**No consumer redeploy required.** The running sentinel loads the profile from the same venv; next orchestration cycle picks up the new self-heal automatically. New scaffolds get the template fix on the next `set-project init`.

## Capabilities

### New Capabilities

- `e2e-env-drift-guard`: Pre-flight DB env validation in the e2e template's `globalSetup`, plus gate-runner self-heal for `DATABASE_URL` / schema-provider mismatch caused by a stale worktree `.env` that no longer matches the schema's declared provider.

### Modified Capabilities

<!-- none — e2e-dep-drift-guard covers npm-package drift, this is the parallel env-drift concern -->

## Impact

- **Code**: `modules/web/set_project_web/gates.py` (new `_extract_db_env_drift`, `_resolve_database_url_from_config`, `_resync_dotenv_database_url`, `_self_heal_db_env_drift`; integration into `execute_e2e_gate`); `modules/web/set_project_web/templates/nextjs/tests/e2e/global-setup.ts` (forward-port `validateDatabaseUrl()` + 1 call site).
- **Tests**: unit tests for each new helper (drift signature regex, config.yaml parse with missing/malformed keys, .env resync with existing/missing/multiple `DATABASE_URL` lines), plus an integration test that fabricates a worktree with stale `.env` and a mismatched schema and asserts the gate returns `pass` with the self-heal marker without incrementing `verify_retry_count`.
- **Retry budget**: self-heal does NOT consume `verify_retry_count`, keeping the 4-attempt budget for real failures (mirrors `e2e-dep-drift-guard`).
- **Logs**: new INFO events `e2e_db_env_drift_detected`, `e2e_db_env_self_heal_resynced_and_rerun`. Forensics + `set-run-logs` will surface these.
- **Behavior invariance**: when `.env` matches the schema provider, no extra work runs — zero overhead for the common case (one regex match against e2e_output on the unparseable-fail path).
- **Dependencies**: `pyyaml` is already a transitive dep through `set-project-web` (`pyyaml>=5.0` in `pyproject.toml`). No new packages.
- **Forward port**: the agent's worktree commit (harvested from a recent project run) becomes the basis for the template change — proven against real failures.
