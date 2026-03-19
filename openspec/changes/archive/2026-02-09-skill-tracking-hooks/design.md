## Context

The GUI Control Center has a "Skill" column that shows which Claude skill is active per worktree. Currently this is always empty because:
1. `wt-skill-start` is not in the install script list (not on PATH after install)
2. Only the `wt` SKILL.md calls `wt-skill-start`; opsx skills don't
3. The 30-minute TTL in `wt-status` means even a single registration expires during long sessions
4. There is no mechanism to refresh the timestamp while an agent is working

The existing data flow: `wt-skill-start` writes `name|timestamp` to `.set-core/current_skill` → `wt-status --json` reads it (30min TTL) → GUI displays in Skill column.

## Goals / Non-Goals

**Goals:**
- Skill column shows the active skill accurately for the entire agent session
- Works automatically via Claude Code hooks — no manual intervention
- Hooks deployed to all wt-managed projects during install and `wt-add`
- Hook scripts update automatically via `git pull` (symlinked from PATH)
- Zero token consumption, minimal latency

**Non-Goals:**
- Cross-machine context sharing (future: context-sharing change)
- Changing the `.set-core/current_skill` file format
- Changing the `wt-status` TTL logic (30min stays)
- GUI changes (the column already works, just needs data)

## Decisions

### 1. Use Claude Code `Stop` hook for timestamp refresh

The `Stop` event fires after every Claude response. This is ideal because:
- Fires once per turn (not per tool call like PreToolUse)
- Guarantees freshness as long as agent is interacting
- Zero token cost (PostToolUse/Stop stdout is not injected into context)

**Alternatives considered:**
- PreToolUse on every tool: Too frequent, unnecessary overhead
- PreToolUse on Skill tool only: Fires only at session start, same TTL problem
- Periodic background script: Complex, needs process management

### 2. Separate concerns: SKILL.md sets name, hook refreshes timestamp

`wt-skill-start <name>` in SKILL.md sets the skill name + initial timestamp.
`wt-hook-stop` only refreshes the timestamp if a skill file already exists.
This avoids the hook needing to know which skill is running.

### 3. Hook script referenced by name (PATH), not absolute path

Project `.claude/settings.json` contains `"command": "wt-hook-stop"`.
Since `wt-hook-stop` is symlinked to PATH via `install_scripts()`:
- `git pull` on set-core automatically updates the script
- No need to re-run install for script content changes
- Only need to re-run install when adding new hook event types

### 4. Graceful fallback when set-core not installed

Hook script exits 0 immediately if `wt-hook-stop` is not on PATH.
This allows `.claude/settings.json` to be committed to project repos —
team members without set-core get zero impact.

### 5. install_project_hooks() merges into existing settings.json

Uses `jq` to merge hooks config into existing `.claude/settings.json`
without overwriting other settings (statusLine, permissions, etc.).
Same pattern as existing `install_mcp_statusline()`.

### 6. wt-add deploys hooks on project registration

When a new project is added via `wt-add`, hooks are deployed to its
`.claude/settings.json` automatically. No separate install step needed.

## Risks / Trade-offs

- [Hook not firing if Claude Code changes hook API] → Low risk; hooks are stable. Script is trivial to update.
- [settings.json merge conflicts with user edits] → jq merge preserves existing keys. Backup created before modify.
- [wt-hook-stop on PATH but project not wt-managed] → Graceful: checks for `.set-core/` dir before writing.
