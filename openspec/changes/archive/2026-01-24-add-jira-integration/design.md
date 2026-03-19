## Context
Integration of a standalone JIRA Server (e.g., `jira.example.com`) into Claude Code via MCP protocol. The goal is to configure credentials once and have every worktree/project automatically use them.

Target platforms:
- Linux (primary)
- macOS
- Windows (Git Bash, WSL)

## Goals / Non-Goals
**Goals:**
- Global credential storage - configured once, works in every worktree
- MCP server for Claude Code to perform JIRA operations
- JIRA REST API v2 support (for legacy standalone JIRA servers)
- Simple CLI tool for credential management

**Non-Goals:**
- JIRA Cloud specific features (OAuth 2.0, Atlassian Connect)
- JIRA webhooks/listeners
- Full JIRA admin features (user management, schemes)
- GUI

## Decisions

### Credential Storage Location
**Decision:** `~/.config/set-core/jira.json` (global, in user home directory)

**Structure:**
```json
{
  "servers": {
    "default": {
      "url": "https://jira.example.com",
      "username": "john.smith",
      "password": "...",
      "defaultProject": "EXAMPLE"
    }
  },
  "activeServer": "default"
}
```

**Alternatives:**
- Project-level config (`.set-core/jira.json`): would need to be configured per-worktree - REJECTED
- Environment variables: not persistent, shell-dependent - SUPPORTED as fallback
- System keychain (libsecret/keyring): platform-specific complexity - FUTURE VERSION

**Rationale:** Global config configured once works everywhere. The `~/.config/set-core/` directory is already used for the project registry.

### Project-level JIRA Configuration
**Decision:** `.set-core/jira.json` in repo root for project-specific settings

**Structure:**
```json
{
  "titlePrefix": "[OpenSpec]",
  "defaultProject": "EXAMPLE",
  "defaultParentTask": "EXAMPLE-100"
}
```

**Fields:**
- `titlePrefix`: Prefix added before JIRA ticket titles (e.g., `"[OpenSpec]"`, `"[MyProject]"`)
- `defaultProject`: Overrides the global config `defaultProject` value
- `defaultParentTask`: Default parent Task key for non-interactive sync (`wt-jira sync -y`)

**Example result:**
- Proposal title: `Add JIRA Integration`
- JIRA Sub-Task summary: `[OpenSpec] Add JIRA Integration`

**Config priority (merged):**
1. Environment variables (JIRA_URL, JIRA_USERNAME, JIRA_PASSWORD)
2. Project config (`.set-core/jira.json`) - titlePrefix, defaultProject
3. Global config (`~/.config/set-core/jira.json`) - credentials, defaultProject

**Rationale:** Project-level config enables using different prefixes in different repos, making tickets from different sources distinguishable in JIRA.

### Environment Variable Support
**Decision:** Env vars override the config file (higher priority)

**Supported variables:**
- `JIRA_URL` - server URL
- `JIRA_USERNAME` - username
- `JIRA_PASSWORD` - password
- `JIRA_PROJECT` - default project key

**Priority order:**
1. Environment variables (if all 3 basic ones are provided)
2. Config file (`~/.config/set-core/jira.json`)
3. Error if neither is available

**Rationale:** CI/CD environments and Docker containers commonly use env vars. This adds flexibility without complicating the normal workflow.

### MCP Server Selection
**Decision:** Use `mcp-atlassian` (existing, tested solution)

**Rationale:**
- Already works in the project
- Supports standalone JIRA Server (not just Cloud)
- Python-based, installable via `uvx` or `pip`
- No need to develop and maintain a custom MCP server

**Alternatives:**
- Custom Node.js MCP server: more work but full control - REJECTED
- Custom Python MCP server: more work - REJECTED

### MCP Server Configuration
**Decision:** `.mcp.json` file in repo root (gitignored)

**Claude Code config example (`.mcp.json`):**
```json
{
  "mcpServers": {
    "jira": {
      "command": "uvx",
      "args": ["mcp-atlassian"],
      "env": {
        "JIRA_URL": "https://jira.example.com",
        "JIRA_USERNAME": "user.name",
        "JIRA_API_TOKEN": "..."
      }
    }
  }
}
```

**Template file:** `.mcp.template.json` - committed, without credentials

**Rationale:** `.mcp.json` is project-level, but credentials are inside as env vars. This is compatible with the existing project approach.

### JIRA API Version
**Decision:** JIRA REST API v2 (legacy compatibility)

**Endpoint examples:**
- `GET /rest/api/2/issue/{issueKey}`
- `POST /rest/api/2/search` (JQL)
- `POST /rest/api/2/issue`
- `PUT /rest/api/2/issue/{issueKey}`
- `GET /rest/api/2/issue/{issueKey}/transitions`
- `POST /rest/api/2/issue/{issueKey}/transitions`
- `POST /rest/api/2/issue/{issueKey}/comment`

**Authentication:** HTTP Basic Auth (username:password base64 encoded)

**Rationale:** Most standalone JIRA servers use API v2. V3 (JIRA Cloud) requires different authentication.

### MCP Tools Definitions
**Decision:** 10 tools for the most common operations

| Tool | Input | Output |
|------|-------|--------|
| `jira_get_issue` | `key: string` | Issue details (summary, description, status, assignee, etc.) |
| `jira_search` | `jql: string, maxResults?: number` | List of matching issues |
| `jira_create_issue` | `project, summary, issueType, description?, assignee?, parent?` | Created issue key |
| `jira_update_issue` | `key, fields: object` | Updated issue |
| `jira_add_comment` | `key, body: string` | Created comment |
| `jira_get_transitions` | `key` | Available transitions |
| `jira_transition_issue` | `key, transitionId, comment?` | Transitioned issue |
| `jira_link_issues` | `inwardKey, outwardKey, linkType` | Created link |
| `jira_get_issue_links` | `key` | List of linked issues |
| `jira_add_worklog` | `key, duration, comment?` | Created worklog entry |

### OpenSpec-JIRA Automation
**Decision:** Automatic Sub-Task creation in JIRA after proposal creation

**Workflow:**
1. Claude creates the OpenSpec proposal (`openspec/changes/<id>/`)
2. Proposal validation succeeds (`openspec validate <id> --strict`)
3. System asks for the parent Task:
   - "Create new Task" → asks for Task summary, creates it, then creates Sub-Task under it
   - "Use existing Task" → lists open Tasks or asks for key
4. Sub-Task creation:
   - **Summary:** title after `# Change:` in proposal.md
   - **Description:** change-id + proposal.md content (or link)
   - **Issue Type:** Sub-task
   - **Parent:** selected Task
5. JIRA Key added to proposal.md

**JIRA Key storage in proposal.md:**
```markdown
# Change: Add JIRA Integration

JIRA Key: EXAMPLE-509
Parent Task: EXAMPLE-100

## Why
...
```

**Format:**
- `JIRA Key: <issue-key>` - the Sub-Task JIRA key
- `Parent Task: <issue-key>` - the parent Task key

**Rationale:**
- All information in one place
- Easy to read and search
- No need to maintain a separate file
- JIRA connection visible in git history

### Worklog Function
**Decision:** CLI and MCP tool for work time logging, with automatic ticket resolution

**CLI usage:**
```bash
# Explicit issue key
wt-jira log EXAMPLE-509 2h "Proposal implementation"

# Automatic - in change directory or worktree
wt-jira log 2h "Proposal implementation"
# → Finds openspec/changes/<current-change>/proposal.md and reads the JIRA Key line
```

**Ticket resolution order:**
1. Explicit `<issue-key>` parameter (if provided)
2. Current worktree change-id → `openspec/changes/<id>/proposal.md` → `JIRA Key:` line
3. Error if neither is available

**Duration formats:**
- `2h` - 2 hours
- `30m` - 30 minutes
- `1h 30m` - 1 hour 30 minutes
- `1d` - 1 day (8 hours)

**API endpoint:** `POST /rest/api/2/issue/{issueKey}/worklog`

**Rationale:** Simple CLI interface for quick logging, MCP tool for use through Claude ("log 2 hours for today's work").

### Batch JIRA Sync
**Decision:** `wt-jira sync` command for syncing all worktree JIRA status

**Workflow:**
```
wt-jira sync [--dry-run] [-p <project>]
  │
  ├─ 1. wt-list --all (or -p for specific project)
  │
  ├─ 2. In each worktree:
  │     └─ Search for openspec/changes/*/proposal.md
  │
  ├─ 3. For each proposal:
  │     ├─ Has JIRA Key? → Verify (exists in JIRA?)
  │     └─ No JIRA Key? → Create (interactive parent Task prompt)
  │
  └─ 4. Summary report
```

**Output example:**
```
Syncing JIRA for all worktrees...

[myproject] add-user-auth
  ✓ JIRA Key: EXAMPLE-510 (exists)

[myproject] fix-login-bug
  ✗ No JIRA Key found
  → Create Sub-Task? (y/n/skip-all)
  → Parent Task: [1] EXAMPLE-100 (existing) / [2] Create new
  ✓ Created: EXAMPLE-511

[other-project] add-feature
  ✓ JIRA Key: OTHER-42 (exists)

Summary: 3 proposals, 2 synced, 1 created
```

**Flags:**
- `--dry-run`: Only shows what would be done, doesn't modify anything
- `-p, --project <name>`: Only for specific project worktrees
- `--skip-existing`: Don't verify existing JIRA Keys
- `-y, --yes`: Don't ask, create automatically (uses default parent Task)

**Rationale:** Batch sync enables synchronizing all active work with JIRA in one command, instead of handling each one individually.

### Password Security
**Decision:** Plain text storage in config file, protected by file permissions (600)

**Alternatives:**
- Encryption with master password: extra complexity
- System keychain: platform-specific implementation
- Environment variable only: not persistent

**Rationale:** `~/.config/` files have user-only access (permission 600). This provides adequate security on single-user development machines. Keychain support can be added in a future version.

**Mitigation:**
- `wt-jira init` warns about plain text storage
- Config file automatically created with 600 permissions
- `wt-jira show` masks the password

## Risks / Trade-offs
- **Risk:** Plain text password storage → **Mitigation:** File permission 600, user warning
- **Risk:** Different JIRA version incompatibility → **Mitigation:** API v2 is widely supported
- **Risk:** Network issues → **Mitigation:** Timeout and retry logic, informative error messages
- **Trade-off:** Node.js dependency → Simpler implementation and better MCP integration

## Migration Plan
1. Run `wt-jira init` to set up credentials
2. Install MCP server (`install` script)
3. Restart Claude Code to load MCP server
4. Testing: `wt-jira test` and JIRA commands in Claude Code

**Rollback:** Remove MCP server from Claude Code config, credential deletion optional.

## Open Questions
- API token support instead of password (if the JIRA server supports it)?

## Closed Questions
- **Multi-server support:** Not needed (single JIRA instance)
- **Attachment handling:** Not needed
- **Issue linking:** Yes - proposals are created as Sub-Tasks, linked to parent Tasks (NOT JIRA Epic type!)
