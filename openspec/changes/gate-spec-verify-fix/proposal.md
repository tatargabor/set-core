# Proposal: gate-spec-verify-fix

**Series: programmatic-gate-enforcement (3/4)**

## Why

The spec_verify gate in the verify pipeline is effectively a no-op: it returns "pass" for ALL outcomes including explicit FAIL and timeout. The gate calls Claude to run `/opsx:verify`, parses the output for `VERIFY_RESULT: PASS` or `VERIFY_RESULT: FAIL` sentinels, but then returns GateResult("pass") regardless of the result. This means specification coverage failures never block a merge.

The gate was likely made non-blocking during early development when spec verification was unreliable, but it should now enforce coverage when the verifier reports a clear FAIL.

## What Changes

- **FAIL means FAIL**: When the verify output contains `VERIFY_RESULT: FAIL`, return GateResult("fail") with retry_context instead of silently passing
- **Timeout stays non-blocking**: When no sentinel is found (timeout), continue returning "pass" with a warning — timeout is not a definitive failure
- **CLI error stays non-blocking**: When the claude CLI exits non-zero (process error), keep returning "pass" — infrastructure failures shouldn't block merges
- **Retry context**: On FAIL, provide the verification output as retry_context so the agent can fix coverage gaps

## Capabilities

### Modified Capabilities
- `verify-gate`: spec_verify gate now blocks on explicit VERIFY_RESULT: FAIL

## Impact

- **Files modified**: `lib/set_orch/verifier.py` (_execute_spec_verify_gate — ~10 lines changed)
- **Risk**: Very low — single conditional change. Only affects changes where spec verification explicitly reports FAIL.
- **Tests**: Update existing spec_verify gate test to verify fail → fail behavior
