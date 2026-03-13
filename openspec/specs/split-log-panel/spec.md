## ADDED Requirements

### Requirement: Side-by-side orch log and session log
The log panel displays orchestration log and session log simultaneously when a change is selected.

#### Scenario: Change selected — split view
- **WHEN** a change is selected in the ChangeTable
- **THEN** the log panel splits horizontally: left side shows orch log, right side shows session log
- **THEN** both sides scroll independently
- **THEN** both sides have auto-scroll behavior (jump-to-bottom)

#### Scenario: No change selected — full width orch log
- **WHEN** no change is selected
- **THEN** the log panel shows the orch log at full width (no split)

#### Scenario: Split ratio persistence
- **WHEN** the user resizes the horizontal split
- **THEN** the ratio is saved to localStorage
- **THEN** on next visit, the saved ratio is restored
