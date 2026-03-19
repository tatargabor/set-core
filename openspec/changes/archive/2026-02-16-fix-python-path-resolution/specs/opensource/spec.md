## MODIFIED Requirements

### Requirement: Cross-Platform Support
The system SHALL run on Linux, macOS, and Windows. The `install.sh` installer SHALL use `find_python()` from `wt-common.sh` to locate the target Python interpreter and install Python dependencies using `$PYTHON -m pip install` instead of bare `pip3`. After successful shodh-memory installation, the installer SHALL persist the Python path to `~/.config/set-core/shodh-python`.

#### Scenario: Platform detection
- **GIVEN** the application starts
- **WHEN** the platform is detected
- **THEN** the appropriate platform implementation is loaded
- **AND** platform-specific features use native APIs

#### Scenario: Install shodh-memory into correct Python
- **WHEN** `install.sh` runs `install_shodh_memory()`
- **THEN** it calls `find_python()` to locate a Python interpreter
- **AND** it installs shodh-memory with `$PYTHON -m pip install shodh-memory`
- **AND** it verifies the install with `$PYTHON -c "from shodh_memory import Memory"`
- **AND** it saves the Python path to `~/.config/set-core/shodh-python`

#### Scenario: Install GUI dependencies into correct Python
- **WHEN** `install.sh` runs `install_gui_dependencies()`
- **THEN** it calls `find_python()` to locate a Python interpreter
- **AND** it installs dependencies with `$PYTHON -m pip install -r requirements.txt`

#### Scenario: PATH python3 is wrong environment
- **WHEN** the first `python3` in PATH belongs to a venv without shodh-memory
- **AND** shodh-memory is installed in `$HOME/miniconda3/bin/python3`
- **THEN** `install.sh` detects and uses the miniconda Python for shodh-memory operations

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
