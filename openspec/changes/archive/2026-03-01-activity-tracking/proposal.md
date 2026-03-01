## Why

Multiple Claude agents working on the same machine (different worktrees) have no way to see what each other is doing in real-time. The existing team-sync system tracks worktree-level state (branch, change-id, agent running/idle) but not activity-level detail (which skill is running, what files are being modified, what the agent is focused on). This gap leads to duplicate work, merge conflicts, and missed coordination opportunities. The original `context-sharing` change proposed a separate git-synced system, but we've decided to merge this into team-sync as a two-layer architecture: instant local sharing + periodic git sync for remote machines.

## What Changes

- Add **local activity file** per worktree (`.claude/activity.json`) written by Claude hooks, containing active skill, skill args, modified files, and optional broadcast message
- Extend **`wt-control-sync`** to read local activity files and include activity data in `members/*.json`
- Extend **MCP server** `get_ralph_status()` or add new `get_activity()` tool to expose local activity for same-machine agents
- Add **`/context broadcast`** skill for agents to announce what they're working on (free-form text, overwrites previous)
- Add **`/context status`** skill to display all agents' current activity (reads local files for same-machine, member JSON for remote)
- Add **Claude hook** (PreToolUse on Skill tool) that writes activity to `.claude/activity.json` with throttling
- Update **GUI team status** to show activity info (skill, broadcast) in tooltips and detail dialogs

## Capabilities

### New Capabilities

- `activity-tracking`: Local file-based activity tracking per worktree, Claude hook for auto-capture, broadcast skill, status skill

### Modified Capabilities

- `team-sync`: Member JSON extended with activity block; wt-control-sync reads local activity files during sync
- `cross-context-visibility`: MCP server extended to expose activity data for same-machine agent coordination

## Impact

- `bin/wt-control-sync` - reads `.claude/activity.json` from each worktree, adds to member JSON
- `mcp-server/wt_mcp_server.py` - new or extended tool for activity queries
- `.claude/hooks/` - new hook script for skill tracking (project-level)
- `.claude/commands/context/` - new broadcast and status skills
- `gui/workers/team.py` - pass activity data through to GUI
- `gui/control_center/mixins/team.py` - display activity in tooltips/details
- `.claude/activity.json` per worktree - new local state file
