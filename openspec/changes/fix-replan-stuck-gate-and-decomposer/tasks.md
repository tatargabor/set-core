## 1. State Schema Groundwork (Layer 1)

- [x] 1.1 Add `stuck_loop_count: int = 0` to the Change dataclass in `lib/set_orch/state.py` with `to_dict()`/`from_dict()` round-trip and default-0 back-compat on load [REQ: stuck_loop_count-state-field]
- [x] 1.2 Add `last_gate_fingerprint: str | None = None` to the Change dataclass with serialisation guard (omit when None) [REQ: state-schema-carries-runaway-fields]
- [x] 1.3 Add `token_runaway_baseline: int | None = None` to the Change dataclass [REQ: state-schema-carries-runaway-fields]
- [x] 1.4 Add `fix_iss_child: str | None = None` to the Change dataclass [REQ: fix_iss_child-state-field]
- [x] 1.5 Add `gate_recheck_done: bool = False` to the Change dataclass [REQ: re-detection-on-first-commit-poll]
- [x] 1.6 Add `touched_file_globs: list[str] = []` to the Change dataclass (produced by decomposer, consumed by gate registry) [REQ: content-hints-for-gate-selection]
- [x] 1.7 Add `trigger_backoffs: dict[str, BackoffEntry]` as a NEW field on `SupervisorStatus` in `lib/set_orch/supervisor/state.py` (parallel to the existing `trigger_counters` field — do NOT repurpose `trigger_counters`, they have different semantics: counters track attempts for budget math; backoffs track suppression windows). Include JSON round-trip [REQ: trigger_backoffs-persisted-in-supervisorstatus]
- [x] 1.8 Write round-trip unit tests for all new fields (no state file needed; pure dataclass tests) [REQ: stuck_loop_count-state-field, state-schema-carries-runaway-fields, fix_iss_child-state-field, trigger_backoffs-persisted-in-supervisorstatus]

## 2. Verifier — Single Fingerprint Writer + Stale-Branch Guard (Layer 1)

- [x] 2.1 Implement `_compute_gate_fingerprint(gate_result) -> str` in `lib/set_orch/verifier.py` returning stable SHA-hash of `(stop_gate, sorted(finding_ids))` [REQ: verifier-writes-last_gate_fingerprint-after-gate-completion]
- [x] 2.2 In `run_verify_pipeline()`, write `change.last_gate_fingerprint` in the same state transaction as the `VERIFY_GATE` event emission [REQ: verifier-writes-last_gate_fingerprint-after-gate-completion]
- [x] 2.3 Guard the stale-detection branch that writes `status=stalled` on `ralph_status ∈ {stopped, stalled, stuck}`: before writing, query `git log --since=<stalled_at>` and skip the write if new commits exist [REQ: verifier-stale-detection-branch-checks-commit-progress]
- [x] 2.4 Add DEBUG log `Skipping stall write: <N> new commits since <T0>` when the guard fires [REQ: verifier-stale-detection-branch-checks-commit-progress]
- [x] 2.5 Remove the verifier's `Change <name> stuck — marking stalled for watchdog` WARNING write from the path where `loop_status=stuck` AND `new_commits_since_dispatch > 0` [REQ: single-handler-path-for-stuck-fix-loop-exits-with-new-commits]

## 3. Engine — Stuck-Loop Handler Unification (Layer 1)

- [x] 3.1 In `lib/set_orch/engine.py::_handle_agent_exit()`, when `ralph_status=stuck` AND `new_commits_since_dispatch > 0`, call `verifier.run_verify_pipeline(change)` directly without writing `status=stalled` [REQ: single-handler-path-for-stuck-fix-loop-exits-with-new-commits]
- [x] 3.2 Add `stuck_loop_count` update logic: after each verify-pipeline run following a stuck exit, compare new fingerprint to `last_gate_fingerprint`; increment if same, reset if different [REQ: stuck-loop-circuit-breaker]
- [x] 3.3 Ordering: check the threshold BEFORE evaluating reset, per the "Threshold check before reset" clause [REQ: stuck-loop-circuit-breaker]
- [x] 3.4 When `stuck_loop_count >= max_stuck_loops` AND fingerprint unchanged, set `status='failed:stuck_no_progress'` and emit `STUCK_LOOP_ESCALATED` event [REQ: stuck-loop-circuit-breaker]
- [x] 3.5 Add directive `max_stuck_loops: int = 3` in `lib/set_orch/config.py` defaults [REQ: stuck-loop-circuit-breaker]
- [x] 3.6 Integration test: simulate 3 consecutive stuck exits with identical fingerprints → change transitions to `failed:stuck_no_progress` [REQ: stuck-loop-circuit-breaker]
- [x] 3.7 Unit test for the ordering edge-case: simultaneous threshold-reached AND fingerprint-changed → threshold does NOT fire, counter resets to 0 [REQ: stuck-loop-circuit-breaker]

## 4. Engine — Token-Runaway Circuit Breaker (Layer 1)

- [x] 4.1 In the monitor poll after a `VERIFY_GATE` event, if `token_runaway_baseline is None`, set it to current `input_tokens` and record current `last_gate_fingerprint` [REQ: per-change-token-runaway-circuit-breaker]
- [x] 4.2 If fingerprint unchanged, check `input_tokens - token_runaway_baseline > threshold`; if so, emit `TOKEN_RUNAWAY` event and set `status='failed:token_runaway'` [REQ: per-change-token-runaway-circuit-breaker]
- [x] 4.3 If fingerprint changed, reset `token_runaway_baseline` to current `input_tokens` [REQ: per-change-token-runaway-circuit-breaker]
- [x] 4.4 Add directive `per_change_token_runaway_threshold: int = 20_000_000` [REQ: per-change-token-runaway-circuit-breaker]
- [x] 4.5 Integration test: simulate same-fingerprint iterations pushing `input_tokens` over threshold → change transitions to `failed:token_runaway` [REQ: per-change-token-runaway-circuit-breaker]

## 5. Supervisor — Exponential Back-off (Layer 1)

- [x] 5.1 In `lib/set_orch/supervisor/anomaly.py` trigger executor, before emitting any `SUPERVISOR_TRIGGER`, compute `tuple_key = f"{trigger}::{change or ''}::{reason_hash}"` [REQ: trigger_backoffs-persisted-in-supervisorstatus]
- [x] 5.2 If `trigger_backoffs[tuple_key]` exists and `now < back_off_until`, SKIP emission (no event written) [REQ: exponential-back-off-on-retry_budget_exhausted]
- [x] 5.3 On `skipped: retry_budget_exhausted`, set or advance back-off: steps 60, 120, 240, 480, 600 (cap) [REQ: exponential-back-off-on-retry_budget_exhausted]
- [x] 5.4 Clear the tuple's entry from `trigger_backoffs` when `is_triggered()` returns False on a subsequent poll [REQ: exponential-back-off-on-retry_budget_exhausted]
- [x] 5.5 Unit test with a fake clock: verify 15s polling produces exactly 1 event in first 60s, 1 event at 60-120s, etc., not a stream [REQ: exponential-back-off-on-retry_budget_exhausted]

## 6. Replan Reconciliation (Layer 1)

- [x] 6.1 Add `force_dirty: bool = False` parameter to `lib/set_orch/recovery.py::cleanup_orphans()` (or wherever orphan_cleanup actually lives; grep for the function and add there) [REQ: clean-orphaned-worktrees-on-startup]
- [x] 6.2 When `force_dirty=True` AND the worktree's change name is NOT in the currently-active plan, run `git stash push -u -m "auto-stash: divergent-replan <ts>"` inside the worktree; then archive + `git worktree remove --force` [REQ: worktree-has-uncommitted-changes-during-divergent-plan-reconciliation]
- [x] 6.3 Stash-failure fallback: create rescue branch `wip/<name>-<epoch>`, `git add -A && git commit --no-verify`, log WARNING with branch name + owning repo path [REQ: stash-failure-falls-back-to-rescue-branch]
- [x] 6.4 Return a structured dict with fields `worktrees_removed, dirty_skipped, dirty_forced, pids_cleared, steps_fixed, artifacts_collected, merge_queue_entries_restored, issues_released` [REQ: orphan-cleanup-returns-structured-summary]
- [x] 6.5 Update the cleanup summary log line to include `, <M> dirty forced` when `dirty_forced > 0` [REQ: conservative-safety-rules]
- [x] 6.6 In `lib/set_orch/planner.py::auto_replan_cycle()`, detect divergence: `old ^ new != ∅` (symmetric-diff of change-name sets from prior plan vs new plan) [REQ: divergent-plan-state-reconciliation]
- [x] 6.7 On divergence, after plan validation succeeds: (a) write cleanup manifest; (b) call `cleanup_orphans(force_dirty=True)`; (c) delete `change/<name>` branches not in the new plan; (d) remove `openspec/changes/<name>/` dirs not in the new plan AND not in `state-archive.jsonl`. Honor `divergent_plan_dir_cleanup=dry-run` directive: write manifest but skip destructive ops [REQ: divergent-plan-state-reconciliation, reconciler-writes-a-cleanup-manifest-and-honors-dry-run]
- [x] 6.7b Write manifest file `orchestration-cleanup-<epoch>.log` BEFORE any destructive op, listing each branch/dir path with operation and rationale [REQ: reconciler-writes-a-cleanup-manifest-and-honors-dry-run]
- [x] 6.7c Add directive `divergent_plan_dir_cleanup: str = "enabled"` (values: `enabled`, `dry-run`) in `lib/set_orch/config.py` defaults [REQ: reconciler-writes-a-cleanup-manifest-and-honors-dry-run]
- [x] 6.8 Assert the sequence: `collect_replan_context()` snapshot taken BEFORE reconciliation so archived dirs don't leak into the prompt [REQ: replan-context-captured-before-reconciliation]
- [x] 6.9 Reset `SupervisorStatus.rapid_crashes` to 0 when all current-plan changes reach terminal status AND no replan is pending [REQ: supervisor-rapid_crashes-reset-on-clean-plan-completion]
- [x] 6.10 Integration test: simulate a divergent replan with dirty worktrees → verify stash refs created, worktrees archived, branches deleted, state reconciled [REQ: divergent-plan-state-reconciliation, worktree-has-uncommitted-changes-during-divergent-plan-reconciliation]

## 7. Content-Aware Gate Selection (Layer 1 + Web module)

- [x] 7.0 **Module refactor first**: create `lib/set_orch/gate_registry.py` by moving `GateConfig` + selector logic out of `gate_profiles.py`. `gate_profiles.py` keeps public re-exports for back-compat. ALL subsequent tasks in section 7 depend on this. [REQ: content-classifier]
- [x] 7.1 Add `ProjectType.content_classifier_rules() -> dict[str, list[str]]` to the ABC in `lib/set_orch/profile_types.py` (default `{}` on `CoreProfile`) [REQ: content-classifier]
- [x] 7.2 Implement `classify_content(globs: list[str]) -> set[str]` in the new `lib/set_orch/gate_registry.py` (created in 7.0) [REQ: content-classifier]
- [x] 7.3 Add `ProjectType.content_tag_to_gates() -> dict[str, set[str]]` with core defaults per spec ("ui"→{design-fidelity, i18n_check}, "e2e_ui"→{e2e}, "server"→{test}, "schema"→{build}, "config"→{build}, "i18n_catalog"→{i18n_check}) [REQ: content-tag-to-gate-name-mapping]
- [x] 7.4 Implement `WebProjectType.content_classifier_rules()` in `modules/web/set_project_web/project_type.py`: map `src/app/**/*.tsx` and `src/components/**/*.tsx` → `"ui"`, map `tests/e2e/**/*.spec.ts` → `"e2e_ui"`, map `src/server/**` and `src/lib/**` → `"server"`, map `prisma/**` → `"schema"`, map `messages/*.json` → `"i18n_catalog"` [REQ: content-classifier]
- [x] 7.5 In the gate selector (currently static `change_type → gate_set`), invoke `classify_content(change.touched_file_globs)` and union the mapped gate names with the existing gate set [REQ: content-aware-gate-selector]
- [x] 7.6 Ensure selection is additive: `gate_hints` with value `"require"` forces inclusion; `"skip"` excludes; content scan can only add, never subtract [REQ: content-aware-gate-selector]
- [x] 7.7 In `engine.monitor_loop()`, detect the first-commit transition: when a change's `new_commits_since_dispatch` goes from 0 to 1 AND `gate_recheck_done == False`, call `gate_registry.redetect(change)` before running the verify pipeline; set `gate_recheck_done = True` [REQ: re-detection-on-first-commit-poll]
- [x] 7.8 `redetect()` scans the files from the first commit's diff, classifies them, unions new tags into `touched_file_globs`, and recomputes the gate set; emits `GATE_SET_EXPANDED` event if the set grew [REQ: re-detection-on-first-commit-poll]
- [x] 7.9 Integration test: change with `change_type=infrastructure` and scope containing `src/app/**/*.tsx` → verify `design-fidelity` + `e2e` + `i18n_check` appear in active gate set [REQ: content-aware-gate-selector]

## 8. Web Gate Tuning (Layer 2 — web module)

- [x] 8.1 In `modules/web/set_project_web/gates.py` (or wherever i18n_check is implemented), change the return type from `warn-fail | pass` to `pass | fail | skipped` [REQ: i18n_check-is-a-hard-fail-gate]
- [x] 8.2 Update the gate registry/verifier's treatment of `i18n_check`: treat `fail` as a blocking `stop_gate` like any other gate [REQ: i18n_check-is-a-hard-fail-gate]
- [x] 8.3 Add `WebProjectType.parallel_gate_groups() -> list[set[str]]` returning `[{"spec_verify", "review"}]` by default; `CoreProfile` returns `[]` [REQ: web-profile-exposes-gate-tuning-hooks]
- [x] 8.4 In `lib/set_orch/gate_runner.py` (owns parallel dispatch; `verifier.py` calls through it), when a group is active and both gates are in the current gate set, dispatch both concurrently via `concurrent.futures.ThreadPoolExecutor` (process-bound external subprocesses) [REQ: spec_verify-and-review-run-in-parallel]
- [x] 8.5 Record both `gate_ms.spec_verify` and `gate_ms.review`; add `parallel_group: [...]` field to the `VERIFY_GATE` event [REQ: spec_verify-and-review-run-in-parallel]
- [x] 8.6 If both gates fail, ensure findings from BOTH are surfaced to the retry agent's context even though the `stop_gate` will be the earliest-ordered one [REQ: spec_verify-and-review-run-in-parallel]
- [x] 8.7 Audit `grep -r "warn-fail"` across set-core and built-in templates; replace/remove obsolete references [REQ: i18n_check-is-a-hard-fail-gate]
- [x] 8.8 Integration test: web change with i18n gap → `VERIFY_GATE` event has `stop_gate: i18n_check, i18n_check: fail` [REQ: i18n_check-is-a-hard-fail-gate]

## 9. Decomposer — skip_test Guard + Granularity Budget (Layer 1)

- [x] 9.1 In `lib/set_orch/planner.py::validate_plan()`, add a file-path-substring scan on each change's `scope` for the guard list (`server/`, `actions/`, `handlers/`, `services/`, `validators/`, `/lib/business/`, `/api/`); if any match AND `skip_test=true`, validation fails [REQ: skip_test-guarded-by-scope-file-path-content]
- [x] 9.2 Add a reverse whitelist: `skip_test=true` is allowed only when ALL scope paths are under `scaffolding/`, `public/`, `messages/`, `prisma/`, `docs/`, or match `*.config.*` / `*.json` / `*.yaml` / `*.toml` [REQ: skip_test-guarded-by-scope-file-path-content]
- [x] 9.3 In `validate_plan()`, compute `estimated_loc(change)` per the size-estimate formula; if over threshold, trigger auto-split [REQ: size-estimate-formula-for-change-sizing]
- [x] 9.3a Add `ProjectType.loc_weights() -> dict[str, int]` to the ABC in `lib/set_orch/profile_types.py` returning `{}` (all paths fall back to default 150) on `CoreProfile` [REQ: size-estimate-formula-for-change-sizing]
- [x] 9.3b Implement `WebProjectType.loc_weights()` in `modules/web/set_project_web/project_type.py` with the declared path→weight mapping: `src/app/admin/**/page.tsx`→350, `src/app/[locale]/**/page.tsx`→200, `src/components/**/*.tsx`→180, `src/server/**/*.ts`→200, `tests/**/*.spec.ts`→150 [REQ: size-estimate-formula-for-change-sizing]
- [x] 9.3c Implement `_resolve_loc_weight(path, weights)` with longest-glob-wins resolution + specificity tiebreaker in `lib/set_orch/planner.py` [REQ: size-estimate-formula-for-change-sizing]
- [x] 9.3d Add directives `per_change_estimated_loc_threshold: int = 1500`, `loc_schema_weight: int = 120`, `loc_ambiguity_weight: int = 80` in `lib/set_orch/config.py` defaults [REQ: size-estimate-formula-for-change-sizing]
- [x] 9.4 Implement `auto_split_change(change) -> list[Change]` using linked-sibling strategy: group file paths by first-2-segment directory prefix OR by explicit scope sub-headings; emit `<base>-<group-label>-<N>` siblings with sequential `depends_on` chain in the same phase [REQ: linked-sibling-split-strategy]
- [x] 9.4a Infer `group-label` from the grouped content: if paths are all under `src/app/admin/<X>/` use `<X>`; if all under `src/server/<X>/` use `<X>-server`; if all under `tests/e2e/` use `tests`; fallback to first-2-segment concat [REQ: linked-sibling-split-strategy]
- [x] 9.4b Distribute `requirements`, `also_affects_reqs`, `spec_files`, `resolved_ambiguities` across siblings by file-path affinity; first sibling inherits original `scope` preamble, subsequent siblings get a generated preamble from their grouped content [REQ: linked-sibling-split-strategy]
- [x] 9.4c After splitting, recompute `estimated_loc` for each sibling; accept if each is ≤ `threshold * 1.1` (10% grace); otherwise subdivide again [REQ: linked-sibling-split-strategy]
- [x] 9.5 Run auto-split BEFORE plan persistence: modify the plan in-memory, revalidate, then return [REQ: linked-sibling-split-strategy]
- [x] 9.5a Unit test: `admin-operations` (est 3760) splits into `admin-operations-orders-1 → admin-operations-dashboard-2 → admin-operations-returns-3` with correct `depends_on` [REQ: linked-sibling-split-strategy]
- [x] 9.5b Unit test: `promotions-engine` (est 2000) splits into `promotions-engine-server-1 → promotions-engine-admin-2` [REQ: linked-sibling-split-strategy]
- [x] 9.5c Unit test: `stories-and-content` (est 900) passes through unchanged [REQ: size-estimate-formula-for-change-sizing]
- [x] 9.5d Unit test: pre-split name never appears in output plan [REQ: linked-sibling-split-strategy]
- [x] 9.6 Populate `touched_file_globs` on each change: parse the scope paragraph, collect explicit file paths + add wildcard parents for each directory mentioned [REQ: content-hints-for-gate-selection]
- [x] 9.7 Update the decomposer prompt schema in `lib/set_orch/templates/` or `modules/web/set_project_web/planning_rules.txt` to document the `skip_test` guard and the `touched_file_globs` output field [REQ: skip_test-guarded-by-scope-file-path-content, content-hints-for-gate-selection]
- [x] 9.8 Unit tests: validate_plan rejects skip_test with server/ scope; accepts skip_test with scaffolding-only scope [REQ: skip_test-guarded-by-scope-file-path-content]
- [x] 9.9 Unit tests: auto-split on 15-requirement change produces ≥3 splits with correct `depends_on` [REQ: granularity-budget-with-auto-split]

## 10. Investigation / fix-iss Auto-Escalation (Layer 1)

The investigation machinery already lives under `lib/set_orch/issues/` (`investigator.py` dispatches `/opsx:ff`; `fixer.py`, `manager.py`, `policy.py`, `registry.py`, `models.py` are its support modules). These tasks wire NEW trigger points into the existing module — they do NOT create a greenfield `investigation_runner.py`.

- [x] 10.1 In `lib/set_orch/issues/manager.py`, add a public helper `escalate_change_to_fix_iss(change, stop_gate, findings, escalation_reason) -> str` (returns new change name). Reuse `investigator.py`'s existing `/opsx:ff` dispatch path; `escalation_reason ∈ {"retry_budget_exhausted", "stuck_no_progress", "token_runaway"}` [REQ: auto-escalate-to-fix-iss-on-retry-budget-exhaustion]
- [x] 10.2 Implement path-based `Target` classification inside `escalate_change_to_fix_iss()`: framework if any finding path is under `lib/set_orch/`, `modules/*/`, `templates/core/rules/`, `.claude/rules/`; else consumer [REQ: fix-iss-change-gets-a-diagnostic-proposal]
- [x] 10.3 Ensure the generated `proposal.md` has sections `Why`, `What Changes`, `Capabilities`, `Impact`, `Fix Target`. The existing `investigator.py` already produces a proposal; verify the Fix Target heuristic lands correctly and extend if needed [REQ: fix-iss-change-gets-a-diagnostic-proposal]
- [x] 10.4 In `verifier.run_verify_pipeline()`, on retry-budget exhaustion (`review 5/5`, other gates `4/4`), invoke `escalate_change_to_fix_iss(..., escalation_reason="retry_budget_exhausted")`; set parent `status='failed:retry_budget_exhausted'` and `fix_iss_child=<new_name>` [REQ: auto-escalate-to-fix-iss-on-retry-budget-exhaustion]
- [x] 10.5 Hook from stuck-loop escalation (completes the work in task 3.4): same call with `escalation_reason="stuck_no_progress"` and set `fix_iss_child` [REQ: stuck-loop-circuit-breaker-also-triggers-fix-iss]
- [x] 10.6 Hook from token-runaway (completes the work in task 4.2): same call with `escalation_reason="token_runaway"` and include runaway metadata (baseline, current, delta) in the proposal [REQ: token-runaway-also-triggers-fix-iss]
- [x] 10.7 Dispatcher routes to `fix_iss_child` on the next monitor poll after escalation [REQ: auto-escalate-to-fix-iss-on-retry-budget-exhaustion]
- [x] 10.8 Integration test: a change that exhausts review budget → fix-iss proposal appears in `openspec/changes/fix-iss-*/proposal.md` with correct `Target` [REQ: auto-escalate-to-fix-iss-on-retry-budget-exhaustion]
- [x] 10.9 Integration test: stuck-loop escalation produces fix-iss with `escalation_reason=stuck_no_progress` and parent `fix_iss_child` populated [REQ: stuck-loop-circuit-breaker-also-triggers-fix-iss]
- [x] 10.10 Integration test: token-runaway escalation produces fix-iss with runaway metadata in proposal body [REQ: token-runaway-also-triggers-fix-iss]
- [x] 10.11 In `lib/set_orch/state.py` extract `is_terminal_status(status)` helper (accepts base set + any `failed:*` prefix) and use it in `all_phase_changes_terminal()`; also fix the inline `change_terminal` set in `lib/set_orch/supervisor/daemon.py:694` to accept `failed:*` prefix. Without this the phase-advance guard blocks the next phase when a failed:* residue remains even though fix-iss children already cover the work [REQ: auto-escalate-to-fix-iss-on-retry-budget-exhaustion]
- [x] 10.12 In `lib/set_orch/issues/manager.py:escalate_change_to_fix_iss()` also call `IssueRegistry.register(source="circuit-breaker:<reason>", affected_change=<parent>, ...)` so the escalation surfaces in the web `Issues` tab. Without this `/.set/issues/registry.json` stays empty and operators see `[]` from `/api/{project}/issues` even after multiple circuit-breaker trips [REQ: auto-escalate-to-fix-iss-on-retry-budget-exhaustion]
- [x] 10.13 After `IssueRegistry.register()` in `escalate_change_to_fix_iss()`, set the returned `Issue.change_name = fix_iss_name` and call `registry.save()` so the issue is linked to the ALREADY-created fix-iss change. In `InvestigationRunner.spawn()`, reuse `issue.change_name` when it is pre-populated instead of regenerating a slug from `error_summary`. Preserves the full investigation pipeline mandated by spec `investigation-runner` (deep root-cause analysis, framework/consumer classification) while targeting the ONE fix-iss change the circuit breaker pre-created — no ghost duplicate [REQ: auto-escalate-to-fix-iss-on-retry-budget-exhaustion]

## 12. Gate-Retry-Policy — Scoped Re-Gate (Layer 1 + Web module)

- [x] 12.1 Add `ProjectType.gate_retry_policy() -> dict[str, Literal["always", "cached", "scoped"]]` to the ABC in `lib/set_orch/profile_types.py` returning `{}` (all gates default to `"always"`) on `CoreProfile` [REQ: profile-declares-per-gate-retry-policy]
- [x] 12.2 Implement `WebProjectType.gate_retry_policy()` in `modules/web/set_project_web/project_type.py` returning the declared mapping: build/test/scope_check/test_files/e2e_coverage/rules/lint/i18n_check → `"always"`; review/spec_verify/design-fidelity → `"cached"`; e2e → `"scoped"` [REQ: profile-declares-per-gate-retry-policy]
- [x] 12.3 Add `ProjectType.gate_cache_scope(gate_name) -> list[str]` returning glob patterns whose modification invalidates the gate's cache. Core default returns `[]` per gate [REQ: cached-policy-reuses-prior-verdict-with-invalidation]
- [x] 12.4 Implement `WebProjectType.gate_cache_scope(gate_name)`: `review`→[`src/**`, `tests/**`, `prisma/**`]; `spec_verify`→[`src/**`, `prisma/**`, `openspec/specs/**`]; `design-fidelity`→[`src/**/*.tsx`, `src/**/*.css`, `public/design-tokens.json`, `tailwind.config.ts`] [REQ: cached-policy-reuses-prior-verdict-with-invalidation]
- [x] 12.5 Add `ProjectType.gate_scope_filter(gate_name, retry_diff_files) -> list[str] | None` to the ABC for `scoped` policy. Core default returns `None` for all gates [REQ: scoped-policy-shards-gate-by-retry-diff]
- [x] 12.6 Implement `WebProjectType.gate_scope_filter("e2e", retry_diff_files)`: compute union of (a) Playwright test files whose corresponding `src/app/**` pages import files in the diff, (b) test files sharing a domain label with diff files (co-located heuristic); return `None` if union is empty [REQ: scoped-policy-shards-gate-by-retry-diff]
- [x] 12.7 Add `gate_retry_tracking: dict[str, GateRetryEntry]` to the Change dataclass in `lib/set_orch/types.py` with `GateRetryEntry = {consecutive_cache_uses: int, last_verdict_sha: str | None, last_run_retry_index: int | None}`. Default `{}`. JSON round-trip tested [REQ: state-schema-for-retry-policy-tracking]
- [x] 12.8 Add `verify_retry_index: int = 0` to the Change dataclass to distinguish first run (index 0) from retries (index ≥ 1) [REQ: first-verify-run-ignores-retry-policy]
- [x] 12.9 In `lib/set_orch/gate_runner.py`, before dispatching each gate, consult `profile.gate_retry_policy()[gate_name]` and route: `always` → normal execution; `cached` → call `_try_cache_reuse()` first; `scoped` → call `_try_scoped_run()` first [REQ: verify-pipeline-honors-per-gate-retry-policy]
- [x] 12.10 Implement `_try_cache_reuse(change, gate_name)` checking: (1) `consecutive_cache_uses < max_consecutive_cache_uses` (default 2); (2) retry diff does not touch any file matching `profile.gate_cache_scope(gate_name)`; (3) no new public API surface in diff (scan for `^\+export (async )?function`, `^\+export const .* = async`, `^\+\s*model \w+ \{` in prisma, `^\+export async function (GET|POST|...)` for route handlers). If all pass, emit `GATE_CACHED` event with prior verdict's sidecar SHA and skip execution [REQ: cached-policy-reuses-prior-verdict-with-invalidation]
- [x] 12.11 Implement `_try_scoped_run(change, gate_name)` calling `profile.gate_scope_filter(gate_name, retry_diff_files)`. If returns `None` → fall through to `_try_cache_reuse`. If returns list → pass filter tokens to the gate executor's `scoped_subset` kwarg; record in `VERIFY_GATE` event's `scoped_subset` field [REQ: scoped-policy-shards-gate-by-retry-diff]
- [x] 12.12 Update `execute_e2e_gate()` in `modules/web/set_project_web/gates.py` to accept `scoped_subset: list[str] | None` kwarg; when provided, pass the test-file paths to Playwright as explicit test args (e.g., `npx playwright test tests/e2e/cart.spec.ts`) [REQ: scoped-policy-shards-gate-by-retry-diff]
- [x] 12.13 Update tracking counters: `consecutive_cache_uses` increments on cache reuse; resets on full run; `last_verdict_sha` updated on every full run [REQ: state-schema-for-retry-policy-tracking]
- [x] 12.14 Add directive `max_consecutive_cache_uses: int = 2` in `lib/set_orch/config.py` [REQ: cache-use-cap-reached]
- [x] 12.15 Extend `gate-retry-context` prompt builder to emit a "## Cached Gates" section listing each cached gate with its reused verdict SHA [REQ: retry-prompt-references-cached-verdicts]
- [x] 12.16 Integration test: change with only i18n file touched in retry → `review` cached (out of scope), `design-fidelity` cached (`.tsx` not touched), `e2e` cached (no UI route coverage) [REQ: cached-review-reused-when-retry-diff-is-small]
- [x] 12.17 Integration test: retry touching `src/components/cart/cart-item.tsx` → `design-fidelity` cache invalidated (diff-touches-scope) and full re-run [REQ: cache-invalidated-by-scope-overlap]
- [x] 12.18 Integration test: 3 consecutive retries → 3rd retry forces full run on all previously-cached gates [REQ: cache-use-cap-reached]
- [x] 12.19 Integration test: scoped e2e with cart-page touched → Playwright runs only `cart.spec.ts`, `VERIFY_GATE.scoped_subset` present [REQ: e2e-scoped-to-affected-test-files]

## 13. Cumulative Retry Wall-Time Budget (Layer 1)

- [x] 13.1 Add `retry_wall_time_ms: int = 0` to the Change dataclass; increment by each retry's verify-pipeline wall time [REQ: aggregate-retry-wall-time-budget]
- [x] 13.2 Add directive `max_retry_wall_time_ms: int = 1_800_000` (30 min) in `lib/set_orch/config.py` [REQ: aggregate-retry-wall-time-budget]
- [x] 13.3 After each verify-pipeline run in `run_verify_pipeline()`, if `change.retry_wall_time_ms >= max_retry_wall_time_ms`, emit `RETRY_WALL_TIME_EXHAUSTED` event with `{change, cumulative_ms, retry_count}`, set `change.status = "failed:retry_wall_time_exhausted"`, invoke `escalate_change_to_fix_iss(..., escalation_reason="retry_wall_time_exhausted")` [REQ: aggregate-retry-wall-time-budget]
- [x] 13.4 Integration test: 5 retries of 400s each → 3rd or 4th retry trips the wall-time budget and escalates [REQ: aggregate-retry-wall-time-budget]

## 11. End-to-End Validation

- [ ] 11.1 Re-run the problematic E2E scenario (replan mid-run with different decomposition) using `tests/e2e/runners/run-craftbrew.sh`: verify no tangled state post-replan [REQ: divergent-plan-state-reconciliation]
- [ ] 11.2 Seed an artificial stuck-loop: inject a change whose agent always exits `stuck` → verify `max_stuck_loops=3` escalates to fix-iss [REQ: stuck-loop-circuit-breaker]
- [ ] 11.3 Seed a gate-failure cycle: change that can't pass review → verify budget exhaustion triggers fix-iss auto-creation [REQ: auto-escalate-to-fix-iss-on-retry-budget-exhaustion]
- [ ] 11.4 Verify supervisor event log during a quiet startup: max 1 `log_silence` event per 60s window (then 120s, 240s...) [REQ: exponential-back-off-on-retry_budget_exhausted]
- [ ] 11.5 Decomposer regression: generate a plan for a medium-complexity web spec → confirm all changes meet caps (6/20/12) or are split [REQ: granularity-budget-with-auto-split]
- [ ] 11.6 Gate selection regression: run a foundation-style change with UI files → confirm `design-fidelity`, `e2e`, `i18n_check` are in the active gate set [REQ: content-aware-gate-selector]

## Acceptance Criteria (from spec scenarios)

### REQ: divergent-plan-state-reconciliation
- [x] AC-1: WHEN the prior plan's change set has zero intersection with the new plan THEN reconciliation archives all old worktrees, deletes old branches, and removes orphan `openspec/changes/` dirs [REQ: divergent-plan-state-reconciliation, scenario: new-plan-introduces-entirely-new-change-names]
- [x] AC-2: WHEN there is partial overlap THEN reconciliation touches only non-overlapping artifacts [REQ: divergent-plan-state-reconciliation, scenario: partial-overlap-preserves-shared-names]
- [x] AC-3: WHEN auto_replan_cycle() runs THEN the sequence is context-snapshot → generate → validate → reconcile → init-state [REQ: divergent-plan-state-reconciliation, scenario: replan-context-captured-before-reconciliation]

### REQ: worktree-has-uncommitted-changes-during-divergent-plan-reconciliation
- [x] AC-4: WHEN force_dirty=True and a dirty worktree is not in the new plan THEN stash, archive, and `git worktree remove --force` [REQ: worktree-has-uncommitted-changes-during-divergent-plan-reconciliation, scenario: worktree-has-uncommitted-changes-during-divergent-plan-reconciliation]
- [x] AC-5: WHEN stash fails THEN create `wip/<name>-<epoch>` rescue branch with non-verified commit [REQ: stash-failure-falls-back-to-rescue-branch, scenario: stash-failure-falls-back-to-rescue-branch]

### REQ: single-handler-path-for-stuck-fix-loop-exits-with-new-commits
- [x] AC-6: WHEN loop_status=stuck and new commits exist THEN engine runs verify pipeline directly; verifier does NOT write status=stalled [REQ: single-handler-path-for-stuck-fix-loop-exits-with-new-commits, scenario: stuck-exit-with-new-commits-re-enters-gate]
- [x] AC-7: WHEN loop_status=stuck and no new commits THEN verifier writes status=stalled (existing behavior retained) [REQ: single-handler-path-for-stuck-fix-loop-exits-with-new-commits, scenario: stuck-exit-with-no-new-commits-stalls-normally]

### REQ: stuck-loop-circuit-breaker
- [x] AC-8: WHEN same fingerprint twice THEN stuck_loop_count increments [REQ: stuck-loop-circuit-breaker, scenario: counter-increments-on-identical-fingerprint]
- [x] AC-9: WHEN fingerprint changes THEN stuck_loop_count resets to 0 [REQ: stuck-loop-circuit-breaker, scenario: counter-resets-on-progress]
- [x] AC-10: WHEN stuck_loop_count reaches max_stuck_loops AND fingerprint unchanged THEN status=failed:stuck_no_progress + STUCK_LOOP_ESCALATED event + fix-iss triggered [REQ: stuck-loop-circuit-breaker, scenario: max-stuck-loops-triggers-hard-fail]

### REQ: exponential-back-off-on-retry_budget_exhausted
- [x] AC-11: WHEN first retry_budget_exhausted THEN back_off_until = now + 60s; no further event for 60s [REQ: exponential-back-off-on-retry_budget_exhausted, scenario: first-retry-budget-exhausted-records-back-off-start]
- [x] AC-12: WHEN subsequent exhaustion THEN back-off grows 60 → 120 → 240 → 480 → 600 (cap) [REQ: exponential-back-off-on-retry_budget_exhausted, scenario: back-off-grows-on-repeated-exhaustion]
- [x] AC-13: WHEN detector's condition no longer holds THEN back-off clears [REQ: exponential-back-off-on-retry_budget_exhausted, scenario: back-off-resets-on-transition]

### REQ: per-change-token-runaway-circuit-breaker
- [x] AC-14: WHEN first gate run THEN baseline captured [REQ: per-change-token-runaway-circuit-breaker, scenario: baseline-captured-at-first-gate-run]
- [x] AC-15: WHEN same fingerprint and delta ≥ threshold THEN status=failed:token_runaway + TOKEN_RUNAWAY event [REQ: per-change-token-runaway-circuit-breaker, scenario: delta-exceeds-threshold-triggers-circuit-breaker]
- [x] AC-16: WHEN fingerprint changes THEN baseline resets [REQ: per-change-token-runaway-circuit-breaker, scenario: baseline-resets-on-gate-state-change]

### REQ: content-aware-gate-selector
- [x] AC-17: WHEN change_type=infrastructure but scope has UI globs THEN design-fidelity + e2e + i18n_check in gate set [REQ: content-aware-gate-selector, scenario: foundation-change-with-ui-content-activates-design-plus-e2e]
- [x] AC-18: WHEN server-only globs THEN unit test gate in gate set, no design-fidelity [REQ: content-aware-gate-selector, scenario: server-only-change-activates-unit-tests]
- [x] AC-19: WHEN gate_hints has "require" THEN that gate included regardless of content scan [REQ: content-aware-gate-selector, scenario: gate_hints-wins-over-content-scan]

### REQ: re-detection-on-first-commit-poll
- [x] AC-20: WHEN first commit observed on monitor poll AND gate_recheck_done=False THEN redetect runs before verify pipeline; flag set to True [REQ: re-detection-on-first-commit-poll, scenario: monitor-poll-observes-first-commit]
- [x] AC-21: WHEN re-detection flags UI content not in original scope THEN GATE_SET_EXPANDED event emitted with added_gates [REQ: re-detection-on-first-commit-poll, scenario: agent-commits-ui-file-not-in-original-scope]

### REQ: i18n_check-is-a-hard-fail-gate
- [x] AC-22: WHEN missing translation key detected THEN i18n_check returns fail AND VERIFY_GATE stop_gate=i18n_check [REQ: i18n_check-is-a-hard-fail-gate, scenario: missing-hungarian-translation-key-fails-gate]
- [x] AC-22b: WHEN every `t(...)` call has a key in both hu.json and en.json THEN i18n_check returns pass [REQ: i18n_check-is-a-hard-fail-gate, scenario: both-locales-match]

### REQ: spec_verify-and-review-run-in-parallel
- [x] AC-23: WHEN both gates active THEN VERIFY_GATE includes parallel_group field [REQ: spec_verify-and-review-run-in-parallel, scenario: parallel-execution-records-both-gate_ms]
- [x] AC-24: WHEN spec_verify fails while review is running THEN review completes AND both findings sets surfaced to retry agent [REQ: spec_verify-and-review-run-in-parallel, scenario: both-gates-allowed-to-complete-stop_gate-is-earliest-by-order]

### REQ: granularity-budget-with-auto-split
- [x] AC-25: WHEN proposed change has 15 requirements THEN split into ≥3 changes chained via depends_on, pre-split name never on disk [REQ: granularity-budget-with-auto-split, scenario: change-with-15-requirements-auto-splits-before-persistence]

### REQ: skip_test-guarded-by-scope-file-path-content
- [x] AC-26: WHEN scope has server-path files AND skip_test=true THEN validator rejects [REQ: skip_test-guarded-by-scope-file-path-content, scenario: scope-with-validators-rejects-skip_test]

### REQ: auto-escalate-to-fix-iss-on-retry-budget-exhaustion
- [x] AC-27: WHEN review gate fails 5/5 THEN `escalate_change_to_fix_iss()` invoked; parent status=failed:retry_budget_exhausted; fix_iss_child populated [REQ: auto-escalate-to-fix-iss-on-retry-budget-exhaustion, scenario: review-gate-5-5-fail-triggers-fix-iss]
- [x] AC-27b: WHEN stuck-loop circuit fires THEN `escalate_change_to_fix_iss()` invoked with escalation_reason=stuck_no_progress; parent status=failed:stuck_no_progress; fix_iss_child populated [REQ: stuck-loop-circuit-breaker-also-triggers-fix-iss, scenario: stuck-loop-circuit-breaker-also-triggers-fix-iss]
- [x] AC-27c: WHEN token-runaway fires THEN `escalate_change_to_fix_iss()` invoked with escalation_reason=token_runaway and runaway metadata in proposal; parent status=failed:token_runaway; fix_iss_child populated [REQ: token-runaway-also-triggers-fix-iss, scenario: token-runaway-also-triggers-fix-iss]
- [x] AC-28: WHEN findings are framework paths THEN Fix Target: framework [REQ: fix-iss-change-gets-a-diagnostic-proposal, scenario: framework-findings-produce-target-framework]
- [x] AC-28b: WHEN findings are consumer paths THEN Fix Target: consumer [REQ: fix-iss-change-gets-a-diagnostic-proposal, scenario: consumer-findings-produce-target-consumer]

### REQ: content-hints-for-gate-selection
- [x] AC-29: WHEN scope mentions UI files THEN touched_file_globs includes both explicit paths AND wildcard parents [REQ: content-hints-for-gate-selection, scenario: scope-mentions-ui-files]
- [x] AC-30: WHEN scope mentions only server files THEN touched_file_globs has NO UI-route globs [REQ: content-hints-for-gate-selection, scenario: scope-mentions-only-server-files]

### REQ: divergent-plan-dir-cleanup-safety
- [x] AC-31: WHEN reconciler deletes branches and `openspec/changes/` dirs THEN a manifest file `orchestration-cleanup-<epoch>.log` is written first listing every removed path [REQ: divergent-plan-state-reconciliation, scenario: new-plan-introduces-entirely-new-change-names]
- [x] AC-32: WHEN `divergent_plan_dir_cleanup=dry-run` directive is set THEN the reconciler logs planned deletes but takes no destructive action [REQ: divergent-plan-state-reconciliation, scenario: new-plan-introduces-entirely-new-change-names]

### REQ: size-estimate-formula-for-change-sizing
- [x] AC-33: WHEN estimated_loc < threshold THEN change passes through unchanged [REQ: size-estimate-formula-for-change-sizing, scenario: small-change-under-threshold-passes-through]
- [x] AC-34: WHEN estimated_loc > threshold THEN planner auto-splits into ≥2 siblings [REQ: size-estimate-formula-for-change-sizing, scenario: large-change-triggers-sibling-split]
- [x] AC-35: WHEN active profile is web AND path matches `src/app/admin/**/page.tsx` THEN loc_weight = 350 [REQ: size-estimate-formula-for-change-sizing, scenario: profile-supplies-web-specific-weights]

### REQ: linked-sibling-split-strategy
- [x] AC-36: WHEN admin-operations (est 3760) splits THEN three siblings appear with sequential depends_on chain, same phase=2 [REQ: linked-sibling-split-strategy, scenario: admin-operations-splits-into-3-linked-siblings]
- [x] AC-37: WHEN promotions-engine (est 2000) splits THEN two siblings split by directory prefix (server vs admin) [REQ: linked-sibling-split-strategy, scenario: promotions-engine-splits-by-concern]
- [x] AC-38: WHEN any auto-split runs THEN the pre-split name NEVER appears in orchestration-plan.json [REQ: linked-sibling-split-strategy, scenario: pre-split-name-never-persists]

### REQ: profile-declares-per-gate-retry-policy
- [x] AC-39: WHEN CoreProfile.gate_retry_policy() is invoked THEN returns empty dict (all gates default to always) [REQ: profile-declares-per-gate-retry-policy, scenario: core-profile-default-is-always]
- [x] AC-40: WHEN WebProjectType.gate_retry_policy() is invoked THEN returns the declared mapping with cached=review/spec_verify/design-fidelity and scoped=e2e [REQ: profile-declares-per-gate-retry-policy, scenario: web-profile-declares-policy-per-gate]

### REQ: cached-policy-reuses-prior-verdict-with-invalidation
- [x] AC-41: WHEN retry commit touches only i18n JSON AND review is cached-policy THEN GATE_CACHED event emitted + no review LLM call [REQ: cached-policy-reuses-prior-verdict-with-invalidation, scenario: cached-review-reused-when-retry-diff-is-small]
- [x] AC-42: WHEN retry diff touches `.tsx` THEN design-fidelity cache invalidated with reason diff-touches-scope [REQ: cached-policy-reuses-prior-verdict-with-invalidation, scenario: cache-invalidated-by-scope-overlap]
- [x] AC-43: WHEN 3rd consecutive cache use THEN cache invalidated with reason cache-use-cap-reached, gate runs fully [REQ: cache-use-cap-reached, scenario: cache-use-cap-reached]
- [x] AC-44: WHEN retry diff adds new exported function THEN cache invalidated with reason new-api-surface-detected [REQ: cached-policy-reuses-prior-verdict-with-invalidation, scenario: new-api-surface-invalidates-cache]

### REQ: scoped-policy-shards-gate-by-retry-diff
- [x] AC-45: WHEN retry touches cart page AND e2e is scoped THEN Playwright runs only cart.spec.ts; VERIFY_GATE.scoped_subset present [REQ: scoped-policy-shards-gate-by-retry-diff, scenario: e2e-scoped-to-affected-test-files]
- [x] AC-46: WHEN gate_scope_filter returns None THEN gate falls through to cached policy [REQ: scoped-policy-shards-gate-by-retry-diff, scenario: e2e-no-overlap-falls-through-to-cached]
- [x] AC-47: WHEN scoped gate has been filtered for 2 consecutive retries THEN 3rd retry runs full suite [REQ: scoped-policy-shards-gate-by-retry-diff, scenario: scoped-filter-still-subject-to-cache-use-cap]

### REQ: verify-pipeline-honors-per-gate-retry-policy
- [x] AC-48: WHEN verify_retry_index == 0 THEN every gate runs fully regardless of policy, no GATE_CACHED events [REQ: verify-pipeline-honors-per-gate-retry-policy, scenario: first-verify-run-ignores-retry-policy]
- [x] AC-49: WHEN verify_retry_index >= 1 THEN policy consulted and applied per gate [REQ: verify-pipeline-honors-per-gate-retry-policy, scenario: second-verify-run-applies-retry-policy]

### REQ: retry-prompt-references-cached-verdicts
- [x] AC-50: WHEN retry dispatched with some cached gates THEN retry prompt contains ## Cached Gates section listing them with SHAs [REQ: retry-prompt-references-cached-verdicts, scenario: retry-prompt-lists-cached-gates]

### REQ: aggregate-retry-wall-time-budget
- [x] AC-51: WHEN cumulative retry_wall_time_ms exceeds max_retry_wall_time_ms THEN RETRY_WALL_TIME_EXHAUSTED event + status=failed:retry_wall_time_exhausted + fix-iss escalation [REQ: aggregate-retry-wall-time-budget, scenario: wall-time-budget-tripped-on-5th-retry]
- [x] AC-52: WHEN retries are fast (5 × 60s) THEN no wall-time-exhausted event fires [REQ: aggregate-retry-wall-time-budget, scenario: wall-time-budget-never-tripped-on-fast-retries]
