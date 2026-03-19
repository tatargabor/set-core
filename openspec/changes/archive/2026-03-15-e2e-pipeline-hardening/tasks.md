## 1. Uncommitted Work Detection

- [x] 1.1 Create `git_has_uncommitted_work(wt_path) -> tuple[bool, str]` in `lib/set_orch/git_utils.py` (new file, shared by loop_tasks and verifier) — runs `git status --porcelain` with 10s timeout, parses output into counts (modified, untracked), returns `(has_work, summary)`. Fail-open on timeout/error.
- [x] 1.2 Add uncommitted pre-check to `is_done()` in `loop_tasks.py` — before evaluating any done_criteria (except `manual`), call `git_has_uncommitted_work()`. If True, return False immediately. Import from `git_utils`.
- [x] 1.3 Unit tests for `git_has_uncommitted_work()` — test clean worktree, modified files, untracked files, git timeout, git error scenarios in `tests/unit/test_git_utils.py`
- [x] 1.4 Unit tests for `is_done()` uncommitted pre-check — test all non-manual criteria (`test`, `tasks`, `build`, `merge`, `openspec`) return False when uncommitted work exists, and `manual` skips the check. In `tests/unit/test_loop_tasks.py`.

## 2. Verify Gate Uncommitted Guard

- [x] 2.1 Add uncommitted-check step to `handle_change_done()` in `lib/set_orch/verifier.py` — insert before VG-BUILD step (after merge-rebase fast path early return). Import `git_has_uncommitted_work` from `git_utils`. If returns True, set `verify_ok = False` with reason including summary.
- [x] 2.2 Confirm merge-rebase fast path already prevents uncommitted check — verify the early return at ~line 1189 runs before the new guard. Add a code comment noting this.
- [x] 2.3 Include `uncommitted_check` result in VERIFY_GATE event — add field to gate timing/results
- [x] 2.4 Unit test for verify gate uncommitted guard in `tests/unit/test_verifier.py`

## 3. Startup Guide Generator

- [x] 3.1 Create `generate_startup_guide(wt_path) -> str` function in `lib/set_orch/dispatcher.py` — detect PM from lockfile, framework dev command from package.json scripts, DB tool (Prisma/Drizzle) from dependencies, Playwright config existence. Return markdown section content.
- [x] 3.2 Create `append_startup_guide_to_claudemd(wt_path)` function — read CLAUDE.md, check for existing `## Application Startup`, append if absent, create file if missing. Idempotent: never overwrite existing section.
- [x] 3.3 Insert `append_startup_guide_to_claudemd(wt_path)` call in `dispatch_change()` between `_setup_change_in_worktree()` and `dispatch_via_wt_loop()` calls
- [x] 3.4 Unit tests for startup guide generation — test Next.js+Prisma+Playwright project, minimal project, already-has-section idempotency

## 4. Build-Inclusive Smoke Command

- [x] 4.1 Add `auto_detect_smoke_command(directory) -> str` to `lib/set_orch/config.py` — resolution chain: explicit config → build+test → test_command fallback. Detect build script from package.json, combine with PM.
- [x] 4.2 Wire `auto_detect_smoke_command()` into directive resolution in `config.py` `resolve_directives()` — when `smoke_command` is empty after config load, call `auto_detect_smoke_command(".")` and set the result. This ensures callers of `handle_change_done()` receive the resolved value.
- [x] 4.3 Unit tests for smoke command auto-detection — test with build script present, without build script, with explicit config override

## 5. Template Updates (set-project-web)

- [x] 5.1 Update `wt_project_web/planning_rules.txt` — add instruction that infrastructure/foundational changes MUST update CLAUDE.md Application Startup section when adding new setup steps
- [x] 5.2 Update `wt_project_web/templates/nextjs/rules/testing-conventions.md` — add note about startup guide maintenance in infrastructure bootstrap section
- [x] 5.3 Verify `headless: true` is in all Playwright config templates (already done — confirm no regressions)

## 6. Integration Verification

- [x] 6.1 Run existing unit tests (`python -m pytest tests/unit/ -x`) — confirm no regressions
- [x] 6.2 Verify the uncommitted guard works end-to-end: create a temp worktree with uncommitted files, call `is_done("test")`, confirm it returns False
- [x] 6.3 Note for spec archive: when merging verify-gate delta spec into canonical spec, append the 3 new uncommitted-check scenarios alongside existing gate-profiles scenarios — do not replace them
