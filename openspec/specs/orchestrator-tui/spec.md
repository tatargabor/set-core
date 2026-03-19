### Requirement: TUI launch
The orchestrator SHALL provide a terminal dashboard via `set-orchestrate tui`.

#### Scenario: Launch with state file
- **WHEN** `set-orchestrate tui` is invoked
- **AND** `orchestration-state.json` exists
- **THEN** the orchestrator SHALL launch a Textual-based Python TUI app
- **AND** pass the state file path and log file path as arguments

#### Scenario: Launch without state file
- **WHEN** `set-orchestrate tui` is invoked
- **AND** no `orchestration-state.json` exists
- **THEN** the orchestrator SHALL exit with: "No orchestration state found."

#### Scenario: Textual dependency check
- **WHEN** launching the TUI
- **THEN** the orchestrator SHALL verify the `textual` Python package is importable
- **AND** try conda python as fallback if system python lacks textual
- **AND** exit with install instructions if textual is not available

### Requirement: Header status display
The TUI SHALL display orchestrator status in a header bar.

#### Scenario: Running state header
- **WHEN** the orchestrator status is `running`
- **THEN** the header SHALL show: status indicator, plan version (with replan cycle if >0), progress ratio (merged+done/total), cumulative tokens, active time / time limit with remaining

#### Scenario: Checkpoint state header
- **WHEN** the orchestrator status is `checkpoint`
- **THEN** the header SHALL display a highlighted/blinking checkpoint indicator

#### Scenario: Time limit exceeded header
- **WHEN** the orchestrator status is `time_limit`
- **THEN** the header SHALL display a yellow time limit indicator

### Requirement: Change table display
The TUI SHALL display a table of all changes with their status and metrics.

#### Scenario: Table columns
- **WHEN** rendering the change table
- **THEN** columns SHALL include: Name (25 chars), Status (colored), Iteration (from loop-state.json), Tokens, Gates (T/B/R/V indicators)

#### Scenario: Status coloring
- **WHEN** rendering change status
- **THEN** colors SHALL be: green=running, blue=done, bright_green=merged, red=failed, yellow=pending/dispatched

#### Scenario: Gate display
- **WHEN** all gates passed
- **THEN** display "T✓ B✓ R✓ V✓" in green
- **WHEN** a gate failed
- **THEN** display the failed gate with ✗ in red, omit subsequent gates

### Requirement: Live log tail
The TUI SHALL display the orchestration log with auto-scroll.

#### Scenario: Log display
- **WHEN** `.claude/orchestration.log` exists
- **THEN** the TUI SHALL display the last ~200 lines with color by level: INFO=default, WARN=yellow, ERROR=red
- **AND** update within 3-5 seconds

#### Scenario: Missing log
- **WHEN** the log file does not exist
- **THEN** the TUI SHALL display "No log file yet" dimmed

### Requirement: Checkpoint approval via TUI
The TUI SHALL allow approving checkpoints via keyboard shortcut.

#### Scenario: Approve checkpoint
- **WHEN** the user presses `a` during a checkpoint
- **THEN** the TUI SHALL atomically write approval to orchestration-state.json (temp file + rename)
- **AND** set `checkpoints[-1].approved = true` and `approved_at` timestamp

#### Scenario: Approve outside checkpoint
- **WHEN** the user presses `a` and status is NOT `checkpoint`
- **THEN** the keypress SHALL be ignored

### Requirement: Auto-refresh
The TUI SHALL automatically refresh data from state and log files.

#### Scenario: Periodic refresh
- **WHEN** the TUI is running
- **THEN** it SHALL re-read state + log every 3 seconds without flicker

#### Scenario: Manual refresh
- **WHEN** the user presses `r`
- **THEN** the TUI SHALL immediately refresh all data

### Requirement: Keyboard navigation
The TUI SHALL support keyboard shortcuts for common actions.

#### Scenario: Keyboard bindings
- **WHEN** the TUI is running
- **THEN** the following keys SHALL be active:
  - `q`: quit the TUI
  - `a`: approve checkpoint
  - `r`: force refresh
  - `l`: toggle between split view (table+log) and full log view
- **AND** a footer bar SHALL display the available keybindings
## Requirements
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

