## MODIFIED Requirements

### Requirement: Install Memory Hooks action in Memory submenu
The Memory submenu in the project header context menu SHALL include an "Install Skill Memory Hooks..." action when OpenSpec is detected and skills are present but hooks are not installed. When hooks are already installed, a "Reinstall Skill Memory Hooks..." action SHALL appear instead.

#### Scenario: OpenSpec present, hooks not installed
- **WHEN** user right-clicks project header where OpenSpec is installed and memory hooks are NOT installed
- **THEN** the Memory submenu shows an enabled "Install Skill Memory Hooks..." action

#### Scenario: OpenSpec present, hooks installed
- **WHEN** user right-clicks project header where OpenSpec is installed and memory hooks ARE installed
- **THEN** the Memory submenu shows an enabled "Reinstall Skill Memory Hooks..." action

#### Scenario: OpenSpec not present
- **WHEN** user right-clicks project header where OpenSpec is NOT installed
- **THEN** the Memory submenu does NOT show any hooks-related action

#### Scenario: Install action execution
- **WHEN** user clicks "Install Skill Memory Hooks..."
- **THEN** the GUI runs `set-memory-hooks install` via `CommandOutputDialog` targeting the main repo path, then triggers a feature cache refresh

### Requirement: Memory Hooks in OpenSpec submenu
The OpenSpec submenu SHALL mirror the Memory submenu's hook install/reinstall actions with matching labels.

#### Scenario: OpenSpec submenu hook labels match Memory submenu
- **WHEN** user right-clicks project header where OpenSpec is installed
- **THEN** the OpenSpec submenu shows "Install Skill Memory Hooks..." or "Reinstall Skill Memory Hooks..." matching the Memory submenu's state
