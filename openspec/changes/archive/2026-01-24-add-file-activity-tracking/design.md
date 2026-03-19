# Design: File Activity Tracking via Claude Hooks

## Context

`wt-jira auto` currently calculates work time based on git commits and IDE/editor logs. With the Claude Code hooks system, we can directly log Claude agent file operations, providing more accurate and context-rich data.

## Goals / Non-Goals

### Goals
- Logging Claude agent file operations (Read/Edit/Write)
- Simple setup (hook configuration)
- Integration with reconstruct mode
- File-level activity review

### Non-Goals
- Tracking non-Claude file operations (IDE log handles that)
- Real-time dashboard
- Bash tool tracking (would be too noisy)

## Decisions

### Decision 1: PostToolUse Hook

**What:** Using the Claude Code `PostToolUse` hook to monitor Read/Edit/Write tools.

**Why:**
- Built-in mechanism, no extra daemon
- Exact context (tool name, input, session)
- Only successful operations are logged (PostToolUse)

**Hook config:**
```json
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

### Decision 2: Environment Variables

**What:** The hook uses environment variables provided by Claude.

**Available variables:**
- `$TOOL_NAME` - The tool name (Read, Edit, Write)
- `$TOOL_INPUT` - JSON string with tool input (contains file_path)
- `$CWD` - Current working directory
- `$SESSION_ID` - Claude session identifier (if available)

**Why:** No need for complex parsing, Claude passes the necessary data.

### Decision 3: JSONL Activity Log

**What:** Every event is a JSON line in the `~/.config/set-core/claude-activity.jsonl` file.

**Format:**
```json
{"ts":"2026-01-21T10:15:32Z","tool":"Edit","path":"/home/user/src/api.ts","cwd":"/home/user/project","project":"my-project","change_id":"add-feature"}
```

**Fields:**
- `ts` - ISO timestamp
- `tool` - Read/Edit/Write
- `path` - Absolute file path
- `cwd` - Working directory (project root)
- `project` - Detected project name
- `change_id` - Detected change/branch name

**Why:**
- Append-only, fast writes
- Easily processable with jq
- Greppable

### Decision 4: Project/Change Detection

**What:** Inferring project and change_id from CWD.

**Algorithm:**
1. Find git root from CWD
2. If worktree, infer change_id from branch name
3. Project name = git root dirname

**Why:** Consistent with existing reconstruct logic.

### Decision 5: Confidence Level

**What:** Claude activity confidence = 0.85 (same as Claude session confidence).

**Why:**
- Higher than IDE logs (0.75-0.8), because we know it was active work
- Lower than git commit (1.0), because not every Read is relevant

### Decision 6: Ignore Patterns

**What:** Filtering out certain paths (node_modules, .git, etc.)

**Implementation:**
```bash
# wt-activity-log script
case "$file_path" in
  */node_modules/*|*/.git/*|*.log) exit 0 ;;
esac
```

**Why:** Reduces noise, reading framework files is not relevant.

## Risks / Trade-offs

### Risk 1: Hook doesn't execute

**Problem:** If the hook is broken or times out, nothing is logged.

**Mitigation:**
- Simple, fast script (< 100ms)
- Async write (doesn't block Claude)
- Fallback: Claude session log still works

### Risk 2: Tool input parsing

**Problem:** The `$TOOL_INPUT` JSON format may change.

**Mitigation:**
- Robust parsing with jq
- Fallback to default values

### Risk 3: Log size

**Problem:** Many Read operations = large log.

**Mitigation:**
- Optional: only log Edit/Write
- Daily/weekly cleanup

## Migration Plan

1. Create new `bin/wt-activity` script
2. `wt-activity setup` command for hook configuration
3. Extend `wt-jira auto --reconstruct` with claude-activity source
4. Documentation

No breaking changes, opt-in feature.

## Open Questions

1. **Log Reads?** - Yes by default, but should it be configurable?
2. **Bash tool?** - Should we log Bash tool calls? (Probably too noisy)
3. **Log retention?** - How long to keep? (Default: 30 days?)
