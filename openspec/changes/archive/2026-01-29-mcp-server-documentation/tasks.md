## 1. MCP Server Core

- [x] 1.1 Create `mcp-server/` directory structure
- [x] 1.2 Create `pyproject.toml` with FastMCP dependency
- [x] 1.3 Implement `wt_mcp_server.py` with FastMCP framework
- [x] 1.4 Add `list_worktrees()` tool - reads from projects.json and git
- [x] 1.5 Add `get_ralph_status()` tool - reads loop-state.json files
- [x] 1.6 Add `get_team_status()` tool - reads team_status.json cache
- [x] 1.7 Add `get_worktree_tasks()` tool - reads tasks.md from worktree

## 2. MCP Configuration

- [x] 2.1 Test MCP server starts without errors
- [x] 2.2 Add MCP server to Claude Code with `claude mcp add --scope user`
- [x] 2.3 Verify server shows "Connected" in `claude mcp list`
- [x] 2.4 Add MCP setup to install.sh

## 3. Ralph State Integration

- [x] 3.1 Document loop-state.json schema in design or spec
- [x] 3.2 Verify wt-loop writes all required fields to loop-state.json
- [x] 3.3 Implement duration calculation in MCP (from started_at)
- [x] 3.4 Handle missing/corrupt loop-state.json gracefully

## 4. Status Line Integration

- [x] 4.1 Research Claude Code status line hook format
- [x] 4.2 Create status line hook script that detects current worktree
- [x] 4.3 Hook reads loop-state.json directly (faster than MCP call)
- [x] 4.4 Format output: `🔄 Ralph: 3/10` with status icons
- [x] 4.5 Configure hook in `~/.claude/settings.json`

## 5. GUI Team Status Cache

- [x] 5.1 Create `~/.cache/set-core/` directory if not exists
- [x] 5.2 Update Control Center GUI to write team_status.json
- [x] 5.3 Define team_status.json schema (members, agent_status, change_id)
- [x] 5.4 Test MCP reads team status correctly

## 6. Ralph Auto-Detect Change-ID

- [x] 6.1 Extract worktree detection logic into reusable function `detect_change_id_from_pwd()`
- [x] 6.2 Update `cmd_start()` to use auto-detection when change-id not provided
- [x] 6.3 Update `cmd_stop()` to use auto-detection when change-id not provided
- [x] 6.4 Update `cmd_history()` to use auto-detection when change-id not provided
- [x] 6.5 Update `cmd_monitor()` to use auto-detection when change-id not provided
- [x] 6.6 Verify `cmd_status()` already has auto-detection (just confirm)
- [x] 6.7 Update usage text to show change-id is optional when in worktree

## 7. Documentation

- [x] 7.1 Add MCP section to README.md
- [x] 7.2 Document available MCP tools and their parameters
- [x] 7.3 Document status line configuration
- [x] 7.4 Add troubleshooting guide for MCP connection issues
- [x] 7.5 Update wt-loop --help to show optional change-id
