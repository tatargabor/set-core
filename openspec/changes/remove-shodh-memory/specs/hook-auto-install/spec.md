## MODIFIED Requirements

### Requirement: Reusable hook deployment script
A reusable `set-deploy-hooks` script SHALL deploy the framework's hooks to any directory,
and the deployed set SHALL contain no memory hooks.

#### Scenario: Deploy to directory without settings.json
- **WHEN** `set-deploy-hooks /path/to/worktree` is called
- **AND** `/path/to/worktree/.claude/settings.json` does not exist
- **THEN** the script SHALL create `.claude/` directory and `settings.json` with the UserPromptSubmit hook `set-hook-skill` and the Stop hook `set-hook-stop`
- **AND** the resulting file SHALL contain no command beginning with `set-hook-memory`

#### Scenario: Deploy to directory with existing settings.json
- **WHEN** `set-deploy-hooks /path/to/worktree` is called
- **AND** `/path/to/worktree/.claude/settings.json` already exists
- **THEN** the script SHALL merge the framework's hooks additively, preserving every hook the project owns

#### Scenario: Deploy to directory with hooks already present
- **WHEN** `set-deploy-hooks /path/to/worktree` is called
- **AND** `/path/to/worktree/.claude/settings.json` already contains `set-hook-skill` and `set-hook-stop` and no memory hook
- **THEN** the script SHALL exit 0 without modification

#### Scenario: A deploy removes memory hooks it finds
- **WHEN** `set-deploy-hooks /path/to/project` is called
- **AND** the project's settings.json carries nine `set-hook-memory` entries
- **THEN** all nine SHALL be removed without any flag being passed
- **AND** the project's own hooks SHALL remain, unchanged in count and order

#### Scenario: Deploy with --no-memory flag
- **WHEN** `set-deploy-hooks --no-memory /path/to/worktree` is called
- **THEN** the script SHALL behave identically to a call without the flag
- **AND** the flag SHALL be accepted rather than rejected, so existing callers do not break

#### Scenario: Deploy with --quiet flag
- **WHEN** `set-deploy-hooks --quiet /path/to/worktree` is called
- **THEN** the script SHALL suppress success/info messages (only errors printed)
