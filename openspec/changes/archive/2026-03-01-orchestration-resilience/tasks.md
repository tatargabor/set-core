## 1. FF Retry Limit in Ralph Loop

- [x] 1.1 Add `ff_attempts` counter variable in `cmd_run()` (initialized to 0, reset on tasks.md creation)
- [x] 1.2 After each `ff:` iteration, check if `tasks.md` exists in the change directory — if not, increment `ff_attempts`
- [x] 1.3 If `ff_attempts >= ff_max_retries` (default 2, read from loop-state), stop loop with status `"stalled"` and message about ff exhaustion
- [x] 1.4 Write `ff_attempts` to `loop-state.json` on each update and include `ff_exhausted: true` in the iteration record when limit hit

## 2. Token Budget Enforcement

- [x] 2.1 Add `--token-budget N` flag parsing in `cmd_start()` argument loop (N in thousands, stored as N*1000 in state)
- [x] 2.2 Store `token_budget` in `loop-state.json` via `init_loop_state` — default 0 (unlimited)
- [x] 2.3 Display budget in banner line if non-zero: "Budget: {N}K tokens"
- [x] 2.4 After updating `total_tokens` in the iteration loop, check if `token_budget > 0 && total_tokens > token_budget` — if so, stop with status `"budget_exceeded"`
- [x] 2.5 In `wt-orchestrate dispatch_change()`, pass `--token-budget` based on change size annotation (S:100, M:300, L:500, XL:1000)

## 3. Worktree .env Bootstrap

- [x] 3.1 Add `bootstrap_env_files()` function in `wt-new` that copies `.env` and `.env.local` from main repo to worktree (skip if source missing, don't overwrite existing)
- [x] 3.2 Resolve main repo path via `git worktree list | head -1 | awk '{print $1}'`
- [x] 3.3 Call `bootstrap_env_files` BEFORE `bootstrap_dependencies` in the main flow

## 4. No-op Iteration Marker

- [x] 4.1 In `cmd_run()` iteration loop, after stall detection block: if `new_commits == "[]"` AND `has_artifact_progress == false`, write `.claude/loop-iteration-noop` with ISO timestamp
- [x] 4.2 If iteration is productive (commits or artifact progress), remove `.claude/loop-iteration-noop` if it exists
- [x] 4.3 Add `no_op: true` to iteration record in `add_iteration` call when no-op detected

## 5. Session-End Hook No-op Guard

- [x] 5.1 In `wt-hook-stop` (or the memory extraction hook), check for `.claude/loop-iteration-noop` at the start
- [x] 5.2 If marker exists and is less than 1 hour old, skip memory extraction, log "Skipping memory save — no-op loop iteration", and remove the marker
- [x] 5.3 If marker is stale (>1 hour), ignore it and proceed normally

## 6. Loop-State Status Value Update

- [x] 6.1 Update `"budget_exceeded"` as a recognized status in any status-checking code (wt-orchestrate `poll_change`, `get_changes_by_status`, sentinel)
- [x] 6.2 In `wt-orchestrate`, treat `budget_exceeded` like a checkpoint — log it, notify, allow manual resume with extended budget
