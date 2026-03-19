## ADDED Requirements

### Requirement: Configuration Management
The GUI SHALL support persistent user configuration through a settings dialog.

#### Scenario: Open settings dialog
- **GIVEN** the Control Center is running
- **WHEN** the user clicks "Settings..." from the menu (≡)
- **THEN** a settings dialog opens with configuration tabs

#### Scenario: Control Center settings tab
- **GIVEN** the settings dialog is open
- **WHEN** the user views the "Control Center" tab
- **THEN** the following settings are available:
  - Default opacity (0.0-1.0 slider)
  - Hover opacity (0.0-1.0 slider)
  - Window width (pixels)
  - Status refresh interval (milliseconds)
  - Blink interval (milliseconds)

#### Scenario: JIRA settings tab
- **GIVEN** the settings dialog is open
- **WHEN** the user views the "JIRA" tab
- **THEN** the following settings are available:
  - JIRA base URL
  - Default project key
  - Credentials file path

#### Scenario: Git settings tab
- **GIVEN** the settings dialog is open
- **WHEN** the user views the "Git" tab
- **THEN** the following settings are available:
  - Branch name prefix (default: "change/")
  - Fetch timeout in seconds

#### Scenario: Notifications settings tab
- **GIVEN** the settings dialog is open
- **WHEN** the user views the "Notifications" tab
- **THEN** the following settings are available:
  - Enable notifications (checkbox)
  - Play sound (checkbox)

#### Scenario: Save configuration
- **GIVEN** the settings dialog has modified values
- **WHEN** the user clicks "OK" or "Apply"
- **THEN** settings are saved to `~/.config/set-core/gui-config.json`
- **AND** changes take effect immediately where applicable

#### Scenario: Load configuration on startup
- **GIVEN** a config file exists at `~/.config/set-core/gui-config.json`
- **WHEN** the Control Center starts
- **THEN** all settings are loaded from the config file

#### Scenario: Default values
- **GIVEN** no config file exists or a setting is missing
- **WHEN** the Control Center starts
- **THEN** default values are used for missing settings
