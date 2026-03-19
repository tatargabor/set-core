## 1. State Initialization Fix (prerequisite for everything)

- [x] 1.1 In `lib/orchestration/state.sh` `init_state()`, add logic to copy `requirements[]` and `also_affects_reqs[]` from each plan change entry to the state change object (using jq). Only copy if the fields exist in the plan (non-digest plans won't have them).
- [x] 1.2 Add test: create a mock digest-mode plan with requirements and also_affects_reqs, run init_state, verify the fields appear in orchestration-state.json per change
- [x] 1.3 Add test: create a mock brief-mode plan without requirements fields, run init_state, verify no empty arrays are added

## 2. Digest Prompt Granularity

- [x] 2.1 In `lib/orchestration/digest.sh` `build_digest_prompt()`, find the existing granularity paragraph (near "One requirement = one independently testable behavior" ~line 288) and EXTEND it with additional rules: CRUD = 4+ REQs, compound "X and Y" = 2 REQs, edge cases = separate REQs, one behavior per REQ. Do NOT duplicate the existing example.
- [x] 2.2 Add test in `tests/orchestrator/test-digest-integration.sh`: verify the granularity rules text appears in the built prompt (grep for "CRUD" and "compound" in prompt output)

## 3. Require Full Coverage Directive

- [x] 3.1 Add `require_full_coverage` directive support: read from directives JSON in `cmd_plan` using `$(echo "$directives" | jq -r '.require_full_coverage // false')`, export as `REQUIRE_FULL_COVERAGE` for `populate_coverage()` to read
- [x] 3.2 Document `require_full_coverage` in `docs/orchestration.md` directives table

## 4. Coverage Enforcement at Plan Time

- [x] 4.1 Modify `populate_coverage()` in `lib/orchestration/digest.sh`: after computing `uncovered[]`, check `REQUIRE_FULL_COVERAGE`. If true and uncovered is non-empty, emit error with uncovered REQ-IDs and return 1. If false, emit warning (existing behavior) and return 0.
- [x] 4.2 Modify `cmd_plan` call site in `lib/orchestration/planner.sh`: change bare `populate_coverage "$PLAN_FILENAME"` to `if ! populate_coverage "$PLAN_FILENAME"; then error "Plan validation failed: incomplete requirement coverage"; return 1; fi`
- [x] 4.3 Handle cross-cutting REQs: if a REQ-ID is in `also_affects_reqs[]` of some changes but in `requirements[]` of none, include it in uncovered[] with a note about which also_affects changes reference it
- [x] 4.4 Add test: plan with uncovered REQs + `REQUIRE_FULL_COVERAGE=true` → `populate_coverage` returns 1
- [x] 4.5 Add test: plan with uncovered REQs + `REQUIRE_FULL_COVERAGE=false` → `populate_coverage` returns 0, warns
- [x] 4.6 Add test: plan with all REQs covered → `populate_coverage` returns 0 regardless of directive
- [x] 4.7 Add test: REQ in also_affects but not in any requirements[] → counted as uncovered

## 5. Requirement-Aware Code Review

- [x] 5.1 In `lib/orchestration/verifier.sh`, add helper function `build_req_review_section()` that takes `change_name`, reads `requirements[]` and `also_affects_reqs[]` from `$STATE_FILENAME` via jq, looks up each REQ-ID's title+brief from `$DIGEST_DIR/requirements.json`, returns formatted "## Assigned Requirements" + "## Cross-Cutting Requirements" + "## Requirement Coverage Check" prompt section. Returns empty string if no requirements found or digest file missing.
- [x] 5.2 Handle edge case: REQ-ID in state but not found in digest requirements.json → include with "(not found in digest)" note, log warning
- [x] 5.3 Handle edge case: change has empty requirements[] array → return empty string, skip REQ injection
- [x] 5.4 Modify `review_change()`: after building the existing review prompt, call `build_req_review_section "$change_name"` and append result if non-empty. This goes BEFORE the `REVIEW_EOF` heredoc close.
- [x] 5.5 Ensure the escalation path (Sonnet fails → Opus retry, lines 94-103) uses the same enriched prompt
- [x] 5.6 Modify the retry context construction in `handle_change_done()` when review fails: extract specific REQ-IDs from `REVIEW_OUTPUT` that were flagged as CRITICAL (grep for `REQ-[A-Z0-9]+-[0-9]+`), include them in the retry prompt instead of just truncating the review output to 500 chars
- [x] 5.7 Add test: mock state with requirements + mock digest requirements.json → verify `build_req_review_section` output contains REQ-IDs and titles
- [x] 5.8 Add test: mock state with empty requirements[] → verify `build_req_review_section` returns empty string
- [x] 5.9 Add test: mock state with REQ-ID not in digest → verify output includes "(not found in digest)" and no crash
- [x] 5.10 Add test: no digest/requirements.json file → verify `build_req_review_section` returns empty string

## 6. Final Coverage Assertion

- [x] 6.1 Create `final_coverage_check()` function in `lib/orchestration/digest.sh`: reads `$DIGEST_DIR/coverage.json` and `$STATE_FILENAME`, categorizes each requirement as merged/running/planned/uncovered/failed/blocked by cross-referencing coverage change names with state change statuses. Emits `COVERAGE_GAP` event if any gaps exist. Returns formatted summary string. Returns empty if no digest data.
- [x] 6.2 Create `build_coverage_summary()` helper that produces a one-line summary: "Coverage: 42 merged, 3 running, 5 uncovered, 2 failed, 1 blocked (total: 53)"
- [x] 6.3 Call `final_coverage_check()` at ALL 5 exit paths in `monitor_loop()`: time_limit (~line 138), external stop (~line 145), auto-replan done (~line 358), replan-exhausted (~line 383), normal completion (~line 393)
- [x] 6.4 Modify `send_summary_email()` call sites: before calling, run `build_coverage_summary` and pass result as additional context. The email template includes this string if non-empty.
- [x] 6.5 Add test: mock coverage.json with 3 merged + 2 uncovered + 1 failed change → verify `final_coverage_check` output categorizes correctly
- [x] 6.6 Add test: no digest/coverage.json → verify `final_coverage_check` returns empty string silently
- [x] 6.7 Add test: all requirements merged → verify no COVERAGE_GAP event emitted
- [x] 6.8 Add test: change in merge-blocked state → its requirements categorized as "blocked", not "uncovered"

## 7. HTML Report Generator

- [x] 7.1 Create `lib/orchestration/reporter.sh` with `generate_report()` entry function: reads state + digest files, calls section renderers, writes HTML via atomic tmp+mv to `wt/orchestration/report.html`
- [x] 7.2 Implement `render_html_wrapper()`: produces HTML5 skeleton with embedded CSS dark theme (#1e1e1e background, #e0e0e0 text), meta-refresh 15s, responsive tables, status color classes, timestamp footer
- [x] 7.3 Implement `render_digest_section()`: reads `$DIGEST_DIR/index.json`, `requirements.json`, `ambiguities.json`, `domains/*.md`. Renders spec source, file count, domain table with coverage bars, ambiguity list. Shows "Not available" message if digest files missing.
- [x] 7.4 Implement `render_plan_section()`: reads `orchestration-plan.json` and `$STATE_FILENAME`. Renders change table (name, REQ count, spec file count, deps, status), dependency list, coverage summary (assigned/uncovered).
- [x] 7.5 Implement `render_execution_section()`: reads `$STATE_FILENAME`. Renders change timeline with status color-coding and elapsed time/tokens_used, gate results matrix (test_result/build_result/scope_check/e2e_result/has_tests as checkmarks/crosses/dashes), active issues list for non-success states.
- [x] 7.6 Implement `render_coverage_section()`: reads `$DIGEST_DIR/requirements.json`, `$DIGEST_DIR/coverage.json`, and `$STATE_FILENAME`. Cross-references coverage change→state status for effective colors. Groups by domain in collapsible `<details>` elements. Shows per-domain coverage percentage. Summary row with totals.
- [x] 7.7 Add test: generate report from CraftBrew fixture data (digest + mock state + coverage) → verify HTML file exists, contains all 4 section headings, has valid HTML structure (opening/closing tags match)
- [x] 7.8 Add test: generate report with no digest data → verify "Not available" appears in digest and coverage sections, plan and execution sections still render

## 8. Report Generation Hooks

- [x] 8.1 Source `reporter.sh` in `bin/set-orchestrate` alongside other lib modules (after sourcing digest.sh since reporter reads digest data)
- [x] 8.2 Add `generate_report 2>/dev/null || true` call at the end of `cmd_digest` in `lib/orchestration/digest.sh` (after write_digest_output succeeds)
- [x] 8.3 Add `generate_report 2>/dev/null || true` call after `populate_coverage()` in `cmd_plan` in `lib/orchestration/planner.sh`
- [x] 8.4 Add `generate_report 2>/dev/null || true` call in `monitor_loop()` after `dispatch_ready_changes` and before checkpoint check, wrapped in error guard
- [x] 8.5 Add `generate_report 2>/dev/null || true` call at each of the 5 terminal exit points in `monitor_loop()` before break/return
- [x] 8.6 Add test: verify `generate_report` is called but its failure does not affect orchestration (mock it as a failing function, verify monitor_loop continues)

## 9. Integration Tests — Full Pipeline Scenarios

- [x] 9.1 Test: requirement-aware review prompt construction — create fixture with digest requirements.json (5 REQs across 2 domains) + state with change having 3 requirements + 1 also_affects_req. Call `build_req_review_section`. Verify: assigned REQs have title+brief, also_affects REQ has "awareness only" note, coverage check instruction present.
- [x] 9.2 Test: coverage enforcement end-to-end — create fixture plan.json with 10 REQs, 8 assigned to changes, 2 unassigned. Run `populate_coverage` with REQUIRE_FULL_COVERAGE=true. Verify: returns 1, error lists the 2 uncovered REQ-IDs. Run again with REQUIRE_FULL_COVERAGE=false. Verify: returns 0, warning emitted.
- [x] 9.3 Test: final coverage cross-reference — create fixture coverage.json (REQ-A→change-1 merged, REQ-B→change-2 status:running, REQ-C→change-3 in state as failed, REQ-D uncovered). Call `final_coverage_check`. Verify: output categorizes A=merged, B=running, C=failed, D=uncovered.
- [x] 9.4 Test: HTML report with full fixture — create mock digest dir (index.json, requirements.json with 10 REQs, 3 domains, ambiguities.json with 2 entries, coverage.json), mock state (5 changes in various states with gate results). Call `generate_report`. Verify HTML contains: 4 section headings, domain names, REQ-IDs, change names, gate checkmarks, coverage colors, timestamp footer.
- [x] 9.5 Test: HTML report graceful degradation — call `generate_report` with no digest dir. Verify HTML renders plan+execution sections and shows "Not available" for digest+coverage.
- [x] 9.6 Test: review with REQ-ID not in digest — state has REQ-GHOST-001 but digest requirements.json doesn't. Verify `build_req_review_section` includes it with "(not found in digest)" and does not crash.
- [x] 9.7 Test: coverage with merge-blocked change — change-1 owns REQ-A, change-1 is merge-blocked in state, coverage.json says REQ-A→change-1 status:running. Verify `final_coverage_check` reports REQ-A as "blocked" (not "running" or "uncovered").
- [x] 9.8 Test: coverage with removed REQ — requirements.json has REQ-OLD-001 with status:removed. Verify it is excluded from uncovered count and shown as gray/removed in report.
- [x] 9.9 Test: empty requirements array in state — change has `requirements: []` in state. Verify `build_req_review_section` returns empty, review falls back to scope-only prompt.
- [x] 9.10 Test: report atomic write — verify `generate_report` writes to a temp file first and moves it (check that no partial file exists at the target path during generation)
