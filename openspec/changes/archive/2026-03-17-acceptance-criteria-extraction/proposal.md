## Why

The digest pipeline extracts requirements with only a `brief` (1-2 sentence summary), which means implementing agents write tests based on vague scope text and reviewers check coverage against descriptions rather than concrete, verifiable behaviors. Adding structured acceptance criteria at digest time closes the loop between spec intent and test precision — the agent knows exactly what to test, and the reviewer has a concrete checklist.

## What Changes

- **`digest.py`**: Add `acceptance_criteria: []` array to each REQ object in the digest prompt schema; the LLM extracts concrete Given/When/Then or HTTP contract statements from spec scenarios
- **`dispatcher.py` `_build_input_content()`**: Inject the assigned REQ acceptance criteria into `input.md` so the implementing agent sees testable conditions alongside scope
- **`verifier.py` `build_req_review_section()`**: Render AC items as a checkbox list in the review prompt, replacing the vague `brief` with concrete pass/fail checks

## Capabilities

### New Capabilities
- `acceptance-criteria-extraction`: Digest extracts and stores structured `acceptance_criteria` per REQ; AC items flow through to dispatch (input.md) and verify (review prompt)

### Modified Capabilities
- `spec-digest`: REQ schema gains `acceptance_criteria: string[]` field
- `dispatch-input-context`: input.md gains AC-annotated requirement list per change
- `verify-review`: Requirement section renders AC items as checkboxes instead of plain briefs

## Impact

- `lib/set_orch/digest.py`: digest prompt template (`_DIGEST_PROMPT_TEMPLATE`) — add AC extraction instruction + schema field
- `lib/set_orch/dispatcher.py`: `_build_input_content()` — include AC items when building input.md
- `lib/set_orch/verifier.py`: `build_req_review_section()` — render AC checklist in review prompt
- No breaking changes to existing digest output (AC field is additive, absent in old digests gracefully)
- Existing digests without `acceptance_criteria` degrade gracefully: dispatcher and verifier fall back to `brief`
