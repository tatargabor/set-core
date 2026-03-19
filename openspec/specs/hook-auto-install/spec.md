## ADDED Requirements

### Requirement: Reusable hook deployment script
The system SHALL provide a `bin/set-deploy-hooks` script that deploys Claude Code hooks to a target directory's `.claude/settings.json`.

#### Scenario: Deploy to directory without settings.json
- **WHEN** `set-deploy-hooks /path/to/worktree` is called
- **AND** `/path/to/worktree/.claude/settings.json` does not exist
- **THEN** the script SHALL create `.claude/` directory and `settings.json` with UserPromptSubmit hooks (`set-hook-skill`, `set-hook-memory-recall`) and Stop hooks (`set-hook-stop`, `set-hook-memory-save`)

#### Scenario: Deploy to directory with existing settings.json
- **WHEN** `set-deploy-hooks /path/to/worktree` is called
- **AND** `/path/to/worktree/.claude/settings.json` already exists
- **AND** it does not contain all four required hooks
- **THEN** the script SHALL merge the hook configuration into the existing file
- **AND** create a `.claude/settings.json.bak` backup before modification

#### Scenario: Deploy to directory with hooks already present
- **WHEN** `set-deploy-hooks /path/to/worktree` is called
- **AND** `/path/to/worktree/.claude/settings.json` already contains all four hooks (set-hook-skill, set-hook-stop, set-hook-memory-recall, set-hook-memory-save)
- **THEN** the script SHALL exit 0 without modification

#### Scenario: Deploy with --quiet flag
- **WHEN** `set-deploy-hooks --quiet /path/to/worktree` is called
- **THEN** the script SHALL suppress success/info messages (only errors printed)

#### Scenario: Deploy with --no-memory flag
- **WHEN** `set-deploy-hooks --no-memory /path/to/worktree` is called
- **THEN** the script SHALL deploy only `set-hook-skill` (UserPromptSubmit) and `set-hook-stop` (Stop)
- **AND** SHALL NOT include `set-hook-memory-recall` or `set-hook-memory-save`

### Requirement: Hook presence detection in set-status
The `set-status --json` output SHALL include a `hooks_installed` boolean for each worktree.

#### Scenario: Worktree with hooks installed
- **WHEN** `set-status --json` checks a worktree
- **AND** the worktree has `.claude/settings.json` containing both `hooks.UserPromptSubmit` and `hooks.Stop` entries
- **THEN** the worktree JSON SHALL include `"hooks_installed": true`

#### Scenario: Worktree without hooks
- **WHEN** `set-status --json` checks a worktree
- **AND** the worktree does not have `.claude/settings.json` or it is missing hook entries
- **THEN** the worktree JSON SHALL include `"hooks_installed": false`

### Requirement: Hook deployment on worktree creation
The `set-new` command SHALL deploy hooks to newly created worktrees.

#### Scenario: New worktree gets hooks
- **WHEN** `set-new` creates a new worktree
- **THEN** `set-deploy-hooks` SHALL be called on the new worktree directory
- **AND** the worktree SHALL have a working `.claude/settings.json` with hooks

#### Scenario: Hook deployment failure does not block worktree creation
- **WHEN** `set-new` creates a worktree
- **AND** hook deployment fails (e.g., jq not available)
- **THEN** the worktree SHALL still be created successfully
- **AND** a warning message SHALL be shown

### Requirement: GUI shows hook status
The GUI SHALL indicate when a worktree is missing hooks and offer a fix action.

#### Scenario: Tooltip shows hooks missing warning
- **WHEN** a worktree row is rendered
- **AND** `hooks_installed` is false
- **THEN** the status cell tooltip SHALL include a warning about missing hooks

#### Scenario: Context menu offers Install Hooks
- **WHEN** user right-clicks a worktree row
- **AND** `hooks_installed` is false
- **THEN** the context menu SHALL include an "Install Hooks" action

#### Scenario: Install Hooks action deploys hooks
- **WHEN** user clicks "Install Hooks" from the context menu
- **THEN** `set-deploy-hooks` SHALL be called on the worktree path
- **AND** a status refresh SHALL be triggered after deployment

#### Scenario: Context menu hides Install Hooks when not needed
- **WHEN** user right-clicks a worktree row
- **AND** `hooks_installed` is true
- **THEN** the context menu SHALL NOT include "Install Hooks"
