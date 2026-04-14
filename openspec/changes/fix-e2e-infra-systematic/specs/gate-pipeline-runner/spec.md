## ADDED Requirements

### Requirement: Gate phase ordering

The pre-merge gate pipeline SHALL execute gates in four phases by default, each phase completing before the next begins. A blocking failure in any phase SHALL skip all subsequent phases.

- **Phase 1 — Mechanical fail-fast**: `build`, `test`, `scope_check`, `test_files`, `e2e_coverage`, `i18n_check`
- **Phase 2 — Smoke (env/server sanity)**: `smoke_e2e`
- **Phase 3 — LLM quality**: `spec_verify`, `review`, `rules`
- **Phase 4 — Ground-truth verification**: `e2e` (full, `--grep` scoped by `change.requirements`)

The phase assignment SHALL be overridable via `orchestration.gate_order.phase_N` config lists.

#### Scenario: spec_verify runs before full e2e
- **WHEN** the pipeline runs with the default phase ordering
- **THEN** `spec_verify` SHALL execute before `e2e`
- **AND** if `spec_verify` fails with a blocking verdict, `e2e` SHALL NOT run in the same pipeline invocation

#### Scenario: smoke_e2e catches broken server before LLM gates
- **GIVEN** the app throws on `/` due to a missing i18n key
- **WHEN** the pipeline runs
- **THEN** Phase 1 `i18n_check` SHALL fail first (fastest signal)
- **AND** if `i18n_check` is disabled, Phase 2 `smoke_e2e` SHALL fail (catches render errors)
- **AND** `spec_verify` SHALL NOT run (Phase 3 skipped)

#### Scenario: Config override reorders gates
- **GIVEN** `orchestration.gate_order.phase_2: [smoke_e2e, e2e]` (custom)
- **WHEN** the pipeline runs
- **THEN** full `e2e` SHALL execute in Phase 2 after `smoke_e2e`
- **AND** Phase 4 SHALL be empty (overridden)

### Requirement: Per-gate retry counters

Each gate SHALL track its own retry budget for in-gate and subagent retry layers, stored in `change.extras.gate_retries[<gate>]`. Full-redispatch attempts SHALL continue to be tracked in the shared `change.redispatch_count`. A gate exhausting its own budget SHALL NOT consume another gate's budget.

#### Scenario: build retries don't deplete spec_verify retry budget
- **GIVEN** `build` has consumed 2 in-gate retries (budget exhausted)
- **AND** `spec_verify` has consumed 0 retries
- **WHEN** `spec_verify` later fails
- **THEN** `spec_verify` SHALL still have its full Layer 2 subagent budget (2 attempts) available

#### Scenario: State forward-compat for pre-Phase-B changes
- **GIVEN** an orchestration-state.json written before Phase B landed (no `gate_retries` field)
- **WHEN** the engine loads the state
- **THEN** `change.extras.gate_retries` SHALL initialize to default empty counters
- **AND** the legacy `verify_retry_count` value SHALL be treated as `redispatch_count` (Layer 3 attempts)

#### Scenario: Reset on full redispatch
- **WHEN** a change undergoes a full redispatch (Layer 3)
- **THEN** all `gate_retries[*]` counters SHALL reset to zero
- **AND** `finding_fingerprints` SHALL be preserved across redispatches (convergence tracking)

### Requirement: Incremental re-verification after fix

When a Layer 1 or Layer 2 fix commits changes to the worktree, the engine SHALL re-run only the failing gate plus upstream gates invalidated by the diff. The integration gate (in the merger) SHALL continue to run the full gate suite before merge regardless.

The invalidation mapping SHALL be:
- Touched source files (`src/`, `lib/`, `app/` + `.ts`/`.tsx`/`.js`) → invalidate `build`, `test`, `smoke_e2e`, `e2e`.
- Touched only `.spec.ts` (test files) → invalidate `e2e` (scoped to affected tests via `--grep`).
- Touched only `.md` or `openspec/` → invalidate `spec_verify`, `review`.
- Touched `prisma/` → invalidate `build`, `smoke_e2e`, `e2e`.
- Touched `package.json` or `pnpm-lock.yaml` → invalidate `build`, `test`, `smoke_e2e`, `e2e`.

Re-execution SHALL preserve the phase order.

#### Scenario: Subagent fix to test file only
- **GIVEN** Layer 2 subagent fixed a failing e2e test by editing `tests/e2e/cart.spec.ts:145`
- **WHEN** re-verification runs
- **THEN** only `e2e` SHALL re-run (with `--grep` matching the affected test)
- **AND** `build` SHALL NOT re-run (source unchanged)

#### Scenario: Subagent fix to component source
- **GIVEN** Layer 2 subagent added a testid to `src/components/CartPage.tsx`
- **WHEN** re-verification runs
- **THEN** `build`, `smoke_e2e`, and the failing `e2e` SHALL all re-run (in phase order)

#### Scenario: Subagent fix to spec document only
- **GIVEN** Layer 2 subagent updated `openspec/changes/<name>/proposal.md`
- **WHEN** re-verification runs
- **THEN** only `spec_verify` SHALL re-run
- **AND** no code gate SHALL re-run

### Requirement: Per-phase runtime ceiling

The orchestrator SHALL enforce a `max_phase_runtime_secs` ceiling (default 5400 = 90 min) per change. When elapsed exceeds the ceiling, the engine SHALL kill the agent process, mark the change `stalled_phase_timeout`, and trigger a Layer 3 redispatch.

#### Scenario: Agent hangs for 120 min on one phase
- **GIVEN** `max_phase_runtime_secs=5400` and a change started its current phase at `T0`
- **AND** current time is `T0 + 5500` seconds with no CHANGE_DONE emitted
- **WHEN** the main poll loop checks elapsed time
- **THEN** the agent PID SHALL be killed via `safe_kill`
- **AND** the change SHALL be marked `stalled_phase_timeout`
- **AND** a Layer 3 redispatch SHALL be enqueued with the "phase timeout" context

#### Scenario: Normal-duration change not impacted
- **GIVEN** `max_phase_runtime_secs=5400` and a change completed its phase in 2500 seconds
- **WHEN** the change proceeds to the next phase
- **THEN** no kill SHALL occur
- **AND** the timer SHALL reset for the new phase

### Requirement: Pre-merge e2e scope filter

When a change has non-empty `requirements`, the pre-merge e2e gate SHALL invoke Playwright with `--grep "@(REQ-A|REQ-B|...)"` constructed from those REQ-ids. The integration gate in the merger SHALL continue to run the full suite regardless. Scope filtering SHALL be disableable via `orchestration.e2e_scope_filter.enabled: false`.

#### Scenario: Change with 2 requirements
- **GIVEN** `change.requirements = ["REQ-CART-001", "REQ-CART-002"]`
- **WHEN** the pre-merge e2e gate runs
- **THEN** Playwright SHALL be invoked with `--grep "@(REQ-CART-001|REQ-CART-002)"`
- **AND** only matching `@REQ-CART-001` / `@REQ-CART-002` tagged tests SHALL execute

#### Scenario: Empty requirements list
- **GIVEN** `change.requirements = []` or absent
- **WHEN** the pre-merge e2e gate runs
- **THEN** Playwright SHALL run the full suite (no `--grep`)

#### Scenario: Scope filter disabled via config
- **GIVEN** `orchestration.e2e_scope_filter.enabled: false`
- **AND** `change.requirements = ["REQ-X"]`
- **WHEN** the pre-merge e2e gate runs
- **THEN** Playwright SHALL run the full suite regardless of requirements

#### Scenario: Integration gate always full suite
- **WHEN** a change enters the merger's integration phase
- **THEN** the integration e2e gate SHALL run the full suite (never `--grep` scoped)

### Requirement: Retry layer orchestration

`GatePipeline._handle_blocking_failure` SHALL orchestrate the three retry layers in order:
1. Layer 1 (in-gate same-session quick fix) — attempted if gate in `{build, test, rules}` AND session age < 60 min AND `in_gate_attempts < budget`.
2. Layer 2 (targeted fix-subagent) — attempted if Layer 1 skipped or exhausted AND `subagent_attempts < budget`.
3. Layer 3 (full redispatch) — if convergence detection fires OR Layers 1–2 exhausted AND `redispatch_count < budget`.

Each layer attempt SHALL emit `RETRY_LAYER_ATTEMPT` on start and `RETRY_LAYER_RESULT` on completion. Convergence detection SHALL run after every gate failure with findings.

#### Scenario: spec_verify fail → Layer 2 fix → gate pass
- **GIVEN** `spec_verify` returns `fail` with 1 CRITICAL finding
- **AND** `gate_retries.spec_verify.subagent_attempts = 0` (budget available)
- **WHEN** the pipeline handles the failure
- **THEN** Layer 1 SHALL be skipped (spec_verify not in Layer 1 eligible set)
- **AND** Layer 2 subagent SHALL be spawned with the finding
- **AND** on subagent success, the gate SHALL re-run
- **AND** on re-run pass, pipeline SHALL continue to the next gate
- **AND** `RETRY_LAYER_ATTEMPT(layer=2, gate=spec_verify)` and `RETRY_LAYER_RESULT(outcome=pass)` SHALL be emitted

#### Scenario: Layers 1 and 2 exhausted → Layer 3
- **GIVEN** `build` has failed 2 Layer-1 attempts and 2 Layer-2 attempts
- **AND** `redispatch_count < 1`
- **WHEN** the pipeline handles the next failure
- **THEN** Layer 3 full redispatch SHALL be triggered
- **AND** the retry_context SHALL include findings from all prior attempts across all gates

#### Scenario: Convergence short-circuits to Layer 3
- **GIVEN** a finding fingerprint `a3f92c7e` has `count >= 3` in `change.extras.finding_fingerprints`
- **WHEN** the same fingerprint appears again in a gate result
- **THEN** `RETRY_CONVERGENCE_FAIL` SHALL be emitted
- **AND** Layer 3 full redispatch SHALL be triggered regardless of Layer 1/2 budgets remaining
- **AND** the redispatch retry_context SHALL include a "seen 4x — rethink approach" framing for that fingerprint
