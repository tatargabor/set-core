# Change: Add File Activity Tracking via Claude Hooks

## Why

Current activity detection only uses timestamps from existing sources (git commits, IDE logs, Claude sessions). With the Claude Code hooks system, we can directly track which files the Claude agent reads/writes, providing:

- More accurate activity detection (no need to wait for a commit)
- Knowledge of which files Claude worked on
- Uncommitted work is also trackable
- Session context is preserved
- No separate daemon needed

## What Changes

### Core Features

- **Claude hooks integration**: PostToolUse hook for Read/Edit/Write tools
- **Activity log**: Logging every file operation with timestamp and context
- **Reconstruct integration**: `auto --reconstruct` uses the activity log
- **Query commands**: View which files were modified

### Activity Log Format

`~/.config/set-core/claude-activity.jsonl`:
```json
{"ts":"2026-01-21T10:15:32Z","tool":"Edit","path":"/home/user/project/src/api.ts","session":"abc123","project":"my-project","change_id":"add-feature"}
{"ts":"2026-01-21T10:16:45Z","tool":"Read","path":"/home/user/project/src/utils.ts","session":"abc123","project":"my-project","change_id":"add-feature"}
```

### Hook Configuration

```json
// ~/.claude/settings.json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": ["Read", "Edit", "Write"],
        "command": "wt-activity-log \"$CWD\" \"$TOOL_NAME\" \"$TOOL_INPUT\""
      }
    ]
  }
}
```

### CLI Commands

```bash
# Setup
wt-activity setup              # Adds hooks to Claude settings

# Query
wt-activity list [--date DATE] # List today's file activities
wt-activity files [--date DATE] # List unique files worked on
wt-activity stats [--date DATE] # Summary statistics

# Worklog integration (automatic)
wt-jira auto --reconstruct     # Now includes claude-activity source
```

## Impact

- Affected specs: `jira-worklog` (extended with claude-activity source)
- Affected code: `bin/wt-jira` (reconstruct mode)
- New files:
  - `bin/wt-activity` - Activity logging and query script
  - `~/.config/set-core/claude-activity.jsonl` - Activity log
- New dependencies: None (uses Claude Code built-in hooks)

## Configuration

```json
{
  "activityTracking": {
    "enabled": true,
    "logReads": true,
    "logEdits": true,
    "logWrites": true,
    "confidence": 0.85,
    "ignorePatterns": [
      "node_modules/**",
      ".git/**"
    ]
  }
}
```

## Advantages Over Filesystem Watcher

| Aspect | Filesystem Watcher | Claude Hooks |
|--------|-------------------|--------------|
| Daemon | Required | Not needed |
| Scope | All file changes | Only Claude activity |
| Context | File path only | Tool, session, project |
| Reads | Cannot track | Tracked |
| Setup | Start daemon | One-time hook setup |
| Resource usage | Continuous | On-demand |
