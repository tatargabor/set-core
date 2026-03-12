## Decision: Structured verify output with sentinel line

The `/opsx:verify` skill already produces a detailed report with CRITICAL/WARNING/SUGGESTION classifications. The problem is the gate can't reliably parse free-form LLM output. Instead of complex NLP parsing, add a mandatory **sentinel line** at the end of the verify output:

```
VERIFY_RESULT: PASS
```
or
```
VERIFY_RESULT: FAIL critical=3 warning=2
```

The gate greps for `^VERIFY_RESULT:` — simple, deterministic, no false positives. If the sentinel line is missing (LLM didn't follow instructions), treat as FAIL (fail-closed).

**Why not parse for "CRITICAL" in the body?** The word "CRITICAL" can appear in recommendations, quotes, or descriptions without meaning the verify failed. A dedicated sentinel line is unambiguous.

## Decision: Review default change is opt-out, not opt-in

Change `DEFAULT_REVIEW_BEFORE_MERGE` from `"false"` to `"true"`. Projects that don't want it can set `review_before_merge: false` in orchestration.yaml. This is defense-in-depth — even if the verify step has issues, the code review catches requirement gaps in digest mode.

## Approach: Verify output parsing in handle_change_done

The verify step (Step 6) currently does:

```bash
verify_output=$( (cd "$wt_path" && echo "Run /opsx:verify $change_name" \
    | run_claude --max-turns 5) 2>&1) || verify_ok=false
```

Change to:

1. Keep the same Claude invocation
2. After completion, grep for `VERIFY_RESULT: PASS` in `$verify_output`
3. If not found, or if `VERIFY_RESULT: FAIL` found → set `verify_ok=false`
4. Extract the full verify output (truncated to 2000 chars) as retry context
5. Follow the existing retry pattern (same as code review retry)

## Approach: VERIFY_GATE event enrichment

Add these fields to the VERIFY_GATE event JSON:

```json
{
  "scope_check": "pass|fail",
  "has_tests": true|false,
  "spec_coverage": "pass|fail|skipped",
  ...existing fields...
}
```

These are already tracked as change state fields but missing from the event emission at line 1367.

## Approach: Skill output format addition

Add to the `/opsx:verify` SKILL.md a final step after generating the report:

> After the report, output exactly one of:
> - `VERIFY_RESULT: PASS` — if zero CRITICAL issues
> - `VERIFY_RESULT: FAIL critical=N warning=M` — if any CRITICAL issues

This is additive — doesn't change the report format, just appends a machine-readable line.

## Risk: LLM may not emit sentinel line

The LLM may ignore the instruction and not output the sentinel line. Mitigation: **fail-closed** — if `VERIFY_RESULT:` is not found in output, treat as failure. This is conservative but safe. The retry will re-run verify, and the LLM will likely emit it the second time. Worst case: a change that actually passes gets one extra verify cycle.
