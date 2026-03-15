## MODIFIED Requirements

### Requirement: Test done criteria runs test command
The loop system SHALL support `done_criteria = "test"` in `is_done()`. When active, `_check_test_done()` SHALL run the project's test command and return True if tests pass (exit code 0), False otherwise.

**Added pre-condition:** Before running the test command, `is_done()` SHALL check for uncommitted work via `git_has_uncommitted_work(wt_path)`. If uncommitted work exists, `is_done()` SHALL return False regardless of test results.

#### Scenario: Test command passes but uncommitted work exists
- **WHEN** `is_done("test")` is called
- **AND** `git_has_uncommitted_work(wt_path)` returns `(True, "7 untracked")`
- **THEN** `is_done()` SHALL return False without running the test command

#### Scenario: Test command passes and worktree is clean
- **WHEN** `is_done("test")` is called
- **AND** `git_has_uncommitted_work(wt_path)` returns `(False, "")`
- **AND** the test command exits with code 0
- **THEN** `is_done()` SHALL return True

#### Scenario: Test command fails and worktree is clean
- **WHEN** `is_done("test")` is called
- **AND** `git_has_uncommitted_work(wt_path)` returns `(False, "")`
- **AND** the test command exits with non-zero code
- **THEN** `is_done()` SHALL return False

### Requirement: Uncommitted check applies to all done_criteria except manual
The uncommitted work pre-check SHALL apply to done_criteria values: `tasks`, `openspec`, `build`, `merge`, `test`. It SHALL NOT apply to `manual` (manual tasks may have no code changes). For `openspec` criteria, the check catches agents that have completed artifact work but forgotten to commit code changes.

#### Scenario: Tasks done but uncommitted work
- **WHEN** `is_done("tasks")` is called
- **AND** all tasks are checked in tasks.md
- **AND** `git_has_uncommitted_work(wt_path)` returns `(True, "1 modified")`
- **THEN** `is_done()` SHALL return False

#### Scenario: Manual done with uncommitted work
- **WHEN** `is_done("manual")` is called
- **AND** `manual_done` is True in loop-state.json
- **AND** `git_has_uncommitted_work(wt_path)` returns `(True, "2 untracked")`
- **THEN** `is_done()` SHALL return True (uncommitted check skipped for manual)
