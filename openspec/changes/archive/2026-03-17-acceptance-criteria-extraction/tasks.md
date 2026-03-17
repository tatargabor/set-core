## 1. Digest — schema + prompt

- [x] 1.1 Add `acceptance_criteria: string[]` field to the digest prompt JSON output schema in `_DIGEST_PROMPT_TEMPLATE` (digest.py) [REQ: requirement-extraction]
- [x] 1.2 Add AC extraction instruction to the prompt: "For each requirement, extract up to 5 concrete, verifiable acceptance criteria from spec scenarios — HTTP contracts, state assertions, error responses. Use `[]` if none found." [REQ: requirement-extraction]
- [x] 1.3 Update `DigestResult.requirements` list structure note in `_dict_to_digest_result()` — no code change needed if field passes through naturally (verify) [REQ: requirement-extraction]
- [x] 1.4 Update `validate_digest()` to accept (not require) `acceptance_criteria` — warn if field missing entirely from a freshly generated digest, but don't block [REQ: requirement-extraction]

## 2. Dispatcher — AC injection into input.md

- [x] 2.0 Extend `_build_input_content()` signature to accept `change_requirements: list[str] | None` and `digest_dir: str | None`; update call site in `_setup_change_in_worktree()` to pass these values from the `Change` object and `DispatchContext` [REQ: dispatch-context-written-to-input-md]
- [x] 2.1 In `_build_input_content()`, load `acceptance_criteria` per REQ from `requirements.json` (via `digest_dir`) when building a new `## Assigned Requirements` section [REQ: dispatch-context-written-to-input-md]
- [x] 2.2 Render AC items as a bullet list under each assigned REQ — format: `  - <ac item>` [REQ: dispatch-context-written-to-input-md]
- [x] 2.3 Fallback: if `acceptance_criteria` is absent or `[]`, or if `digest_dir` is None/missing, render `REQ-ID: title — brief` (new behavior matching verifier's existing pattern) [REQ: dispatch-context-written-to-input-md]
- [x] 2.4 Cross-cutting REQs (`also_affects_reqs`): title-only, no AC items (new behavior matching verifier's existing cross-cutting pattern) [REQ: dispatch-context-written-to-input-md]

## 3. Verifier — AC checkboxes in review prompt

- [x] 3.1 In `build_req_review_section()` (verifier.py), load `acceptance_criteria` per REQ from `requirements.json` [REQ: requirement-review-section-builder]
- [x] 3.2 Render AC items as `- [ ] <ac item>` checkboxes under each assigned REQ [REQ: requirement-review-section-builder]
- [x] 3.3 Update "Requirement Coverage Check" instruction block: when AC items are present, replace the coarse-grained `ISSUE: [CRITICAL] REQ-ID has no implementation` with per-AC-item checks — `ISSUE: [CRITICAL] REQ-ID: "<ac item>" not implemented`. When AC is absent (old digest), retain the existing coarse check as fallback. [REQ: requirement-review-section-builder]
- [x] 3.4 Fallback: if `acceptance_criteria` is absent or `[]`, emit `- REQ-ID: title — brief` (existing behavior) [REQ: requirement-review-section-builder]

## 4. Tests

- [x] 4.1 Unit test: `validate_digest()` accepts a requirement with `acceptance_criteria: []` and with a populated array [REQ: requirement-extraction]
- [x] 4.2 Unit test: `_build_input_content()` emits AC bullet list when requirements.json has `acceptance_criteria`; falls back to brief when absent [REQ: dispatch-context-written-to-input-md]
- [x] 4.3 Unit test: `build_req_review_section()` emits checkboxes when AC present; falls back to brief when absent [REQ: requirement-review-section-builder]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN spec has explicit WHEN/THEN scenarios THEN `acceptance_criteria` array is populated with concrete strings [REQ: requirement-extraction, scenario: ac-extracted-from-explicit-spec-scenarios]
- [x] AC-2: WHEN spec is vague THEN `acceptance_criteria` is `[]` and `brief` is populated [REQ: requirement-extraction, scenario: ac-array-empty-when-spec-is-vague]
- [x] AC-3: WHEN old digest lacks `acceptance_criteria` THEN consumers fall back to `brief` without error [REQ: requirement-extraction, scenario: old-digest-files-without-ac-field]
- [x] AC-4: WHEN dispatching with requirements that have AC THEN input.md lists AC items as bullets under each REQ [REQ: dispatch-context-written-to-input-md, scenario: ac-items-injected-into-input-md-for-assigned-reqs]
- [x] AC-5: WHEN dispatching with requirements without AC THEN input.md shows `REQ-ID: title — brief` [REQ: dispatch-context-written-to-input-md, scenario: fallback-to-brief-when-ac-absent]
- [x] AC-6: WHEN review prompt is built with AC THEN each AC item appears as `- [ ] <item>` checkbox [REQ: requirement-review-section-builder, scenario: ac-items-rendered-as-checkboxes-in-review-prompt]
- [x] AC-7: WHEN diff has no evidence for an AC item THEN reviewer flags `ISSUE: [CRITICAL] REQ-ID: "<ac item>" not implemented` [REQ: requirement-review-section-builder, scenario: reviewer-flags-unimplemented-ac-item-as-critical]
