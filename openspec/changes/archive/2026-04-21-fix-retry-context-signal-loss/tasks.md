# Tasks: fix-retry-context-signal-loss

## 1. Bug A — E2E retry_context tail preservation (module/web)

- [x] 1.1 Replace `e2e_output[:2000]` in `modules/web/set_project_web/gates.py:645` with `smart_truncate_structured(e2e_output, 6000)` import from `set_orch.truncate` [REQ: e2e-gate-retry-context-preserves-error-tail-evidence]
- [x] 1.2 Verify the `e2e_output_header` (failing-test header) remains prepended verbatim before the truncated body so the `"E2E: N NEW failures"` line and test list are always visible [REQ: e2e-gate-retry-context-preserves-error-tail-evidence]
- [x] 1.3 Add unit test `tests/unit/test_gate_e2e_retry_context.py` with a synthetic Playwright output: prisma setup noise (10k chars) + test list (5k) + assertion error at the tail (2k). Assert retry_context contains at least one error-marker line from the tail (`Error:`, `expected`, `Timeout`, or the assertion message) [REQ: e2e-gate-retry-context-preserves-error-tail-evidence]
- [x] 1.4 Add regression test asserting retry_context does NOT end with `"Running generate... ["` (the literal truncation symptom observed in the run) [REQ: e2e-gate-retry-context-preserves-error-tail-evidence]
- [x] 1.5 Add passthrough test: output shorter than budget appears verbatim without truncation markers [REQ: e2e-gate-retry-context-preserves-error-tail-evidence]

## 2. Bug B — spec_verify three-category classification (core)

- [x] 2.1 Extract a helper `_classify_spec_verify_outcome(cmd_result, verify_output) -> Literal["verdict", "infra", "ambiguous"]` in `lib/set_orch/verifier.py` [REQ: spec-verify-gate-shall-distinguish-llm-verdict-from-infrastructure-failure]
- [x] 2.2 Parse the stream-json output for `terminal_reason` field. If it equals `"max_turns"` AND no `VERIFY_RESULT` sentinel is present, classify as `"infra"`. If the `run_claude_logged` result has `timed_out=True`, classify as `"infra"` regardless of output. Otherwise, if a `VERIFY_RESULT: PASS|FAIL` sentinel is present, classify as `"verdict"`. Else `"ambiguous"` [REQ: spec-verify-gate-shall-distinguish-llm-verdict-from-infrastructure-failure]
- [x] 2.3 Replace the current `if verify_cmd_result.exit_code != 0:` branch in `_execute_spec_verify_gate` with classification-based dispatch: verdict → existing sentinel paths (VERIFY_RESULT PASS/FAIL); infra → infra-retry then abstain; ambiguous → existing classifier fallback [REQ: spec-verify-gate-shall-distinguish-llm-verdict-from-infrastructure-failure]
- [x] 2.4 Implement infra retry: on first infra classification, invoke opus once more with `--max-turns` doubled (40 → 80). If the retry also classifies as infra, return `GateResult("spec_verify", "skipped")` with empty `retry_context` [REQ: spec-verify-gate-shall-distinguish-llm-verdict-from-infrastructure-failure]
- [x] 2.5 On skipped-infra outcome, do NOT call `_persist_spec_verify_verdict` with verdict="fail". Persist verdict="skipped" with `source="infra_fail"` and a brief summary of the terminal_reason [REQ: spec-verify-gate-shall-distinguish-llm-verdict-from-infrastructure-failure]
- [x] 2.6 Verify `gate_runner.py` treats `"skipped"` result status as non-blocking and does NOT increment `verify_retry_count` (already the case per `_GateEntry.blocking=False` when status is skipped — confirm by reading `lib/set_orch/gate_runner.py` and adding a comment if any code path touches skipped differently) [REQ: spec-verify-gate-shall-distinguish-llm-verdict-from-infrastructure-failure]
- [x] 2.7 Emit `VERIFY_GATE` event with `data.infra_fail=True` and `data.terminal_reason=<max_turns|timeout>` alongside existing data when the gate abstains. Add the field in `lib/set_orch/gate_runner.py` where gate events are emitted, reading the flag from the GateResult (new optional attribute `GateResult.infra_fail: bool = False`) [REQ: spec-verify-gate-shall-distinguish-llm-verdict-from-infrastructure-failure]
- [x] 2.8 Unit test `tests/unit/test_spec_verify_classification.py`: three scenarios — LLM with `VERIFY_RESULT: PASS` → verdict/pass; LLM stream-json with `terminal_reason:"max_turns"` + no sentinel → infra; both attempts infra → skipped with infra_fail flag on event [REQ: spec-verify-gate-shall-distinguish-llm-verdict-from-infrastructure-failure]
- [x] 2.9 Unit test: real `VERIFY_RESULT: FAIL` + CRITICAL_COUNT=2 with exit_code=1 still produces `GateResult("spec_verify", "fail")` with structured retry_context (sentinel is authoritative over exit_code) [REQ: spec-verify-gate-shall-distinguish-llm-verdict-from-infrastructure-failure]

## 3. Bug C — unit test gate default in web template

- [x] 3.1 Edit `modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml` to uncomment the `test_command: pnpm test` line and add a brief comment above it noting "no-op when no test files exist" [REQ: default-web-template-enables-the-unit-test-gate]
- [x] 3.2 Inspect the test gate's skipped-on-no-tests handling in `lib/set_orch/verifier.py` (or wherever the test gate lives) and confirm the vitest "no tests found" output path leads to a `skipped` classification. Add a code comment at that site if the path is nontrivial [REQ: default-web-template-enables-the-unit-test-gate]
- [x] 3.3 Update `tests/e2e/scaffolds/*/scaffold.yaml` (if any override `test_command`) to remain consistent or intentionally override — document each override [REQ: default-web-template-enables-the-unit-test-gate]
- [x] 3.4 Add integration-style test that runs `set-project init --project-type web --template nextjs` in a temp dir and asserts the generated `set/orchestration/config.yaml` contains a non-commented `test_command:` line [REQ: default-web-template-enables-the-unit-test-gate]

## 4. Broader truncation audit sites (core)

- [x] 4.1 Replace `e2e_output[:8000]` at `lib/set_orch/verifier.py:2008` with `smart_truncate_structured(e2e_output, 8000)`. Rationale: this feeds `phase_e2e_failure_context` into replan context; assertion errors at the tail were being dropped same as Bug A [REQ: e2e-gate-retry-context-preserves-error-tail-evidence]
- [x] 4.2 Replace `rr.output[:1500]` at `lib/set_orch/verifier.py:2764` (review_history persistence) with `smart_truncate_structured(rr.output, 1500)`. The review output is LLM reasoning — tail contains conclusions/verdicts and must be preserved [REQ: e2e-gate-retry-context-preserves-error-tail-evidence]
- [x] 4.3 Add a source-level audit test `tests/unit/test_no_head_only_llm_slices.py` that scans `lib/set_orch/**/*.py` and `modules/**/*.py` for patterns matching `_output\[:\d+\]` or `stdout\[:\d+\]` on variables passed into `retry_context=` or string-formatted into templates that become retry_context / replan context. The test SHOULD allowlist the three cosmetic sites (`cli.py:693`, `orch_memory.py:150`, `planner.py:1949`) explicitly by line number or a `# noqa: signal-loss` comment and SHOULD fail for any new head-only slice on LLM-bound output [REQ: e2e-gate-retry-context-preserves-error-tail-evidence]

## 5. Observability

- [x] 5.1 Add `infra_fail: bool` optional field to `GateResult` dataclass in `lib/set_orch/gate_runner.py` (default False). Populate in the spec_verify abstain path. Include in the `data` payload of the `VERIFY_GATE` event when True [REQ: spec-verify-gate-shall-distinguish-llm-verdict-from-infrastructure-failure]
- [x] 5.2 Ensure existing dashboards/event consumers that parse `VERIFY_GATE` treat unknown data keys as no-ops (verify `lib/set_orch/api/sentinel.py`, web `web/src/lib/dag/journalToAttemptGraph.ts`, and any status renderer). Add a passthrough test if needed [REQ: spec-verify-gate-shall-distinguish-llm-verdict-from-infrastructure-failure]
- [x] 5.3 Log at WARNING when spec_verify abstains on infra_fail: include change name, terminal_reason, both attempt durations, and token totals (infrastructure failures with expensive opus re-runs are a cost signal worth surfacing) [REQ: spec-verify-gate-shall-distinguish-llm-verdict-from-infrastructure-failure]

## 6. Documentation

- [x] 6.1 Update `lib/set_orch/truncate.py` module docstring (or `openspec/specs/smart-truncate/spec.md` Application Sites table) to list the newly-migrated sites (`gates.py:645`, `verifier.py:2008`, `verifier.py:2764`) [REQ: e2e-gate-retry-context-preserves-error-tail-evidence]
- [x] 6.2 Add a short section to `docs/` (or an existing gate-debugging doc) titled "Distinguishing infra failure from verdict failure" summarizing the three-category spec_verify logic and the `infra_fail` event field [REQ: spec-verify-gate-shall-distinguish-llm-verdict-from-infrastructure-failure]

## Acceptance Criteria (from spec scenarios)

### E2E retry_context preservation

- [x] AC-1: WHEN `e2e_output` is 32000 chars with assertion errors in the last 5000 chars THEN retry_context contains at least one error-marker line preserved from the tail or middle [REQ: e2e-gate-retry-context-preserves-error-tail-evidence, scenario: playwright-output-with-assertion-errors-at-the-tail]
- [x] AC-2: WHEN `e2e_output` is 3000 chars and the budget is 6000 THEN full output appears without truncation markers [REQ: e2e-gate-retry-context-preserves-error-tail-evidence, scenario: output-within-budget-is-passed-through-unchanged]
- [x] AC-3: WHEN 33 tests fail THEN the failing-test header appears verbatim before the truncated output [REQ: e2e-gate-retry-context-preserves-error-tail-evidence, scenario: failing-test-header-is-preserved-regardless-of-truncation]

### Unit test gate default

- [x] AC-4: WHEN `set-project init --project-type web --template nextjs` runs against a clean repo THEN generated `config.yaml` contains an active (uncommented) `test_command: pnpm test` entry [REQ: default-web-template-enables-the-unit-test-gate, scenario: fresh-consumer-project-has-active-test-command]
- [x] AC-5: WHEN `test_command: pnpm test` runs and no test files exist THEN gate classifies as `skipped` not `fail` [REQ: default-web-template-enables-the-unit-test-gate, scenario: unit-test-gate-is-a-no-op-when-no-tests-exist]

### spec_verify classification

- [x] AC-6: WHEN sonnet returns `terminal_reason: max_turns` AND opus escalation also max_turns AND infra-retry also max_turns THEN gate returns `GateResult("spec_verify", "skipped")` with `infra_fail=True` and `verify_retry_count` unchanged [REQ: spec-verify-gate-shall-distinguish-llm-verdict-from-infrastructure-failure, scenario: llm-hits-max-turns-on-both-sonnet-and-opus]
- [x] AC-7: WHEN LLM output contains `VERIFY_RESULT: FAIL` and `CRITICAL_COUNT: 2` THEN gate returns fail with structured finding list, NOT raw stream-json transcript [REQ: spec-verify-gate-shall-distinguish-llm-verdict-from-infrastructure-failure, scenario: llm-produces-verify-result-fail-with-critical-findings]
- [x] AC-8: WHEN LLM output contains `VERIFY_RESULT: PASS` THEN gate returns pass regardless of exit_code value [REQ: spec-verify-gate-shall-distinguish-llm-verdict-from-infrastructure-failure, scenario: llm-produces-verify-result-pass]
- [x] AC-9: WHEN `run_claude_logged` times out with no sentinel THEN gate retries once with doubled max-turns, then abstains if still timeout [REQ: spec-verify-gate-shall-distinguish-llm-verdict-from-infrastructure-failure, scenario: run-exit-is-timeout-subprocess-timeout-not-max-turns]
- [x] AC-10: WHEN exit_code != 0 AND `VERIFY_RESULT: FAIL` sentinel is present THEN gate still returns fail with structured retry_context (sentinel authoritative over exit_code) [REQ: spec-verify-gate-shall-distinguish-llm-verdict-from-infrastructure-failure, scenario: legacy-cli-error-stays-non-blocking-replaced]
