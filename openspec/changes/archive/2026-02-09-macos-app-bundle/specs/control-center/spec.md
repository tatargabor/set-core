## MODIFIED Requirements

### Requirement: Robust GUI Launch
The system SHALL start the Control Center GUI reliably regardless of how it is invoked.

#### Scenario: Launch via symlink
- **GIVEN** wt-control is symlinked from ~/.local/bin to the source directory
- **WHEN** the user runs `wt-control`
- **THEN** the GUI starts without import errors
- **AND** all relative imports within the gui package resolve correctly

#### Scenario: Launch directly
- **GIVEN** the user is in the set-core source directory
- **WHEN** the user runs `python gui/main.py`
- **THEN** the GUI starts without import errors

#### Scenario: Launch as module
- **GIVEN** the user is in the set-core source directory
- **WHEN** the user runs `python -m gui.main`
- **THEN** the GUI starts without import errors

#### Scenario: Launch from desktop entry
- **GIVEN** install.sh has been run
- **WHEN** the user launches "Worktree Control Center" from Alt+F2 or application menu
- **THEN** the GUI starts without import errors
- **AND** no terminal window is required

#### Scenario: Launch from macOS app bundle
- **GIVEN** install.sh has been run on macOS
- **WHEN** the user launches "WT Control" from Spotlight, Alfred, Raycast, or Dock
- **THEN** the GUI starts without import errors
- **AND** no terminal window is required
- **AND** the app bundle delegates to `~/.local/bin/wt-control`

#### Scenario: Startup failure diagnostics
- **GIVEN** the GUI fails to start (missing dependency, import error, etc.)
- **WHEN** the user runs `wt-control`
- **THEN** the error message is displayed to stderr
- **AND** the error includes the Python traceback for debugging
