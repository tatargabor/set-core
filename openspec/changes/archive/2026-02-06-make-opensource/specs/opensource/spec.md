## ADDED Requirements

### Requirement: Plugin Architecture
The system SHALL support optional plugins for JIRA and Confluence integration.

#### Scenario: Load plugins via entry points
- **GIVEN** a plugin is registered in pyproject.toml entry points
- **WHEN** the application starts
- **THEN** the plugin is discovered and loaded
- **AND** plugin features become available in the GUI

#### Scenario: Graceful degradation without plugins
- **GIVEN** JIRA plugin is not installed or configured
- **WHEN** the user opens the GUI
- **THEN** the GUI starts without errors
- **AND** JIRA-specific features are disabled or hidden

### Requirement: Cross-Platform Support
The system SHALL run on Linux, macOS, and Windows.

#### Scenario: Platform detection
- **GIVEN** the application starts
- **WHEN** the platform is detected
- **THEN** the appropriate platform implementation is loaded
- **AND** platform-specific features use native APIs

#### Scenario: Window focus on Linux
- **GIVEN** the platform is Linux and xdotool is installed
- **WHEN** the user requests to focus a window by PID
- **THEN** xdotool is used to activate the window

#### Scenario: Window focus on macOS
- **GIVEN** the platform is macOS
- **WHEN** the user requests to focus a window by PID
- **THEN** AppleScript/osascript is used to activate the window

#### Scenario: Window focus on Windows
- **GIVEN** the platform is Windows and pywin32 is installed
- **WHEN** the user requests to focus a window by PID
- **THEN** Win32 API is used to activate the window

### Requirement: English Documentation
The system SHALL have English documentation for international users.

#### Scenario: README in English
- **GIVEN** a user visits the GitHub repository
- **WHEN** they view the README
- **THEN** all content is in English
- **AND** installation instructions are provided for all platforms

### Requirement: No Proprietary Content
The system SHALL NOT contain proprietary URLs, project names, or personal paths.

#### Scenario: Clean codebase verification
- **GIVEN** the codebase is searched for proprietary content
- **WHEN** grep is run for the former employer's name, "EXAMPLE", or personal paths
- **THEN** no matches are found in non-archived files
