### Requirement: Label flag for loop identification
The `set-loop start` command SHALL accept an optional `--label <text>` flag to identify the loop instance.

#### Scenario: Starting with a label
- **WHEN** user runs `set-loop start "task" --label "Run A (baseline)"`
- **THEN** the label SHALL be stored in `loop-state.json` as `"label": "Run A (baseline)"`
- **AND** the label SHALL appear in the startup banner and terminal title

#### Scenario: Starting without a label
- **WHEN** user runs `set-loop start "task"` without `--label`
- **THEN** `loop-state.json` SHALL contain `"label": null`
- **AND** the banner SHALL omit the Label line
- **AND** the terminal title SHALL use the existing format without parenthetical

### Requirement: Expanded startup banner
The `set-loop run` command SHALL display an expanded banner at startup with full context.

#### Scenario: Banner content with label
- **WHEN** Ralph loop starts with a label set
- **THEN** the banner SHALL include in order:
  - Worktree name
  - Label (the `--label` value)
  - Full absolute path of the worktree
  - Current git branch name
  - Full task description (not truncated)
  - A separator line
  - Loop parameters: permission mode, max iterations, stall threshold, iteration timeout
  - Memory status: "active" if `set-memory health` succeeds, "inactive" otherwise
  - Start timestamp in `YYYY-MM-DD HH:MM:SS` format

#### Scenario: Banner content without label
- **WHEN** Ralph loop starts without a label
- **THEN** the banner SHALL include all lines except the Label line

#### Scenario: Memory status detection
- **WHEN** the banner is rendered
- **THEN** the system SHALL run `set-memory health` once
- **AND** display "active" if exit code is 0, "inactive" otherwise

### Requirement: Label in terminal title
The terminal title SHALL include the label when set.

#### Scenario: Title with label during iteration
- **WHEN** a loop iteration starts and a label is set
- **THEN** the terminal title SHALL be: `Ralph: <worktree_name> (<label>) [<iter>/<max>]`

#### Scenario: Title without label during iteration
- **WHEN** a loop iteration starts and no label is set
- **THEN** the terminal title SHALL be: `Ralph: <worktree_name> [<iter>/<max>]`

#### Scenario: Title with label on completion
- **WHEN** the loop completes/stalls/gets stuck and a label is set
- **THEN** the terminal title SHALL be: `Ralph: <worktree_name> (<label>) [<status>]`

### Requirement: macOS Terminal.app explicit title
On macOS, the spawned Terminal.app tab SHALL have its title set explicitly via AppleScript.

#### Scenario: macOS terminal title on start
- **WHEN** `set-loop start` spawns a Terminal.app tab on macOS
- **THEN** the AppleScript SHALL set the custom title of the tab to the terminal title value
