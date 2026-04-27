# Spec: Orchestration Log Quality

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Spec verify sentinel detection and logging
- Context window metric correction (model detection + peak vs cumulative)
- `run_git` best_effort flag and adoption in fetch calls
- Design context anomaly conditional logging
- `parse_test_plan` log level fix
- Worktree-aware claude project dir derivation

### Out of scope
- Planner coverage gap handling (uncovered REQs) — separate change
- Removing or rewriting the spec_verify gate
- Changing test plan format (`JOURNEY-TEST-PLAN.md` vs `test-plan.json`)
- Token usage per-worktree isolation (stays per-repo)

## Requirements

### Requirement: Spec verify gate detects missing sentinel
The `spec_verify` gate SHALL distinguish between three outcomes: PASS sentinel found, FAIL sentinel found, and missing sentinel. Missing sentinel SHALL log at WARNING level with text identifying it as a missing sentinel (not "timeout"), and emit an ANOMALY entry tagged for sentinel tracking. Backward compat: missing sentinel still resolves to PASS.

#### Scenario: Agent writes PASS sentinel
- **WHEN** the verify command output contains `VERIFY_RESULT: PASS`
- **THEN** the gate logs `Gate[spec-verify] END <change> result=pass` and returns pass

#### Scenario: Agent writes FAIL sentinel
- **WHEN** the verify command output contains `VERIFY_RESULT: FAIL`
- **THEN** the gate logs `Spec coverage FAIL` and returns fail with retry context

#### Scenario: Agent writes neither sentinel
- **WHEN** the verify command exits 0 but output contains neither sentinel
- **THEN** the gate logs `Spec verify: missing VERIFY_RESULT sentinel — assuming PASS (verify skill prompt issue)` and returns pass

### Requirement: Verify skill prompt requires sentinel
The `/opsx:verify` skill SHALL include explicit instructions that the agent MUST output a final line of either `VERIFY_RESULT: PASS` or `VERIFY_RESULT: FAIL` before terminating.

#### Scenario: Verify skill includes sentinel requirement
- **WHEN** the `/opsx:verify` skill markdown is read
- **THEN** it contains a section explicitly instructing the agent to write `VERIFY_RESULT: <verdict>` as the final line

### Requirement: Context window metric uses correct window size
The `_context_window_for_model` function SHALL return `1_000_000` for `opus`, `sonnet`, `claude-opus`, `claude-sonnet`, and any 4.x family model name when no explicit `[1m]` or `200k` suffix is present. This reflects the Claude 4.x default of 1M context.

#### Scenario: Default opus model
- **WHEN** `_context_window_for_model("opus")` is called
- **THEN** it returns `1_000_000`

#### Scenario: Default sonnet model
- **WHEN** `_context_window_for_model("sonnet")` is called
- **THEN** it returns `1_000_000`

#### Scenario: Explicit 1m suffix
- **WHEN** `_context_window_for_model("opus[1m]")` is called
- **THEN** it returns `1_000_000`

#### Scenario: Explicit 200k requested
- **WHEN** `_context_window_for_model("opus[200k]")` is called
- **THEN** it returns `200_000`

### Requirement: Context tokens end uses peak iteration value
The `_capture_context_tokens_end` function SHALL compute peak context size as `max(iter.cache_create_tokens for iter in iterations)`, not `total_cache_create` (cumulative).

#### Scenario: Single iteration
- **WHEN** loop_state has 1 iteration with `cache_create_tokens=300000`
- **THEN** `context_tokens_end = 300000`

#### Scenario: Multiple iterations
- **WHEN** loop_state has 3 iterations with `cache_create_tokens` values `[300000, 350000, 280000]` and `total_cache_create=930000`
- **THEN** `context_tokens_end = 350000` (the max), not `930000`

### Requirement: Run git supports best-effort mode
The `run_git` helper SHALL accept a `best_effort: bool = False` parameter. When `True`, the helper SHALL NOT log a WARNING on non-zero exit code. The function SHALL still return the GitResult so callers can inspect the exit code.

#### Scenario: Default behavior unchanged
- **WHEN** `run_git("status")` fails
- **THEN** a WARNING is logged (current behavior)

#### Scenario: Best-effort fetch fails
- **WHEN** `run_git("fetch", "origin", "main", best_effort=True)` fails
- **THEN** no WARNING is logged, but the GitResult.exit_code is still non-zero

### Requirement: Best-effort flag adopted by fetch callers
All `git fetch origin` invocations in `merger.py`, `verifier.py`, and `loop_tasks.py` that are documented as "best-effort" SHALL pass `best_effort=True` to `run_git`.

#### Scenario: Merger fetch
- **WHEN** `_integrate_main_into_branch` runs in a project without origin remote
- **THEN** no WARNING is logged for the fetch failure

### Requirement: Design context anomaly is conditional
The `[ANOMALY]` warning for empty design context SHALL only fire when at least one design asset (`docs/design-system.md`, `docs/design-snapshot.md`, or `docs/design-brief.md`) exists in the project root. Otherwise, log at INFO level as `Design context not available for <change> — no design assets in project`.

#### Scenario: No design assets
- **WHEN** dispatching a change in a project without any design files and the context is empty
- **THEN** an INFO log is emitted, not an ANOMALY warning

#### Scenario: Design assets exist but context is empty
- **WHEN** `docs/design-snapshot.md` exists but `get_design_dispatch_context` returns empty
- **THEN** the `[ANOMALY]` WARNING is emitted (real bug in bridge.sh or matcher)

### Requirement: Test plan missing logs at debug level
The `parse_test_plan` function SHALL log at `debug` level (not `warning`) when the file is not found. Callers always have a fallback path.

#### Scenario: JOURNEY-TEST-PLAN.md missing
- **WHEN** `parse_test_plan(Path("nonexistent.md"))` is called
- **THEN** a debug log is emitted, no warning

### Requirement: Worktree-aware claude project dir
The `get_current_tokens` shell function in `lib/loop/state.sh` SHALL detect worktrees via `git rev-parse --git-common-dir` and derive the parent repository path. The parent path SHALL be used to compose the `--project-dir` flag for `set-usage`.

#### Scenario: Running in a worktree
- **WHEN** `get_current_tokens` is called from `/path/to/.local/share/set-core/e2e-runs/minishop-run2-wt-foundation-setup`
- **THEN** the function derives the parent repo dir, finds the matching `~/.claude/projects/<derived>` if present, and passes `--project-dir=<derived>`. No warning is emitted.

#### Scenario: Running in a regular repo
- **WHEN** `get_current_tokens` is called from a non-worktree directory
- **THEN** behavior is unchanged from current
