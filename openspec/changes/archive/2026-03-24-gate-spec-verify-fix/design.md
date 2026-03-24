# Design: gate-spec-verify-fix

## Context

The `_execute_spec_verify_gate` function in verifier.py runs Claude with `/opsx:verify` and parses the output for sentinel strings. Currently all three code paths return "pass":

```python
if "VERIFY_RESULT: PASS" in output:    return pass  # correct
elif "VERIFY_RESULT: FAIL" in output:  return pass  # BUG — should be fail
else:                                   return pass  # timeout — acceptable
```

## Goals / Non-Goals

**Goals:**
- Make VERIFY_RESULT: FAIL return a blocking gate failure with retry context
- Keep timeout (no sentinel found) as non-blocking pass with warning

**Non-Goals:**
- Change the spec verify invocation method (still uses `run_claude`)
- Change what `/opsx:verify` checks internally
- Make timeout blocking (too fragile — process-level issues shouldn't block)

## Decisions

### D1: FAIL → GateResult("fail") with retry context

**Decision:** When output contains `VERIFY_RESULT: FAIL`, return a blocking failure.

```python
elif "VERIFY_RESULT: FAIL" in verify_output:
    return GateResult(
        "spec_verify", "fail",
        output=verify_output[:2000],
        retry_context=(
            "Spec verification FAILED — requirements not fully covered.\n\n"
            f"Verify output:\n{verify_output[-2000:]}\n\n"
            f"Original scope: {scope}\n\n"
            "Fix: Ensure all requirements from the scope are implemented and "
            "acceptance criteria are satisfied."
        ),
    )
```

### D2: CLI exit code non-zero stays non-blocking

**Decision:** When `run_claude` returns non-zero exit code (line 2441), keep returning pass. This means the CLI process itself failed (timeout, crash), not that verification found issues.

### D3: Timeout (no sentinel) stays non-blocking

**Decision:** When neither PASS nor FAIL sentinel is found, keep returning pass with warning. This is typically a timeout where the verify process didn't complete.

### Summary of all paths

| Condition | Current | New |
|-----------|---------|-----|
| VERIFY_RESULT: PASS | pass | pass (unchanged) |
| VERIFY_RESULT: FAIL | pass ← BUG | **fail** (blocking) |
| No sentinel (timeout) | pass | pass (unchanged) |
| CLI non-zero exit | pass | pass (unchanged) |
