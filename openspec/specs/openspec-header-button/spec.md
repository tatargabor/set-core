## ADDED Requirements

### Requirement: OpenSpec [O] button in project header
The project header row SHALL display an [O] button (22x22px) between the [M] memory button and the team filter button. The button color SHALL be green (`status_running` theme color) when OpenSpec is detected, gray (`status_idle`) when absent.

#### Scenario: OpenSpec detected
- **WHEN** a project has `openspec/config.yaml` in the main repo
- **THEN** the [O] button appears green with tooltip "OpenSpec: N active changes"

#### Scenario: OpenSpec not detected
- **WHEN** a project does not have `openspec/config.yaml`
- **THEN** the [O] button appears gray with tooltip "OpenSpec: not initialized"

#### Scenario: Button reads from cache
- **WHEN** the table re-renders (every 2 seconds)
- **THEN** the [O] button reads status from `self._feature_cache` and does NOT run any subprocess

### Requirement: OpenSpec section in project header context menu
The project header context menu SHALL include an "OpenSpec" submenu after the "Memory" submenu.

#### Scenario: Context menu when OpenSpec installed
- **WHEN** user right-clicks a project header where OpenSpec is installed
- **THEN** the OpenSpec submenu shows: disabled status line ("Version: X, N active changes"), separator, "Update Skills..." action (enabled)

#### Scenario: Context menu when OpenSpec not installed
- **WHEN** user right-clicks a project header where OpenSpec is not installed
- **THEN** the OpenSpec submenu shows: disabled status line ("Not initialized"), separator, "Initialize OpenSpec..." action (enabled)

#### Scenario: Initialize action runs set-openspec init
- **WHEN** user clicks "Initialize OpenSpec..."
- **THEN** the GUI runs `set-openspec init` via `CommandOutputDialog` targeting the main repo path, then triggers a feature cache refresh

#### Scenario: Update action runs set-openspec update
- **WHEN** user clicks "Update Skills..."
- **THEN** the GUI runs `set-openspec update` via `CommandOutputDialog` targeting the main repo path, then triggers a feature cache refresh
