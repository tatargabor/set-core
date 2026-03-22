## 1. Lint gate: comment-aware matching

- [x] 1.1 Update `_extract_added_lines()` in `modules/web/set_project_web/gates.py`: add `skip_comments` param (default True), filter out lines starting with `//`, `*`, `#`, `/**`, `* ` [REQ: lint-gate-shall-skip-comment-lines]
- [x] 1.2 Unit test: comment line with forbidden pattern → no match [REQ: lint-gate-shall-skip-comment-lines, scenario: comment-mentioning-forbidden-pattern-passes]
- [x] 1.3 Unit test: actual code usage → still matched [REQ: lint-gate-shall-skip-comment-lines, scenario: actual-code-usage-still-caught]

## 2. Review gate: fix-verification mode

- [x] 2.1 In `_execute_review_gate()` (`lib/set_orch/verifier.py`): when `verify_retry_count > 0`, prepend fix-verification instructions to review prompt — "ONLY verify previous findings were fixed, do NOT scan for new issues" [REQ: review-gate-shall-use-fix-verification-mode-on-retries]
- [x] 2.2 Read previous review findings from `review-findings.jsonl` and include in retry prompt as the checklist to verify [REQ: review-gate-shall-use-fix-verification-mode-on-retries]

## 3. Review extra_retries default

- [x] 3.1 Change `review_extra_retries` default from 3 to 1 in `GateConfig.__init__()` (`lib/set_orch/gate_profiles.py`) [REQ: review-extra-retries-default-shall-be-1]
- [x] 3.2 Change `extra_retries` default in `handle_change_done` review registration from `getattr(gc, "review_extra_retries", 1)` (already 1, verify) [REQ: review-extra-retries-default-shall-be-1]

## 4. Tests

- [x] 4.1 Run existing tests: must all pass [REQ: lint-gate-shall-skip-comment-lines]
