# Change: Add Automatic JIRA Worklog Generation

JIRA Key: EXAMPLE-521
Story: EXAMPLE-466

## Why

Manual JIRA worklog entry is time-consuming and often inaccurate. Developers want to automatically generate worklog entries based on their activity during the day, at end of day, or even retroactively. Currently `wt-jira log` only supports manual time entry.

## What Changes

### Core Features

- **Git-based activity detection**: Identifying work intervals based on commit timestamps
- **Retroactive worklog**: Collecting activity for a specified date
- **Multi-machine support**: Merging activity from multiple machines, machine ID tracking
- **Parallel work handling**: Distributing overlapping time intervals across multiple tasks
- **Gap analysis**: Displaying the difference from daily target hours
- **Structured comments**: Storing metadata in worklog comments (sessions, commit refs)
- **JIRA worklog API integration**: Automatic upload and update

### Reconstruct Mode (`--reconstruct`)

Multi-source activity reconstruction - not just from git commits:

| Source | Confidence | Description |
|--------|------------|-------------|
| Git commits | 1.0 | Most reliable |
| Git reflog | 0.9 | Deleted branches, uncommitted work |
| Zed editor | 0.85 | `~/.local/share/zed/db/0-stable/db.sqlite` |
| Claude CLI | 0.85 | `~/.claude/projects/` session timestamps |
| JetBrains IDE | 0.8 | `~/.config/JetBrains/*/options/recentProjects.xml` |
| VS Code | 0.75 | `~/.config/Code/User/globalStorage/state.vscdb` |

### Date Range Support

```bash
wt-jira auto --date 2026-01-15           # Single day
wt-jira auto --from 2026-01-13 --to 2026-01-17  # Date range
wt-jira auto --range last-week           # Last week (Mon-Fri)
wt-jira auto --range this-week           # This week (Mon-today)
```

### Machine Tracking

Multi-machine work support with duplicate prevention:

- Machine ID tracking (`hostname`)
- Local history: `~/.config/set-core/worklog-history.jsonl`
- Worklog ID saved to history for reliable updates
- Display: "✓ logged" or "✓ logged from <machine>"

### Time Caps

Preventing over-logging:

- **Daily cap**: 8 hours maximum total
- **Per-ticket cap**: 6 hours maximum per ticket
- Proportional reduction if limit would be exceeded

### Worklog Deduplication

Handling midnight-crossing sessions:

- ±1 day window search for existing worklogs
- Prevents creating duplicates
- `change_id` based matching in comments

## Impact

- Affected specs: `jira-worklog` (extended capability)
- Affected code: `bin/wt-jira` (`auto` command)
- New files: `~/.config/set-core/worklog-history.jsonl`
- New dependencies: None (uses existing git, sqlite3, jq)

## CLI Interface

```bash
# Basic usage
wt-jira auto                      # Today
wt-jira auto --date yesterday     # Yesterday
wt-jira auto --dry-run            # Preview, no upload

# Date range
wt-jira auto --from DATE --to DATE
wt-jira auto --range last-week|this-week

# Reconstruct mode
wt-jira auto --reconstruct        # Multi-source
wt-jira auto --reconstruct --timeline  # Timeline view

# Flags
-y, --yes                         # Skip confirmation
-v, --verbose                     # Detailed output
--dry-run                         # Show only, don't upload
```

## Configuration

```json
{
  "autoWorklog": {
    "dailyTarget": "8h",
    "minActivityGap": "30m",
    "roundTo": "15m",
    "reconstruct": {
      "enabled": true,
      "sources": ["git", "zed", "claude"],
      "minConfidence": 0.5
    }
  }
}
```

## Worklog Comment Format

```
---wt-auto---
change: feature-name
source: git|reconstruct:git,zed,claude
sessions:
  #1: 10:22-10:53 (30m) @ hostname [git] 2 activities
  #2: 13:51-14:23 (31m) @ hostname [zed] 1 activities

total: 1h 1m
---/wt-auto---
```

## Key Challenges

### 1. Multi-machine work
- Solution: Machine ID tracking, local history, worklog ID saving

### 2. Midnight-crossing sessions
- Solution: ±1 day window worklog search, `started` field set to session start

### 3. Over-logging prevention
- Solution: Daily 8h and per-ticket 6h cap, proportional reduction

### 4. Duplicates
- Solution: `change_id` matching in comments, worklog ID history

## History File Format

`~/.config/set-core/worklog-history.jsonl`:

```json
{"date":"2026-01-13","jira_key":"EXAMPLE-549","duration":14400,"machine":"hostname","submitted_at":"2026-01-13T16:20:00Z","sources":"git","change_id":"feature-name","worklog_id":"527960"}
```
