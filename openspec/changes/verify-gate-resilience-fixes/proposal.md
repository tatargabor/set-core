## Why

Across the last 4 craftbrew/minishop runs the orchestration framework hit **circuit-breaker false positives** that wasted hours of agent time and required operator intervention to unstick. The pattern is consistent:

- **Limit divergence** — `max_verify_retries` is `8` in `config.py` but `6` in `engine.py @dataclass` defaults; `max_retry_wall_time_ms` and `per_change_token_runaway_threshold` had the same drift before being raised. The smaller value silently wins at runtime, so engineers raise one constant thinking they fixed the problem while the other still bites.
- **Hardcoded constants masquerading as defaults** — `MAX_MERGE_RETRIES=3` (`merger.py:148`), `max_integration_retries=3` (`verifier.py:3802` inline literal), `WATCHDOG_TIMEOUT_RUNNING=600s`, `WATCHDOG_TIMEOUT_VERIFYING=300s`, `DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS=3600s` — none configurable via directives, no runtime override.
- **Aggressive ceilings vs reality** — verify e2e gate suites take ~15-20 min, but watchdog "verifying" timeout is 5 min → kills agents mid-suite. Issue diagnosis routinely takes >60 min for cross-cutting bugs but the watchdog flips after 60 min.
- **Lossy retry context** — `subscription-management` integration-test fail looped before `db2e6a5c` because the merger returned without dispatching; same class of bugs likely lurk in other gate paths.
- **Redundant token caps** — `token_hard_limit=20M` and `per_change_token_runaway_threshold=50M` both exist; operators raise one and forget the other.

The fix is a sweep: unify the limit sources, raise defaults to evidence-based values, make hardcoded constants configurable, and add a unit test that pins config↔engine parity so future raises can never silently downgrade.

## What Changes

- Hoist all retry/circuit limits to `config.py DIRECTIVE_DEFAULTS` as **single source of truth**; `EngineConfig @dataclass` defaults read from `DIRECTIVE_DEFAULTS` (no second source).
- Raise default ceilings (evidence-based, see proposal Risks for rationale):
  - `max_verify_retries`: 8 → **12**
  - `MAX_MERGE_RETRIES`: 3 → **5** (now configurable)
  - `max_integration_retries`: 3 → **5** (now configurable)
  - `DEFAULT_E2E_RETRY_LIMIT`: 5 → **8**
  - `max_stuck_loops`: 3 → **5**
  - `DEFAULT_MAX_REPLAN_RETRIES`: 3 → **5**
  - `WATCHDOG_TIMEOUT_RUNNING`: 600s → **1800s** (30 min)
  - `WATCHDOG_TIMEOUT_VERIFYING`: 300s → **1200s** (20 min)
  - `DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS`: 3600s → **5400s** (90 min)
- Make hardcoded constants configurable via directives: `max_merge_retries`, `max_integration_retries`, `watchdog_timeout_running`, `watchdog_timeout_verifying`, `watchdog_timeout_dispatched`, `issue_diagnosed_timeout_secs`.
- **BREAKING (operator-facing)**: remove redundant `token_hard_limit` directive — it overlapped with `per_change_token_runaway_threshold` and confused operators. Migration: any orchestration.yaml setting `token_hard_limit` is logged once at startup and ignored; ops should rely solely on `per_change_token_runaway_threshold`.
- **Pre-warning at 80% of token-runaway threshold**: emit a `WARNING` log + memory entry when a change's input_tokens cross 80% of `per_change_token_runaway_threshold` so operators see the squeeze before the kill.
- **Scoped-subset spec-existence validation** in `gate_runner.py`: when `retry_diff_files` produces a candidate spec list for the e2e scoped gate, filter out entries whose spec file does not exist (`Path.exists()`) before entering subset mode. Without this, the gate logs `Scoped gate: e2e running on N items: [bogus]` then falls back to the full 24-spec suite, wasting ~30 min per retry.
- **Integration-test failure dispatch path audit**: enumerate every gate path in `merger.py` and `verifier.py` that returns a "test failed" signal; verify each one calls `resume_change()` with a populated `retry_context`. Add a regression test that asserts no gate path can return `False` from a fail without a dispatch event being emitted.
- **Config↔Engine parity unit test**: pytest that fails if any field in `EngineConfig` has a default value different from `DIRECTIVE_DEFAULTS[field_name]`.

## Capabilities

### New Capabilities
- `circuit-breaker-config-unification`: single-source-of-truth for all retry/circuit limits between `config.py` and `engine.py`, with parity test.
- `gate-failure-dispatch-audit`: invariant that every gate-failure path dispatches the agent with retry_context, enforced by regression test.

### Modified Capabilities
- `engine-resilience`: add requirement that no gate-failure code path may return without dispatching the agent or emitting a terminal failure event.
- `verify-gate`: raise default `max_verify_retries` ceiling and document how directives override engine defaults.
- `merge-retry`: raise `MAX_MERGE_RETRIES` ceiling, expose as directive `max_merge_retries`.
- `orchestration-watchdog`: raise `WATCHDOG_TIMEOUT_*` defaults to evidence-based values, expose as directives.
- `gate-retry-context`: enforce scoped-subset spec-existence validation before scope mode is entered.

## Impact

**Code:**
- `lib/set_orch/config.py` — `DIRECTIVE_DEFAULTS` becomes single source; new directive entries; remove `token_hard_limit`.
- `lib/set_orch/engine.py` — `EngineConfig @dataclass` defaults read from `DIRECTIVE_DEFAULTS`; raise `DEFAULT_E2E_RETRY_LIMIT`, `DEFAULT_MAX_REPLAN_RETRIES`.
- `lib/set_orch/merger.py` — `MAX_MERGE_RETRIES` constant removed, replaced with directive lookup; ensure all gate-fail paths dispatch agent.
- `lib/set_orch/verifier.py` — `max_integration_retries` inline literal removed, replaced with directive lookup.
- `lib/set_orch/watchdog.py` — `WATCHDOG_TIMEOUT_*` and `WATCHDOG_LOOP_THRESHOLD` raised + directive-overridable.
- `lib/set_orch/issues/models.py` — `DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS` raised + directive-overridable.
- `lib/set_orch/gate_runner.py` — scoped-subset spec-existence pre-validation.
- `lib/set_orch/state.py` — token pre-warning emission at 80% threshold.

**Tests:**
- New unit test: `tests/unit/test_config_engine_parity.py` — asserts all `EngineConfig` defaults equal corresponding `DIRECTIVE_DEFAULTS` entries.
- New regression test: `tests/unit/test_gate_failure_dispatch.py` — every gate-failure return path must dispatch or emit terminal-fail event.
- New unit test: `tests/unit/test_scoped_subset_validation.py` — bogus spec paths filtered before subset mode entry.

**Operator-facing:**
- `orchestration.yaml`: `token_hard_limit` deprecated (logged + ignored); new directives `max_merge_retries`, `max_integration_retries`, `watchdog_timeout_*`, `issue_diagnosed_timeout_secs` available.
- Documentation update: `docs/operator-directives.md` (or equivalent) — limit table.

**Risk surface:**
- Higher retry ceilings could mask genuinely broken changes that should fail fast. Mitigation: token-runaway pre-warning at 80% gives operators visibility before the runaway happens, and the regression test ensures no silent stalls.
- Watchdog timeout raises mean stalled changes take longer to detect. Acceptable trade-off because false-positive kills cost more (lose 30 min of agent work) than late detection (still detected within 30 min).

**Out of scope (deliberate):**
- Layout-pattern divergence detection (covered by sibling change `design-fidelity-deepening`).
- Auto-bisect on token-runaway (would need iter-level snapshot infrastructure — separate change).
- Dispatcher chain refactor for issue-watchdog→fix-iss latency (~30 min observed delay) — this proposal raises the timeout but does not refactor the dispatch chain itself; that is a follow-up.

## Validation evidence — craftbrew-run-20260423-2223

The `.set/issues/registry.json` from this run contains 6 ISS issues; **4 of 6 are direct circuit-breaker false positives** that this change addresses:

| ISS | Trigger reason | Affected change | Outcome with raised limits |
|---|---|---|---|
| ISS-001 | `retry_wall_time_exhausted` (30 min budget hit at iter ~10) | `catalog-product-detail` | Phase 3 raise to 90 min budget eliminates this trigger (90 min covers ~6 retry rounds at ~15 min each). |
| ISS-002 | `token_runaway` (baseline 82M → 102M, +20M delta on 20M old threshold) | `auth-user-registration-and-login` | Phase 3 raise to 50M absorbs sibling-spec convergence pollution; +Pre-warning at 40M gives operator early signal. |
| ISS-003 | `retry_wall_time_exhausted` on stop_gate=`e2e` | `catalog-product-detail` | Same as ISS-001 — 90 min budget. |
| ISS-004 | `retry_wall_time_exhausted` after recovery | `catalog-product-detail` | Same as ISS-001 — 90 min budget. |
| ISS-005 | (no diagnosis) | `order-cancellation-and-returns` | Out of scope. |
| ISS-006 | E2E regression remained after archive | `order-cancellation-and-returns` | Out of scope (post-archive regression — separate concern). |

The bug docs at `docs/bugs/001-public-login-form-not-implemented.md` through `006` document the **downstream impact** of these breakers:
- 3 of 6 user-facing bugs (`bug-001`, `bug-002`, `bug-003`) trace to the **single** `auth-user-registration-and-login` `token_runaway` event. The bug doc itself recommends *"a fix-iss újra-nekifutásnál érdemes csak a két form + cart-merge wiring-re szűkíteni"* — but the underlying scope was within the new 50M threshold, only blocked because the breaker fired at the old 20M.
- The pattern across `catalog-product-detail` (3 separate ISS issues for the same change) shows that with a budget that was actually *tight*, the agent was making forward progress but each retry pushed slightly past the 30 min wall time. The 90 min budget breaks this loop.

**Net effect on a hypothetical re-run with the raised limits:** at least 5 of 6 user-facing bugs (auth flow + cart-merge) would not have been bugs because the owning change would have completed merge. The 6th (admin scope hézag, bug-004/005) is unaffected by this change — see `design-binding-completeness` for partial coverage.
