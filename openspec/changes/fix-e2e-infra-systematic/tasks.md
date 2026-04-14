# Tasks: fix-e2e-infra-systematic

Phases ship independently. Each phase's tasks must be completed and tested before moving to the next. Phase B–D gated behind `orchestration.smart_retry.enabled` flag (default off initially, flipped on after Phase D tuning).

## Phase A — Template & scaffold hardening

### A.1 — i18n baseline + completeness check

- [ ] A.1.1 Add `home.*`, `nav.*`, `footer.*`, `common.*` baseline keys to `modules/web/set_project_web/templates/nextjs/messages/hu.json` and `messages/en.json`. Mirror key list between both files. [REQ: web-gates/i18n-baseline-prevents-cascading-e2e-failures]

- [ ] A.1.2 Add `modules/web/set_project_web/templates/nextjs/scripts/check-i18n-completeness.ts` that greps `useTranslations('<ns>')` and `t('<ns>.<key>')` across `src/`, compares against `messages/*.json`, and exits non-zero on missing keys with a clear report. [REQ: web-gates/i18n-baseline-prevents-cascading-e2e-failures]

- [ ] A.1.3 Add `i18n_check` as a Phase 1 gate (pre-e2e) in `modules/web/set_project_web/gates.py`. Fast fail, ≤2s typical runtime. [REQ: web-gates/i18n-baseline-prevents-cascading-e2e-failures]

- [ ] A.1.4 Unit test: `tests/unit/test_web_template_i18n_baseline.py` — verify template ships with required keys present and mirrored across locales. [REQ: web-gates/i18n-baseline-prevents-cascading-e2e-failures]

### A.2 — Playwright config hardening

- [ ] A.2.1 Edit `modules/web/set_project_web/templates/nextjs/playwright.config.ts`: replace hardcoded `globalTimeout: 3_600_000` with `process.env.PW_TIMEOUT ? parseInt(process.env.PW_TIMEOUT) * 1000 : 3_600_000`. [REQ: web-gates/playwright-config-respects-gate-timeout]

- [ ] A.2.2 Replace hardcoded `webServer.port` with `parseInt(process.env.PW_PORT ?? "3000")`. Disable `reuseExistingServer` default (set `reuseExistingServer: !process.env.CI && !process.env.PW_FRESH_SERVER`). [REQ: web-gates/playwright-config-respects-gate-timeout]

- [ ] A.2.3 Update `modules/web/set_project_web/gates.py` `_execute_e2e_gate` to pass `PW_TIMEOUT` and `PW_PORT` env vars constructed from `gate.e2e_timeout` and per-worktree port allocation. [REQ: web-gates/playwright-config-respects-gate-timeout]

- [ ] A.2.4 Unit test: verify env vars flow from directive → gate → subprocess env. [REQ: web-gates/playwright-config-respects-gate-timeout]

### A.3 — Global-setup stale-process + build-id validation

- [ ] A.3.1 Edit `modules/web/set_project_web/templates/nextjs/tests/e2e/global-setup.ts`:
  - Before webServer start, kill any process bound to `PW_PORT` (via `lsof -ti :$PORT | xargs kill -9` — cross-platform fallback).
  - Compute current HEAD SHA; read `.next/BUILD_COMMIT` marker; if mismatched or missing, `rm -rf .next` and log the reason.
  - After successful build, write `.next/BUILD_COMMIT` with current HEAD SHA.
  [REQ: web-gates/playwright-global-setup-invalidates-stale-build]

- [ ] A.3.2 Add fail-fast check: if `.next/BUILD_ID` exists but `.next/BUILD_COMMIT` doesn't (legacy), treat as stale. [REQ: web-gates/playwright-global-setup-invalidates-stale-build]

- [ ] A.3.3 Integration test in `tests/e2e/runners/` — modify a scaffold to simulate stale `.next` and verify global-setup clears it. [REQ: web-gates/playwright-global-setup-invalidates-stale-build]

### A.4 — Prisma schema-hash cache

- [ ] A.4.1 Extend `modules/web/set_project_web/templates/nextjs/prisma/seed.ts` (or a sibling script) to compute SHA-256 of `prisma/schema.prisma`, compare with `.set/seed-schema-hash`. If unchanged, skip `db push --force-reset`. Write new hash on successful seed. [REQ: web-gates/prisma-seed-skips-when-schema-unchanged]

- [ ] A.4.2 Add opt-out env var `PRISMA_FORCE_RESEED=1` for debugging. [REQ: web-gates/prisma-seed-skips-when-schema-unchanged]

- [ ] A.4.3 Unit test: verify hash logic — same schema → skip; changed schema → run. [REQ: web-gates/prisma-seed-skips-when-schema-unchanged]

### A.5 — Deterministic port allocation

- [ ] A.5.1 Edit `lib/set_orch/dispatcher.py` (or the worktree-creation path in engine) to compute per-worktree port offset as `hash(change.name) % port_range`, where `port_range = e2e_port_base + 100`. Write the assigned port into change state (`change.extras['assigned_e2e_port']`). [REQ: web-gates/worktree-port-allocation-deterministic]

- [ ] A.5.2 Update gate runner to read `change.extras['assigned_e2e_port']` when constructing `PW_PORT` env. Fall back to dynamic allocation if missing (forward-compat). [REQ: web-gates/worktree-port-allocation-deterministic]

- [ ] A.5.3 Unit test: same change name → same port; different change names → non-colliding ports. [REQ: web-gates/worktree-port-allocation-deterministic]

### A.6 — Convention docs expansion

- [ ] A.6.1 Add to `templates/core/rules/web-conventions.md`:
  - Ban on `navigator.sendBeacon` for cart/order mutations (with fetch+error fallback pattern).
  - Upsert unique-key discriminator rule (e.g., gift-card includes `recipientEmail`).
  - testid naming convention: `data-testid="<feature>-<element>"` consistent across test + component.
  - storageState pattern for admin authentication (link to helper).
  - REQ-id comment convention on specs.
  [REQ: web-gates/conventions-catch-anti-patterns]

- [ ] A.6.2 Mirror relevant rules into `tests/e2e/scaffolds/craftbrew/templates/rules/craftbrew-conventions.md` (scaffold-specific). [REQ: web-gates/conventions-catch-anti-patterns]

- [ ] A.6.3 Add `lib/auth/storage-state.ts` helper template + reference doc. [REQ: web-gates/conventions-catch-anti-patterns]

### A.7 — Change-scoped e2e (--grep on REQ-ids)

- [ ] A.7.1 Edit `modules/web/set_project_web/gates.py` `_execute_e2e_gate`: if `change.requirements` non-empty, construct `--grep "@(REQ-A|REQ-B|...)"` from the REQ-ids. Otherwise run full suite. [REQ: gate-pipeline-runner/pre-merge-e2e-scope-filter]

- [ ] A.7.2 Add directive `orchestration.e2e_scope_filter.enabled` (default true). When false, always run full suite. [REQ: gate-pipeline-runner/pre-merge-e2e-scope-filter]

- [ ] A.7.3 Integration gate in `lib/set_orch/merger.py` MUST continue running the full suite regardless. Add a code comment. [REQ: gate-pipeline-runner/pre-merge-e2e-scope-filter]

- [ ] A.7.4 Unit test: `tests/unit/test_web_gate_e2e_scope_filter.py` — requirements=[] → full; requirements=["REQ-CART-001"] → `--grep "@(REQ-CART-001)"`. [REQ: gate-pipeline-runner/pre-merge-e2e-scope-filter]

### A.8 — config.yaml → directives.json drift detection

- [ ] A.8.1 At engine startup, compare mtime of `config.yaml` vs `directives.json`. If yaml newer, log WARNING and emit `CONFIG_DRIFT` event. [REQ: verify-gate/config-drift-warning]

- [ ] A.8.2 Document in `docs/guide/orchestration.md` that `config.yaml` edits require supervisor restart (or future: hot-reload). [REQ: verify-gate/config-drift-warning]

- [ ] A.8.3 Unit test: touch yaml after directives.json → CONFIG_DRIFT emitted. [REQ: verify-gate/config-drift-warning]

## Phase B — Gate ordering + incremental re-verification

### B.1 — Gate order reshuffle

- [ ] B.1.1 Introduce `GATE_PHASE_ORDER` constant in `lib/set_orch/gate_runner.py`: `[{phase:1, gates:[build, test, scope_check, test_files, e2e_coverage, i18n_check]}, {phase:2, gates:[smoke_e2e]}, {phase:3, gates:[spec_verify, review, rules]}, {phase:4, gates:[e2e]}]`. [REQ: gate-pipeline-runner/gate-phase-ordering]

- [ ] B.1.2 Modify `GatePipeline.register()` to accept `phase` metadata (1–4). Modify `GatePipeline.run()` to execute phase-by-phase, stopping at first blocking failure. [REQ: gate-pipeline-runner/gate-phase-ordering]

- [ ] B.1.3 Update `verifier.py` pipeline registration to set `phase` on each gate (keep existing registrations, add phase attribute). [REQ: gate-pipeline-runner/gate-phase-ordering]

- [ ] B.1.4 Register `smoke_e2e` as a pre-merge Phase 2 gate (currently only runs in merger as integration). Add profile method `profile.register_smoke_e2e_premerge()` returning the gate executor. [REQ: gate-pipeline-runner/gate-phase-ordering]

- [ ] B.1.5 Add config `orchestration.gate_order.phase_N` lists (override defaults). [REQ: gate-pipeline-runner/gate-phase-ordering]

- [ ] B.1.6 Unit test: verify gates execute in phase order; failure in phase 1 skips phase 2–4; spec_verify runs BEFORE full e2e in phase 3 vs 4. [REQ: gate-pipeline-runner/gate-phase-ordering]

### B.2 — Per-gate retry counters

- [ ] B.2.1 Add `GATE_RETRY_DEFAULTS` map in `lib/set_orch/state.py`:
  ```python
  {gate_name: {"in_gate_attempts": 0, "subagent_attempts": 0, "last_layer": None, "last_outcome": None}}
  ```
  Applied to `change.extras['gate_retries']` on change creation. [REQ: gate-pipeline-runner/per-gate-retry-counters]

- [ ] B.2.2 Extend `_RESET_FAILED_FIELDS` in `lib/set_orch/engine.py` to reset `gate_retries` on full-redispatch. [REQ: gate-pipeline-runner/per-gate-retry-counters]

- [ ] B.2.3 Forward-compat: if `gate_retries` missing from state, initialize from `verify_retry_count` (treat as Layer 3 attempts only). [REQ: gate-pipeline-runner/per-gate-retry-counters]

- [ ] B.2.4 Unit test: state without `gate_retries` loads cleanly; counters isolated per gate. [REQ: gate-pipeline-runner/per-gate-retry-counters]

### B.3 — verdict.json structured findings

- [ ] B.3.1 Extend `lib/set_orch/gate_verdict.py` `_persist_spec_verify_verdict` (and analogous review-verdict) to include `findings: [{id, severity, title, file, line_start, line_end, code_context, fix_block, fingerprint, confidence}]`. Parse from the gate's LLM output. [REQ: gate-retry-context/verdict-stores-structured-findings]

- [ ] B.3.2 Add `fingerprint` computation helper in `lib/set_orch/truncate.py` or new `lib/set_orch/findings.py`. [REQ: gate-retry-context/verdict-stores-structured-findings]

- [ ] B.3.3 Backward compatibility: legacy verdict.json without `findings` still parseable; graceful fallback to summary-only. [REQ: gate-retry-context/verdict-stores-structured-findings]

- [ ] B.3.4 Unit test: parse a real spec_verify FAIL output → ≥1 structured finding extracted. [REQ: gate-retry-context/verdict-stores-structured-findings]

### B.4 — Incremental re-verification

- [ ] B.4.1 Add `lib/set_orch/gate_invalidation.py` with `affected_gates(touched_files, current_phase) -> set[str]` mapping file patterns to invalidated gates (see design.md). [REQ: gate-pipeline-runner/incremental-reverify-after-fix]

- [ ] B.4.2 After a Layer 1/2 fix commits, invoke `affected_gates` from `git diff` since baseline_sha. Re-run ONLY those gates (in phase order). [REQ: gate-pipeline-runner/incremental-reverify-after-fix]

- [ ] B.4.3 Add config `orchestration.smart_retry.incremental_reverify.enabled` (default true when smart_retry enabled). [REQ: gate-pipeline-runner/incremental-reverify-after-fix]

- [ ] B.4.4 Unit test: touched `.spec.ts` only → only e2e re-runs; touched `.tsx` → build + e2e re-run; touched `.md` only → only spec_verify re-runs. [REQ: gate-pipeline-runner/incremental-reverify-after-fix]

### B.5 — max_phase_runtime_secs

- [ ] B.5.1 Add directive `max_phase_runtime_secs: int = 5400` in `lib/set_orch/engine.py` Directives. [REQ: gate-pipeline-runner/per-phase-runtime-ceiling]

- [ ] B.5.2 Track `phase_started_at` in change state; on poll, if elapsed > ceiling, kill agent PID, mark `stalled_phase_timeout`, trigger Layer 3 redispatch. [REQ: gate-pipeline-runner/per-phase-runtime-ceiling]

- [ ] B.5.3 Unit test: simulate elapsed > ceiling → kill + redispatch invoked. [REQ: gate-pipeline-runner/per-phase-runtime-ceiling]

## Phase C — Smart retry layers

### C.1 — Finding extractors per gate type

- [ ] C.1.1 Add `lib/set_orch/findings.py` with extractors:
  - `extract_build_findings(output)` → parse TS/lint errors with file+line
  - `extract_test_findings(output)` → parse vitest/jest failures
  - `extract_e2e_findings(output)` → parse Playwright failing tests
  - `extract_review_findings(output)` → parse reviewer FILE/LINE/FIX blocks
  - `extract_spec_verify_findings(output)` → parse CRITICAL block structure
  [REQ: gate-retry-context/structured-finding-extractors]

- [ ] C.1.2 Each extractor returns `list[Finding]` dataclass with full structured fields. [REQ: gate-retry-context/structured-finding-extractors]

- [ ] C.1.3 Unit tests: per-extractor fixtures with known outputs from the craftbrew run. [REQ: gate-retry-context/structured-finding-extractors]

### C.2 — Layer 1 in-gate same-session quick fix

- [ ] C.2.1 Add `lib/set_orch/retry_layers.py` with `layer_1_in_gate_fix(change, gate, findings, session_id) -> FixResult`. [REQ: gate-retry-context/layer-1-in-gate-quick-fix]

- [ ] C.2.2 Render Layer 1 prompt template per gate (`build`, `test`, `rules`). [REQ: gate-retry-context/layer-1-in-gate-quick-fix]

- [ ] C.2.3 Invoke `claude --resume <sid>` with the prompt, 300s timeout, max 15 turns. Wait for "done" or "blocked" signal. [REQ: gate-retry-context/layer-1-in-gate-quick-fix]

- [ ] C.2.4 On return, re-run ONLY the failing gate. If pass, continue pipeline. If fail, increment counter + retry Layer 1 (different prompt variation) up to budget. [REQ: gate-retry-context/layer-1-in-gate-quick-fix]

- [ ] C.2.5 Session-staleness check: if session > 60min, skip Layer 1. [REQ: gate-retry-context/layer-1-in-gate-quick-fix]

- [ ] C.2.6 Unit test: mock Claude session, verify prompt construction and re-run flow. [REQ: gate-retry-context/layer-1-in-gate-quick-fix]

### C.3 — Layer 2 fix-subagent

- [ ] C.3.1 Add `lib/set_orch/fix_subagent.py` with `spawn_fix_subagent(gate, change, findings, wt_path) -> SubagentResult`. [REQ: gate-retry-context/layer-2-targeted-subagent]

- [ ] C.3.2 Create subagent prompt templates in `templates/core/rules/fix-subagent/<gate>.md` (one per gate type: build, test, smoke_e2e, spec_verify, review, e2e). [REQ: gate-retry-context/layer-2-targeted-subagent]

- [ ] C.3.3 Invoke `claude -p "<prompt>" --model sonnet --max-turns 15 --cwd <wt>`. Fresh session (no --resume). [REQ: gate-retry-context/layer-2-targeted-subagent]

- [ ] C.3.4 After return, inspect `git diff baseline..HEAD` to determine touched files. Validate against allowlist from template (gate-specific). If scope violation: `git reset --hard baseline_sha`, return `SubagentResult(outcome="scope_violation")`. [REQ: gate-retry-context/layer-2-targeted-subagent]

- [ ] C.3.5 On accept, call incremental re-verification → re-run failing gate + upstream invalidated gates. [REQ: gate-retry-context/layer-2-targeted-subagent]

- [ ] C.3.6 Unit test: scope-violation fixture (subagent touches unexpected path) → reset + blocked outcome. [REQ: gate-retry-context/layer-2-targeted-subagent]

- [ ] C.3.7 Unit test: each gate template renders correctly with sample findings. [REQ: gate-retry-context/layer-2-targeted-subagent]

### C.4 — Layer 3 consolidated redispatch

- [ ] C.4.1 Refactor `lib/set_orch/engine.py` `_build_reset_retry_context` to produce the consolidated retry_context described in design.md (all gate findings + convergence summary + prior commits). [REQ: gate-retry-context/layer-3-consolidated-redispatch]

- [ ] C.4.2 Prepend convergence-flagged fingerprints with "appeared N times — rethink" framing. [REQ: gate-retry-context/layer-3-consolidated-redispatch]

- [ ] C.4.3 Reduce default `redispatch_count` budget from 2 to 1 when `smart_retry.enabled=true`. [REQ: gate-retry-context/layer-3-consolidated-redispatch]

- [ ] C.4.4 Unit test: consolidated retry_context contains findings from all gates touched in prior attempts. [REQ: gate-retry-context/layer-3-consolidated-redispatch]

### C.5 — Convergence detection

- [ ] C.5.1 Add `check_convergence(change, gate, findings) -> bool` in `lib/set_orch/retry_layers.py`. [REQ: gate-retry-context/convergence-detection]

- [ ] C.5.2 Update `change.extras['finding_fingerprints']` on every gate run with findings. [REQ: gate-retry-context/convergence-detection]

- [ ] C.5.3 When any fingerprint hits threshold (default 3), emit `RETRY_CONVERGENCE_FAIL` event and escalate to Layer 3. [REQ: gate-retry-context/convergence-detection]

- [ ] C.5.4 Unit test: fixture with same finding 3x → convergence fires. [REQ: gate-retry-context/convergence-detection]

### C.6 — Unified infra-fail classifier

- [ ] C.6.1 Generalize `_classify_spec_verify_outcome` in `lib/set_orch/verifier.py` into `classify_gate_outcome(cmd_result, output, gate_name)` handling all LLM gates. [REQ: verify-gate/unified-infra-fail-classification]

- [ ] C.6.2 Handle: `exit_code=0 + verdict` → verdict; `timed_out=True` → infra; `max_turns` without verdict → infra; `exit_code != 0` with verdict sentinel in tail → verdict; otherwise ambiguous. [REQ: verify-gate/unified-infra-fail-classification]

- [ ] C.6.3 Infra outcome → gate returns `status="skipped"` with `infra_fail=True` in GateResult. Pipeline treats as non-blocking, does NOT consume retry counter. [REQ: verify-gate/unified-infra-fail-classification]

- [ ] C.6.4 Extend to review gate (currently has no infra-fail detection). [REQ: verify-gate/unified-infra-fail-classification]

- [ ] C.6.5 Unit test: fixture with `exit=1 + VERIFY_RESULT: FAIL` in tail → verdict (not infra). [REQ: verify-gate/unified-infra-fail-classification]

- [ ] C.6.6 Unit test: `exit=1 + timed_out=False + no sentinel` → infra → skipped with flag. [REQ: verify-gate/unified-infra-fail-classification]

### C.7 — RESUME_CONTEXT.md

- [ ] C.7.1 Add `lib/set_orch/resume_context.py` with `write_resume_context(wt_path, change, findings_history)` that writes a markdown summary. [REQ: gate-retry-context/resume-context-md]

- [ ] C.7.2 Hook into `_recover_verify_failed` and `MANUAL_RESUME` / `ISSUE_DIAGNOSED_TIMEOUT` handlers. [REQ: gate-retry-context/resume-context-md]

- [ ] C.7.3 Update dispatcher prompt construction to reference "Read RESUME_CONTEXT.md first" when file present. [REQ: gate-retry-context/resume-context-md]

- [ ] C.7.4 Unit test: RESUME_CONTEXT.md contains all gate findings + convergence warnings. [REQ: gate-retry-context/resume-context-md]

### C.8 — Retry orchestration integration

- [ ] C.8.1 Rewrite `gate_runner.GatePipeline._handle_blocking_failure` to call through the retry layers in order (Layer 1 → 2 → 3), respecting per-gate budgets and convergence state. [REQ: gate-pipeline-runner/retry-layer-orchestration]

- [ ] C.8.2 Emit `RETRY_LAYER_ATTEMPT` / `RETRY_LAYER_RESULT` events at each layer boundary. [REQ: gate-pipeline-runner/retry-layer-orchestration]

- [ ] C.8.3 End-to-end test: simulate a spec_verify fail → Layer 2 subagent success → gate pass → pipeline continues. [REQ: gate-pipeline-runner/retry-layer-orchestration]

- [ ] C.8.4 End-to-end test: Layer 1–2 both fail → Layer 3 full redispatch. [REQ: gate-pipeline-runner/retry-layer-orchestration]

## Phase D — Observability + tuning

### D.1 — Event schema + emission

- [ ] D.1.1 Add event types to `lib/set_orch/events.py`: `RETRY_LAYER_ATTEMPT`, `RETRY_LAYER_RESULT`, `SUBAGENT_FIX_START`, `SUBAGENT_FIX_END`, `RETRY_CONVERGENCE_FAIL`, `INCREMENTAL_REVERIFY`, `CONFIG_DRIFT`. [REQ: gate-observability/smart-retry-events]

- [ ] D.1.2 Unit test: each retry path emits the expected event sequence with correct payloads. [REQ: gate-observability/smart-retry-events]

### D.2 — Dashboard visualization

- [ ] D.2.1 Add API endpoint `/api/<project>/retry-layers` returning per-change histogram `{layer_1_success: N, layer_2_success: N, layer_3_success: N, convergence_fails: N}`. [REQ: gate-observability/retry-layer-dashboard]

- [ ] D.2.2 Add React component `web/src/components/RetryLayerHistogram.tsx` showing the histogram per change. [REQ: gate-observability/retry-layer-dashboard]

- [ ] D.2.3 Add a summary row per change in existing `ChangeTable` showing dominant retry layer. [REQ: gate-observability/retry-layer-dashboard]

### D.3 — Metrics

- [ ] D.3.1 Add `metrics.retry_layer_success_rate` (per layer), `metrics.convergence_failures`, `metrics.avg_retries_per_gate`, `metrics.subagent_tokens_total` to orchestration-state extras. Updated on each pipeline run. [REQ: gate-observability/retry-metrics]

- [ ] D.3.2 Unit test: metrics aggregation produces correct values from synthetic events. [REQ: gate-observability/retry-metrics]

### D.4 — Rollout gate

- [ ] D.4.1 Run craftbrew spec with `smart_retry.enabled=false` (baseline) → record VERIFY_GATE count, wall-clock, token cost.

- [ ] D.4.2 Run same spec with `smart_retry.enabled=true` → record same metrics.

- [ ] D.4.3 Compare: require ≥30% reduction in VERIFY_GATE count and no regression in merged-change count before flipping default to `true`.

- [ ] D.4.4 Document rollout results in `docs/learn/smart-retry-benchmark.md`.

## Verification

- [ ] Run `pytest tests/unit/` — all existing and new tests pass.
- [ ] Run `tests/e2e/runners/run-micro-web.sh` with smart_retry enabled — all changes merge, retry counts lower than baseline.
- [ ] Run `tests/e2e/runners/run-craftbrew.sh` — full regression validation.
- [ ] Manual: induce each retry-layer path on a dummy change to confirm event emissions and state transitions.
- [ ] OpenSpec verify: `openspec verify fix-e2e-infra-systematic` clean (no unmapped tasks, all REQs have scenarios).
