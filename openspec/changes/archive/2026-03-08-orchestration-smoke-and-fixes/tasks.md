## 1. ff→apply Same-Iteration Chaining (wt-loop)

- [x] 1.1 In `wt-loop` main loop (~line 1240, post-iteration ff tracking section): after detecting `post_action == apply:*` (ff succeeded, tasks.md created), set a `chain_apply=true` flag instead of ending the iteration
- [x] 1.2 Add chaining logic: when `chain_apply=true`, build a new prompt via `build_prompt()` with the apply action, invoke `claude` again within the same iteration, capture its output/commits
- [x] 1.3 Record both ff and apply phases in the iteration metadata — append chained commits to the iteration's commit list, don't increment iteration counter
- [x] 1.4 Handle chained apply failure gracefully: if the second `claude` invocation returns non-zero or times out, end the iteration normally and let the next iteration pick up `apply:*`
- [x] 1.5 Reset stall counter when chained apply produces commits (progress was made)

## 2. Output-Level Idle Iteration Detection (wt-loop)

- [x] 2.1 Add `--max-idle N` flag to `wt-loop` argument parsing (alongside existing `--stall-threshold`), default value 3
- [x] 2.2 Store `max_idle_iterations` in `loop-state.json` alongside existing config
- [x] 2.3 After each iteration completes, compute MD5 hash of last 200 lines of `iter_log_file`: `tail -200 "$iter_log_file" | md5sum | cut -d' ' -f1`
- [x] 2.4 Compare hash with `last_output_hash` in loop state — if match, increment `idle_count`; if different, reset to 0 and update hash
- [x] 2.5 If `idle_count >= max_idle_iterations`: set loop status to `idle`, log "Loop stopped: identical output for $idle_count consecutive iterations", exit loop
- [x] 2.6 On first iteration (no previous hash), set `last_output_hash` but keep `idle_count` at 0
- [x] 2.7 Add `idle_count` and `last_output_hash` fields to iteration history entries in `loop-state.json`

## 3. LLM Merge Conflict Resolver — Additive Pattern (wt-merge)

- [x] 3.1 In `llm_resolve_conflicts()` (~line 143 of `wt-merge`), add an "Additive conflict pattern" section after the general instructions in the prompt
- [x] 3.2 Include explicit instruction: "When both sides ADD new entries to the same list, array, object, or import block, KEEP ALL entries from BOTH sides. Do NOT pick one side."
- [x] 3.3 Include a concrete example showing a conflict with additions on both sides and the correct merged resolution
- [x] 3.4 Keep existing behavior unchanged for non-additive conflicts (modifications, deletions)

## 4. Smoke Blocking Gate — Directives & Parsing (set-orchestrate)

- [x] 4.1 Add new directive defaults at top of `set-orchestrate`: `DEFAULT_SMOKE_BLOCKING=false`, `DEFAULT_SMOKE_FIX_TOKEN_BUDGET=500000`, `DEFAULT_SMOKE_FIX_MAX_TURNS=15`, `DEFAULT_SMOKE_FIX_MAX_RETRIES=3`, `DEFAULT_SMOKE_HEALTH_CHECK_TIMEOUT=30`
- [x] 4.2 Extend `parse_directives()` to parse: `smoke_blocking`, `smoke_fix_token_budget`, `smoke_fix_max_turns`, `smoke_fix_max_retries`, `smoke_health_check_url`, `smoke_health_check_timeout` — with validation (boolean, positive integers, valid URL)
- [x] 4.3 Store new directives in state.json under `.directives`
- [x] 4.4 Add unit tests in `test-orchestrate.sh` for new directive parsing (valid values, invalid values, defaults)

## 5. Health Check Function (set-orchestrate)

- [x] 5.1 Implement `health_check()` function: takes URL and timeout, uses `curl -s -o /dev/null -w '%{http_code}'` in a retry loop (1s interval), returns 0 on 200 response, 1 on timeout
- [x] 5.2 Implement `extract_health_check_url()`: parses `localhost:PORT` from `smoke_command` using grep, returns `http://localhost:PORT`
- [x] 5.3 Add 5-second recompile buffer (sleep) after health check passes before running smoke

## 6. Scoped Smoke Fix Agent (set-orchestrate)

- [x] 6.1 Implement `smoke_fix_scoped()` function that replaces the current inline smoke fix in `merge_change()`. Parameters: change_name, smoke_command, smoke_timeout, max_retries, token_budget, max_turns
- [x] 6.2 Build scoped fix prompt: include smoke output (full, not truncated), modified files list (`git diff HEAD~1 --name-only`), change scope from state.json, containment constraints ("MAY ONLY modify files from this change", "MUST NOT delete test assertions")
- [x] 6.3 Implement fix-verify-retry loop: after each fix attempt, run unit tests + build → if fail, `git revert HEAD --no-edit` and count as failed attempt → if pass, re-run smoke → if smoke pass, return success
- [x] 6.4 Track `smoke_fix_attempts` in state.json per change
- [x] 6.5 On all retries exhausted: set `smoke_result="fail"`, `smoke_status="failed"`, send critical notification

## 7. Smoke Blocking Pipeline in merge_change() (set-orchestrate)

- [x] 7.1 Refactor the smoke section (lines 4323-4376) of `merge_change()`: branch on `smoke_blocking` — if false, keep existing non-blocking behavior; if true, enter blocking pipeline
- [x] 7.2 Blocking pipeline: after post_merge_command → `health_check()` → if fail: status=`smoke_blocked`, notify, release lock, return → if pass: sleep 5 (recompile buffer) → run smoke
- [x] 7.3 If smoke passes: status=`completed`, `smoke_result="pass"`, release lock
- [x] 7.4 If smoke fails: call `smoke_fix_scoped()` → if fixed: status=`completed`, `smoke_result="fixed"` → if exhausted: status=`smoke_failed`, notify sentinel
- [x] 7.5 Update `smoke_status` granularly through the pipeline: "pending" → "checking" → "running" → "fixing" → "done"|"failed"|"blocked"
- [x] 7.6 Ensure flock is held through the entire blocking pipeline (merge + smoke + fix)

## 8. Integration Test Infrastructure (tests/orchestrator/)

- [x] 8.1 Create `test-orchestrate-integration.sh` with test framework (reuse test_start/test_pass/test_fail/assert_equals/assert_contains from existing test file)
- [x] 8.2 Implement `setup_test_repo()`: creates temp git repo with main branch, user.name/email configured, initial commit
- [x] 8.3 Implement `create_feature_branch()`: creates `change/<name>` branch with specified file changes, returns to main
- [x] 8.4 Implement `init_test_state()`: creates orchestration-state.json with a single change entry (configurable status, worktree_path, etc.)
- [x] 8.5 Implement `stub_run_claude()`: override function that returns configurable exit code and optionally creates/modifies files
- [x] 8.6 Implement `stub_smoke()`: creates a temp script that returns configurable exit code with configurable output
- [x] 8.7 Implement `cleanup_test()`: removes all temp dirs and files

## 9. Integration Tests — Merge Pipeline

- [x] 9.1 Test: clean merge → completed (merge succeeds, post_merge runs, build passes, smoke passes → status=completed)
- [x] 9.2 Test: merge conflict → merge-blocked (merge fails, status=merge-blocked, no crash — regression test)
- [x] 9.3 Test: already-merged branch (branch is ancestor of HEAD → status=merged, no merge attempted)
- [x] 9.4 Test: post-merge build fail → LLM fix (build fails, stub fix agent runs, verify status)

## 10. Integration Tests — Smoke Pipeline

- [x] 10.1 Test: smoke pass (blocking mode) — smoke returns 0 → status=completed, smoke_result=pass
- [x] 10.2 Test: smoke fail → fix → pass — smoke returns 1, stub agent fixes, re-run passes → smoke_result=fixed, smoke_fix_attempts=1
- [x] 10.3 Test: smoke fail → fix exhausted — smoke returns 1, fix fails max_retries times → status=smoke_failed, notification sent
- [x] 10.4 Test: health check fail — curl returns non-200 → status=smoke_blocked, smoke not run
- [x] 10.5 Test: smoke non-blocking mode — smoke_blocking=false, smoke fails but merge proceeds → status=merged (not blocked)

## 11. Integration Tests — Loop Control & Idle Detection

- [x] 11.1 Test: detect_next_change_action returns ff:* when tasks.md missing, apply:* when tasks exist with unchecked items, done when all checked
- [x] 11.2 Test: stall detection — N commit-less iterations → status=stalled
- [x] 11.3 Test: idle detection — 3 iterations with identical output hash → loop stops with status=idle
- [x] 11.4 Test: idle counter reset — 2 identical iterations then different output → idle_count resets to 0
- [x] 11.5 Test: repeated commit message detection — same message N times → status=stalled
- [x] 11.6 Test: artifact progress resets stall counter (ff creates files, no commits → not stall)

## 12. Integration Tests — Merge Conflict Resolver

- [x] 12.1 Test: additive conflict pattern — both sides add entries to same array, verify prompt includes additive pattern guidance
- [x] 12.2 Test: non-additive conflict — modifications on both sides, verify existing behavior unchanged

## 13. Verify & Finalize

- [x] 13.1 Run existing tests: `./tests/orchestrator/test-orchestrate.sh` — all must still pass
- [x] 13.2 Run new integration tests: `./tests/orchestrator/test-orchestrate-integration.sh` — all must pass
- [x] 13.3 Run merge tests if they exist: verify additive resolver changes don't break existing merge tests
- [x] 13.4 Verify smoke_blocking=false preserves exact existing behavior (no regression)
- [x] 13.5 Verify max_idle_iterations=3 default doesn't affect loops that make progress
- [x] 13.6 Verify new directives are parsed from both orchestration.yaml and spec brief markdown
