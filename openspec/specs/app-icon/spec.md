## ADDED Requirements

### Requirement: Icon Source File
The project SHALL include a vector icon source file at `assets/icon.svg`.

#### Scenario: SVG content
- **WHEN** the icon source is generated
- **THEN** `assets/icon.svg` SHALL contain a valid SVG with a stylized white "W" letter on a dark rounded-rectangle background

#### Scenario: Readability at small sizes
- **WHEN** the SVG is rendered at 16x16 pixels
- **THEN** the "W" letter SHALL be recognizable

### Requirement: Pre-built Icon Files
The project SHALL include pre-built icon files committed to the repository.

#### Scenario: PNG file
- **WHEN** the icon is generated
- **THEN** `assets/icon.png` SHALL exist as a 256x256 PNG rendering of the SVG

#### Scenario: macOS icon set
- **WHEN** the icon is generated on macOS
- **THEN** `assets/icon.icns` SHALL exist containing icon sizes from 16x16 to 512x512

### Requirement: Icon Generation Script
The project SHALL include a developer script to regenerate icon files from the SVG source.

#### Scenario: Run generation script
- **WHEN** a developer runs `scripts/generate-icon.py`
- **THEN** `assets/icon.svg`, `assets/icon.png`, and `assets/icon.icns` (macOS only) SHALL be created or updated

#### Scenario: No runtime dependency
- **WHEN** a user runs `install.sh`
- **THEN** no icon generation tools (cairosvg, sips, iconutil) SHALL be required
- **AND** pre-built files from the repository SHALL be used directly

### Requirement: Icon Installation
The installer SHALL deploy the appropriate icon file for each platform.

#### Scenario: macOS icon installation
- **WHEN** `install.sh` runs on macOS
- **THEN** `assets/icon.icns` SHALL be copied to `~/Applications/WT Control.app/Contents/Resources/app.icns`

#### Scenario: Linux icon installation
- **WHEN** `install.sh` runs on Linux
- **THEN** `assets/icon.png` SHALL be copied to `~/.local/share/icons/set-control.png`
- **AND** the `.desktop` entry SHALL reference this path in its `Icon=` field

### Requirement: Qt Application Icon
The GUI SHALL set a custom application icon on startup.

#### Scenario: Window icon set
- **WHEN** the Control Center starts
- **THEN** `QApplication.setWindowIcon()` SHALL be called with the icon from `assets/icon.png`

#### Scenario: Icon file missing
- **WHEN** `assets/icon.png` does not exist at the resolved path
- **THEN** the application SHALL start normally without an icon (no crash)
