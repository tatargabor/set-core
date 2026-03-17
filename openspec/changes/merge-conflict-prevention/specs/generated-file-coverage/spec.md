# Generated File Coverage Expansion

## Requirements

### GF-1: wt-merge GENERATED_FILE_PATTERNS
Add to the bash array in `bin/wt-merge`:
- `coverage/**` — test coverage output directories
- `node_modules/**` — pnpm/npm symlinks (Bug #37 root cause)

These are already handled by `_FRAMEWORK_NOISE_PREFIXES` in `git_utils.py` but missing from the wt-merge bash script's pattern list.

### GF-2: Pattern consistency
The following pattern lists MUST be kept in sync:
- `bin/wt-merge` `GENERATED_FILE_PATTERNS` (bash array)
- `lib/wt_orch/dispatcher.py` `_CORE_GENERATED_FILE_PATTERNS` + `_AUTO_RESOLVE_PREFIXES`
- `lib/wt_orch/git_utils.py` `_FRAMEWORK_NOISE_PREFIXES`

All three serve different purposes (merge resolution, sync auto-resolve, dirty-check filtering) but MUST agree on which paths are framework-generated.

## Acceptance Criteria

- `coverage/lcov-report/index.html` matches `is_generated_file()` in wt-merge → true
- `node_modules/.bin/jest` matches `is_generated_file()` in wt-merge → true
- Merge conflict involving only coverage/ + node_modules/ files auto-resolves without LLM
