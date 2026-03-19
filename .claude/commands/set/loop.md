# Start Ralph Loop

Start an autonomous Ralph loop for the given change-id and task.

**Arguments:** `<change-id> "<task description>" [--max N] [--done criteria]`

## Instructions

Start the Ralph loop and then monitor its progress until completion.

### Step 1: Start the loop

```bash
set-loop start $ARGUMENTS
```

### Step 2: Monitor progress

After starting, run the monitor command to track progress until the loop completes:

```bash
set-loop monitor <change-id> --interval 30
```

This will output iteration updates and report the final status (done/stuck/stopped).

## Options

- `--max N` - Maximum iterations (default: 10)
- `--done criteria` - Done detection: `tasks`, `openspec`, or `manual` (default: tasks, auto-detects openspec)
- `--capacity-limit PCT` - Stop if capacity exceeds threshold (default: 80%)
- `--stall-threshold N` - Stall after N commit-less iterations (default: 2)
- `--iteration-timeout N` - Per-iteration timeout in minutes (default: 45)
- `--permission-mode MODE` - Claude permission mode: `auto-accept`, `allowedTools`, `plan` (default: config)
- `--label TEXT` - Label for this loop instance (shown in banner and terminal title)
- `--force` - Force start even with incompatible permission mode (e.g. plan)

## Examples

```bash
# Basic usage - implement feature per tasks.md
set-loop start add-auth "Implement authentication per spec"

# With options
set-loop start add-api "Build REST API endpoints" --max 15 --done tasks

# Manual done criteria (you mark it done)
set-loop start refactor "Refactor UserService" --done manual
```

## What happens

1. A new terminal window opens with the Ralph loop
2. Claude Code runs iteratively on the task
3. After each iteration, checks if tasks.md is complete
4. Loop ends when done criteria met OR max iterations reached
5. Notification sent when complete or stuck
6. The monitor command reports progress back to you

## Manual commands

```bash
set-loop status <change-id>   # Check current status
set-loop list                 # List all active loops
set-loop stop <change-id>     # Stop a running loop
set-loop history <change-id>  # View iteration history
set-loop monitor <change-id>  # Monitor until complete
```
