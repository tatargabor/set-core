## ADDED Requirements

### Requirement: Global JIRA Credentials Configuration
The system SHALL provide a global credentials configuration mechanism that allows users to configure JIRA server access once and use it across all worktrees and projects.

#### Scenario: First-time credentials setup
- **WHEN** user runs `wt-jira init`
- **THEN** the system prompts for JIRA server URL, username, and password
- **AND** stores credentials in `~/.config/set-core/jira.json` with file permission 600
- **AND** displays confirmation with masked password

#### Scenario: Environment variables override config file
- **WHEN** `JIRA_URL`, `JIRA_USERNAME`, and `JIRA_PASSWORD` environment variables are set
- **THEN** the MCP server uses these values instead of config file credentials
- **AND** partial env vars fall back to config file for missing values

#### Scenario: Config file location
- **WHEN** system looks for JIRA credentials
- **THEN** it reads from `~/.config/set-core/jira.json` on Linux/macOS
- **AND** it reads from `%APPDATA%\set-core\jira.json` on Windows

### Requirement: Project-Level JIRA Configuration
The system SHALL support project-level JIRA configuration stored in the repository root.

#### Scenario: Read project config
- **WHEN** system creates a JIRA issue from a repository
- **THEN** it reads `.set-core/jira.json` from the repository root
- **AND** merges project config with global config (project takes precedence for overlapping keys)

#### Scenario: Title prefix applied to issues
- **WHEN** system creates a Task or Sub-Task with titlePrefix configured as "[OpenSpec]"
- **AND** the proposal title is "Add JIRA Integration"
- **THEN** the JIRA issue summary becomes "[OpenSpec] Add JIRA Integration"

#### Scenario: No project config exists
- **WHEN** `.set-core/jira.json` does not exist in repository
- **THEN** system uses global config only
- **AND** no prefix is added to issue titles

#### Scenario: Project overrides default JIRA project
- **WHEN** project config has `defaultProject: "MYPROJ"`
- **AND** global config has `defaultProject: "OTHER"`
- **THEN** issues are created in MYPROJ

#### Scenario: Default parent Task for non-interactive sync
- **WHEN** project config has `defaultParentTask: "EXAMPLE-100"`
- **AND** user runs `wt-jira sync -y`
- **THEN** new Sub-Tasks are created under EXAMPLE-100 without prompting

### Requirement: JIRA MCP Server
The system SHALL provide an MCP (Model Context Protocol) server that exposes JIRA operations as tools for Claude Code.

#### Scenario: MCP server starts with Claude Code
- **WHEN** Claude Code starts with jira-mcp configured in mcpServers
- **THEN** the MCP server initializes and reads credentials from global config
- **AND** reports available tools to Claude Code

#### Scenario: MCP server handles missing credentials gracefully
- **WHEN** MCP server starts without valid credentials
- **THEN** it returns a clear error message explaining how to configure credentials
- **AND** does not crash or hang

### Requirement: JIRA Issue Reading
The system SHALL allow reading JIRA issue details through MCP tools.

#### Scenario: Get issue by key
- **WHEN** Claude invokes `jira_get_issue` with key "EXAMPLE-508"
- **THEN** the tool returns issue summary, description, status, assignee, reporter, created date, and updated date
- **AND** formats the response in a human-readable structure

#### Scenario: Issue not found
- **WHEN** Claude invokes `jira_get_issue` with a non-existent key
- **THEN** the tool returns a clear error message indicating the issue was not found

### Requirement: JIRA JQL Search
The system SHALL allow searching JIRA issues using JQL (JIRA Query Language).

#### Scenario: Search with JQL query
- **WHEN** Claude invokes `jira_search` with jql "project = EXAMPLE AND status = Open"
- **THEN** the tool returns a list of matching issues with key, summary, and status
- **AND** respects the optional maxResults parameter (default 50)

#### Scenario: Invalid JQL query
- **WHEN** Claude invokes `jira_search` with an invalid JQL query
- **THEN** the tool returns the JIRA error message explaining the syntax error

### Requirement: JIRA Issue Creation
The system SHALL allow creating new JIRA issues through MCP tools.

#### Scenario: Create issue with required fields
- **WHEN** Claude invokes `jira_create_issue` with project, summary, and issueType
- **THEN** the tool creates the issue in JIRA
- **AND** returns the created issue key (e.g., "EXAMPLE-509")

#### Scenario: Create issue with optional fields
- **WHEN** Claude invokes `jira_create_issue` with description and assignee
- **THEN** the tool includes these fields in the created issue

#### Scenario: Create issue with invalid project
- **WHEN** Claude invokes `jira_create_issue` with a non-existent project key
- **THEN** the tool returns a clear error message about the invalid project

### Requirement: JIRA Issue Modification
The system SHALL allow modifying existing JIRA issues through MCP tools.

#### Scenario: Update issue fields
- **WHEN** Claude invokes `jira_update_issue` with key and fields to update
- **THEN** the tool updates the specified fields in JIRA
- **AND** returns confirmation with the updated values

#### Scenario: Add comment to issue
- **WHEN** Claude invokes `jira_add_comment` with issue key and comment body
- **THEN** the tool adds the comment to the issue
- **AND** returns the created comment ID

#### Scenario: Transition issue status
- **WHEN** Claude invokes `jira_transition_issue` with key and transitionId
- **THEN** the tool changes the issue status to the target state
- **AND** optionally adds a transition comment if provided

#### Scenario: Get available transitions
- **WHEN** Claude invokes `jira_get_transitions` with issue key
- **THEN** the tool returns a list of available transitions with id and name
- **AND** indicates the current status

### Requirement: JIRA Issue Linking
The system SHALL allow linking JIRA issues to establish relationships such as parent-child (Sub-Task to Task/Epic) and other link types.

#### Scenario: Create Sub-Task under parent issue
- **WHEN** Claude invokes `jira_create_issue` with issueType "Sub-task" and parent key
- **THEN** the tool creates the Sub-Task linked to the specified parent issue
- **AND** returns the created Sub-Task key

#### Scenario: Link two existing issues
- **WHEN** Claude invokes `jira_link_issues` with inwardKey, outwardKey, and linkType (e.g., "blocks", "relates to")
- **THEN** the tool creates the link between the two issues
- **AND** returns confirmation of the created link

#### Scenario: Get linked issues
- **WHEN** Claude invokes `jira_get_issue_links` with issue key
- **THEN** the tool returns all linked issues grouped by link type
- **AND** includes parent issue for Sub-Tasks
- **AND** includes child Sub-Tasks for parent issues

#### Scenario: Invalid link type
- **WHEN** Claude invokes `jira_link_issues` with an unsupported link type
- **THEN** the tool returns an error with available link types

### Requirement: JIRA Worklog
The system SHALL allow logging work time to JIRA issues through MCP tools and CLI.

#### Scenario: Add worklog via MCP
- **WHEN** Claude invokes `jira_add_worklog` with issue key, duration "2h", and optional comment
- **THEN** the tool creates a worklog entry on the issue
- **AND** returns confirmation with logged time

#### Scenario: Add worklog via CLI with explicit key
- **WHEN** user runs `wt-jira log EXAMPLE-509 2h "Implementation work"`
- **THEN** the tool creates a worklog entry with 2 hours duration
- **AND** includes the comment in the worklog

#### Scenario: Add worklog via CLI with automatic ticket resolution
- **WHEN** user runs `wt-jira log 2h "Implementation work"` inside a worktree
- **AND** the worktree has an associated change with `openspec/changes/<id>/proposal.md` containing `JIRA Key:`
- **THEN** the tool reads the issue key from proposal.md
- **AND** creates a worklog entry on that issue

#### Scenario: Worklog without ticket context
- **WHEN** user runs `wt-jira log 2h` without explicit key
- **AND** no `JIRA Key:` line exists in proposal.md for current context
- **THEN** the tool shows an error explaining how to specify the issue key or add JIRA Key to proposal.md

#### Scenario: Duration format parsing
- **WHEN** user provides duration in format "1h 30m" or "1d" or "45m"
- **THEN** the system correctly parses and converts to JIRA time format

### Requirement: OpenSpec-JIRA Automatic Sync
The system SHALL automatically create JIRA Sub-Tasks when OpenSpec proposals are created and validated.

#### Scenario: Create Sub-Task after proposal validation
- **WHEN** an OpenSpec proposal is created and passes `openspec validate <id> --strict`
- **THEN** the system prompts for parent Task selection
- **AND** creates a Sub-Task in JIRA with proposal title as summary
- **AND** stores the mapping in `openspec/changes/<id>/jira.json`

#### Scenario: Select existing parent Task
- **WHEN** system prompts for parent Task and user selects "Use existing Task"
- **THEN** the system lists open Tasks in the project or accepts a Task key
- **AND** creates the Sub-Task under the selected parent

#### Scenario: Create new parent Task
- **WHEN** system prompts for parent Task and user selects "Create new Task"
- **THEN** the system prompts for Task summary
- **AND** creates the parent Task first
- **AND** then creates the Sub-Task under it

#### Scenario: JIRA Key added to proposal.md
- **WHEN** Sub-Task is created successfully
- **THEN** `JIRA Key: <issue-key>` and `Parent Task: <parent-key>` lines are added to proposal.md after the title

#### Scenario: Skip JIRA sync
- **WHEN** user declines JIRA Sub-Task creation during prompt
- **THEN** the proposal remains valid without JIRA Key
- **AND** no JIRA Key line is added to proposal.md

### Requirement: Batch JIRA Sync
The system SHALL provide batch synchronization of all worktree proposals with JIRA.

#### Scenario: Sync all worktrees
- **WHEN** user runs `wt-jira sync`
- **THEN** the tool iterates through all worktrees from `wt-list --all`
- **AND** checks each `openspec/changes/*/proposal.md` for JIRA Key
- **AND** reports sync status for each proposal

#### Scenario: Create missing JIRA issues during sync
- **WHEN** `wt-jira sync` finds a proposal without JIRA Key
- **THEN** the tool prompts for parent Task selection
- **AND** creates the Sub-Task in JIRA
- **AND** adds JIRA Key to proposal.md

#### Scenario: Verify existing JIRA issues
- **WHEN** `wt-jira sync` finds a proposal with JIRA Key
- **THEN** the tool verifies the issue exists in JIRA
- **AND** reports success or warns if issue not found

#### Scenario: Dry run mode
- **WHEN** user runs `wt-jira sync --dry-run`
- **THEN** the tool shows what would be done
- **AND** does not create or modify any JIRA issues
- **AND** does not modify any proposal.md files

#### Scenario: Sync specific project only
- **WHEN** user runs `wt-jira sync -p myproject`
- **THEN** only worktrees for "myproject" are processed

#### Scenario: Non-interactive sync
- **WHEN** user runs `wt-jira sync -y`
- **THEN** missing JIRA issues are created automatically
- **AND** default parent Task from project config is used
- **AND** no interactive prompts are shown

### Requirement: JIRA CLI Tool
The system SHALL provide a CLI tool for managing JIRA credentials and testing connectivity.

#### Scenario: Initialize credentials interactively
- **WHEN** user runs `wt-jira init`
- **THEN** the tool prompts for server URL, username, and password
- **AND** validates the URL format
- **AND** optionally tests the connection before saving

#### Scenario: Test JIRA connection
- **WHEN** user runs `wt-jira test`
- **THEN** the tool attempts to connect to the configured JIRA server
- **AND** reports success or failure with details

#### Scenario: Show current configuration
- **WHEN** user runs `wt-jira show`
- **THEN** the tool displays the configured server URL and username
- **AND** masks the password (shows only first and last character)

### Requirement: JIRA Authentication
The system SHALL authenticate with JIRA Server using HTTP Basic Authentication.

#### Scenario: Successful authentication
- **WHEN** MCP tool makes a request to JIRA API
- **THEN** it includes Authorization header with base64-encoded username:password
- **AND** the request succeeds if credentials are valid

#### Scenario: Authentication failure
- **WHEN** MCP tool makes a request with invalid credentials
- **THEN** it returns a clear error message indicating authentication failed
- **AND** suggests running `wt-jira init` to reconfigure credentials

### Requirement: JIRA API Error Handling
The system SHALL handle JIRA API errors gracefully and provide informative messages.

#### Scenario: Network timeout
- **WHEN** JIRA server is unreachable or times out
- **THEN** the tool returns an error message indicating network issues
- **AND** includes the configured server URL for debugging

#### Scenario: Rate limiting
- **WHEN** JIRA server returns 429 Too Many Requests
- **THEN** the tool returns an error message about rate limiting
- **AND** suggests waiting before retrying

#### Scenario: Server error
- **WHEN** JIRA server returns 5xx error
- **THEN** the tool returns an error message indicating server-side issues
- **AND** includes the HTTP status code
