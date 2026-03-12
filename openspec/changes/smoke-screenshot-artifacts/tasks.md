## 1. Smoke artifact collection (merger.sh)

- [x] 1.1 After smoke command completes (pass or fail) in both blocking and non-blocking paths, collect `test-results/` into `wt/orchestration/smoke-screenshots/{change_name}/attempt-{N}/` (where N = smoke_fix_attempts + 1) — use `mkdir -p`, `cp -r`, count `.png` files across ALL attempts for the change, then `update_change_field` for `smoke_screenshot_dir` (parent dir without attempt suffix) and `smoke_screenshot_count` (total across attempts)
- [x] 1.2 After each smoke fix attempt (both pass and fail), collect artifacts into the next `attempt-{N}/` subdirectory — this preserves failure screenshots alongside fix screenshots for full diagnostic history
- [x] 1.3 In the "already merged" paths (Case 1: branch deleted, ~line 62; Case 2: already ancestor, ~line 78), set `smoke_result` to `"skip_merged"` and `smoke_status` to `"skipped"` — use `"skip_merged"` not `"skip"` to disambiguate from "no smoke_command configured"

## 2. Per-change E2E artifact collection (verifier.sh)

- [x] 2.1 After per-change E2E gate completes (~line 1113 in verifier.sh), collect `$wt_path/test-results/` into `wt/orchestration/e2e-screenshots/{change_name}/` in the main project directory, then `update_change_field` for `e2e_screenshot_dir` and `e2e_screenshot_count`

## 3. Multi-change smoke context (merger.sh)

- [x] 3.1 On smoke pass (result = "pass" or "fixed"), record `last_smoke_pass_commit` in state.json via `update_state_field` with current `git rev-parse HEAD` — this is the ONLY place where `last_smoke_pass_commit` gets set (NOT on init)
- [x] 3.2 On smoke fail in the scoped fix prompt, if `last_smoke_pass_commit` is non-empty in state, compute `git log --oneline {sha}..HEAD --merges` and include the merged change list in the fix prompt with instruction: "Multiple changes merged since last smoke pass. Investigate which change or interaction caused the regression." — if `last_smoke_pass_commit` is empty (no smoke has passed yet), skip multi-change context entirely and use single-change context only
- [x] 3.3 On smoke fail in the non-blocking (legacy) LLM fix prompt, include the same multi-change context (with same empty-check guard)

## 4. State initialization (state.sh)

- [x] 4.1 Add `smoke_screenshot_dir: ""`, `smoke_screenshot_count: 0`, `e2e_screenshot_dir: ""`, `e2e_screenshot_count: 0` to the per-change state template in `init_state()`
- [x] 4.2 Add `last_smoke_pass_commit: ""` to the top-level state template in `init_state()`, initialized to empty string (NOT current HEAD — only set after first actual smoke pass to avoid false multi-change blame when main starts broken)

## 5. Report screenshot display (reporter.sh)

- [x] 5.1 In the execution table smoke column, when `smoke_screenshot_count > 0`, append a camera icon (📷 or HTML entity) linked to `../../{smoke_screenshot_dir}`; when `smoke_result == "skip_merged"`, show dash with title attribute "Skipped — already merged from previous phase"; when `smoke_result == "skip"`, show dash with title attribute "Skipped — no smoke command configured"
- [x] 5.2 In the execution table E2E column, when `e2e_screenshot_count > 0`, append a camera icon linked to `../../{e2e_screenshot_dir}`
- [x] 5.3 After the execution table, render a collapsible "Smoke Screenshots" `<details>` section if any change has `smoke_screenshot_count > 0` — show up to 8 thumbnails per change (max-width: 320px) grouped by change name, further grouped by attempt subdirectory, using the same gallery pattern as phase-end E2E (~line 354-366)
- [x] 5.4 After the smoke gallery, render a collapsible "E2E Screenshots" `<details>` section if any change has `e2e_screenshot_count > 0` — up to 8 thumbnails per change, grouped by change name

## 6. Testing

- [x] 6.1 In `tests/orchestrator/test-orchestrate-integration.sh`, add a test case that verifies smoke artifact collection: create a stub smoke command that generates a `test-results/screenshot.png`, run merge+smoke, verify `smoke_screenshot_dir` and `smoke_screenshot_count` in state, verify artifacts are in `attempt-1/` subdirectory
- [x] 6.2 Add a test case for versioned attempt directories: run smoke (fail), then smoke fix (pass), verify both `attempt-1/` and `attempt-2/` exist with their respective screenshots, and `smoke_screenshot_count` reflects the total across both
- [x] 6.3 Add a test case for the already-merged skip status: set up a branch that's already ancestor of HEAD, run merge_change, verify `smoke_result: "skip_merged"` in state (not `"skip"`)
- [x] 6.4 Add a test case for multi-change context: set `last_smoke_pass_commit` in state, merge 2 changes, fail smoke, verify the fix prompt includes both change names
- [x] 6.5 Add a test case for cold start: do NOT set `last_smoke_pass_commit`, fail smoke, verify the fix prompt uses single-change context only (no multi-change blame)
