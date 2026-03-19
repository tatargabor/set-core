## Tasks

### Verify output parsing in verifier.sh

- [x] In `handle_change_done()` Step 6 (~line 1328-1357), after the Claude invocation completes, parse `$verify_output` for sentinel line: grep for `VERIFY_RESULT: PASS` → pass, `VERIFY_RESULT: FAIL` → fail, no sentinel → fail (fail-closed)
- [x] On verify fail, store `spec_coverage_result` as `"fail"` on change state and follow existing retry pattern: increment `verify_retry_count`, build `retry_context` with verify output (truncated to 2000 chars) and original scope, call `resume_change()`
- [x] On verify pass, store `spec_coverage_result` as `"pass"` on change state
- [x] When sentinel line is missing, include in retry_context: "Verify output was unparseable — re-run /opsx:verify and ensure output ends with VERIFY_RESULT: PASS or VERIFY_RESULT: FAIL"

### Verify skill structured output

- [x] In `.claude/skills/openspec-verify-change/SKILL.md`, add a final step after the verification report instructing the LLM to output exactly `VERIFY_RESULT: PASS` (zero CRITICAL) or `VERIFY_RESULT: FAIL critical=N warning=M` (any CRITICAL)
- [x] In `.claude/commands/opsx/verify.md`, add the same sentinel line instruction (both files must stay in sync)

### Review default change

- [x] In `bin/set-orchestrate`, change `DEFAULT_REVIEW_BEFORE_MERGE="false"` to `DEFAULT_REVIEW_BEFORE_MERGE="true"`
- [x] In `tests/test_wt_directory.sh` and `tests/orchestrator/test-orchestrate-integration.sh`, update the corresponding `DEFAULT_REVIEW_BEFORE_MERGE` values to `"true"`

### VERIFY_GATE event enrichment

- [x] Add `scope_check` variable tracking (initialize to `"skipped"`, set to `"pass"` or `"fail"` based on `verify_implementation_scope` result at Step 4)
- [x] Add `spec_coverage` variable tracking (initialize to `"skipped"`, set to `"pass"` or `"fail"` based on verify output parsing at Step 6)
- [x] Read `has_tests` from change state field (already set at Step 4b)
- [x] Add `scope_check`, `has_tests`, and `spec_coverage` to the `emit_event "VERIFY_GATE"` jq call (~line 1367)
