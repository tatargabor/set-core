# Opensource Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Plugin Architecture
The system SHALL support optional plugins for extensibility.

#### Scenario: Load plugins via entry points
- **GIVEN** a plugin is registered in pyproject.toml entry points
- **WHEN** the application starts
- **THEN** the plugin is discovered and loaded
- **AND** plugin features become available in the GUI

#### Scenario: Graceful degradation without plugins
- **GIVEN** no plugins are installed or configured
- **WHEN** the user opens the GUI
- **THEN** the GUI starts without errors
- **AND** plugin-specific features are disabled or hidden

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
The system SHALL have English documentation for international users. The README structure and content SHALL follow the rules defined in `docs/readme-guide.md`.

#### Scenario: README in English
- **GIVEN** a user visits the GitHub repository
- **WHEN** they view the README
- **THEN** all content is in English
- **AND** installation instructions are provided for all supported platforms

#### Scenario: README follows guide
- **GIVEN** the `docs/readme-guide.md` exists
- **WHEN** the README is created or updated
- **THEN** it follows the mandatory section structure defined in the guide
- **AND** all user-facing CLI tools are documented

### Requirement: No Proprietary Content
The system SHALL NOT contain proprietary URLs, project names, or personal paths.

#### Scenario: Clean codebase verification
- **GIVEN** the codebase is searched for proprietary content
- **WHEN** grep is run for "zengo", "ARVRMTEAM", or personal paths
- **THEN** no matches are found in non-archived files
