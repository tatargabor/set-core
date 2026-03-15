## Why

E2E run #14 exposed 2 framework bugs that waste tokens and produce false smoke failures. Both were identified through real orchestration runs and have clear root causes with minimal fixes.

## What Changes

- **Fix post-merge dependency install diff base** — `_post_merge_deps_install()` uses `git diff HEAD~1` which misses `package.json` in multi-commit merges. Change to diff against saved pre-merge SHA. This fixes false smoke failures on every first merge.
- **Make spec_coverage a non-blocking warning** — `spec_coverage_result=fail` currently triggers full agent redispatch (same as build/test failures). Change to log a warning and allow merge. This saves ~80k tokens per occurrence.

## Capabilities

### New Capabilities

- `post-merge-install-fix`: Fix dependency install detection to use pre-merge ref instead of HEAD~1
- `spec-coverage-soft-gate`: Make spec_coverage verification a non-blocking warning instead of retry trigger

### Modified Capabilities

- `verify-gate`: spec_coverage changes from blocking retry gate to non-blocking warning
- `post-merge-verification`: deps install uses pre-merge SHA for accurate diff

## Impact

- `lib/wt_orch/merger.py` — `merge_change()` saves pre-merge SHA, `_post_merge_deps_install()` uses it
- `lib/wt_orch/verifier.py` — `handle_change_done()` spec_coverage block no longer sets `verify_ok = False`
- No API changes, no breaking changes, no new dependencies
