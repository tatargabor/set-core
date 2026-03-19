# Proposal: migrate-runtime-to-dot-wt

## Why

Runtime files (orchestration state, agent loop state, logs, caches, sentinel data) are scattered across `.claude/`, project root, `wt/orchestration/`, and `.set-core/`. This creates: (1) complex `.gitignore` rules with frequent merge conflicts in worktrees, (2) config mixed with ephemeral data in the same directories, (3) no clear convention for where new runtime features should write, (4) worktree deletion after merge destroys valuable debug/audit data.

The memory system and metrics already use `~/.local/share/set-core/<project>/` — this change migrates all shared runtime data there, keeping only minimal per-agent ephemeral files in the worktree.

## What Changes

### Shared runtime → `~/.local/share/set-core/<project>/`
- **Move orchestration runtime** — state.json, events.jsonl, plans/, runs/, digest/, report.html, audit logs
- **Move sentinel runtime** — events.jsonl, findings.json, status.json, inbox.jsonl, archive/ (currently in `.wt/sentinel/`)
- **Move logs** — orchestration.log, archived ralph-iter-*.log, change-specific log archives
- **Move caches** — codemaps, designs, skill invocations, memory commit tracker, credentials
- **Move screenshots** — smoke and e2e test evidence
- **Move design-snapshot.md** — fetched design tokens
- **Remove `.set-core/` directory** convention (fully replaced)
- **Simplify `.gitignore`** — remove many scattered runtime patterns

### Per-worktree agent ephemeral → `<worktree>/.set/`
- **loop-state.json, activity.json, ralph-terminal.pid** — agent writes these during execution, ephemeral
- **logs/ralph-iter-*.log** — current run iteration logs (archived to shared location on merge)

### Worktree retention
- **Stop deleting worktrees after merge** — keep them for debugging, log inspection, merge conflict resolution
- **Configurable retention** via `orchestration.yaml` (`worktree_retention: keep | auto-clean-after-Nd | delete-on-merge`)
- **Explicit cleanup only** via `wt-close` (manual) or `wt-cleanup --older-than Nd` (manual/cron)

## Capabilities

### New Capabilities
- `runtime-directory-convention` — standardized `~/.local/share/set-core/<project>/` layout for shared runtime data
- `worktree-retention` — configurable worktree lifecycle after merge

### Modified Capabilities
_(none — all changes are path migrations and lifecycle changes, no behavioral changes)_

## Dependencies

This change depends on `sentinel-tab` being deployed first (sentinel already writes to `.wt/sentinel/` which will be migrated).

## Impact

- **Python modules**: All `lib/set_orch/` modules referencing state files, events, logs, sentinel paths — engine.py, dispatcher.py, verifier.py, merger.py, planner.py, api.py, websocket.py, chat.py, events.py, state.py, logging_config.py, watchdog.py, loop_state.py, auditor.py, reporter.py, digest.py, milestone.py
- **Sentinel modules**: `lib/set_orch/sentinel/wt_dir.py`, events.py, findings.py, status.py, inbox.py, rotation.py — migrate from `.wt/sentinel/` to `~/.local/share/`
- **Bash scripts**: `bin/set-sentinel`, `bin/wt-loop`, `bin/wt-new`, `bin/wt-merge`, `bin/wt-close`, `lib/orchestration/*.sh`, `lib/loop/state.sh`, `lib/design/bridge.sh`, `mcp-server/statusline.sh`
- **Hooks**: `.claude/hooks/activity-track.sh`
- **GUI**: `gui/control_center/mixins/handlers.py`, `gui/control_center/mixins/table.py`
- **MCP server**: `mcp-server/wt_mcp_server.py`
- **Skills/prompts**: sentinel command, design-bridge rule, any referencing `.claude/` runtime files
- **Deploy**: `lib/project/deploy.sh`, `bootstrap_worktree()` in dispatcher.py
- **Merger**: `cleanup_worktree()` → conditional based on retention config
