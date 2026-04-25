# Tasks: e2e-env-drift-guard

## Section 1 — Forward-port the template `validateDatabaseUrl()`

- [ ] 1.1 Open `modules/web/set_project_web/templates/nextjs/tests/e2e/global-setup.ts`.
- [ ] 1.2 Add the `validateDatabaseUrl()` function as harvested from a recent project run's worktree-resident agent fix (a `tests/e2e/global-setup.ts` patch the agent committed mid-run). Function reads schema provider, validates `process.env.DATABASE_URL`, recovers from `set/orchestration/config.yaml.env_vars.DATABASE_URL` on mismatch, throws actionable error if both fail.
- [ ] 1.3 Add the call site: `validateDatabaseUrl();` at the top of the default-exported `globalSetup` function, AFTER the port-listener kill block but BEFORE the schema-hash cache block (so a mismatch is caught before any Prisma command runs).
- [ ] 1.4 Add a brief JSDoc above the function explaining the three failure modes it catches and the recovery contract (mirrors the agent's harvest comment).
- [ ] 1.5 Run `npx tsc --noEmit` against a sample worktree (or the e2e scaffold's tsconfig) to confirm no type errors.

## Section 2 — Implement `_extract_db_env_drift` (gates.py)

- [ ] 2.1 Open `modules/web/set_project_web/gates.py`.
- [ ] 2.2 Define module-level constants near the existing dep-drift constants (line ~83):
  ```python
  _DB_ENV_DRIFT_SIGNATURES = (
      "[global-setup] DATABASE_URL/schema provider mismatch",
      ("Error validating datasource", "URL must start with the protocol"),
      ("Command failed: npx prisma db seed", "PrismaClientInitializationError"),
  )
  ```
- [ ] 2.3 Implement `_extract_db_env_drift(e2e_output: str) -> bool` that returns True if any single-string signature is in `e2e_output` OR any 2-tuple has both substrings present.
- [ ] 2.4 Add an inline doctest with a positive case (a representative `[global-setup] DATABASE_URL/schema provider mismatch` output) and a negative case (a normal Playwright failure list).

## Section 3 — Implement `_resolve_database_url_from_config` (gates.py)

- [ ] 3.1 Implement `_resolve_database_url_from_config(project_root: str) -> str | None`:
  - Build path `os.path.join(project_root, "set", "orchestration", "config.yaml")`.
  - If file missing, return `None`.
  - `import yaml`; `yaml.safe_load(open(path))` inside try/except. On parse failure, log WARNING and return `None`.
  - Navigate to `data.get("env_vars", {}).get("DATABASE_URL")`. Return value or `None`.
- [ ] 3.2 Add a docstring explaining the failure modes (missing file, malformed YAML, missing key) and the contract that callers receive `None` for any unrecoverable state.

## Section 4 — Implement `_resync_dotenv_database_url` (gates.py)

- [ ] 4.1 Implement `_resync_dotenv_database_url(wt_path: str, new_url: str) -> bool`:
  - Build path `os.path.join(wt_path, ".env")`.
  - If file missing, write a fresh `.env` with `DATABASE_URL="<new_url>"\n` and return `True`.
  - Otherwise read line by line, replace the first line that starts with `DATABASE_URL=` (preserving line ending), or append at end if not present.
  - Quote the value: `f'DATABASE_URL="{new_url}"'` to match template style.
  - Atomic write: write to `<path>.tmp` then `os.replace(tmp, path)`. Catch IO errors; return `False` on failure (caller logs and falls through).
- [ ] 4.2 Add a unit-test target: `tests/unit/web-gates/test_resync_dotenv_database_url.py` covering: file absent (creates fresh), file present with one DATABASE_URL line (replaces), file present with no DATABASE_URL line (appends), file present with multiple DATABASE_URL lines (replaces only the first), atomic-write race protection (no partial file visible).

## Section 5 — Implement `_self_heal_db_env_drift` (gates.py)

- [ ] 5.1 Implement `_self_heal_db_env_drift(...)` mirroring `_self_heal_missing_module`'s signature:
  ```python
  def _self_heal_db_env_drift(
      wt_path: str,
      profile,
      e2e_output: str,
      change_name: str,
      env: dict,
      actual_e2e_cmd: str,
      e2e_timeout: int,
  ) -> tuple[bool, str, object] | None:
  ```
- [ ] 5.2 Body:
  - If `_extract_db_env_drift(e2e_output)` is False → return `None`.
  - Resolve project root from the gate-runner conventions (the worktree IS the project root for e2e gate purposes — same as `_self_heal_missing_module`).
  - Read schema provider via the same regex used in the TS template (Python equivalent). If schema missing or unparseable → log INFO `e2e_db_env_drift_detected_no_schema` and return `None`.
  - Call `_resolve_database_url_from_config(wt_path)`. If `None` → log WARNING `e2e_db_env_drift_no_config_url` and return `None`.
  - Validate the recovered URL against the schema provider's regex (postgresql / mysql / sqlite / sqlserver). If mismatch → log WARNING `e2e_db_env_drift_config_url_also_mismatch` and return `None`.
  - Log INFO `e2e_db_env_drift_detected change=<name> wt=<path> recovered_url_provider=<provider>`.
  - Capture `t0 = time.monotonic()`. Call `_resync_dotenv_database_url(wt_path, recovered_url)`. If False → return `None`.
  - Build a fresh env dict for the rerun: copy `env`, override `env["DATABASE_URL"] = recovered_url` (so the in-process child sees the corrected URL even if Node ignores `.env` reload).
  - Invoke `run_command(["bash", "-c", actual_e2e_cmd], timeout=e2e_timeout, cwd=wt_path, env=env_with_url, max_output_size=_E2E_CAPTURE_MAX_BYTES)`.
  - Compute `healed`: `rerun_result.exit_code == 0 and not rerun_result.timed_out and rerun_flaky == 0 and not rerun_runtime_errors`.
  - Log INFO `e2e_db_env_self_heal_resynced_and_rerun change=<name> resync_duration_ms=<int> rerun_outcome=<pass|fail_parseable|fail_unparseable>`.
  - Return `(healed, recovered_url, rerun_result)`.

## Section 6 — Wire into `execute_e2e_gate`

- [ ] 6.1 Locate the existing self-heal call site (where `self_heal_attempted` is set after `_self_heal_missing_module`). The integration point is the unparseable-fail branch — after `_extract_e2e_failure_ids(e2e_output)` returns empty AND `exit_code != 0`.
- [ ] 6.2 Add the env-drift self-heal call AFTER the dep-drift self-heal, gated by the same `self_heal_attempted` flag:
  ```python
  if not self_heal_attempted:
      env_drift_result = _self_heal_db_env_drift(
          wt_path, profile, e2e_output, change_name,
          e2e_env, actual_e2e_cmd, e2e_timeout,
      )
      if env_drift_result is not None:
          self_heal_attempted = True
          healed, recovered_url, env_rerun_result = env_drift_result
          if healed:
              self_heal_marker = f"[self-heal: synced .env from config.yaml]\n"
              # Substitute the rerun result into the variables the rest of
              # the gate flow reads (e2e_cmd_result, e2e_output, exit_code).
              e2e_cmd_result = env_rerun_result
              e2e_output = env_rerun_result.stdout + env_rerun_result.stderr
          # else: fall through to the normal fail path with the rerun output
  ```
- [ ] 6.3 Confirm the marker is correctly prepended to `GateResult.output` in the existing `pass` return path (the dep-drift self-heal already does this — same code path applies to env-drift).
- [ ] 6.4 Confirm `verify_retry_count` is NOT incremented anywhere in this branch (the gate-runner only increments on `_handle_blocking_failure` which is reached only on the fail path).

## Section 7 — Tests

- [ ] 7.1 Unit tests for each new helper:
  - `tests/unit/web-gates/test_extract_db_env_drift.py` — positive cases for each of the three signatures, negative case for a normal Playwright failure list.
  - `tests/unit/web-gates/test_resolve_database_url_from_config.py` — file missing, malformed YAML, missing key, valid key (returns string).
  - `tests/unit/web-gates/test_resync_dotenv_database_url.py` — see 4.2.
- [ ] 7.2 Integration test in `tests/integration/test_e2e_env_drift_self_heal.py`:
  - Fabricate a worktree directory with `prisma/schema.prisma` (provider=postgresql), `.env` (DATABASE_URL=file:./dev.db), `set/orchestration/config.yaml` (env_vars.DATABASE_URL=postgresql://localhost:5432/db), and a `playwright.config.ts` + minimal spec that uses `globalSetup` to validate the URL.
  - Invoke `execute_e2e_gate` directly (as the existing `tests/integration/test_e2e_dep_drift_*.py` style does).
  - Assert: returned `GateResult.verdict == "pass"`, `GateResult.output.startswith("[self-heal: synced .env from config.yaml]")`, `verify_retry_count` unchanged.
- [ ] 7.3 Run `pytest tests/unit/web-gates/ tests/integration/test_e2e_env_drift_self_heal.py -v`. All green.

## Section 8 — Documentation and harvest trail

- [ ] 8.1 Update the module-level docstring in `modules/web/set_project_web/gates.py` to mention the env-drift self-heal alongside the existing dep-drift one.
- [ ] 8.2 Add a one-line entry to `docs/release/` or the changelog noting the new self-heal class (if a changelog exists; otherwise skip).
- [ ] 8.3 Verify `openspec validate e2e-env-drift-guard --strict` passes.

## Section 9 — Manual verification on a live run

- [ ] 9.1 Confirm a running sentinel picks up the new gate code on the next e2e gate invocation (the supervisor process re-imports `gates.py` on each gate run).
- [ ] 9.2 Watch the next e2e gate that would have hit env drift — confirm the marker `[self-heal: synced .env from config.yaml]` appears in `GateResult.output` and `verify_retry_count` does not increment.
- [ ] 9.3 Run `set-run-logs <run-id> --gate e2e | grep self_heal` and confirm the new INFO events appear.
