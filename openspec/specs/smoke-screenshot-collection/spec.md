# Smoke Screenshot Collection Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Smoke test artifact collection
After post-merge smoke tests run on main, the orchestrator SHALL collect Playwright artifacts (screenshots, traces) into a persistent directory.

#### Scenario: Successful artifact collection
- **WHEN** the smoke pipeline completes (pass or fail) for change `{name}`
- **THEN** the orchestrator SHALL check for a `test-results/` directory in the project root (hardcoded Playwright default — conscious decision, see design)
- **AND** if found, copy its contents to `set/orchestration/smoke-screenshots/{name}/attempt-{N}/` where N is the attempt number (1 for initial run, incrementing for fix retries)
- **AND** count `.png` files across ALL attempt subdirectories for the change
- **AND** update the change state with `smoke_screenshot_dir` (parent dir, without attempt suffix) and `smoke_screenshot_count` (total across all attempts)

#### Scenario: No test-results directory
- **WHEN** the smoke pipeline completes
- **AND** no `test-results/` directory exists (e.g., Jest-only smoke with no Playwright)
- **THEN** `smoke_screenshot_count` SHALL be set to 0
- **AND** `smoke_screenshot_dir` SHALL be set to the empty string
- **AND** no error SHALL be raised

#### Scenario: Artifact directory creation
- **WHEN** collecting smoke artifacts for change `{name}` at attempt `{N}`
- **THEN** the directory `set/orchestration/smoke-screenshots/{name}/attempt-{N}/` SHALL be created via `mkdir -p`
- **AND** previous attempt subdirectories SHALL be preserved (NOT overwritten) — failure screenshots are the most diagnostic artifacts

### Requirement: Per-change E2E artifact collection
After pre-merge E2E tests run in a worktree, the orchestrator SHALL collect Playwright artifacts.

#### Scenario: Successful artifact collection from worktree
- **WHEN** the per-change E2E gate completes (pass or fail) for change `{name}`
- **THEN** the orchestrator SHALL check for `test-results/` in the worktree path
- **AND** if found, copy its contents to `set/orchestration/e2e-screenshots/{name}/` in the main project
- **AND** count `.png` files in the directory
- **AND** update the change state with `e2e_screenshot_dir` and `e2e_screenshot_count`

#### Scenario: No test-results in worktree
- **WHEN** the per-change E2E gate completes
- **AND** no `test-results/` directory exists in the worktree
- **THEN** `e2e_screenshot_count` SHALL be set to 0
- **AND** no error SHALL be raised

### Requirement: Multi-change smoke failure context
When smoke tests fail after a checkpoint (multiple merges), the fix agent SHALL receive context about ALL changes merged since the last successful smoke.

#### Scenario: Checkpoint smoke failure
- **WHEN** smoke tests fail after a checkpoint merge
- **THEN** the fix prompt SHALL include the list of ALL changes merged since the last successful smoke pass
- **AND** for each change, include the change name and its file diff summary (`git diff` between merge tags or commits)
- **AND** the prompt SHALL say: "These changes were merged since the last successful smoke. Investigate which change or interaction caused the regression."

#### Scenario: Single merge smoke failure
- **WHEN** smoke tests fail after a single merge (non-checkpoint)
- **THEN** the fix prompt SHALL include only the single change's context (existing behavior)

#### Scenario: Tracking last successful smoke
- **WHEN** a smoke test passes (result = "pass" or "fixed")
- **THEN** the orchestrator SHALL record `last_smoke_pass_commit` in state.json with the current HEAD SHA
- **AND** on subsequent smoke failure, use this SHA to compute `git log --oneline {sha}..HEAD` for the multi-change context

#### Scenario: No previous smoke pass (cold start)
- **WHEN** smoke tests fail and `last_smoke_pass_commit` is empty (no smoke has passed yet in this orchestration run)
- **THEN** multi-change context SHALL be skipped
- **AND** the fix prompt SHALL use single-change context only (existing behavior)

### Requirement: Already-merged smoke skip status
Changes that skip the smoke pipeline (already on main from previous phase) SHALL get an explicit status.

#### Scenario: Already-merged branch detected
- **WHEN** `merge_change()` detects the branch is already ancestor of HEAD (previous phase merge)
- **THEN** `smoke_result` SHALL be set to `"skip_merged"` (distinct from `"skip"` which means no smoke_command configured)
- **AND** `smoke_status` SHALL be set to `"skipped"`

#### Scenario: Branch deleted (assumed merged)
- **WHEN** `merge_change()` detects the branch no longer exists
- **THEN** `smoke_result` SHALL be set to `"skip_merged"` (distinct from `"skip"` which means no smoke_command configured)
- **AND** `smoke_status` SHALL be set to `"skipped"`
