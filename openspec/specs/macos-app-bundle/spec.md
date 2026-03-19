## Requirements

### Requirement: macOS App Bundle Structure
The installer SHALL generate a valid macOS `.app` bundle at `~/Applications/WT Control.app` with the standard directory structure.

#### Scenario: Bundle directory structure
- **WHEN** `install.sh` runs on macOS
- **THEN** the following structure is created:
  - `~/Applications/WT Control.app/Contents/Info.plist`
  - `~/Applications/WT Control.app/Contents/MacOS/set-control` (executable)
  - `~/Applications/WT Control.app/Contents/Resources/` (directory)
  - `~/Applications/WT Control.app/Contents/Resources/app.icns` (application icon)

#### Scenario: Info.plist contents
- **WHEN** the `.app` bundle is generated
- **THEN** `Info.plist` SHALL contain:
  - `CFBundleName` = "WT Control"
  - `CFBundleIdentifier` = "com.set-core.control"
  - `CFBundleExecutable` = "set-control"
  - `CFBundleIconFile` = "app"
  - `LSUIElement` = true

#### Scenario: Executable wrapper delegates to set-control
- **WHEN** the `.app` bundle's `MacOS/set-control` is executed
- **THEN** it SHALL exec `$HOME/.local/bin/set-control` with all arguments forwarded

#### Scenario: Executable has correct permissions
- **WHEN** the `.app` bundle is generated
- **THEN** `Contents/MacOS/set-control` SHALL have executable permission (chmod +x)

### Requirement: Spotlight Discoverability
The `.app` bundle SHALL be discoverable by macOS application launchers.

#### Scenario: Spotlight discovery
- **WHEN** `install.sh` completes on macOS
- **THEN** the user SHALL be able to find "WT Control" via Spotlight (Cmd+Space)

#### Scenario: Spotlight indexing trigger
- **WHEN** the `.app` bundle is created or updated
- **THEN** the installer SHALL run `mdimport` on the bundle to trigger Spotlight indexing

#### Scenario: Alfred and Raycast discovery
- **WHEN** the `.app` bundle exists in `~/Applications/`
- **THEN** Alfred and Raycast SHALL discover it via their standard application scanning

### Requirement: Dock Support
The `.app` bundle SHALL support being pinned to the macOS Dock.

#### Scenario: Pin to Dock
- **WHEN** the user drags "WT Control" from Finder or Spotlight to the Dock
- **THEN** it SHALL remain pinned and launch the GUI when clicked

#### Scenario: LSUIElement hides automatic Dock icon
- **WHEN** the GUI is running (launched from any method)
- **THEN** no Dock icon SHALL appear automatically (LSUIElement=true)
- **AND** the app SHALL remain accessible via its system tray icon

### Requirement: Graceful Failure
The `.app` wrapper SHALL handle missing dependencies gracefully.

#### Scenario: set-control not installed
- **WHEN** the `.app` bundle's executable runs but `~/.local/bin/set-control` does not exist
- **THEN** a macOS dialog SHALL appear with an error message explaining that set-core is not installed
- **AND** the script SHALL exit with a non-zero status

### Requirement: Platform Guard
The `.app` bundle installation SHALL only run on macOS.

#### Scenario: Skip on Linux
- **WHEN** `install.sh` runs on Linux
- **THEN** the macOS app bundle step SHALL be skipped entirely

#### Scenario: Run on macOS
- **WHEN** `install.sh` runs on macOS (darwin)
- **THEN** the macOS app bundle SHALL be generated
