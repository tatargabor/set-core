# Tasks: verify-merge-pipeline-v2

## 1. E2E baseline comparison

- [ ] 1.1 Add `_get_or_create_e2e_baseline()` to `lib/set_orch/verifier.py` — runs Playwright on main (project root, not worktree), caches to e2e-baseline.json via `SetRuntime().orchestration_dir` (fallback: `wt/orchestration/`)
- [ ] 1.2 Invalidate baseline when main HEAD changes — check stored main_sha vs current HEAD before reuse, regenerate if stale. Log warning when baseline is regenerated post-merge.
- [ ] 1.3 Update `_execute_e2e_gate()` — after Playwright run, compare failures against baseline; filter out pre-existing failures; only NEW failures = gate fail
- [ ] 1.4 Log baseline comparison results — "E2E: 1 new failure (12 pre-existing on main)" format
- [ ] 1.5 Fallback: if baseline creation fails (infra issue, timeout, Playwright crash), log warning and fall back to current behavior (all failures count as new)

## 2. E2E server cleanup

- [ ] 2.1 Remove manual port path from `_execute_e2e_gate()` — delete `E2E_PORT_BASE`, random port, `health_check()` call, `PW_PORT` env, `pkill` cleanup
- [ ] 2.2 Apply same cleanup to `run_phase_end_e2e()` — it has the identical broken manual port + pkill pattern
- [ ] 2.3 When `pw_config["has_web_server"]` is False — return skip with diagnostic message: "playwright.config has no webServer — Playwright must manage the dev server"
- [ ] 2.4 Clean up unused imports/constants (`E2E_PORT_BASE`, `health_check` if only used by E2E)

## 3. Post-merge simplification

- [ ] 3.1 Remove `_run_smoke_pipeline()` call from `merge_change()` in `lib/set_orch/merger.py`
- [ ] 3.2 Remove `smoke_result` from the `MergeResult(...)` return — the variable is undefined after removing the smoke call (would cause NameError)
- [ ] 3.3 Remove `verify_merge_scope()` call from `merge_change()` — scope already verified in verify gate
- [ ] 3.4 Remove smoke timeout check (`_timed_out()` block at merger.py:471-479) — dead code without smoke. Confirm no other post-merge steps need timeout protection.
- [ ] 3.5 Check if `_run_smoke_pipeline()` has any callers left — if not, delete the function and its helpers (`_blocking_smoke_pipeline`, `_nonblocking_smoke_pipeline`). If still called (e.g., by phase-end), keep it.
- [ ] 3.6 Reduce merge timeout constant (no smoke = faster merge, current timeout includes smoke time)

## 4. Decomposer grouping

- [ ] 4.0 Identify where decompose prompt is assembled and how directives (incl. `max_parallel`) are available — check `_get_planning_rules()` callers and `planner.py` to find the injection point
- [ ] 4.1 Update `_PLANNING_RULES_CORE` in `lib/set_orch/templates.py` — add grouping rules: same domain → single change, S-complexity merge into M-complexity, domain-based naming
- [ ] 4.2 Inject `max_parallel` into decompose prompt context — thread from directives through the caller chain into the prompt string
- [ ] 4.3 Update target guidance: "Target max_parallel × 2 changes" instead of "MAX 15 changes"

## 5. Tests & verification

- [ ] 5.1 Verify E2E baseline creates correct JSON structure (main_sha, failures list, counts)
- [ ] 5.2 Verify baseline comparison: pre-existing failure filtered, new failure caught
- [ ] 5.3 Verify baseline fallback: if `_get_or_create_e2e_baseline()` fails, gate falls back to all-failures-count behavior with warning
- [ ] 5.4 Verify post-merge no longer calls smoke or scope verify, and MergeResult has no smoke_result
- [ ] 5.5 Verify decompose prompt includes grouping rules and max_parallel value
