# Proposal: migrate-runtime-to-dot-wt

## Why

Runtime files (orchestration state, agent loop state, logs, caches) are scattered across `.claude/`, project root, `wt/orchestration/`, and `.wt-tools/`. This creates: (1) complex `.gitignore` rules with frequent merge conflicts in worktrees, (2) config mixed with ephemeral data in the same directories, (3) no clear convention for where new runtime features should write. The `sentinel-tab` change introduces `.wt/sentinel/` — this change migrates everything else.

## What Changes

- **Move orchestration runtime** from `wt/orchestration/` to `.wt/orchestration/` (state.json, events.jsonl, plans/, runs/, spec-coverage-report.md)
- **Move agent runtime** from `.claude/` to `.wt/agent/` (loop-state.json, activity.json, ralph-terminal.pid, sentinel.pid, scheduled_tasks.lock, reflection.md)
- **Move logs** from `.claude/orchestration.log` and `.claude/logs/` to `.wt/logs/`
- **Move caches** from `.wt-tools/` to `.wt/cache/` (codemaps, designs, skill invocations, memory commit tracker)
- **Move design-snapshot.md** from project root to `.wt/design-snapshot.md`
- **Update all references** — Python modules, bash scripts, skill prompts, wt-web endpoints
- **Remove `.wt-tools/` directory** convention (fully replaced by `.wt/cache/`)
- **Simplify `.gitignore`** — single `/.wt/` entry replaces many scattered patterns
- **BREAKING**: `orchestration-state.json` path changes — config constant `WtDirs.STATE_DIR` for all access

## Capabilities

### New Capabilities
- `runtime-directory-convention` — standardized `.wt/` directory layout for all runtime data

### Modified Capabilities
_(none — all changes are path migrations, no behavioral changes)_

## Dependencies

This change depends on `sentinel-tab` being deployed first (or simultaneously), as the sentinel CLI tools already write to `.wt/sentinel/` which establishes the convention.

## Impact

- **Python modules**: `lib/wt_orch/engine.py`, `lib/wt_orch/dispatcher.py`, `lib/wt_orch/verifier.py`, `lib/wt_orch/merger.py`, `lib/wt_orch/planner.py`, `lib/wt_orch/api.py`, `lib/wt_orch/websocket.py`, `lib/wt_orch/chat.py` — all paths that reference orchestration-state.json or events.jsonl
- **Bash scripts**: `bin/wt-sentinel`, `bin/wt-loop`, `bin/wt-new`, `bin/wt-merge` and others referencing `.claude/` runtime files
- **Skills/prompts**: any that reference `.claude/loop-state.json`, `orchestration-state.json`, etc.
- **wt-web**: frontend and backend paths for state file locations
- **wt-project init**: deploy script needs to create `.wt/` structure and update `.gitignore`
- **bootstrap_worktree**: needs to create `.wt/` in new worktrees
- **MCP server**: paths in `wt_mcp_server.py` that read state/events
