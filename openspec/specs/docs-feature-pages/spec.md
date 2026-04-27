# Docs Feature Pages Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Getting Started page
`docs/getting-started.md` SHALL contain detailed installation instructions, prerequisites with version checks, GUI dependency setup, platform-specific notes (Qt/conda on Linux), project registration walkthrough, and a first-run tutorial that covers creating a worktree, running a Ralph loop, and starting the sentinel.

#### Scenario: Prerequisites section
- **WHEN** reading the prerequisites section
- **THEN** it SHALL list Git, Python 3.10+, jq, Node.js with check commands for each

#### Scenario: First-run tutorial
- **WHEN** a new user follows the getting-started guide
- **THEN** they SHALL complete: install, register project, create worktree, open worktree, and (optionally) start sentinel

### Requirement: Worktrees page
`docs/worktrees.md` SHALL contain all worktree CLI commands (set-new, set-work, set-close, set-merge, set-list, set-status, set-focus, set-add), Claude Code skills (/wt:new, /wt:work, etc.), and the "parallel feature development" use case from the old README.

#### Scenario: CLI command coverage
- **WHEN** comparing worktree commands in `docs/worktrees.md` with `bin/set-*` scripts
- **THEN** all worktree-related commands SHALL be documented

#### Scenario: Skills mapping
- **WHEN** listing worktree skills
- **THEN** each CLI command SHALL show its corresponding `/wt:*` skill

### Requirement: Ralph page
`docs/ralph.md` SHALL contain Ralph loop commands (set-loop start/stop/status/list/history/monitor), configuration options, the "let the agent work overnight" use case, and guidance on when Ralph is appropriate vs not (well-scoped tasks vs exploratory work).

#### Scenario: Command reference
- **WHEN** reading the Ralph page
- **THEN** all `set-loop` subcommands SHALL be documented with examples

#### Scenario: Use case inclusion
- **WHEN** reading the Ralph page
- **THEN** the "let the agent work overnight" use case from the old README SHALL be present

### Requirement: GUI page
`docs/gui.md` SHALL contain Control Center features, what the GUI shows (agent status, context %, burn rate, Ralph progress, orchestration status, team members), interaction patterns (double-click, right-click, blinking rows), configuration (themes, opacity, refresh interval), system tray behavior, and screenshots.

#### Scenario: Feature list
- **WHEN** reading the GUI page
- **THEN** all GUI features from the old README "What the GUI shows you" section SHALL be present

#### Scenario: Configuration
- **WHEN** looking for GUI config details
- **THEN** gui-config.json settings, color profiles, and window options SHALL be documented

### Requirement: Team Sync page
`docs/team-sync.md` SHALL contain cross-machine setup (set-control-init, set-control-sync), agent messaging (/wt:msg, /wt:inbox, /wt:broadcast, /wt:status), batch messaging architecture (zero extra git ops), history compaction, encrypted chat, and all content from the current `docs/agent-messaging.md`.

#### Scenario: Messaging content present
- **WHEN** reading team-sync.md
- **THEN** all use cases and architecture notes from `docs/agent-messaging.md` SHALL be present

#### Scenario: Cross-machine setup
- **WHEN** reading the setup section
- **THEN** the two-machine setup example from the old README SHALL be present

### Requirement: MCP Server page
`docs/mcp-server.md` SHALL contain the MCP tool reference (list_worktrees, get_ralph_status, get_worktree_tasks, get_team_status, and all memory MCP tools), manual setup command, auto-configuration notes, and how agents use MCP tools to see each other.

#### Scenario: Tool table
- **WHEN** reading the MCP server page
- **THEN** every MCP tool exposed by the server SHALL be listed with description

#### Scenario: Setup instructions
- **WHEN** looking for MCP setup
- **THEN** both auto-configured (via installer) and manual (`claude mcp add`) paths SHALL be documented

### Requirement: Plugins page
`docs/plugins.md` SHALL contain the plugin concept (extend set-core without modifying core), planned installation pattern, plugin registry table (initially empty, with column headers for Name, Repo, Description, Status), and brief guidance on creating a plugin.

#### Scenario: Registry table structure
- **WHEN** viewing the plugin registry
- **THEN** it SHALL be a markdown table with columns: Name, Repository, Description, Status
- **AND** it SHALL start empty with a note: "No plugins registered yet"

#### Scenario: Installation pattern
- **WHEN** reading the plugin install section
- **THEN** it SHALL describe the planned `set-plugin install <repo>` pattern (even if not yet implemented)

### Requirement: CLI Reference page
`docs/cli-reference.md` SHALL contain the complete CLI command reference currently in the README, organized by category: Worktree Management, Project Management, Ralph Loop, Orchestration, Team & Sync, Developer Memory, OpenSpec, Utilities. Internal scripts SHALL be listed in a collapsed section.

#### Scenario: Command completeness
- **WHEN** comparing `docs/cli-reference.md` with `ls bin/set-*`
- **THEN** every user-facing command SHALL be documented

#### Scenario: Category organization
- **WHEN** reading the CLI reference
- **THEN** commands SHALL be grouped by category with category headers

### Requirement: Configuration page
`docs/configuration.md` SHALL contain all configuration files (gui-config.json, projects.json, editor, orchestration.yaml, rules.yaml, project-knowledge.yaml), their locations, format, and complete option reference. The orchestration directive table from `docs/orchestration.md` SHALL be cross-referenced.

#### Scenario: Config file inventory
- **WHEN** reading the configuration page
- **THEN** every config file used by set-core SHALL be listed with path and purpose

#### Scenario: Orchestration config
- **WHEN** looking for orchestration.yaml options
- **THEN** there SHALL be either a full table or a link to the directive reference in `docs/orchestration.md`

### Requirement: Architecture page
`docs/architecture.md` SHALL contain the full 4-layer architecture diagram (currently in README), technology table, the "nested agent collaboration" vision diagram (Layer 1/2/3), Agent Teams integration diagram, and the Future Development section content from the old README.

#### Scenario: Architecture diagram
- **WHEN** reading the architecture page
- **THEN** the full CLI + Orchestration + GUI + MCP layer diagram SHALL be present

#### Scenario: Vision section
- **WHEN** reading the architecture page
- **THEN** the "Nested Agent Collaboration" vision and Agent Teams integration content SHALL be present

### Requirement: Existing docs get navigation
Existing doc pages (`sentinel.md`, `orchestration.md`, `developer-memory.md`, `project-management.md`) SHALL receive navigation headers and "See also" footers without changing their substantive content.

#### Scenario: Navigation added to existing docs
- **WHEN** viewing any existing doc page
- **THEN** it SHALL have a back-to-README link at the top and related page links at the bottom
- **AND** the substantive content SHALL remain unchanged
