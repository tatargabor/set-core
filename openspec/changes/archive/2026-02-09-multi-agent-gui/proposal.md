## Why

Multiple Claude agents can run simultaneously on the same worktree (e.g., one exploring, one applying). The GUI currently assumes 1 agent per worktree — it only detects the first PID, shows a single status row, and the skill tracking file (`current_skill`) gets overwritten by the last writer. The table also wastes horizontal space with two columns (Project, Change/Branch) that are never filled simultaneously — Project is empty on worktree rows, and Change is empty on project headers.

## What Changes

- **`wt-status`**: Detect ALL Claude PIDs per worktree (not just the first). Return `agents: [...]` array instead of single `agent: {}` object. **BREAKING** JSON format change.
- **Skill tracking**: Switch from single `.set-core/current_skill` to per-PID files `.set-core/agents/<pid>.skill`. Clean up stale PIDs on read.
- **GUI table columns**: Merge Project + Branch into single "Name" column. Rename "J" column to "Extra" (shows Ralph indicator and similar per-worktree info).
- **GUI multi-agent rows**: Each agent gets its own row beneath its worktree row. Agent-only rows have empty Name column, but show their own Status, Skill, and Ctx%.
- **GUI compact filter**: Filter on agent-level (show all non-idle agents) instead of worktree-level.
- **Focus action**: Double-click / context menu "Focus" still opens the Zed window for the worktree (not individual agent terminals).

## Capabilities

### New Capabilities
- `multi-agent-detection`: Detecting and reporting multiple Claude agents per worktree, including per-PID skill tracking

### Modified Capabilities
- `control-center`: Table layout changes (column merge, multi-agent rows, column rename), compact filter now operates on agent rows

## Impact

- **`bin/wt-status`**: Breaking JSON output change (`agent` → `agents` array). All consumers must update.
- **`bin/wt-skill-start`**: Must write PID-specific skill files instead of single file.
- **GUI table mixin** (`gui/control_center/mixins/table.py`): Major refactor — row model changes from 1:1 worktree to 1:N agents per worktree.
- **GUI status worker**: Must parse new `agents` array format.
- **GUI compact filter**: Filter logic changes to agent-level granularity.
- **Tests**: Table-related GUI tests need updating for new column layout and multi-agent rows.
