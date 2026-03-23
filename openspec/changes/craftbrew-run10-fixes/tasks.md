# Tasks

## 1. Duplicate Dispatch Guard (dispatcher.py)

- [ ] 1.1 In `dispatch_change()`, add atomic status check with `locked_state` before worktree creation: verify change is "pending", set to "dispatched" atomically
- [ ] 1.2 In `dispatch_all_ready()`, re-read state after each dispatch to catch concurrent changes
- [ ] 1.3 Handle existing worktree gracefully in `dispatch_change()` — if worktree exists and change is "dispatched"/"running", skip instead of creating `-2` suffix

## 2. Merge Retry Counter (merger.py)

- [ ] 2.1 In `retry_merge_queue()`, read `merge_retry_count` from change extras before re-adding to queue
- [ ] 2.2 If `merge_retry_count` >= 3, set status to `integration-failed` and skip (don't re-add to queue)
- [ ] 2.3 Increment `merge_retry_count` in extras when re-adding to queue
- [ ] 2.4 In `resume_change()` (dispatcher.py), reset `merge_retry_count` to 0 when agent is redispatched for fixes

## 3. Stall Detection Reorder (lib/loop/engine.sh)

- [ ] 3.1 Move `check_done` call to BEFORE the commit/stall check block
- [ ] 3.2 If `check_done` returns true, set `is_done=true` and reset stall counter — skip stall detection entirely
- [ ] 3.3 Add fallback: if primary done criteria says "not done" but `find_tasks_file && check_tasks_done` passes, also mark done

## 4. Vitest Planning Rule (modules/web)

- [ ] 4.1 Add explicit rule to `planning_rules.txt`: infrastructure change MUST include `test` script in package.json + vitest in devDependencies
- [ ] 4.2 Add rule: "Do NOT defer test runner setup to later changes — the foundation change owns all tooling"

## 5. Pre-Build Hook (profile_types.py + web module + merger.py)

- [ ] 5.1 Add `integration_pre_build(self, wt_path: str) -> bool` method to `ProjectType` ABC in `profile_types.py` with default `return True`
- [ ] 5.2 Implement `integration_pre_build()` in `WebProjectType`: run `prisma db push --skip-generate --accept-data-loss` if schema exists (no seed)
- [ ] 5.3 In `merger.py _run_integration_gates()`, replace `e2e_pre_gate()` call before build with `integration_pre_build()` call
- [ ] 5.4 If `integration_pre_build()` returns False, log warning but continue (non-blocking)

## 6. Code Review Fixes (from today's review)

- [ ] 6.1 In `engine.py _poll_suspended_changes()`, replace silent `except Exception: pass` with `logger.debug` on loop-state parse error (WARNING from review)
- [ ] 6.2 In `merger.py`, scope `is_empty_fail` heuristic to npm/pnpm only — check if test command contains `pnpm` or `npm` before applying empty-output skip (WARNING from review)
- [ ] 6.3 In `sentinel-autonomy.md`, add explicit mention of `git merge --ff-only` to the prohibition (SUGGESTION from review)
