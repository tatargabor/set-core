## Context

The set-core Control Center manages multiple git worktrees with Claude Code agents. The `wt-status` script polls every ~2 seconds, detecting claude processes via `ps -e` and matching their CWD to worktree paths. Status is determined from session file mtime (< 10s = running, else waiting). The GUI renders this data in a table with PID, status, and skill columns.

The core problem: when Zed editor is closed, the Claude terminal processes spawned inside it survive as detached processes. `wt-status` sees them as alive (`kill -0` succeeds) and reports "waiting" status. The GUI shows these as permanent yellow rows. There is no link between "editor is open" and "agents should exist."

Current stack: bash scripts (`wt-status`, `wt-work`, `wt-new`), Python GUI (PySide6), platform abstraction layer (`gui/platform/`).

## Goals / Non-Goals

**Goals:**
- Detect when editor window is closed and agents are orphaned
- Automatically kill orphan agents (no editor, no Ralph loop)
- Accurate status reporting: no permanent "waiting" rows for dead sessions
- Add `editor_open` field to `wt-status` JSON output
- Verify and fix Zed open/close stability on Linux
- Integration tests for orphan detection and status accuracy

**Non-Goals:**
- Rewriting the agent detection mechanism (ps + CWD matching works)
- Adding new UI features beyond orphan handling
- macOS/Windows implementation of orphan cleanup (stubs only)
- Changing the 2-second refresh interval
- Modifying how Claude Code is launched (keystroke method stays)

## Decisions

### Decision 1: Editor window detection in wt-status (bash side)

**Choice:** Add `is_editor_open()` function to `wt-status` that checks for editor windows per worktree.

**Implementation:** Two-tier detection:
1. **Primary (xdotool):** `xdotool search --name "$wt_basename"` — fast, single syscall, returns window IDs. Filter by editor window class if needed.
2. **Fallback (/proc scan):** If xdotool unavailable, scan `/proc/*/cmdline` for editor processes whose CWD matches the worktree. Slower but no dependency.

**Why in wt-status, not GUI:** Status accuracy is the source's responsibility. The GUI should only render what it receives. This keeps the architecture clean and allows CLI users (`wt-status --json`) to also benefit.

**Performance:** `xdotool search` takes ~5-15ms per call. With 10 worktrees, adds ~50-150ms to the status cycle. Acceptable within the 2s refresh window. The `/proc` fallback is ~100ms total (one scan, match all).

**Alternative considered:** GUI-side detection using Python `subprocess.run(["xdotool", ...])`. Rejected because it splits status logic between bash and Python, making it harder to reason about.

### Decision 2: Orphan kill policy

**Choice:** Automatic kill. When `wt-status` detects agents running in a worktree with no editor window and no active Ralph loop, it sends SIGTERM to those processes.

**Safety guards:**
- Never kill agents in worktrees with active Ralph loops (`loop-state.json` status = "running")
- Never kill agents that are "running" status (session mtime < 10s) — they might be mid-task in a headless terminal
- Only kill "waiting" agents (idle > 10s) with no editor — these are definitively orphaned
- Log kills to stderr for debugging

**Alternative considered:** "Orphan" status badge, user decides. Rejected because user asked for automatic cleanup, and a manual step defeats the purpose of autonomous operation via wt-loop.

### Decision 3: Status transition for orphans

**Choice:** No new "orphan" status in the JSON output. Instead, orphan agents are killed immediately and removed. The next status cycle shows them gone. This keeps the status model simple (running/compacting/waiting/idle).

**Rationale:** An intermediate "orphan" status adds complexity to the GUI renderer for a state that lasts at most one refresh cycle (2s). The kill happens in `cleanup_orphan_agents()` within the same status collection pass, before the JSON is emitted.

### Decision 4: `editor_open` field

**Choice:** Add `"editor_open": true/false` to each worktree JSON entry. Determined by `is_editor_open()`.

**Use cases:**
- GUI can dim/gray worktrees with no editor (purely visual, no logic)
- CLI consumers can filter/report editor state
- Debugging aid: "why was my agent killed?" — check editor_open

### Decision 5: Integration test approach

**Choice:** Tests use the existing `conftest.py` pattern (module-scoped `control_center` fixture) and feed synthetic status data. For orphan testing, fork real dummy processes to simulate agents, verify PID detection, then confirm cleanup removes them.

**No real Zed launching in tests.** Window detection is tested by mocking `subprocess.run` for xdotool calls. Process lifecycle is tested with real `os.fork()` + `os.kill()`.

## Risks / Trade-offs

- **[xdotool not installed on some Linux distros]** → Fallback to /proc scan. Install.sh already recommends xdotool; add it as explicit dependency.
- **[False positive: editor closed briefly during restart]** → The 10s "running" guard prevents killing active agents. Only "waiting" (idle > 10s) agents with no editor are killed. If Zed restarts within 10s, agent survives.
- **[Race condition: agent spawning while status cycle runs]** → Agent appears in next cycle. No data loss — at worst one extra refresh before it shows up.
- **[wt-status becomes slower with window checks]** → Measured: xdotool adds ~5-15ms per worktree. With 20 worktrees, ~100-300ms. Still well within 2s budget.
- **[Killing wrong process]** → We only kill PIDs that match `ps -e -o comm= | awk '$2 == "claude"'` AND have CWD in the worktree. Double verification prevents accidental kills.
