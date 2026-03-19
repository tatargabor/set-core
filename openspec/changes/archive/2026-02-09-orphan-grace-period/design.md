## Context

The `cleanup_orphan_agents()` function in `bin/wt-status` currently kills "waiting" orphan agents immediately on first detection. The detection relies on `is_editor_open()` (osascript on macOS) and TTY checks. Transient failures in editor detection (osascript timing, window focus changes) cause false positive kills of legitimate agents.

`wt-status` is called by the GUI every ~2 seconds via refresh timer.

## Goals / Non-Goals

**Goals:**
- Eliminate false positive orphan kills caused by transient editor detection failures
- Kill genuine orphans automatically after a safe delay (15s + 3 consecutive detections)
- Minimal overhead — no new processes, no heavy I/O

**Non-Goals:**
- Changing the orphan detection criteria (TTY check, editor check logic)
- Changing the GUI orphan display or context menu behavior
- Adding user-configurable grace period settings

## Decisions

### Decision 1: Per-PID marker files in `.set-core/orphan-detect/`

Store orphan tracking state as one file per PID: `.set-core/orphan-detect/<pid>`

File content: `<first_seen_timestamp>:<count>`

Example: `.set-core/orphan-detect/12345` contains `1707400000:2`

**Why files over in-memory:**
- `wt-status` is a bash script invoked fresh each time (no persistent state)
- Files survive across invocations naturally
- Tiny files (< 30 bytes each), trivial I/O

**Why per-PID:**
- Each agent PID has independent tracking
- Easy cleanup — just `rm` the file when PID dies or resets

### Decision 2: Hybrid threshold — 3 consecutive + 15 seconds

Kill condition: `count >= 3 AND (now - first_seen) >= 15`

With ~2s GUI refresh cycles, 3 detections takes ~6 seconds minimum. The 15-second floor ensures even with rapid `wt-status` calls, agents survive at least 15 seconds.

**Reset behavior:**
- If an agent passes any safety check (editor open, TTY active, ralph loop, running/compacting status), delete its marker file → counter resets to 0
- This means one successful check cancels all previous orphan detections

### Decision 3: Stale marker cleanup

On each `cleanup_orphan_agents()` call, before processing agents, clean up marker files for PIDs that no longer exist (`kill -0 $pid` check). This prevents `.set-core/orphan-detect/` from accumulating dead files.

### Decision 4: Marker directory location

Use `$wt_path/.set-core/orphan-detect/` (per-worktree). This keeps tracking local to each worktree and is naturally cleaned up when a worktree is removed.

## Risks / Trade-offs

- [Genuine orphans live 15s longer] → Acceptable; 150MB for 15s is negligible
- [Marker file I/O on every refresh] → Trivial: read/write < 30 bytes per PID, only for "waiting" agents without editor/ralph
- [Race condition if two wt-status calls overlap] → Harmless; worst case the counter increments twice in one cycle, still needs 15s floor
