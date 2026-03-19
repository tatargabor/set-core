# Tasks: sentinel-e2e-intelligence

## Group 1: Tier 1 Expansion — Expected Patterns (A)

- [x] 1.1 Add expected-pattern table to `.claude/commands/wt/sentinel.md` after the existing Tier 1/2 table — include post-merge codegen, watchdog grace, stale cache, long MCP fetch, waiting:api patterns with explanations and durations [REQ: expected-pattern-awareness]
- [x] 1.2 Sync the expanded Tier 1 list to `docs/sentinel.md` [REQ: expected-pattern-awareness]

## Group 2: Token Stuck Detection (B)

- [x] 2.1 Add per-change stuck detection to the poll bash script in sentinel.md — check tokens_used > 500K with no last_commit_at in 30 min, emit WARNING:token_stuck [REQ: token-stuck-detection]
- [x] 2.2 Add WARNING:token_stuck handler in Step 3 — escalate to user on first detection, suppress repeats [REQ: token-stuck-detection]
- [x] 2.3 Add per-change token breakdown with stuck flags to the completion report template in Step 5 [REQ: token-stuck-detection]

## Group 3: Dependency Deadlock Detection (C)

- [x] 3.1 Add deadlock detection to the poll bash script — check pending changes where all depends_on entries are failed, emit WARNING:deadlocked [REQ: dependency-deadlock-detection]
- [x] 3.2 Add WARNING:deadlocked handler in Step 3 — report change names and failed deps to user, no auto-fix [REQ: dependency-deadlock-detection]

## Group 4: E2E Sentinel Mode — Tier 3 (D)

- [x] 4.1 Add "## E2E Mode (Tier 3)" section to `.claude/commands/wt/sentinel.md` after the Guardrails section — scope boundary table, workflow (detect→fix→commit→deploy→sync→restart→log), explicit FORBIDDEN list [REQ: e2e-tier3-framework-fix-authority]
- [x] 4.2 Update `tests/e2e/E2E-GUIDE.md` "When You Fix a set-core Bug" section to reference Tier 3 scope boundary and link to sentinel skill [REQ: e2e-tier3-framework-fix-authority]
- [x] 4.3 Add Tier 3 mention to `docs/sentinel.md` E2E mode description [REQ: e2e-tier3-framework-fix-authority]

## Group 5: set-orchestrate reset CLI (E)

- [x] 5.1 Add `reset` subcommand to `bin/set-orchestrate` — parse `--partial` (default), `--full`, `--yes-i-know` flags [REQ: partial-reset-safe-default, full-reset-requires-confirmation]
- [x] 5.2 Implement partial reset logic — iterate changes, reset failed→pending, clear worktree_path/ralph_pid/verify_retry_count, set status=running, print summary [REQ: partial-reset-safe-default]
- [x] 5.3 Implement full reset dry-run — when `--full` without `--yes-i-know`, print what would be destroyed and exit [REQ: full-reset-requires-confirmation]
- [x] 5.4 Implement full reset execution — backup state, remove worktrees, reset all changes, clear events, print summary [REQ: full-reset-requires-confirmation]
- [x] 5.5 Update `tests/e2e/E2E-GUIDE.md` "State Reset" section to reference `set-orchestrate reset` instead of inline Python/bash snippets [REQ: sentinel-no-longer-resets-state]
- [x] 5.6 Remove any state reset guidance from `.claude/commands/wt/sentinel.md` if present [REQ: sentinel-no-longer-resets-state]

## Group 6: Acceptance Criteria

- [x] 6.1 Verify sentinel skill has expanded Tier 1 table with all 5 expected patterns
- [x] 6.2 Verify poll script emits WARNING:token_stuck and WARNING:deadlocked events
- [x] 6.3 Verify E2E Mode section has explicit FORBIDDEN list matching design
- [x] 6.4 Verify `set-orchestrate reset --partial` only touches failed changes
- [x] 6.5 Verify `set-orchestrate reset --full` without `--yes-i-know` is dry-run only
- [x] 6.6 Verify docs/sentinel.md and E2E-GUIDE.md are in sync with skill changes
