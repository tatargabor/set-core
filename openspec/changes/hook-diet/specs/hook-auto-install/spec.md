## MODIFIED Requirements

### Requirement: Reusable hook deployment script
The system SHALL provide a `bin/set-deploy-hooks` script that deploys Claude Code hooks to a target directory's `.claude/settings.json`. The base set SHALL be the question relay (`PreToolUse`, matcher `AskUserQuestion`), the wave-board reminder and the wait detector (`Stop`). It SHALL NOT deploy `set-hook-skill`, `set-hook-activity` or `set-hook-stop`, and every run SHALL remove those three and the legacy `.claude/hooks/activity-track.sh` command from every event array, keeping the project's own hooks in their order and dropping an entry left with no hooks.

#### Scenario: Deploy to directory without settings.json
- **WHEN** `set-deploy-hooks /path/to/worktree` is called
- **AND** `/path/to/worktree/.claude/settings.json` does not exist
- **THEN** the script SHALL create `.claude/settings.json` with the base set and none of the retired hooks

#### Scenario: Deploy to directory with existing settings.json
- **WHEN** `set-deploy-hooks /path/to/worktree` is called
- **AND** the existing file lacks a base hook or carries a retired or memory hook
- **THEN** the script SHALL merge the base set, remove the retired and memory hooks, keep every project hook
- **AND** create a `.claude/settings.json.bak` backup before modification

#### Scenario: Deploy to directory with hooks already present
- **WHEN** the file carries the whole base set and no retired or memory hook
- **THEN** the script SHALL exit 0 without modification

#### Scenario: A canonical file with a retired hook is still cleaned
- **WHEN** the file carries the whole base set AND `set-hook-stop`
- **THEN** the script SHALL remove `set-hook-stop`

#### Scenario: Deploy with --quiet flag
- **WHEN** `set-deploy-hooks --quiet /path/to/worktree` is called
- **THEN** the script SHALL suppress success/info messages (only errors printed)

#### Scenario: Deploy with --no-memory flag
- **WHEN** `set-deploy-hooks --no-memory /path/to/worktree` is called
- **THEN** the flag SHALL be accepted and change nothing: no memory hook is deployed with or without it
