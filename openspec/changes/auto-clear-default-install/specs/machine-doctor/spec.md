## ADDED Requirements

### Requirement: Each project is checked for auto-clear
`set-doctor` SHALL report one `auto-clear` check per registered project. The check SHALL be `skip`
for archived, `deploy: false` and `auto_clear: false` projects; `warn` when the package templates are
missing or are not the current shipped version, when either the reload or the arm hook is wired by
neither the package nor the project, when no watcher unit exists for the project or it is not
active, or when the unit or a keep-going hook passes a threshold above the measured native
compaction trigger; and `ok` otherwise. It SHALL never be `fail`. Every `warn` SHALL carry the exact
command that fixes it.

#### Scenario: A project without a unit
- **WHEN** a non-archived project has the templates and hooks but no watcher unit
- **THEN** the check is `warn`, its detail says the unit is missing, and its fix is `set-project init --project <name>`

#### Scenario: An inactive unit
- **WHEN** the project's watcher unit exists but is not active
- **THEN** the check is `warn` and its fix is `systemctl --user start <unit>`

#### Scenario: A threshold above the native trigger
- **WHEN** the unit passes `--compact-threshold 500000`, or a keep-going hook in the project's settings passes `--threshold 500000`
- **THEN** the check is `warn` and names the flag, where it sits, and that the package default is below the native trigger

#### Scenario: A complete install
- **WHEN** the templates are current, both hooks are wired, and the unit is active with no overriding flag
- **THEN** the check is `ok`

#### Scenario: An archived project
- **WHEN** the project is archived
- **THEN** the check is `skip` and nothing about its tree is read
