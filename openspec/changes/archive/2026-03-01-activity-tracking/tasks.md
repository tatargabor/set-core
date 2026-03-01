## 1. Local Activity File & Hook

- [x] 1.1 Create `.claude/hooks/activity-track.sh` — hook script that parses PreToolUse Skill input, writes `.claude/activity.json` with skill/skill_args/updated_at, throttles at 10s, runs async
- [x] 1.2 Create or update `.claude/settings.json` — add PreToolUse hook entry for Skill tool pointing to `.claude/hooks/activity-track.sh`
- [x] 1.3 Test hook: simulate PreToolUse input by piping `{"tool_name":"Skill","tool_input":{"skill":"opsx:apply","args":"test-change"}}` to the hook script, verify `.claude/activity.json` contains `skill`, `skill_args`, `updated_at` fields with correct values
- [x] 1.4 Test throttling: run hook twice within 10s, compare `updated_at` timestamps — second run must NOT update the file (same mtime)

## 2. Extend wt-control-sync

- [x] 2.1 Modify `bin/wt-control-sync` — after extracting changes from `wt-status`, read `.claude/activity.json` from each worktree path and add `activity` block to the corresponding change entry in member JSON
- [x] 2.2 Handle missing activity file gracefully (set `activity: null` in change entry)
- [x] 2.3 Test: write a fake `.claude/activity.json` in a worktree with `{"skill":"opsx:apply","skill_args":"test","broadcast":"test msg","updated_at":"..."}`, run `wt-control-sync --json`, parse output and assert the change entry has `activity.skill == "opsx:apply"` and `activity.broadcast == "test msg"`
- [x] 2.4 Test missing: ensure a worktree WITHOUT `.claude/activity.json` has `activity: null` in the sync output (no crash, no missing key)

## 3. MCP Server: get_activity() Tool

- [x] 3.1 Add `get_activity(change_id: str = None)` tool to `mcp-server/wt_mcp_server.py` — reads `.claude/activity.json` from all local worktrees, returns consolidated activity list
- [x] 3.2 Add stale detection: mark entries with `updated_at` older than 5 minutes as stale
- [x] 3.3 Support optional `change_id` filter parameter
- [x] 3.4 Test: create `.claude/activity.json` in two different worktrees (different skills), call `get_activity()`, verify both entries returned with correct worktree paths and skill names
- [x] 3.5 Test stale: create activity file with `updated_at` 10 minutes ago, call `get_activity()`, verify entry has `stale: true`
- [x] 3.6 Test filter: create activity in worktree-A (change_id="feat-a") and worktree-B (change_id="feat-b"), call `get_activity(change_id="feat-a")`, verify only worktree-A returned

## 4. Skills: /context broadcast & /context status

- [x] 4.1 Create `.claude/commands/context/broadcast.md` — skill that writes broadcast message to `.claude/activity.json`, preserving other fields
- [x] 4.2 Create `.claude/commands/context/status.md` — skill that reads local activity files from all worktrees + team cache, displays consolidated view with relative timestamps and stale indicators
- [x] 4.3 Test broadcast: run the broadcast skill logic with "Working on OAuth", then read `.claude/activity.json` and assert `broadcast == "Working on OAuth"` and existing `skill` field is preserved
- [x] 4.4 Test broadcast overwrite: set broadcast "msg1", then "msg2", verify only "msg2" remains (not appended)
- [x] 4.5 Test status local: create activity files in 2 worktrees, run status skill logic, verify output contains both worktree paths with their respective skill/broadcast info
- [x] 4.6 Test status stale indicator: create activity with old timestamp, verify status output shows "(stale)" marker
- [x] 4.7 Test status empty: with no activity files anywhere, verify output shows "No active agents found"

## 5. GUI: Activity in Team Display

- [x] 5.1 Modify `gui/control_center/mixins/team.py` — pass activity data through to tooltips (show skill, broadcast in team row tooltip)
- [x] 5.2 Modify team details dialog — show active skill and broadcast message when activity data is present
- [x] 5.3 Add GUI test for activity tooltip display in `tests/gui/test_XX_activity.py`

## 6. Same-Machine Context Sharing (E2E)

- [x] 6.1 Two-worktree test: create a temporary worktree (wt-new), write `.claude/activity.json` in it with `{"skill":"opsx:apply","skill_args":"feat-x","broadcast":"Building feature X","updated_at":"<now>"}`. From the MAIN worktree, call MCP `get_activity()` and assert the temporary worktree's activity appears with correct skill and broadcast. Then close the temp worktree.
- [x] 6.2 Hook-to-MCP pipeline: from a worktree, pipe simulated PreToolUse JSON into `activity-track.sh`, then immediately call MCP `get_activity()` from another terminal/context, verify the written activity is returned within <1s
- [x] 6.3 Broadcast-to-status pipeline: from worktree-A run broadcast skill logic to write "Refactoring auth module", from worktree-B run status skill logic, verify worktree-A's broadcast "Refactoring auth module" appears in the status output with correct worktree path

## 7. Remote Context Sharing (Git Sync E2E)

- [x] 7.1 Sync round-trip test: write `.claude/activity.json` in a worktree with `skill=opsx:explore`, run `wt-control-sync --push`, then read `members/<member>.json` from `.wt-control/` and assert the change entry has `activity.skill == "opsx:explore"`
- [x] 7.2 Remote member activity: manually create a fake `members/fake-user@remote.json` in `.wt-control/` with an activity block, run `wt-control-sync --pull --json`, parse output and verify fake-user's activity data appears in the members array
- [x] 7.3 Status mixed sources: set up local activity (worktree file) + remote activity (member JSON from 7.2), run `/context status` logic, verify output shows BOTH local entry (no "(remote)" tag) and remote entry (with "(remote)" tag)

## 8. Edge Cases & Robustness

- [x] 8.1 Corrupt activity file: write invalid JSON to `.claude/activity.json`, verify `get_activity()` skips it without crashing, verify `wt-control-sync` sets `activity: null`
- [x] 8.2 Activity file with missing fields: write `{"skill":"opsx:apply"}` (no updated_at, no broadcast), verify all consumers handle missing optional fields gracefully
- [x] 8.3 Concurrent worktrees: create 3 temp worktrees each with different activity, verify `get_activity()` returns all 3, verify `/context status` shows all 3

## 9. macOS Testing

- [ ] 9.1 Hook `stat` compatibility: run `activity-track.sh` on macOS — verify `stat -f %m` fallback works (Linux uses `stat -c %Y`, macOS uses `stat -f %m`)
- [ ] 9.2 Hook `date` compatibility: verify `date -u +"%Y-%m-%dT%H:%M:%SZ"` produces correct ISO 8601 UTC timestamp on macOS
- [ ] 9.3 Hook `jq` availability: verify `jq` is available on macOS (installed via Homebrew or bundled), test full hook pipeline
- [ ] 9.4 GUI activity tooltip on macOS: open wt-control, create a worktree with activity, hover over team row to verify tooltip shows skill and broadcast
- [ ] 9.5 GUI team details dialog on macOS: right-click team worktree → Details, verify activity section renders correctly and dialog stays on top (WindowStaysOnTopHint)
- [ ] 9.6 MCP get_activity() on macOS: run `get_activity()` from Claude Code, verify worktrees with activity files are discovered and stale detection uses correct UTC time
- [ ] 9.7 Full pipeline on macOS: create worktree → trigger hook → verify activity appears in wt-control-sync output → verify MCP get_activity() returns it → verify GUI tooltip shows it
- [ ] 9.8 Cross-platform sync test: write activity on Linux, sync via git, read on macOS (or vice versa) — verify timestamps and data survive the round-trip
