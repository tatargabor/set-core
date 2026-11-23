## 1. Reader check (precondition)

- [x] 1.1 Grep every reader of `.set/activity.json` and `.set/agents/*.skill`: only `api/helpers.py` (worktree enrichment for the orchestration worktree and session routes), `mcp-server/set_mcp_server.py` (`get_activity`), `bin/set-control-sync` and `bin/set-status` — all orchestration-era or git-bus. The fleet (`lib/set_orch/fleet/`, `web/src/**/Fleet*`) reads neither

## 2. Hooks (done 2026-11-23)

- [x] 2.1 `bin/set-deploy-hooks`: drop `set-hook-skill`, `set-hook-activity`, `set-hook-stop` from the base set
- [x] 2.2 Strip them (and `.claude/hooks/activity-track.sh`) on every run, in every event array; a canonical file carrying one is not left alone
- [x] 2.3 `tests/unit/test_deploy_hooks_hook_diet.py` — 3 of 4 red on the reverted script (the fourth, idempotence, holds either way); `test_wave_board.py` deploy test updated
- [ ] 2.4 Roll out: `set-project init` per registered project (dry-run first, diff-check the hand-authored files)
- [ ] 2.5 After 2.4, remove `bin/set-hook-{skill,activity,stop}` and their `install.sh` entries

## 3. Git bus (not started)

- [ ] 3.1 Remove the git-bus MCP tools (`send_message`, `get_inbox`, `get_activity`, `get_team_status`, `get_ralph_status`, `get_worktree_tasks`, `list_worktrees`) and the `set-control*` bins — BREAKING; measure callers first
