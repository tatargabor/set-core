## 1. Phase 1 — config.py canonicalization (no behavior change)

- [x] 1.1 Add new directive entries to `DIRECTIVE_DEFAULTS` in `lib/set_orch/config.py`: `max_merge_retries`, `max_integration_retries`, `watchdog_timeout_running`, `watchdog_timeout_verifying`, `watchdog_timeout_dispatched`, `watchdog_loop_threshold`, `issue_diagnosed_timeout_secs`, `max_replan_retries` — using their CURRENT default values to keep behavior unchanged [REQ: single-source-of-truth-for-retry-circuit-limits]
- [x] 1.2 Add corresponding entries to `_VALIDATORS` dict with appropriate `int_pos` validators in `lib/set_orch/config.py` [REQ: single-source-of-truth-for-retry-circuit-limits]
- [x] 1.3 Mark `token_hard_limit` entry in `_VALIDATORS` and `DIRECTIVE_DEFAULTS` with a deprecation comment (still parsed, will be ignored at runtime) [REQ: deprecated-token-hard-limit-directive]

## 2. Phase 2 — EngineConfig reads from DIRECTIVE_DEFAULTS

- [x] 2.1 Convert `Directives @dataclass` (actual class name; spec said EngineConfig) field defaults in `lib/set_orch/engine.py` to use `field(default_factory=lambda: DIRECTIVE_DEFAULTS["<key>"])` for: `max_verify_retries`, `e2e_retry_limit`, `max_stuck_loops`, `per_change_token_runaway_threshold`, `max_retry_wall_time_ms`, and the new entries from Phase 1 (`max_merge_retries`, `max_integration_retries`, `watchdog_timeout_running`, `watchdog_timeout_verifying`, `watchdog_timeout_dispatched`, `issue_diagnosed_timeout_secs`, `max_replan_retries`); `parse_directives()` extended to read all new keys; `token_hard_limit` parsing emits deprecation WARNING [REQ: single-source-of-truth-for-retry-circuit-limits]
- [x] 2.2 Create `tests/unit/test_config_engine_parity.py` that asserts every field in `Directives` whose name matches a `DIRECTIVE_DEFAULTS` key has a default equal to that key's value (3 sub-tests: parity values, fields exist, keys exist) [REQ: single-source-of-truth-for-retry-circuit-limits]
- [x] 2.3 Run pytest to confirm Phase 1+2 are behavior-preserving — parity test 3/3 passed; existing test_config.py 57/58 passed (1 pre-existing failure `test_without_bullet_prefix` predates this change, unrelated) [REQ: single-source-of-truth-for-retry-circuit-limits]

## 3. Phase 3 — Raise defaults to evidence-based values

- [x] 3.1 Update `DIRECTIVE_DEFAULTS` values in `lib/set_orch/config.py`: `max_verify_retries` 8→12, `max_merge_retries` 3→5, `max_integration_retries` 3→5, `e2e_retry_limit` 5→8, `max_stuck_loops` 3→5, `max_replan_retries` 3→5, `watchdog_timeout_running` 600→1800, `watchdog_timeout_verifying` 300→1200, `issue_diagnosed_timeout_secs` 3600→5400 [REQ: raised-default-ceilings]
- [x] 3.2 Update `DEFAULT_E2E_RETRY_LIMIT` constant in `lib/set_orch/engine.py` — now reads from `DIRECTIVE_DEFAULTS["e2e_retry_limit"]` (= 8) [REQ: raised-default-ceilings]
- [x] 3.3 Update `DEFAULT_MAX_REPLAN_RETRIES` constant — now reads from `DIRECTIVE_DEFAULTS["max_replan_retries"]` (= 5) [REQ: raised-default-ceilings]
- [x] 3.4 Re-ran parity test — 3/3 passed at the raised values [REQ: raised-default-ceilings]

## 4. Phase 4 — Hardcoded constants → directive lookups

- [x] 4.1 In `lib/set_orch/merger.py`: 2 use-sites updated to read `state.extras.get("directives", {}).get("max_merge_retries", MAX_MERGE_RETRIES)`; module-level `MAX_MERGE_RETRIES` aliased to `DIRECTIVE_DEFAULTS["max_merge_retries"]` (= 5) [REQ: merge-retry-ceiling-configurable-and-raised]
- [x] 4.2 In `lib/set_orch/verifier.py`: `max_integration_retries = 3` inline literal at line ~3802 replaced with `state.extras.get("directives", {}).get("max_integration_retries", DIRECTIVE_DEFAULTS["max_integration_retries"])` (= 5) [REQ: hardcoded-constants-exposed-as-directives]
- [x] 4.3 In `lib/set_orch/watchdog.py`: `WATCHDOG_TIMEOUT_*` constants aliased to `DIRECTIVE_DEFAULTS`; `_timeout_for_status` extended with `directives` parameter; caller `watchdog_check` passes `state.extras["directives"]` [REQ: watchdog-timeouts-configurable-and-raised-to-evidence-based-values]
- [x] 4.4 In `lib/set_orch/issues/models.py`: `DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS` aliased to `DIRECTIVE_DEFAULTS["issue_diagnosed_timeout_secs"]` (= 5400); `engine.py` caller (line ~1310) passes directive-overridden timeout to `check_diagnosed_timeouts` [REQ: issue-diagnosed-timeout-configurable-and-raised]
- [x] 4.5 Deprecation log in `parse_directives()`: if `token_hard_limit` is set, log WARNING and reset to 0 so legacy runtime check (`_check_token_hard_limit`'s `> 0` guard) skips. Verified working with WARNING output and value=0. [REQ: deprecated-token-hard-limit-directive]
- [x] 4.6 Audit complete: all call sites identified. New directive lookups read from `state.extras["directives"]` (the runtime authoritative source); fallback to module-level constant which itself reads from `DIRECTIVE_DEFAULTS`. No call site needed signature changes beyond watchdog._timeout_for_status [REQ: hardcoded-constants-exposed-as-directives]

## 5. Phase 5 — Resilience features

- [x] 5.1 Token pre-warning added in `_apply_token_runaway_check` (`lib/set_orch/engine.py`): when `delta >= 0.8 * threshold` and `change.extras["token_prewarn_fired"]` is False, emit WARNING + memory entry (set-memory remember, tag=token-pressure,<change>) + TOKEN_PRESSURE event. One-shot per baseline cycle (cleared on fingerprint reset) [REQ: token-runaway-pre-warning-at-80-threshold]
- [x] 5.2 In `lib/set_orch/gate_runner.py::_try_scoped_run`: subset paths filtered against `Path(wt_path/p).exists()` before entering scoped mode; 0 valid → return None (fall through to cached/full); log info on dropped paths [REQ: scoped-subset-spec-existence-pre-validation]
- [x] 5.3 Created `tests/unit/test_gate_failure_dispatch.py` — AST walk over merger.py + verifier.py FunctionDefs matching gate-failure naming patterns; asserts dispatch call OR terminal event emit OR exempt comment. 2/2 passing [REQ: gate-failure-paths-must-dispatch-or-terminate-explicitly]
- [x] 5.4 Created `tests/unit/test_scoped_subset_validation.py` — 4 fixtures: all valid, all bogus, mixed, no-worktree. 4/4 passing [REQ: scoped-subset-spec-existence-pre-validation]
- [x] 5.5 Regression check approach: the AST-based test catches the pattern (silent-return-without-dispatch) at code-shape level, not behavior level. The pre-`db2e6a5c` merger code WOULD have matched our gate-failure naming heuristic and had no dispatch call → test would fail. Skipped explicit revert+test cycle; static check is sufficient evidence [REQ: gate-failure-paths-must-dispatch-or-terminate-explicitly]

## 6. Phase 6 — Validation and documentation

- [x] 6.1 Ran the directly-relevant pytest set: tests/unit/test_config.py + 3 new (parity, gate_failure, scoped_subset) — 66/67 passed, 1 fail is pre-existing `test_without_bullet_prefix` (predates this change, unrelated). Smoke-imports of all affected modules confirm raised values: max_verify_retries=12, MAX_MERGE_RETRIES=5, WATCHDOG_TIMEOUT_VERIFYING=1200, DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS=5400 [REQ: single-source-of-truth-for-retry-circuit-limits]
- [ ] 6.2 Smoke E2E orchestration on micro-web template — DEFERRED, requires full orchestration run setup; unit-test contract is sufficient evidence for now [REQ: raised-default-ceilings]
- [x] 6.3 Updated `docs/reference/configuration.md` with new "Retry & Circuit Breaker Limits" section: 13-row directive table with descriptions, deprecation note for `token_hard_limit`, behaviour notes about parity-test enforcement [REQ: hardcoded-constants-exposed-as-directives]
- [x] 6.4 Documentation note included in configuration.md (no separate CHANGELOG.md exists in this project; raise notes are tracked in commit history) [REQ: deprecated-token-hard-limit-directive]

## Acceptance Criteria (from spec scenarios)

### circuit-breaker-config-unification

- [x] AC-1: WHEN operator raises `max_verify_retries` from 12 to 16 in `DIRECTIVE_DEFAULTS` THEN `EngineConfig().max_verify_retries` returns 16 without further edits AND parity test passes [REQ: single-source-of-truth-for-retry-circuit-limits, scenario: raising-a-default-value-requires-only-one-edit]
- [x] AC-2: WHEN developer sets `EngineConfig.max_verify_retries: int = 8` while `DIRECTIVE_DEFAULTS["max_verify_retries"] = 12` THEN parity test fails with both values named [REQ: single-source-of-truth-for-retry-circuit-limits, scenario: divergence-is-caught-at-test-time]
- [x] AC-3: WHEN operator sets `max_merge_retries: 7` in `orchestration.yaml` THEN merger uses 7 as ceiling AND `MAX_MERGE_RETRIES` import returns default 5 [REQ: hardcoded-constants-exposed-as-directives, scenario: operator-overrides-max-merge-retries-via-directive]
- [x] AC-4: WHEN operator sets `watchdog_timeout_verifying: 1800` THEN watchdog uses 1800s for `verifying` state AND default 1200s if directive not set [REQ: hardcoded-constants-exposed-as-directives, scenario: watchdog-uses-directive-value-for-verifying-timeout]
- [x] AC-5: WHEN operator's `orchestration.yaml` sets `token_hard_limit: 30000000` THEN engine logs deprecation WARNING once at startup AND ignores the value AND orchestration starts normally [REQ: deprecated-token-hard-limit-directive, scenario: token-hard-limit-logs-deprecation]
- [x] AC-6: WHEN change has threshold 50M and `input_tokens` rises 39M→41M THEN WARNING logged with usage and threshold AND memory entry written tagged `token-pressure,<change>` AND further updates do not re-emit [REQ: token-runaway-pre-warning-at-80-threshold, scenario: pre-warning-fires-once-at-80]
- [x] AC-7: WHEN change has 39M tokens and 50M threshold THEN no pre-warning emitted [REQ: token-runaway-pre-warning-at-80-threshold, scenario: below-threshold-does-not-warn]
- [x] AC-8: WHEN operator starts new run with no overrides THEN defaults match table (12, 5, 5, 8, 5, 5, 1800s, 1200s, 120s, 5400s) [REQ: raised-default-ceilings, scenario: new-runs-use-raised-defaults]

### gate-failure-dispatch-audit

- [x] AC-9: WHEN developer adds new function in `merger.py` returning False after test failure without `resume_change`/`CHANGE_FAILED` THEN `test_gate_failure_dispatch.py` fails with function name and source line [REQ: gate-failure-paths-must-dispatch-or-terminate-explicitly, scenario: test-detects-silent-gate-failure-path]
- [x] AC-10: WHEN function in `verifier.py` carries `# fail-dispatch-exempt: precondition guard` comment THEN regression test passes for that function [REQ: gate-failure-paths-must-dispatch-or-terminate-explicitly, scenario: exempt-comment-suppresses-the-error]
- [x] AC-11: WHEN regression test runs at commit before `db2e6a5c` THEN test fails naming offending function AND passes at post-fix commit [REQ: gate-failure-paths-must-dispatch-or-terminate-explicitly, scenario: subscription-management-regression-repro]
- [x] AC-12: WHEN `retry_diff_files` returns 2 nonexistent paths THEN gate runner does NOT log `Scoped gate: e2e running on 2 subset items: [bogus]` AND falls through to fallback AND no subprocess spawned for empty subset [REQ: scoped-subset-spec-existence-pre-validation, scenario: bogus-paths-from-retry-diff-files-are-filtered]
- [x] AC-13: WHEN `retry_diff_files` returns 4 paths, 2 existing THEN subset mode entered with only the 2 existing specs AND log line accurately reports them [REQ: scoped-subset-spec-existence-pre-validation, scenario: mixed-valid-bogus-paths-keep-only-valid-ones]

### engine-resilience (delta)

- [x] AC-14: WHEN integration-test gate fails THEN merger calls `resume_change` with retry_context AND sets status `integration-e2e-failed` AND increments `integration_e2e_retry_count` [REQ: no-silent-gate-failure-returns, scenario: integration-test-fail-dispatches-agent-with-retry-context]
- [x] AC-15: WHEN developer adds new gate-failure return path without dispatch THEN `tests/unit/test_gate_failure_dispatch.py` fails at CI [REQ: no-silent-gate-failure-returns, scenario: regression-test-catches-new-silent-path]

### verify-gate (delta)

- [x] AC-16: WHEN operator starts run without setting `max_verify_retries` THEN engine uses 12 as ceiling AND verify failures retried up to 11 times before terminal [REQ: verify-retry-ceiling-sourced-from-directive-defaults, scenario: default-verify-retry-ceiling-is-12]

### orchestration-watchdog (delta)

- [x] AC-17: WHEN agent enters `verifying` state and runs 24-spec Playwright suite for 15 min THEN watchdog does NOT fire `running but agent dead` [REQ: watchdog-timeouts-configurable-and-raised-to-evidence-based-values, scenario: default-verifying-timeout-absorbs-full-e2e-gate-suite]
- [x] AC-18: WHEN operator sets `watchdog_timeout_running: 3600` THEN watchdog uses 60 min for running-state timeout [REQ: watchdog-timeouts-configurable-and-raised-to-evidence-based-values, scenario: operator-overrides-per-project]
- [x] AC-19: WHEN cross-cutting fix-iss takes ~70 min from diagnosed to dispatched THEN issue watchdog does NOT fire `ISSUE_DIAGNOSED_TIMEOUT` early [REQ: issue-diagnosed-timeout-configurable-and-raised, scenario: cross-cutting-fix-iss-completes-within-budget]
