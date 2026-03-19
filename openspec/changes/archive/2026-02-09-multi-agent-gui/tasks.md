## 1. Multi-Agent Detection (wt-status)

- [x] 1.1 Refactor `detect_agent_status()` in `bin/wt-status` to return ALL matching PIDs per worktree instead of stopping at the first match. Return a newline-separated list of `status:pid` entries.
- [x] 1.2 For multi-PID worktrees, match N PIDs to N freshest session files by mtime order to determine per-agent status (running/waiting/compacting).
- [x] 1.3 Change `collect_worktree_status()` JSON output from `"agent": {status, skill}` to `"agents": [{pid, status, skill}, ...]`.
- [x] 1.4 Update `format_terminal()` and `format_compact()` to handle the new agents array format and update summary counts to reflect agent totals.
- [x] 1.5 Fix CWD prefix match bug in `detect_agents()`: use path-boundary match (`== "$wt_path" || == "$wt_path/"*`) instead of plain prefix match to prevent PID duplication across worktrees with similar path prefixes.

## 2. Per-PID Skill Tracking

- [x] 2.1 Update `bin/wt-skill-start` to write `.set-core/agents/<PPID>.skill` instead of (or in addition to) `.set-core/current_skill`. Create `.set-core/agents/` directory if needed.
- [x] 2.2 Update `get_current_skill()` in `bin/wt-status` to read from `.set-core/agents/<pid>.skill` for each detected PID, with `kill -0` stale check and cleanup.

## 3. GUI Status Worker Update

- [x] 3.1 Update the status worker (`gui/control_center/workers/`) to parse the new `agents` array from `wt-status --json` output instead of single `agent` object.

## 4. GUI Table Refactor

- [x] 4.1 Change table column count from 6 to 5. Update column headers from `["Project", "Change", "Status", "Skill", "Ctx%", "J"]` to `["Name", "Status", "Skill", "Ctx%", "Extra"]` in `main_window.py`.
- [x] 4.2 Update `_render_worktree_row()` in `table.py` to write branch/change label into column 0 (Name) instead of column 1, and adjust all subsequent column indices (Status→1, Skill→2, Ctx%→3, Extra→4).
- [x] 4.3 Update `_render_team_worktree_row()` to write `member: change_id` into column 0 (Name) and adjust column indices.
- [x] 4.4 Update project header `setSpan()` from 6 to 5 columns, and all hardcoded column count references.
- [x] 4.5 Implement multi-agent row rendering: when a worktree has N agents (N > 1), render N rows. First row has Name + first agent's Status/Skill + worktree Ctx% + Extra. Subsequent rows have empty Name, their own Status/Skill, empty Ctx%/Extra.
- [x] 4.6 Update `row_to_worktree` mapping to handle agent sub-rows (secondary agent rows should map back to the parent worktree for focus/context-menu actions).
- [x] 4.7 Update `running_rows` tracking and `update_pulse()` to work with multi-agent rows (each running agent row pulses independently).

## 5. GUI Compact Filter Update

- [x] 5.1 Update compact filter logic: show a worktree if ANY of its agents have non-idle status. When visible, show ALL agent rows for that worktree.

## 6. Row Count and Height Calculation

- [x] 6.1 Update `refresh_table_display()` total row count calculation to account for extra agent rows (sum of max(1, agent_count) per worktree instead of 1 per worktree).

## 8. Bug fixes

- [x] 8.1 Fix `wt-hook-stop` to refresh per-PID skill files in addition to legacy `current_skill`.
- [x] 8.2 Fix Ctx% to show per-agent: pass `agent_index` to `get_context_usage()`, match Nth agent to Nth-freshest session file. Show on all agent rows, not just primary.
- [x] 8.3 Fix `pgrep -x claude` skipping ancestors on macOS: replace with `ps -e` in `detect_agents()`, `wt-skill-start`, and `wt-hook-stop`.
- [x] 8.4 Fix `wt-skill-start` and `wt-hook-stop` PID resolution: walk ancestor tree and match against `ps -e` claude list (not `$PPID`).
- [x] 8.5 Add dedicated PID column (col 1): shows agent PID for each row, empty for idle/team rows. Layout: Name, PID, Status, Skill, Ctx%, Extra (6 columns).

## 7. Tests

- [x] 7.1 Add or update GUI tests in `tests/gui/` to verify the new 5-column layout (column headers, column count).
- [x] 7.2 Add test for multi-agent row rendering: mock a worktree with 2+ agents and verify correct row count and content.
- [x] 7.3 Update all test files from old `"agent": {}` format to new `"agents": []` format (test_05, test_08, test_09, test_11, test_12, test_16_compact_view, test_16_focus).
- [ ] 7.4 Run GUI tests: `PYTHONPATH=. python -m pytest tests/gui/ -v --tb=short`
