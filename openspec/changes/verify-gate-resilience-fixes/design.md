## Context

The orchestration framework has accumulated retry/circuit-breaker limits across 4 layers — `config.py DIRECTIVE_DEFAULTS`, `engine.py @dataclass` defaults, hardcoded module-level constants (`merger.py`, `verifier.py`, `watchdog.py`, `issues/models.py`), and inline literals inside functions. Three concrete incidents in production runs traced back to limit divergence:

- `craftbrew-run-20260423-2223` `catalog-product-detail` was killed at `failed:retry_wall_time_exhausted` after 47 minutes when the operator believed the budget was 90 min — `engine.py` had been raised to 90 min but `config.py` still had 30 min, and config wins at runtime.
- `subscription-management` was stuck in `integration-failed` until `db2e6a5c` because the merger returned False without dispatching the agent — silent failure from a gate-fail return path.
- `auth-password-reset-flow` agent was killed by `WATCHDOG_TIMEOUT_VERIFYING=300s` mid-suite (e2e gate suite is realistically ~15-20 min for ~24 specs).

The root pattern is a **lack of single source of truth** for configuration values. Anyone raising a limit must remember to raise it in 2-3 places, and divergence silently downgrades to the smaller value.

Stakeholders: framework operators (raise limits to make runs complete), agent runtime (predictable execution budgets), debugging (single place to read effective config).

## Goals / Non-Goals

**Goals:**
- Single source of truth for retry/circuit limits — `config.py DIRECTIVE_DEFAULTS` only.
- Defaults reflect observed-needed budgets, not historical ceilings.
- All hardcoded retry/circuit constants become directive-overridable.
- Regression tests prevent silent gate-failure-without-dispatch and silent default downgrades.
- 80% token-runaway pre-warning so operators see the squeeze before the kill.
- Scoped-subset spec validation prevents wasted retry runs on bogus paths.

**Non-Goals:**
- No structural refactor of the gate runner / verifier / merger pipelines themselves — the failure modes are addressed by limit hoisting + invariant tests, not by reorganizing the dispatch chain.
- No automatic auto-bisect on token runaway — still terminal failure, just earlier visibility.
- No layout-pattern fidelity — covered by sibling change `design-fidelity-deepening`.
- No watchdog→fix-iss dispatch chain refactor — observed ~30 min latency is acknowledged, but this change only raises the timeout; chain refactor is deferred.

## Decisions

### D1. `DIRECTIVE_DEFAULTS` is canonical; `EngineConfig` reads from it
**Choice:** Convert `EngineConfig @dataclass` defaults to use `field(default_factory=lambda: DIRECTIVE_DEFAULTS["<key>"])`. This means at class-definition time the values are pulled from `DIRECTIVE_DEFAULTS`, eliminating the ability to set a different default in two places.

**Rationale:** A single read path means raising a limit is a one-line change. The pattern is already used elsewhere in the codebase. The alternative (delete `EngineConfig` defaults entirely and require explicit construction) is more disruptive and breaks existing callers.

**Alternatives considered:**
- *Drop @dataclass defaults entirely* — too disruptive; some call sites construct EngineConfig with kwargs only.
- *Runtime assertion in `__post_init__`* — catches divergence but only when a test actually constructs an EngineConfig with defaults; less reliable than a pytest parity test.

### D2. Raise defaults to evidence-based values, not "round numbers"
**Choice:** Each raise has a per-incident justification (see proposal). Specifically:
- `WATCHDOG_TIMEOUT_VERIFYING`: 300s → 1200s. Empirical e2e gate-suite duration in craftbrew-run-20260423-2223 across 24 specs averaged 12-15 min; 20 min ceiling absorbs flake.
- `DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS`: 3600s → 5400s. ISS-006 in the same run took ~65 min from `diagnosed` to `fix-iss-005` dispatch; 90 min absorbs the chain latency.
- `max_verify_retries`: 8 → 12. Observed verify-retry counts: most changes retry 0-2 times, but `order-cancellation-and-returns` retried 9 times before convergence. 12 leaves slack.
- `MAX_MERGE_RETRIES`: 3 → 5. Three runs hit MAX_MERGE_RETRIES on cross-cutting changes that needed >3 rebases; 5 unblocks them.

**Rationale:** Round numbers ("let's just double everything") would over-allocate in some places and still under-allocate in others. Per-limit evidence prevents the next divergence.

### D3. Hardcoded constants → directive parameters with backward-compatible defaults
**Choice:** Each hardcoded constant gets a corresponding directive name and lookup at use site:
- `MAX_MERGE_RETRIES` → `directives.get("max_merge_retries", DEFAULT)`
- `WATCHDOG_TIMEOUT_RUNNING` → `directives.get("watchdog_timeout_running", DEFAULT)`
- etc.

The constant name remains as a module-level alias for the default value (e.g., `MAX_MERGE_RETRIES = DIRECTIVE_DEFAULTS["max_merge_retries"]`) so external callers and tests don't break.

**Rationale:** Configurability without breaking imports. The constant becomes a documented "default" rather than a hard ceiling.

**Alternatives considered:**
- *Remove the constants entirely* — breaks all `from .merger import MAX_MERGE_RETRIES` imports.
- *Make them properties of an EngineConfig instance* — too invasive; current code paths don't have an EngineConfig in scope at every use site.

### D4. `token_hard_limit` deprecation, not removal
**Choice:** `token_hard_limit` directive is logged at startup if set (`WARNING: token_hard_limit is deprecated, use per_change_token_runaway_threshold`) and ignored. Not removed from the directive parser to avoid breaking existing `orchestration.yaml` files.

**Rationale:** Operators have running setups. A hard removal would crash directive parsing on next reload. Deprecation log gives a 1-2 release window for them to migrate.

### D5. Pre-warning at 80% of `per_change_token_runaway_threshold`
**Choice:** `state.py` token-update path checks if `input_tokens / per_change_token_runaway_threshold >= 0.8` and the same check at the previous update was below 0.8 — emits a `WARNING` log + writes a memory entry under `tags=token-pressure,<change-name>`. One-shot per change (subsequent updates above 80% don't re-warn).

**Rationale:** Operators get visibility before runaway. The memory entry surfaces in future-run `proactive_context` so the planner can flag oversized changes earlier in the next run.

**Alternatives considered:**
- *Hard-stop at 80%* — too aggressive; some changes legitimately use 80%+ of budget.
- *Auto-pause for review* — would block autonomous runs.

### D6. Scoped-subset spec-existence pre-validation in `gate_runner.py`
**Choice:** Before `run_e2e_gate_subset(spec_paths)` enters subset mode, filter `spec_paths` against `Path.exists()`. If 0 valid paths remain → log info, fall through to fallback (own-specs / full) directly without entering subset mode at all.

**Rationale:** The current `Scoped gate: e2e running on N items: [bogus_path]` log is misleading — operators read it as "N specs were targeted" when actually 0 are valid. Filtering before the log eliminates the false signal AND saves the bogus subprocess spawn that would have run zero tests.

### D7. Gate-failure dispatch invariant via regression test, not refactor
**Choice:** Add `tests/unit/test_gate_failure_dispatch.py` that walks every function in `merger.py` and `verifier.py` matching naming pattern `*_gate_*` or `*_handle_failure_*`, parses the AST, and asserts that every code path returning `False`/`fail`/raises a fail-status exception has a `resume_change` call OR an `event_bus.emit("CHANGE_FAILED")` on the same path.

**Rationale:** A pure runtime regression test would be flaky (need to simulate every gate failure mode). A static AST walk is deterministic and catches the pattern that bit `subscription-management`. False positives are tolerable — operator can opt out a specific function with a `# fail-dispatch-exempt` comment.

**Alternatives considered:**
- *Refactor every gate path through a single dispatcher façade* — large surface change, would require re-validating every gate type (build/test/e2e/lint/etc).
- *Rely on integration tests* — too slow, requires full orchestration setup.

## Risks / Trade-offs

**Risk:** Higher retry ceilings could mask broken changes that should fail fast.
**Mitigation:** Token pre-warning at 80% gives early signal; runaway threshold itself unchanged at 50M; wall-time budget still bounded at 90 min.

**Risk:** `WATCHDOG_TIMEOUT_VERIFYING=1200s` means a truly hung agent isn't detected for 20 min.
**Mitigation:** Acceptable trade-off — false-positive kill costs more (lose 30 min of agent state) than late detection (still detected within 30 min total). Operators can override per-project via directive.

**Risk:** AST-based gate-failure dispatch test is brittle to refactors that change function names.
**Mitigation:** Test failure message is actionable ("function X returns fail without dispatch") and the `# fail-dispatch-exempt` escape valve allows targeted opt-outs.

**Risk:** Removing redundant `token_hard_limit` could break operator workflows that relied on it as a soft cap below the runaway threshold.
**Mitigation:** Deprecation-only (still parsed, logged + ignored), giving operators time to migrate.

**Risk:** Single-source-of-truth via `field(default_factory=...)` evaluates `DIRECTIVE_DEFAULTS[key]` at class-definition time — if anything mutates `DIRECTIVE_DEFAULTS` at runtime, the EngineConfig class sees stale values.
**Mitigation:** Add invariant: `DIRECTIVE_DEFAULTS` is `Final[dict]` (or convention-only — no `[]=` writes anywhere). Parity test catches divergence regardless.

## Migration Plan

1. **Phase 1 — config.py canonicalization** (no behavior change yet):
   - Add new directive entries for all soon-to-be-configurable constants.
   - Keep current default values unchanged.
   - Add parity unit test (passes today because values match).

2. **Phase 2 — EngineConfig reads from DIRECTIVE_DEFAULTS** (still no behavior change):
   - `EngineConfig @dataclass` defaults use `default_factory`.
   - Run full pytest; if parity test passes, all existing call sites unchanged.

3. **Phase 3 — Raise defaults**:
   - Update `DIRECTIVE_DEFAULTS` values to evidence-based numbers.
   - Engine and all consumers automatically pick up new defaults.

4. **Phase 4 — Hardcoded → directive lookups**:
   - `merger.py`, `verifier.py`, `watchdog.py`, `issues/models.py`: replace constant uses with `directives.get(key, DEFAULT)`.
   - Add deprecation log for `token_hard_limit`.

5. **Phase 5 — Resilience features**:
   - Token pre-warning in `state.py`.
   - Scoped-subset validation in `gate_runner.py`.
   - Gate-failure dispatch regression test.

**Rollback:** Each phase is independently revertable via `git revert`. No state-file migration. No changes to running orchestrations — new defaults take effect on next sentinel restart.

## Open Questions

- Should `WATCHDOG_TIMEOUT_DISPATCHED` (currently 120s) also be raised? Empirically dispatch-bootstrap takes 30-60s, so 120s seems sufficient. **Decision:** leave at 120s for now, raise only if a future incident shows otherwise.
- Should the parity test also check directive validators (`_VALIDATORS` dict in `config.py`) against `EngineConfig` field types? **Decision:** out of scope for this change — would expand the test surface beyond limit unification. Track as follow-up.
- The `max_stuck_loops` raise (3→5) means an agent in a genuine stuck loop wastes ~2 extra iterations before the breaker fires. Is the visibility worth it? **Decision:** yes — the alternative is false-positive stuck detections on planner-blamed (but actually-progressing) work, which we've seen in 2 runs.
