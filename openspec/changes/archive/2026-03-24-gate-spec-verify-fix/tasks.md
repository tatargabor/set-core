## 1. Fix Gate Logic

- [x] 1.1 In `_execute_spec_verify_gate` (verifier.py:2452-2455), change the `VERIFY_RESULT: FAIL` branch from returning GateResult("pass") to GateResult("fail") with retry_context containing verify output tail and original scope [REQ: spec-verify-gate-shall-block-on-explicit-fail, scenario: verify-result-fail-blocks]
- [x] 1.2 Verify the VERIFY_RESULT: PASS branch remains unchanged (returns pass) [REQ: spec-verify-gate-shall-block-on-explicit-fail, scenario: verify-result-pass-unchanged]
- [x] 1.3 Verify the no-sentinel branch remains unchanged (returns pass with timeout warning) [REQ: spec-verify-gate-shall-block-on-explicit-fail, scenario: timeout-stays-non-blocking]
- [x] 1.4 Verify the CLI non-zero exit branch behavior — currently returns GateResult("fail") with retry_context (line 2441-2448), this is already correct [REQ: spec-verify-gate-shall-block-on-explicit-fail, scenario: cli-error-stays-non-blocking]

## 2. Tests

- [x] 2.1 Unit test: mock run_claude returning output with "VERIFY_RESULT: FAIL" → gate returns "fail" status [REQ: spec-verify-gate-shall-block-on-explicit-fail, scenario: verify-result-fail-blocks]
- [x] 2.2 Unit test: mock run_claude returning output with "VERIFY_RESULT: PASS" → gate returns "pass" [REQ: spec-verify-gate-shall-block-on-explicit-fail, scenario: verify-result-pass-unchanged]
- [x] 2.3 Unit test: mock run_claude returning output without any sentinel → gate returns "pass" [REQ: spec-verify-gate-shall-block-on-explicit-fail, scenario: timeout-stays-non-blocking]
- [x] 2.4 Run existing tests: `python -m pytest tests/unit/test_verifier.py -x` — must pass [REQ: spec-verify-gate-shall-block-on-explicit-fail]
