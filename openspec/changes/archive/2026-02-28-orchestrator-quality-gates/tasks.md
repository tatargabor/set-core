## 1. Worktree Bootstrap

- [x] 1.1 Add `bootstrap_env_files()` to `bin/wt-new` — copies `.env`, `.env.local`, `.env.development`, `.env.development.local` from main project if they exist
- [x] 1.2 Add `bootstrap_dependencies()` to `bin/wt-new` — detects PM from lockfile (pnpm/yarn/bun/npm), runs install if `package.json` exists and `node_modules` doesn't
- [x] 1.3 Call both bootstrap functions in `main()` after worktree creation, before hook deploy

## 2. Verify Gate — Test File Check

- [x] 2.1 Add step 3b in `handle_change_done` after opsx:verify — count `*.test.*` / `*.spec.*` files in the branch diff
- [x] 2.2 Log WARNING and send notification if zero test files; store `has_tests` boolean in state

## 3. Verify Gate — Build Verification

- [x] 3.1 Add step 4 in `handle_change_done` — detect build command from `package.json` (`build:ci` or `build`)
- [x] 3.2 Auto-detect package manager from lockfile for `$pm run $build_command`
- [x] 3.3 On failure: retry with build error context (same mechanism as test failures)
- [x] 3.4 On permanent failure: set status `"failed"`, send critical notification
- [x] 3.5 Update gate total log line to include `build=Nms`

## 4. Scope Overlap Detection

- [x] 4.1 Add `check_scope_overlap()` function — extracts lowercase keywords (3+ chars) from each change scope, computes pairwise jaccard similarity
- [x] 4.2 Warn at 40%+ overlap between plan-internal change pairs
- [x] 4.3 Compare new plan scopes against active worktrees (running/dispatched/done) in state file
- [x] 4.4 Call from `validate_plan()` after circular dependency check
- [x] 4.5 Send notification with total overlap warning count
