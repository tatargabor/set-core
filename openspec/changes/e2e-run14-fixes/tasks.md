## 1. Post-merge dependency install fix

- [x] 1.1 In `merger.py` `merge_change()`: capture `pre_merge_sha = git rev-parse HEAD` before the `wt-merge` call (~line 313)
- [x] 1.2 Pass `pre_merge_sha` to `_post_merge_deps_install()` call at ~line 347
- [x] 1.3 Update `_post_merge_deps_install()` signature to accept `pre_merge_sha: str = ""` parameter
- [x] 1.4 Change the diff command from `git diff HEAD~1 --name-only` to `git diff {pre_merge_sha}..HEAD --name-only` when pre_merge_sha is provided, falling back to HEAD~1 when empty

## 2. Spec coverage soft gate

- [x] 2.1 In `verifier.py` `handle_change_done()`: remove `verify_ok = False` from the `VERIFY_RESULT: FAIL` branch (~line 1538) — replace with `logger.warning()` that logs spec coverage as non-blocking
- [x] 2.2 In the VERIFY_GATE event emission: add `spec_coverage_blocking: False` field alongside existing `spec_coverage` field
- [x] 2.3 Remove or skip the spec_coverage-specific retry prompt construction (~line 1571) since it will no longer trigger retries

## 3. Verification

- [x] 3.1 Verify `merger.py` changes: confirm pre_merge_sha is captured and passed correctly, fallback to HEAD~1 works
- [x] 3.2 Verify `verifier.py` changes: confirm spec_coverage=fail no longer triggers retry, VERIFY_GATE event has correct fields
