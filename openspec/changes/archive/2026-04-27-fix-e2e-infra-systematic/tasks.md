# Tasks: fix-e2e-infra-systematic

Two tiers. Tier 1 ships as a self-contained unit (template + gate-runner hardening, safe). Tier 2 ships after Tier 1 validates (structured findings + cross-change regression signal). Tier 3 items from proposal.md are deferred — NOT part of this change's implementation.

## Tier 1 — Template & gate-runner hardening (SHIP NOW)

### T1.1 — i18n baseline + completeness check

- [ ] T1.1.1 Add `home.*`, `nav.*`, `footer.*`, `common.*` baseline keys to `modules/web/set_project_web/templates/nextjs/messages/hu.json` and `messages/en.json`. Mirror key list between both files. [REQ: web-gates/i18n-baseline-prevents-cascading-e2e-failures]

- [ ] T1.1.2 Add `modules/web/set_project_web/templates/nextjs/scripts/check-i18n-completeness.ts` that greps `useTranslations('<ns>')` and `t('<ns>.<key>')` across `src/`, compares against `messages/*.json`, and exits non-zero on missing keys with a clear report. [REQ: web-gates/i18n-baseline-prevents-cascading-e2e-failures]

- [ ] T1.1.3 Register `i18n_check` as a pre-e2e gate in `modules/web/set_project_web/gates.py`. Fast fail, ≤2s typical runtime. Non-blocking (warn) on first rollout; can be flipped to blocking via `gate_overrides.i18n_check: run`. [REQ: web-gates/i18n-baseline-prevents-cascading-e2e-failures]

- [ ] T1.1.4 Unit test: `tests/unit/test_web_template_i18n_baseline.py` — verify template ships with required keys present and mirrored across locales. [REQ: web-gates/i18n-baseline-prevents-cascading-e2e-failures]

- [ ] T1.1.5 Unit test: `scripts/check-i18n-completeness.ts` via a synthetic fixture — missing key fails; complete keys pass. [REQ: web-gates/i18n-baseline-prevents-cascading-e2e-failures]

### T1.2 — Playwright config env-driven

- [ ] T1.2.1 Edit `modules/web/set_project_web/templates/nextjs/playwright.config.ts`: replace hardcoded `globalTimeout` with `process.env.PW_TIMEOUT ? parseInt(process.env.PW_TIMEOUT) * 1000 : 3_600_000`. [REQ: web-gates/playwright-config-respects-gate-timeout]

- [ ] T1.2.2 Replace hardcoded `webServer.port` with `parseInt(process.env.PW_PORT ?? "3000")`. Set `reuseExistingServer: !process.env.CI && !process.env.PW_FRESH_SERVER`. [REQ: web-gates/playwright-config-respects-gate-timeout]

- [ ] T1.2.3 Update `modules/web/set_project_web/gates.py` `_execute_e2e_gate` to construct and pass `PW_TIMEOUT`, `PW_PORT`, and (when fresh server is needed) `PW_FRESH_SERVER=1` env vars. [REQ: web-gates/playwright-config-respects-gate-timeout]

- [ ] T1.2.4 Unit test: verify env vars flow from directive → gate → subprocess env. [REQ: web-gates/playwright-config-respects-gate-timeout]

### T1.3 — Global-setup: stale process kill + BUILD_COMMIT marker

- [ ] T1.3.1 Edit `modules/web/set_project_web/templates/nextjs/tests/e2e/global-setup.ts`:
  - Before webServer start, kill any process bound to `PW_PORT` (unix: `lsof -ti :$PORT | xargs kill -9`; skip on unsupported platforms with a log).
  - Compute current HEAD SHA; read `.next/BUILD_COMMIT` marker; if missing/mismatched (or legacy `.next/BUILD_ID` present without `BUILD_COMMIT`), `rm -rf .next/` and log the reason.
  - After successful build, write current HEAD SHA to `.next/BUILD_COMMIT`.
  [REQ: web-gates/playwright-global-setup-invalidates-stale-build]

- [ ] T1.3.2 Integration test: a scaffold fixture with stale `.next/BUILD_COMMIT` → global-setup removes it. [REQ: web-gates/playwright-global-setup-invalidates-stale-build]

### T1.4 — Prisma schema-hash cache

- [ ] T1.4.1 Extend `modules/web/set_project_web/templates/nextjs/prisma/seed.ts` (or sibling helper script) to compute SHA-256 of `prisma/schema.prisma`, compare with `.set/seed-schema-hash`, skip `db push --force-reset` if unchanged. Write new hash on successful seed. Opt-out env `PRISMA_FORCE_RESEED=1`. [REQ: web-gates/prisma-seed-skips-when-schema-unchanged]

- [ ] T1.4.2 Unit test: hash cache logic — same schema → skip; changed schema → run; force flag bypasses. [REQ: web-gates/prisma-seed-skips-when-schema-unchanged]

### T1.5 — Deterministic port allocation

- [ ] T1.5.1 Add port allocation in `lib/set_orch/dispatcher.py` (or worktree-creation path) that computes per-worktree port as `e2e_port_base + (hash(change.name) % port_range)` where `port_range` defaults to 100. Persist in `change.extras.assigned_e2e_port`. [REQ: web-gates/worktree-port-allocation-deterministic]

- [ ] T1.5.2 Update gate runner to read `change.extras.assigned_e2e_port` when constructing `PW_PORT`. Fall back to dynamic allocation if absent (forward-compat). [REQ: web-gates/worktree-port-allocation-deterministic]

- [ ] T1.5.3 Unit test: same change name → same port across runs; 20 representative change names → no pairwise collision at `range=100`. [REQ: web-gates/worktree-port-allocation-deterministic]

### T1.6 — Convention docs expansion

- [ ] T1.6.1 Add to `templates/core/rules/web-conventions.md`:
  - Ban on `navigator.sendBeacon` for cart/order mutations (with fetch+error fallback pattern).
  - Upsert unique-key discriminator rule (e.g., gift-card includes `recipientEmail`).
  - testid naming convention: `data-testid="<feature>-<element>"` consistent across test + component.
  - storageState pattern for admin authentication (link to helper).
  - REQ-id comment convention on specs for scope-filtered e2e.
  [REQ: web-gates/conventions-catch-anti-patterns]

- [ ] T1.6.2 Mirror relevant rules into `tests/e2e/scaffolds/<scaffold>/templates/rules/<scaffold>-conventions.md` where a scaffold override already exists. [REQ: web-gates/conventions-catch-anti-patterns]

- [ ] T1.6.3 Add `modules/web/set_project_web/templates/nextjs/lib/auth/storage-state.ts` helper template. [REQ: web-gates/conventions-catch-anti-patterns]

### T1.7 — Config drift warning

- [ ] T1.7.1 At engine startup (after state load, before main loop), compare mtime of `set/orchestration/config.yaml` vs `set/orchestration/directives.json`. If yaml newer, emit `CONFIG_DRIFT` event + WARNING log naming both mtimes and the delta in seconds. [REQ: verify-gate/config-drift-warning]

- [ ] T1.7.2 Document in `docs/guide/orchestration.md` that `config.yaml` edits require supervisor restart (or future: hot-reload). [REQ: verify-gate/config-drift-warning]

- [ ] T1.7.3 Unit test: touch yaml after directives.json → `CONFIG_DRIFT` emitted. [REQ: verify-gate/config-drift-warning]

### T1.8 — Tier 1 verification

- [ ] T1.8.1 Run `pytest tests/unit/` — all existing + new tests pass.
- [ ] T1.8.2 Run a smoke E2E via `tests/e2e/runners/run-micro-web.sh` on the hardened templates — validate `i18n_check`, `BUILD_COMMIT`, prisma cache, port allocation end-to-end.
- [ ] T1.8.3 Document Tier 1 shipping in a short `docs/learn/e2e-infra-tier1.md` summarizing the template changes and how to consume them in a project.

## Tier 2 — Structured findings + cross-change regression signal (SHIP NEXT)

Starts after Tier 1 merges and at least one full E2E run validates Tier 1 measurably reduces retries without regressions.

### T2.1 — verdict.json structured findings (forward-compatible)

- [ ] T2.1.1 Add `lib/set_orch/findings.py` with the `Finding` dataclass (`id, severity, title, file, line_start, line_end, code_context, fix_block, fingerprint, confidence`) and per-gate extractor stubs: `extract_review_findings`, `extract_spec_verify_findings`, `extract_e2e_findings`. Each extractor returns `list[Finding]` and never raises. [REQ: gate-retry-context/verdict-stores-structured-findings]

- [ ] T2.1.2 Add `fingerprint` helper: first 8 hex chars of `SHA256(f"{file}:{line_start}:{title[:50]}")`. [REQ: gate-retry-context/verdict-stores-structured-findings]

- [ ] T2.1.3 Extend `lib/set_orch/gate_verdict.py` `_persist_spec_verify_verdict` (and analogous review verdict) to OPTIONALLY include `findings: [...]` when the extractor produced any. Backward-compat: legacy verdicts without `findings` still parseable. [REQ: gate-retry-context/verdict-stores-structured-findings]

- [ ] T2.1.4 Update `lib/set_orch/engine.py` `_build_reset_retry_context` (and verifier retry assembly) to prefer `findings` when present — render as "FILE/LINE/FIX" structured block, keep summary as fallback when findings empty. [REQ: gate-retry-context/verdict-stores-structured-findings]

- [ ] T2.1.5 Unit test: each extractor parses representative gate output → ≥1 structured finding extracted. [REQ: gate-retry-context/verdict-stores-structured-findings]

- [ ] T2.1.6 Unit test: verdict.json without `findings` loads cleanly; retry_context falls back to summary. [REQ: gate-retry-context/verdict-stores-structured-findings]

### T2.2 — Cross-change regression detection at integration gate

- [ ] T2.2.1 Add `lib/set_orch/cross_change.py` with `resolve_owning_change(test_path, test_title, state) -> Optional[str]` — matches in order: (a) `tests/e2e/<change>.spec.ts` filename → change name; (b) `@REQ-...` tag in test body → change with that REQ in `requirements`; (c) touched file overlap with any merged change's `merged_scope_files`. Returns None when unresolved. [REQ: gate-pipeline-runner/cross-change-regression-detection]

- [ ] T2.2.2 In `lib/set_orch/merger.py` `_run_integration_gates`, after parsing the failing-test list from e2e output, call `resolve_owning_change` for each. Partition into: "current-change tests" vs "already-merged-change tests". [REQ: gate-pipeline-runner/cross-change-regression-detection]

- [ ] T2.2.3 If any failing test is owned by an already-merged change, emit event `CROSS_CHANGE_REGRESSION` with `{current_change, regressed_tests: [{test, owning_change}], touched_files}`. [REQ: gate-pipeline-runner/cross-change-regression-detection]

- [ ] T2.2.4 Prepend a prescriptive block to the agent's redispatch `retry_context`:
  - Header: "⚠ Cross-change regression: your change broke tests belonging to already-merged feature(s): <list>. These tests pass on main. Do NOT modify those features' code."
  - List of failing tests grouped by owning change.
  - List of touched files in this change that overlap each owning change's scope.
  - Prescriptive directive: "Fix your change so it doesn't affect the overlapping surface. Revert the overlapping changes or achieve your goal via your own scope only."
  [REQ: gate-pipeline-runner/cross-change-regression-detection]

- [ ] T2.2.5 Populate `change.merged_scope_files` at merge time (in merger post-merge step): list of files the merge touched. Stored on the merged change for later lookup. [REQ: gate-pipeline-runner/cross-change-regression-detection]

- [ ] T2.2.6 Forward-compat: when `merged_scope_files` is absent on legacy merged changes, `resolve_owning_change` skips path (c) and falls back to (a) and (b) only. [REQ: gate-pipeline-runner/cross-change-regression-detection]

- [ ] T2.2.7 Unit test: synthetic integration-gate failure with a test from an already-merged change → `CROSS_CHANGE_REGRESSION` event emitted; retry_context contains the prescriptive framing. [REQ: gate-pipeline-runner/cross-change-regression-detection]

- [ ] T2.2.8 Unit test: integration-gate failure with only own-change tests failing → NO `CROSS_CHANGE_REGRESSION` event; normal retry_context used. [REQ: gate-pipeline-runner/cross-change-regression-detection]

### T2.3 — Tier 2 verification

- [ ] T2.3.1 Run `pytest tests/unit/` — all existing + new tests pass.
- [ ] T2.3.2 Compare retry_context quality on a synthetic review-gate failure before vs after Tier 2: findings block present and actionable.

## Tier 3 — Deferred (NOT implemented in this change)

The following items are documented in `design.md` for reference but are intentionally not in this change's task list. Each would be considered for a follow-up change after Tier 1–2 ship and metrics justify the additional investment:

- Gate phase restructure (mechanical → smoke → LLM → full e2e ordering).
- Per-gate retry counters replacing the single `verify_retry_count`.
- Incremental re-verification (re-run only failing gate + diff-invalidated upstream).
- `max_phase_runtime_secs` ceiling.
- Smart-retry Layer 1 (in-gate same-session quick fix) and Layer 2 (targeted fix-subagent with gate-specific templates).
- Consolidated Layer 3 redispatch with reduced budget.
- Convergence detection (fingerprint count threshold → Layer 3 escalation).
- Unified infra-fail classifier across all LLM gates.
- `RESUME_CONTEXT.md` on timeout/manual-resume paths.
- Full `scope_boundary` gate (blocking) + explicit per-change `scope_files` declaration.
- Cross-change-regression specialized Layer 2 subagent (Tier 2 gives the signal, Tier 3 would add the subagent).
- Observability: retry-layer dashboard, metrics aggregation.

These are NOT tasks in this change. Do not mark them as in-progress.
