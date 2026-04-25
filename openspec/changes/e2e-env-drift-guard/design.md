# Design: e2e-env-drift-guard

## Context

`e2e-dep-drift-guard` (archived 2026-04-21) established the pattern: detect a known crash signature on the unparseable-fail path of `execute_e2e_gate`, recover in-gate, do not consume `verify_retry_count`, prepend a `[self-heal: ...]` marker. This change ports that pattern to a different but adjacent failure class — env drift.

Dep drift = "package.json declares X, node_modules doesn't have it". Env drift = "schema.prisma declares provider X, .env carries a URL for provider Y". Both are bootstrap-time mismatches caused by the orchestrator writing one file (`package.json` from agent commit, `.env` from `set/orchestration/config.yaml`) while the worktree was already in a state that drifted from it. Both are cheap to recover and waste a retry slot if not caught.

## Decisions

### 1. Two layers of defense, not one

**Decision**: Forward-port the agent's `validateDatabaseUrl()` pre-flight to the template AND add a gate-runner self-heal.

**Why**: The pre-flight in `globalSetup` is the cheapest correct path — it runs in the same Node process before Playwright starts, has direct read/write access to `process.env.DATABASE_URL`, and surfaces a clear error to logs. But it only protects projects that adopt the new template. Existing consumer projects (or projects whose `tests/e2e/global-setup.ts` has been customized and no longer matches the template) still need a safety net at the gate layer.

The gate-runner self-heal is the safety net. It runs only when the pre-flight failed (either absent or unable to recover) and the e2e gate captured an unparseable failure with a known signature. Cost on the happy path: one regex match against e2e_output, evaluated only when `exit_code != 0` and `_extract_e2e_failure_ids()` returned empty.

**Alternative considered**: Layer 1 in `lib/set_orch/dispatcher.py` `_reinstall_deps_if_needed` style — detect drift at worktree dispatch and resync `.env`. **Rejected** because dispatcher runs once per dispatch; the env_vars in `set/orchestration/config.yaml` can change between dispatches (operator edits the file mid-run, as observed in this run when the user changed `DATABASE_URL` from sqlite to postgresql). The gate is the right enforcement point — it runs every time e2e is invoked.

### 2. Detection signature: union of three patterns

**Decision**: `_extract_db_env_drift(output)` returns `True` if ANY of three patterns match:

```
[global-setup] DATABASE_URL/schema provider mismatch
Error validating datasource ... URL must start with the protocol
Command failed: npx prisma db seed ... PrismaClientInitializationError
```

**Why**: The first signature comes from the template self-heal's own error message (when it could not recover from config.yaml — e.g. `env_vars.DATABASE_URL` itself was wrong). The second is Prisma's direct error when `prisma db push` is invoked with a mismatched URL and the template self-heal isn't installed. The third is the seed-time variant (post-push, pre-test) where `.env` still carries the wrong URL after a manual recovery.

All three resolve to the same fix (resync `.env` from `config.yaml`), so they share one helper.

**Why a union and not a single regex**: each signature has different surrounding noise (Playwright runner output vs Prisma stack trace vs Node's `Command failed:` format). Cheaper and more readable as separate string-contains checks.

### 3. config.yaml parsing: yaml.safe_load over regex

**Decision**: Use `yaml.safe_load` to read `env_vars.DATABASE_URL` from `set/orchestration/config.yaml`.

**Why**: `pyyaml>=5.0` is already a hard dep in `modules/web/pyproject.toml`. The agent's worktree fix used a regex line-match because TypeScript can't import a YAML parser without adding a npm dep — that constraint doesn't apply to Python. `yaml.safe_load` correctly handles quoted strings, multi-line values, and comments that a regex would mis-parse.

**Failure mode**: `yaml.safe_load` raises on malformed YAML. Wrap in try/except and treat any parse failure as "no recoverable URL"; log at WARNING level so the operator sees the parse error in `set-run-logs`.

### 4. .env resync: line-replace, not full rewrite

**Decision**: `_resync_dotenv_database_url(wt_path, new_url)` reads `.env` line by line, replaces the first `DATABASE_URL=` line (preserving comments and other vars), or appends if not present. Atomic write: write to `.env.tmp` then `os.replace`.

**Why**: The template-shipped `.env` carries other vars (PW_PORT, PORT, PLAYWRIGHT_SCREENSHOT, PRISMA_USER_CONSENT_FOR_DANGEROUS_AI_ACTION, PW_FLAKY_FAILS, PW_FRESH_SERVER) that must not be lost. A full rewrite would drop these and break unrelated parts of the gate. Atomic write protects against a half-written `.env` if the gate is killed mid-resync.

**Quoting**: write `DATABASE_URL="<url>"` with double quotes — matches the agent's worktree commit and the template's existing format.

### 5. Self-heal ordering: dep-drift before env-drift

**Decision**: In `execute_e2e_gate`, call `_self_heal_missing_module` first, then `_self_heal_db_env_drift`, both gated by a single `self_heal_attempted` boolean.

**Why**: A `MODULE_NOT_FOUND` crash short-circuits the e2e run before Prisma init, so it cannot also produce a `DATABASE_URL` mismatch error in the same output. The orderings are mutually exclusive in practice. We pick dep-drift first because it has been in production longer and its detection has higher confidence (regex + package.json membership check vs string-contains union). If both somehow matched, we'd want to fix the more fundamental (missing module) first.

**Single-attempt guarantee**: at most one self-heal per gate invocation, period. The gate must not loop on self-heal — that defeats the `verify_retry_count` budget by hiding compounding failures.

### 6. Marker text: `[self-heal: synced .env from config.yaml]`

**Decision**: prepend exactly this string to `GateResult.output` when env-drift self-heal recovers.

**Why**: Matches the dep-drift marker pattern (`[self-heal: installed <pkg>]`) so forensics tooling (`set-run-logs`, dashboard) can use a single regex to find any self-healed gate run. The verb (`synced`) is distinct from `installed` so manual log inspection can tell which class fired.

## Alternatives Considered

### A. Add the self-heal to `lib/set_orch/dispatcher.py` instead of the gate

Run the resync at worktree dispatch (alongside `_reinstall_deps_if_needed`). **Rejected**: dispatcher runs once per dispatch; if `set/orchestration/config.yaml.env_vars` is edited between two dispatches of the same change, the gate would still see a stale `.env`. The gate-runner is the right enforcement point because it runs on every e2e invocation.

### B. Put the recovery logic only in the TS template (no Python self-heal)

Skip Layer 2b entirely. **Rejected**: existing consumer projects don't have the template self-heal until they redeploy. The Python self-heal is the safety net for projects that lag the template — and for any future failure mode where the template self-heal can't recover (e.g. `env_vars.DATABASE_URL` itself is wrong, or `set/orchestration/config.yaml` is malformed).

### C. Detect via Playwright reporter exit code only

Return `pass` whenever `exit_code != 0` AND output contains `provider mismatch`. **Rejected**: doesn't actually fix the underlying state. The next gate run would crash again. Self-heal must mutate `.env` to be useful — and a rerun proves the fix worked before reporting `pass`.

### D. Make the schema provider authoritative — overwrite `config.yaml` from `schema.prisma`

If the schema says PostgreSQL, write `DATABASE_URL=postgresql://...` to `config.yaml`. **Rejected**: too aggressive. We don't know what URL the operator wants — only what the schema's provider scheme is. The current design only recovers when `config.yaml` already has a valid URL for the schema provider; if it doesn't, the gate fails with a clear actionable message.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Self-heal masks a real config bug, hiding it from the operator | Forensic logs + `[self-heal: ...]` marker in GateResult.output. The dashboard can flag changes whose merge included a self-heal. |
| `config.yaml` parse fails and we accidentally swallow the error | Try/except with WARNING-level log. Self-heal returns `None` on parse failure; gate proceeds with the original failure path. |
| Concurrent gate runs race on `.env` write | Self-heal runs in the same process as the gate; gates are serialized per change (one verify pipeline per change at a time). No cross-process write contention. |
| The recovery URL itself is wrong in `config.yaml` | Pre-rerun matcher check: `_resolve_database_url_from_config` validates the URL against the schema provider's regex before writing. If the recovery URL also mismatches, return `None` and let the gate fail with the original message. |
| Template change breaks existing scaffolds that have customized `global-setup.ts` | Existing scaffolds keep their files — `set-project init` does not overwrite without `--force`. The gate-runner self-heal is the safety net for these. |

## Forensic Visibility

Operators inspecting a run will see two new log lines on a self-healed e2e:

```
[INFO] set_project_web.gates: e2e_db_env_drift_detected change=<name> wt=<path> recovered_url_provider=postgresql
[INFO] set_project_web.gates: e2e_db_env_self_heal_resynced_and_rerun change=<name> resync_duration_ms=12 rerun_outcome=pass
```

And the gate output will start with `[self-heal: synced .env from config.yaml]\n` — visible in the verdict sidecar and the dashboard's gate-output panel.
