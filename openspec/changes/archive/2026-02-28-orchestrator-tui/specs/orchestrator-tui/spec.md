## ADDED Requirements

### Requirement: TUI launch
The system SHALL provide a `set-orchestrate tui` subcommand that launches a Textual terminal application. The TUI SHALL require an `orchestration-state.json` file in the current directory (or project root). If no state file exists, the TUI SHALL exit with an informative message suggesting `set-orchestrate plan` or `set-orchestrate start`.

#### Scenario: Launch with active orchestration
- **WHEN** `set-orchestrate tui` is run in a directory with `orchestration-state.json`
- **THEN** a full-screen Textual app launches showing orchestration status

#### Scenario: Launch without state file
- **WHEN** `set-orchestrate tui` is run without `orchestration-state.json`
- **THEN** the command exits with message "No orchestration state found. Run 'set-orchestrate plan' first."

---

### Requirement: Header status display
The TUI SHALL display a header bar showing: orchestrator status (running/checkpoint/paused/stopped/done/failed/time_limit), plan version with replan cycle number (if >0), progress ratio (merged+done/total), cumulative total tokens (current cycle tokens_used + prev_total_tokens from prior replan cycles), active time and time limit with remaining.

#### Scenario: Running orchestration header
- **WHEN** orchestration status is "running" with 3/10 changes done, plan_version=7, replan_cycle=5
- **THEN** header shows "● RUNNING  Plan v7 (replan #5)  3/10 done  Tokens: 3.6M  Active: 43m / 5h limit (4h17m remaining)"

#### Scenario: First plan without replans
- **WHEN** orchestration has replan_cycle=0
- **THEN** header shows plan version without replan suffix: "● RUNNING  Plan v1  2/5 done"

#### Scenario: Checkpoint waiting header
- **WHEN** orchestration status is "checkpoint"
- **THEN** header shows "⏸ CHECKPOINT" with blinking/highlighted style to draw attention

#### Scenario: Time limit exceeded header
- **WHEN** orchestration status is "time_limit"
- **THEN** header shows "⏱ TIME LIMIT" in yellow with note "Run 'set-orchestrate start' to continue"

---

### Requirement: Change table
The TUI SHALL display a table of all changes with columns: Name (truncated to 25 chars), Status (colored), Iteration progress (from loop-state.json), Tokens, and Gate results in execution order: test/build/review/verify (T/B/R/V) as pass/fail/pending indicators.

#### Scenario: Change with all gates passed
- **WHEN** a change has test_result=pass, build_result=pass, review_result=pass, verify completed
- **THEN** the row shows "T✓ B✓ R✓ V✓" in the Gates column with green coloring

#### Scenario: Change with build failure
- **WHEN** a change has test_result=pass but build_result=fail
- **THEN** the row shows "T✓ B✗" in the Gates column (build in red), review/verify not shown (not reached)

#### Scenario: Pending change
- **WHEN** a change has status "pending"
- **THEN** the row shows dimmed/gray text with no gate or token data

---

### Requirement: Live log tail
The TUI SHALL display a log panel tailing `.claude/orchestration.log`. Log lines SHALL be colored by level: INFO=default, WARN=yellow, ERROR=red. The log panel SHALL auto-scroll to bottom on new entries.

#### Scenario: New log entry appears
- **WHEN** orchestration writes a new line to the log file
- **THEN** the TUI displays it within the next refresh cycle (3-5 seconds)

#### Scenario: Log file does not exist
- **WHEN** `.claude/orchestration.log` is missing
- **THEN** the log panel shows "No log file yet" in dimmed text

---

### Requirement: Checkpoint approval
The TUI SHALL provide a keyboard shortcut `a` to approve a checkpoint. Approval SHALL only be active when orchestrator status is "checkpoint". The approval SHALL write to `orchestration-state.json` atomically (write temp + rename): set `checkpoints[-1].approved = true` and `checkpoints[-1].approved_at` to current ISO timestamp.

#### Scenario: Approve at checkpoint
- **WHEN** orchestrator is in "checkpoint" status and user presses `a`
- **THEN** the state file is updated atomically and the TUI shows a confirmation notification

#### Scenario: Approve when not at checkpoint
- **WHEN** orchestrator is in "running" status and user presses `a`
- **THEN** nothing happens (shortcut is inactive) or a brief "Not at checkpoint" message appears

---

### Requirement: Auto-refresh
The TUI SHALL re-read `orchestration-state.json` and `.claude/orchestration.log` on a timer interval of 3 seconds. The display SHALL update without flicker. The user SHALL be able to force an immediate refresh with `r`.

#### Scenario: State file updated externally
- **WHEN** the orchestrator updates orchestration-state.json
- **THEN** the TUI reflects the new state within 3 seconds

#### Scenario: Force refresh
- **WHEN** user presses `r`
- **THEN** data is re-read immediately and display updates

---

### Requirement: Keyboard navigation
The TUI SHALL support: `q` to quit, `a` to approve checkpoint, `r` to refresh, `l` to toggle between split view (table+log) and full log view. The TUI SHALL display available keybindings in a footer bar.

#### Scenario: Toggle full log
- **WHEN** user presses `l`
- **THEN** the view switches between split (table+log) and full-screen log

#### Scenario: Quit
- **WHEN** user presses `q`
- **THEN** the TUI exits cleanly
