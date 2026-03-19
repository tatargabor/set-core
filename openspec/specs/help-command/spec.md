## ADDED Requirements

### Requirement: Help command file exists
The system SHALL provide a `.claude/commands/wt/help.md` file that serves as a quick reference for all set-core features.

#### Scenario: File location
- **WHEN** a user or LLM looks for the help command
- **THEN** it SHALL exist at `.claude/commands/wt/help.md`

### Requirement: Help command covers CLI tools
The help command SHALL list all user-facing CLI commands (`set-*` scripts in `bin/`) with a one-line description for each.

#### Scenario: CLI tools listed
- **WHEN** the help command content is loaded
- **THEN** it SHALL contain a "CLI Commands" section listing at minimum: `set-new`, `set-list`, `set-work`, `set-close`, `set-merge`, `set-status`, `set-memory`, `set-loop`, `set-control`, `set-project`, `set-usage`, `set-config`

#### Scenario: Each CLI tool has description
- **WHEN** a CLI tool is listed in the help command
- **THEN** it SHALL have a one-line description of what it does

### Requirement: Help command covers skills
The help command SHALL list all available slash command skills (`/opsx:*` and `/wt:*`) with a one-line description for each.

#### Scenario: OpenSpec skills listed
- **WHEN** the help command content is loaded
- **THEN** it SHALL list `/opsx:new`, `/opsx:ff`, `/opsx:apply`, `/opsx:continue`, `/opsx:verify`, `/opsx:archive`, `/opsx:explore`, `/opsx:sync`, `/opsx:onboard`

#### Scenario: Worktree skills listed
- **WHEN** the help command content is loaded
- **THEN** it SHALL list `/wt:new`, `/wt:work`, `/wt:list`, `/wt:close`, `/wt:merge`, `/wt:push`, `/wt:status`, `/wt:loop`, `/wt:help`

### Requirement: Help command covers MCP tools
The help command SHALL list key MCP tools from `set-memory` with a one-line description for each.

#### Scenario: Core memory tools listed
- **WHEN** the help command content is loaded
- **THEN** it SHALL list at minimum: `remember`, `recall`, `proactive_context`, `forget`, `list_memories`, `brain`, `context_summary`

#### Scenario: Worktree MCP tools listed
- **WHEN** the help command content is loaded
- **THEN** it SHALL list at minimum: `list_worktrees`, `get_activity`, `get_team_status`, `send_message`, `get_inbox`

### Requirement: Help command covers common workflows
The help command SHALL include a "Common Workflows" section showing typical task sequences.

#### Scenario: New feature workflow
- **WHEN** the help command content is loaded
- **THEN** it SHALL describe the typical flow: create worktree → create change → implement → verify → merge

### Requirement: Help command auto-deploys
The help command SHALL be deployed to target projects automatically by the existing `deploy_set_tools()` mechanism without any changes to the deployment code.

#### Scenario: Deployment via set-project init
- **WHEN** `set-project init` is run on a target project
- **THEN** `.claude/commands/wt/help.md` SHALL be copied along with other command files
- **THEN** no changes to `bin/set-project` SHALL be required
