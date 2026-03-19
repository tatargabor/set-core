## MODIFIED Requirements

### Requirement: wt-deploy-hooks deploys full hook configuration
The `wt-deploy-hooks` script SHALL deploy the complete hook configuration covering all 7 events: SessionStart, UserPromptSubmit, PreToolUse (6 tools), PostToolUse (6 tools), PostToolUseFailure (Bash), SubagentStop, and Stop. All hooks SHALL reference the unified `wt-hook-memory` handler.

#### Scenario: Fresh deployment
- **WHEN** `wt-deploy-hooks /path/to/project` is called on a project with no settings.json
- **THEN** it SHALL create settings.json with all 7 hook events
- **AND** all hooks SHALL reference `wt-hook-memory <EventName>` as the command
- **AND** timeouts SHALL be event-specific: SessionStart=10s, UserPromptSubmit=15s, PreToolUse=5s, PostToolUse=5s, PostToolUseFailure=5s, SubagentStop=5s, Stop=30s

#### Scenario: Upgrade from old individual scripts
- **WHEN** `wt-deploy-hooks` detects old individual hook scripts (wt-hook-memory-warmstart, etc.)
- **THEN** it SHALL replace them with `wt-hook-memory <EventName>` commands
- **AND** SHALL add PostToolUse and SubagentStop entries
- **AND** SHALL create a backup of existing settings.json

#### Scenario: PreToolUse tool matchers
- **WHEN** the configuration is deployed
- **THEN** PreToolUse SHALL have matcher entries for: Read, Edit, Write, Bash, Task, Grep

#### Scenario: PostToolUse tool matchers
- **WHEN** the configuration is deployed
- **THEN** PostToolUse SHALL have matcher entries for: Read, Edit, Write, Bash, Task, Grep

### Requirement: set-project init deploys CLAUDE.md with hook + MCP instructions
The `set-project init` command SHALL ensure CLAUDE.md contains the Persistent Memory section documenting both automatic hooks and active MCP tools.

#### Scenario: CLAUDE.md deployed
- **WHEN** `set-project init` runs
- **THEN** CLAUDE.md SHALL contain "On EVERY turn, check for injected memory context"
- **AND** SHALL reference system-reminder labels
- **AND** SHALL document MCP tools (remember, recall, proactive_context)

### Requirement: set-project init registers set-memory MCP server
The `set-project init` command SHALL register the own set-memory MCP server if not already registered.

#### Scenario: MCP not yet registered
- **WHEN** `set-project init` runs and `claude mcp list` does not include set-memory
- **THEN** it SHALL run `claude mcp add set-memory -- python <set-core-path>/bin/set-memory-mcp-server.py`

#### Scenario: MCP already registered
- **WHEN** `set-project init` runs and set-memory MCP is already registered
- **THEN** it SHALL skip MCP registration

### Requirement: set-project init cleans up deprecated memory references
The `set-project init` command SHALL remove deprecated inline memory instructions from all deployed skill and command files.

#### Scenario: Old SKILL.md with set-memory hooks
- **WHEN** a SKILL.md in `.claude/skills/` contains `<!-- set-memory hooks -->` blocks
- **THEN** `set-project init` SHALL remove those blocks

#### Scenario: Old command .md with manual recall
- **WHEN** a command .md in `.claude/commands/` contains `set-memory recall` or `set-memory remember` instructions
- **THEN** `set-project init` SHALL remove those instructions

#### Scenario: Old hot-topics.json
- **WHEN** `.claude/hot-topics.json` exists
- **THEN** `set-project init` SHALL delete it

### Requirement: Explore SKILL.md includes memory-first step
The explore skill SHALL instruct the agent to check memory before exploring.

#### Scenario: Explore skill loaded
- **WHEN** the explore SKILL.md is loaded
- **THEN** it SHALL contain a "Check memory first" section before "Check for context"
- **AND** SHALL instruct the agent to summarize known memory before independent exploration
