## Context

The Control Center GUI displays one row per worktree. Agent detection (`wt-status`) finds the first matching Claude PID per worktree and returns a single `agent: {status, skill}` object. Skill tracking uses a single file (`.set-core/current_skill`) that gets overwritten when multiple agents run on the same worktree.

Users commonly run 2+ Claude agents on the same worktree (e.g., one exploring, one applying). The GUI currently can't display this. The table also has two columns (Project, Change) that are never populated simultaneously — Project is always empty on worktree rows because the project name appears in the header row above.

## Goals / Non-Goals

**Goals:**
- Detect and display multiple Claude agents per worktree
- Each agent gets its own row with Status, Skill, and Ctx%
- Merge Project + Change columns into single "Name" column
- Rename "J" column to "Extra" (Ralph and similar indicators)
- Compact filter works at agent-level granularity

**Non-Goals:**
- PID-to-session-file mapping (no reliable way to match — Claude doesn't keep session files open)
- Per-agent Ctx% (would require PID→session mapping; show worktree-level Ctx% on first agent row only)
- Opening individual agent terminals from GUI (no stable TTY→window mapping)
- Coordinating or locking between agents (out of scope — agents remain independent)

## Decisions

### D1: `agents` array replaces `agent` object in wt-status JSON

**Decision:** Change `wt-status --json` output from `"agent": {status, skill}` to `"agents": [{pid, status, skill}, ...]`. Empty array when no agents running.

**Rationale:** The GUI needs per-agent data. An array naturally represents 0..N agents. Including PID allows the GUI to track agent identity across refreshes.

**Alternative considered:** Keep `agent` for backward compat and add `agents` alongside — rejected because it creates confusion and all consumers are internal.

### D2: Per-PID skill files in `.set-core/agents/`

**Decision:** Replace single `.set-core/current_skill` with `.set-core/agents/<pid>.skill` files. Each file has same format: `<skill-name>|<timestamp>`. On read, verify PID is alive (`kill -0 $pid`); delete stale files.

**Rationale:** Multiple agents need independent skill tracking. PID-based filenames provide natural namespacing without coordination. Stale cleanup is cheap (one `kill -0` per file).

**Alternative considered:** Single JSON file with PID→skill map — rejected because atomic writes are harder and the file becomes a contention point.

### D3: Merge Project + Change into "Name" column

**Decision:** Single column 0 "Name" instead of separate Project (col 0) and Change (col 1). Project header rows use it for project name (spanning all columns as before). Worktree rows use it for branch/change label (with ★ prefix for main repo). Team rows use it for `member: change_id`.

**Rationale:** Project column is always empty on worktree rows. Change column is always empty on project headers. Merging saves horizontal space for the same information. Column count goes from 6 to 5.

### D4: Rename "J" column to "Extra"

**Decision:** Rename column 5 (previously "J") to "Extra". Content: shows Ralph indicator (R button).

**Rationale:** "Extra" is generic enough to accommodate future additions.

### D5: Multi-agent rows are sub-rows with empty Name

**Decision:** When a worktree has N agents (N > 1), render N rows total. The first row has the Name (branch label) + first agent's Status/Skill + worktree-level Ctx% and Extra. Subsequent rows have empty Name, their own Status/Skill, and empty Ctx%/Extra.

**Rationale:** This preserves the worktree identity while showing each agent distinctly. Empty Name makes it visually clear these rows belong to the worktree above. Ctx% and Extra are worktree-level, not agent-level, so they appear once.

### D6: Status determination per-PID uses N freshest session files

**Decision:** For N agents on a worktree, take the N most recently modified session files. Match them to PIDs by mtime order (freshest session → first PID found). Determine running/waiting/compacting from each matched session file's mtime and last line.

**Rationale:** There's no direct PID→session mapping available. Mtime-based matching is a best-effort heuristic. In practice with 2-3 agents, it's accurate enough — the actively running agent will have the freshest session file.

### D7: Compact filter operates on agents, not worktrees

**Decision:** When compact filter is active, show any worktree that has at least one non-idle agent. Show ALL agents for that worktree (not just non-idle ones).

**Rationale:** If a worktree has one running and one waiting agent, the user wants to see both. Filtering individual agents within a worktree would be confusing.

## Risks / Trade-offs

- **Breaking JSON change** → All consumers of `wt-status --json` must update simultaneously. Mitigated by: all consumers are in this repo (GUI status worker, compact output formatter, terminal formatter).
- **Mtime-based session matching is heuristic** → Could mismatch PID to session when multiple agents write at similar times. Mitigated by: worst case is swapped status between agents on same worktree — not destructive, and self-corrects on next refresh.
- **Stale PID files accumulate** → If `wt-skill-start` writes but agent crashes before cleanup. Mitigated by: `kill -0` check on every read, stale files auto-cleaned.
- **Row count increases** → Multi-agent worktrees take more vertical space. Mitigated by: only affects worktrees with multiple agents, which is uncommon.
