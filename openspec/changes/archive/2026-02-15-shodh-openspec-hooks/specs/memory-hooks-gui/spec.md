## ADDED Requirements

### Requirement: Install Memory Hooks action in Memory submenu
The Memory submenu in the project header context menu SHALL include an "Install Memory Hooks" action when OpenSpec is detected but hooks are not installed. When hooks are already installed, a disabled "Memory Hooks: installed" status line SHALL appear instead.

#### Scenario: OpenSpec present, hooks not installed
- **WHEN** user right-clicks project header where OpenSpec is installed and memory hooks are NOT installed
- **THEN** the Memory submenu shows an enabled "Install Memory Hooks" action

#### Scenario: OpenSpec present, hooks installed
- **WHEN** user right-clicks project header where OpenSpec is installed and memory hooks ARE installed
- **THEN** the Memory submenu shows a disabled "Memory Hooks: installed" status line

#### Scenario: OpenSpec not present
- **WHEN** user right-clicks project header where OpenSpec is NOT installed
- **THEN** the Memory submenu does NOT show any hooks-related action

#### Scenario: Install action execution
- **WHEN** user clicks "Install Memory Hooks"
- **THEN** the GUI runs `set-memory-hooks install` via `CommandOutputDialog` targeting the main repo path, then triggers a feature cache refresh

### Requirement: Auto-reinstall hooks after OpenSpec update
After `wt-openspec update` completes successfully, the GUI SHALL automatically run `set-memory-hooks install` to restore hooks that were overwritten by the update.

#### Scenario: Update then reinstall
- **WHEN** user runs "Update Skills..." from the OpenSpec submenu and it completes successfully
- **THEN** the GUI automatically runs `set-memory-hooks install` in the same main repo path before refreshing the feature cache

### Requirement: Hook status in FeatureWorker cache
The FeatureWorker SHALL call `set-memory-hooks check --json` during its poll cycle and include the result in `_feature_cache[project]["memory"]["hooks_installed"]`. The [M] button tooltip SHALL include hook status.

#### Scenario: FeatureWorker polls hook status
- **WHEN** the FeatureWorker runs a poll cycle for a project with OpenSpec
- **THEN** it runs `set-memory-hooks check --json` and merges the result into the memory cache entry

#### Scenario: [M] button tooltip with hooks
- **WHEN** memory is available, has 5 memories, and hooks are installed
- **THEN** the [M] button tooltip shows "Memory: 5 memories (hooks installed)"

#### Scenario: [M] button tooltip without hooks
- **WHEN** memory is available, has 5 memories, OpenSpec is present, but hooks are NOT installed
- **THEN** the [M] button tooltip shows "Memory: 5 memories (hooks not installed)"
