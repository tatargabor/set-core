# Tasks: Cumulative Review Feedback

## Group 1: State helpers

- [x] 1. Add `_append_review_history()` helper to `lib/set_orch/verifier.py` — appends a dict entry to `change.extras["review_history"]` using `locked_state` [REQ: REQ-CRF-01]
- [x] 2. Add `_get_review_history()` helper to `lib/set_orch/verifier.py` — reads `change.extras.get("review_history", [])` from state [REQ: REQ-CRF-02]
- [x] 3. Add `_capture_retry_diff()` to `lib/set_orch/verifier.py` — runs `git diff --stat HEAD~1` in worktree, returns truncated string or None [REQ: REQ-CRF-03]

## Group 2: Write side — append history on CRITICAL review

- [x] 4. In `handle_change_done()` CRITICAL review block (L1771+), before building retry_context: call `_capture_retry_diff()` if `verify_retry_count > 0`, then call `_append_review_history()` with structured entry [REQ: REQ-CRF-01, REQ-CRF-03]

## Group 3: Read side — squashed retry prompt

- [x] 5. Add `_build_review_retry_prompt()` function that reads full `review_history`, builds "PREVIOUS ATTEMPTS" section for attempt 2+, includes current fix instructions and security reference [REQ: REQ-CRF-02, REQ-CRF-04]
- [x] 6. Replace the existing retry_context builder (L1786-1810) with a call to `_build_review_retry_prompt()` [REQ: REQ-CRF-02]
- [x] 7. Add final-attempt escalation: if `verify_retry_count == review_retry_limit - 1`, append "This is your LAST attempt" message [REQ: REQ-CRF-04]

## Group 4: Tests

- [x] 8. Unit test: `_append_review_history` creates and appends to extras.review_history
- [x] 9. Unit test: `_build_review_retry_prompt` with 0, 1, 2 prior attempts — verify "PREVIOUS ATTEMPTS" section presence/absence
- [x] 10. Unit test: final attempt prompt contains "LAST attempt" escalation
