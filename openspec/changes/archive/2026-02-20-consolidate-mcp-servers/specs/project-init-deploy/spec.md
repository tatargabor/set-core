## MODIFIED Requirements

### Requirement: install.sh removes global symlinks
`install.sh`'s `install_skills()` function SHALL NOT create global symlinks at `~/.claude/commands/wt` or `~/.claude/skills/wt`. It SHALL NOT register a global MCP server. Instead, `install.sh` SHALL call `set-project init` for each project registered in `projects.json`.

#### Scenario: Fresh install deploys to all registered projects
- **WHEN** `install.sh` runs with 3 projects registered in `projects.json`
- **THEN** `set-project init` is called for each project, deploying hooks, commands, skills, and MCP registration

#### Scenario: No global MCP registration created
- **WHEN** `install.sh` completes
- **THEN** no `--scope user` MCP server SHALL be registered
- **AND** any existing global `set-core` MCP registration SHALL be removed

#### Scenario: Legacy set-memory MCP cleaned up during install
- **WHEN** `install.sh` runs
- **THEN** it SHALL remove any global `set-memory` MCP registration if present

## ADDED Requirements

### Requirement: set-project init registers unified MCP server
When `set-project init` runs, it SHALL register the unified `set-core` MCP server with `CLAUDE_PROJECT_DIR` set to the project root path.

#### Scenario: MCP registration with project context
- **WHEN** `set-project init` is called with a project path
- **THEN** it SHALL run: `cd "$project_path" && claude mcp remove set-memory; claude mcp remove set-core; claude mcp add set-core -- env CLAUDE_PROJECT_DIR="$project_path" uv --directory "$mcp_server_dir" run python wt_mcp_server.py`

#### Scenario: Worktree MCP registration
- **WHEN** `set-project init` is called with extra paths (e.g., worktree paths)
- **THEN** each extra path SHALL also get a per-project registration with its own `CLAUDE_PROJECT_DIR`
