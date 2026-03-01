## Context

The wt-tools system already has team-sync infrastructure: `wt-control-sync` pushes member status (worktree, branch, agent running/idle) to a git branch, and the GUI polls it every 30s. MCP exposes read-only queries for cross-agent visibility. However, this only tracks structural state (which worktrees exist), not behavioral state (what is the agent actually doing right now).

A previous `context-sharing` proposal designed a separate git-synced context system. We've decided to merge it into the existing team-sync infrastructure with a two-layer architecture: local files for same-machine agents (<100ms), git sync for remote machines (30-65s).

Current communication channels:
- `.claude/loop-state.json` — Ralph loop state (iteration, task, status)
- `.wt-control/members/*.json` — team member state (git-synced)
- `~/.cache/wt-tools/team_status.json` — GUI cache for MCP
- MCP tools — `get_ralph_status()`, `get_team_status()`, `list_worktrees()`

## Goals / Non-Goals

**Goals:**
- Same-machine agents can see each other's active skill + broadcast in <100ms via MCP
- Remote machines receive activity updates through existing team-sync polling (30-65s)
- Claude hook automatically tracks which skill is running without manual intervention
- `/context broadcast` lets agents announce intent in free-form text
- `/context status` shows consolidated view of all agents' activities
- Activity data appears in GUI tooltips and detail dialogs

**Non-Goals:**
- Real-time push notifications (polling is fine)
- Resource locking or mutual exclusion
- Cross-worktree prompting ("request from @peter")
- Test delegation between agents
- Modifying existing team-sync polling intervals

## Decisions

### 1. Local activity file: `.claude/activity.json`

Each worktree gets a local activity file at `.claude/activity.json`, written by a Claude hook.

**Why `.claude/` and not `.wt-control/`**: The `.claude/` directory is per-worktree and local. The MCP server already reads `.claude/loop-state.json` from each worktree, so the pattern is established. No git sync needed for same-machine reads.

**Alternative considered**: Writing directly to `~/.cache/wt-tools/activity/`. Rejected because activity is per-worktree, not per-machine, and `.claude/` is the natural home.

**Format:**
```json
{
  "skill": "opsx:apply",
  "skill_args": "add-oauth",
  "broadcast": "Adding Google OAuth provider",
  "modified_files": ["src/auth/oauth.py"],
  "updated_at": "2026-02-07T21:15:00Z"
}
```

### 2. Hook-based auto-tracking via PreToolUse

A project-level Claude hook (`.claude/hooks/activity-track.sh`) fires on `PreToolUse` for the `Skill` tool. It:
1. Parses the JSON input to extract skill name and args
2. Writes `.claude/activity.json` in the current worktree
3. Throttles: skips if last write was <10s ago
4. Runs async (background, non-blocking)

**Why PreToolUse on Skill**: This captures the moment a skill starts (opsx:apply, opsx:explore, etc.) which is the most meaningful activity signal.

**Alternative considered**: PostToolUse. Rejected because we want to track *start* of activity, not completion. Also considered tracking all tool uses — too noisy.

### 3. Member JSON extended with activity block

`wt-control-sync` reads `.claude/activity.json` from each local worktree and embeds it in `members/*.json`:

```json
{
  "name": "gabor@macbook",
  "changes": [
    {
      "id": "add-oauth",
      "remote_url": "...",
      "agent_status": "running",
      "activity": {
        "skill": "opsx:apply",
        "skill_args": "add-oauth",
        "broadcast": "Adding Google OAuth",
        "updated_at": "2026-02-07T21:15:00Z"
      }
    }
  ]
}
```

**Why inside `changes[]`**: Activity is per-change, not per-member. An agent works on one worktree at a time, so the activity belongs to the change entry.

### 4. MCP: new `get_activity()` tool

A new MCP tool `get_activity()` reads `.claude/activity.json` from all local worktrees. This is the **fast path** for same-machine agents — no git, no GUI polling, just file reads.

**Why new tool vs. extending `get_ralph_status()`**: Ralph status tracks loop state (iteration, stuck, done). Activity tracks skill/intent. Different concerns, different consumers.

### 5. Skills: `/context broadcast` and `/context status`

Two Claude slash commands:
- `/context broadcast "message"` — Writes broadcast to `.claude/activity.json`
- `/context status` — Reads all activity files (local + team cache), displays consolidated view

**Why not just use team-chat**: Broadcast is status (overwrites previous, visible to all), chat is messages (append-only, encrypted, targeted). Different use cases.

### 6. Hook configuration: project-level `.claude/settings.json`

The hook is configured in `.claude/settings.json` at the project root. This means:
- Any Claude Code session in this project automatically gets activity tracking
- No global config pollution
- Version-controlled with the project

## Risks / Trade-offs

**[Hook adds latency to every Skill invocation]** → Throttled (10s) and async (background). Measured overhead: <50ms for file existence check + timestamp comparison.

**[Activity file stale after agent exits]** → `updated_at` timestamp lets consumers judge freshness. Consider it stale if >5 min old. The `/context status` skill shows relative timestamps.

**[Concurrent writes to activity.json]** → Only one agent per worktree, so no real concurrency risk. If somehow two hooks fire simultaneously, last-write-wins is acceptable for a status file.

**[`.claude/settings.json` may conflict with user's existing hooks]** → The hook is additive (PreToolUse on Skill), unlikely to conflict. If `.claude/settings.json` already exists, merge the hooks array rather than overwriting.
