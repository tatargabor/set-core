# Change: Add JIRA Integration with Global Credentials and OpenSpec Automation

JIRA Key: EXAMPLE-523
Story: EXAMPLE-466

## Why
When using a standalone JIRA Server, every developer has to manually copy JIRA issue details and manually synchronize JIRA with OpenSpec proposals. With MCP integration and OpenSpec automation:
- Claude can directly manage JIRA issues
- Sub-Tasks are automatically created in JIRA when proposals are created
- Worklog entries can be easily recorded
- Global credential storage eliminates per-worktree reconfiguration

## What Changes
- **mcp-atlassian MCP server usage** (existing, tested solution)
  - Installation: `uvx mcp-atlassian` or `pip install mcp-atlassian`
  - Supported JIRA operations:
    - `jira_get_issue` - Query issue details
    - `jira_search` - JQL-based search
    - `jira_create_issue` - Create new issue (with Sub-Task support)
    - `jira_update_issue` - Modify issue
    - `jira_add_comment` - Add comment
    - `jira_get_transitions` / `jira_transition_issue` - Status management
    - `jira_add_worklog` / `jira_get_worklog` - Work time logging
- **OpenSpec-JIRA automation:**
  - Automatic Sub-Task creation in JIRA after proposal creation
  - Summary = `[prefix] proposal title` (prefix from project config)
  - Parent Task: interactive prompt (create new Task or use existing)
  - **JIRA Key storage: in proposal.md** in `JIRA Key: EXAMPLE-XXX` format
- **Project-level JIRA config:** `.set-core/jira.json` in repo root
  - `titlePrefix`: JIRA ticket title prefix (e.g., `"[OpenSpec]"`, `"[MyProject]"`)
  - `defaultProject`: Override JIRA project key at project level
  - `defaultParentTask`: Default parent Task key (for non-interactive sync)
- **Worklog function:**
  - `wt-jira log [issue-key] <duration> [comment]` - record work time
  - If no issue-key specified → automatically reads from proposal.md `JIRA Key:` field
  - Duration format: "2h", "30m", "1h 30m"
- **Batch JIRA sync (`wt-jira sync`):**
  - Iterates through all worktrees (based on `wt-list --all`)
  - Checks `openspec/changes/*/proposal.md` files in each worktree
  - If no `JIRA Key:` → creates interactively (parent Task prompt)
  - If has `JIRA Key:` → verifies existence in JIRA (optional update)
  - `--dry-run` flag: only shows what would be done
  - `--project <name>` flag: only for specific project worktrees
- Global credentials configuration: `~/.config/set-core/jira.json`
  - JIRA server URL (e.g., `https://jira.example.com`)
  - Username/password or API token
  - Optional: default project key
- `wt-jira` CLI tool: credentials management and testing
  - `wt-jira init` - interactive credentials setup
  - `wt-jira test` - connection testing
  - `wt-jira show` - display current configuration (password masked)
- MCP server registration: automatically or manually in Claude Code settings

## Impact
- Affected specs: jira-integration (new capability)
- Affected code: `bin/wt-jira` (CLI tool), `.mcp.json` template
- **Depends on:** `add-worktree-tools` change (config infrastructure, install scripts)
- **External dependency:** `mcp-atlassian` Python package
- Extends: `~/.config/set-core/` directory (jira.json), `install.sh/ps1` scripts
