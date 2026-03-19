## ADDED Requirements

### Requirement: Claude permission mode configuration
The system SHALL store and use a configurable Claude Code permission mode instead of hardcoding `--dangerously-skip-permissions`.

#### Scenario: Config file stores permission mode
- **WHEN** the config file `~/.config/set-core/config.json` is read
- **THEN** it SHALL contain a `claude.permission_mode` field
- **AND** valid values are: `"auto-accept"`, `"plan"`, `"allowedTools"`
- **AND** the default value for new installs SHALL be `"auto-accept"`

#### Scenario: auto-accept mode
- **WHEN** `claude.permission_mode` is `"auto-accept"`
- **THEN** Claude SHALL be invoked with `--dangerously-skip-permissions`

#### Scenario: plan mode
- **WHEN** `claude.permission_mode` is `"plan"`
- **THEN** Claude SHALL be invoked without any permission flags (interactive mode)

#### Scenario: allowedTools mode
- **WHEN** `claude.permission_mode` is `"allowedTools"`
- **THEN** Claude SHALL be invoked with `--allowedTools "Edit,Write,Bash,Read,Glob,Grep"`

#### Scenario: Install script prompts for permission mode
- **WHEN** `install.sh` is run
- **THEN** the user SHALL be prompted to choose a Claude permission mode
- **AND** the three options SHALL be explained with their security implications
- **AND** the chosen mode SHALL be saved to config.json

#### Scenario: Settings dialog shows permission mode
- **WHEN** the user opens the Settings dialog in the Control Center
- **THEN** a "Claude Permission Mode" section SHALL be displayed
- **AND** the current mode SHALL be selected
- **AND** changing the mode SHALL update config.json immediately

### Requirement: Permission mode in Zed/VSCode task generation
The system SHALL use the configured permission mode when generating editor task files.

#### Scenario: Zed tasks.json uses config mode
- **WHEN** `install.sh` or `wt-new` generates a Zed `tasks.json`
- **AND** permission mode is `"auto-accept"`
- **THEN** the task args SHALL be `["--dangerously-skip-permissions"]`

#### Scenario: Zed tasks.json plan mode
- **WHEN** permission mode is `"plan"`
- **THEN** the task args SHALL be `[]` (empty array)

#### Scenario: Zed tasks.json allowedTools mode
- **WHEN** permission mode is `"allowedTools"`
- **THEN** the task args SHALL be `["--allowedTools", "Edit,Write,Bash,Read,Glob,Grep"]`

#### Scenario: VSCode tasks.json uses config mode
- **WHEN** `wt-new` generates a VSCode `tasks.json`
- **THEN** the task args SHALL reflect the configured permission mode (same mapping as Zed)

### Requirement: wt-loop permission mode flag
The `wt-loop` command SHALL accept a `--permission-mode` flag to override the config default.

#### Scenario: wt-loop uses config default
- **WHEN** `wt-loop` is started without `--permission-mode`
- **THEN** it SHALL read `claude.permission_mode` from config.json
- **AND** invoke Claude with the corresponding flags

#### Scenario: wt-loop --permission-mode override
- **WHEN** `wt-loop --permission-mode allowedTools` is run
- **THEN** it SHALL use `--allowedTools` for Claude invocations
- **AND** the config.json value SHALL NOT be modified

#### Scenario: wt-loop refuses plan mode
- **WHEN** `wt-loop` would run with permission mode `"plan"`
- **THEN** it SHALL print a warning: "Plan mode is incompatible with Ralph loop (requires interactive approval)"
- **AND** it SHALL refuse to start
- **AND** if `--force` flag is given, it SHALL start anyway with a warning
