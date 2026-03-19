## MODIFIED Requirements

### Requirement: macOS App Bundle Structure
The installer SHALL generate a valid macOS `.app` bundle at `~/Applications/WT Control.app` with the standard directory structure.

#### Scenario: Bundle directory structure
- **WHEN** `install.sh` runs on macOS
- **THEN** the following structure is created:
  - `~/Applications/WT Control.app/Contents/Info.plist`
  - `~/Applications/WT Control.app/Contents/MacOS/wt-control` (executable)
  - `~/Applications/WT Control.app/Contents/Resources/` (directory)
  - `~/Applications/WT Control.app/Contents/Resources/app.icns` (application icon)

#### Scenario: Info.plist contents
- **WHEN** the `.app` bundle is generated
- **THEN** `Info.plist` SHALL contain:
  - `CFBundleName` = "WT Control"
  - `CFBundleIdentifier` = "com.set-core.control"
  - `CFBundleExecutable` = "wt-control"
  - `CFBundleIconFile` = "app"
  - `LSUIElement` = true

#### Scenario: Executable wrapper delegates to wt-control
- **WHEN** the `.app` bundle's `MacOS/wt-control` is executed
- **THEN** it SHALL exec `$HOME/.local/bin/wt-control` with all arguments forwarded

#### Scenario: Executable has correct permissions
- **WHEN** the `.app` bundle is generated
- **THEN** `Contents/MacOS/wt-control` SHALL have executable permission (chmod +x)
