## Context

The `wt-orchestrate` CLI is a ~1200-line bash script that manages multi-change orchestration. It writes state to `orchestration-state.json` (plan, per-change status, gate results, tokens, checkpoints) and logs to `.claude/orchestration.log`. The current `wt-orchestrate status` command is a one-shot CLI output using printf formatting.

Textual 6.11.0 and Rich 14.2.0 are already installed system-wide. The wt-tools project uses Python for the GUI (PySide6) and bash for CLI tools. This TUI bridges the two: a Python Textual app launched from the bash CLI.

The orchestration-state.json structure (top-level):
- `status`: running/checkpoint/paused/stopped/done/failed/time_limit
- `plan_version`, `created_at`, `brief_hash`
- `changes[]`: array of change objects (name, scope, status, tokens_used, test_result, review_result, build_result, gate_*_ms, verify_retry_count, worktree_path, ralph_pid, depends_on)
- `checkpoints[]`, `merge_queue[]`, `changes_since_checkpoint`
- `active_seconds`, `started_epoch`, `time_limit_secs`

Per-change statuses: pending, dispatched, running, paused, verifying, verify-failed, done, merged, failed, stalled, merge-blocked.

## Goals / Non-Goals

**Goals:**
- Live terminal dashboard for orchestration monitoring
- Works over SSH (no X11/Wayland required)
- Keyboard-driven checkpoint approval
- Zero new dependencies
- Single-file implementation (keep it simple)

**Non-Goals:**
- Starting/stopping/replanning orchestration (stays CLI-only)
- Editing plan or brief from TUI
- DAG visualization (the change table with depends_on column is sufficient; fancy DAG is for the long-term PySide6 orchestrator-gui change)
- Per-change drill-down dialogs

## Decisions

### D1: Single Python file, launched as subcommand

The TUI lives in `gui/tui/orchestrator_tui.py` and is launched via `wt-orchestrate tui` which calls `python3 gui/tui/orchestrator_tui.py "$STATE_FILENAME" "$LOG_FILE"`. Arguments are the state file and log file paths.

**Why not inline in bash?** Textual requires Python.
**Why not a separate `wt-orchestrate-tui` binary?** Keeping it as a subcommand is discoverable and consistent.
**Why gui/tui/ directory?** Separates terminal UI from PySide6 GUI, establishes a pattern for future TUI tools.

### D2: File-polling with Textual set_interval

Use `self.set_interval(3.0, self.refresh_data)` in the Textual App. The refresh method reads orchestration-state.json and the last N lines of the log file, then updates reactive data that triggers widget recomposition.

**Why not inotify/watchdog?** Adds complexity and a dependency. 3s polling on a <20KB JSON file is negligible. The orchestrator itself polls at 15s intervals, so 3s is responsive enough.

### D3: Layout structure

```
┌─ Header (Static) ────────────────────────────────────┐
│ ● RUNNING  Plan v6  3/10 done  1.4M tokens  43m/5h  │
├─ Change Table (DataTable) ───────────────────────────┤
│ Name          Status    Iter  Tokens  Gates          │
│ change-a      ✓ merged  8/30  12K     T✓ R✓ V✓ B✓   │
│ change-b      ● run     3/30  8K      T✓ R✓         │
│ change-c      ○ pend    -     -       -              │
├─ Log (RichLog) ──────────────────────────────────────┤
│ [12:01] [INFO] Gate test pass: change-a              │
│ [12:02] [ERROR] Gate build fail: change-b            │
├─ Footer (Static) ────────────────────────────────────┤
│ [a] Approve  [r] Refresh  [l] Toggle Log  [q] Quit  │
└──────────────────────────────────────────────────────┘
```

Three-panel vertical layout:
1. **Header**: Textual `Static` widget, updated on each refresh. Shows replan cycle when >0 (e.g., "Plan v7 (replan #5)"). Token total is cumulative: sum of current `tokens_used` + `prev_total_tokens` from prior replan cycles.
2. **Change Table**: Textual `DataTable` widget with sortable columns. Gate order follows execution pipeline: T/B/R/V (test, build, review, verify).
3. **Log Panel**: Textual `RichLog` widget for auto-scrolling log tail

The `l` key toggles between split view (table 60% + log 40%) and full log view.

### D4: Color mapping

Status colors using Rich markup:

| Status | Color | Icon |
|--------|-------|------|
| running | green | ● |
| verifying | cyan | ◎ |
| done | blue | ✓ |
| merged | bright_green | ✓✓ |
| pending | dim | ○ |
| dispatched | yellow | ▶ |
| failed | red bold | ✗ |
| verify-failed | red | ⚠ |
| stalled | magenta | ⚠ |
| merge-blocked | yellow | ⛔ |
| checkpoint | yellow bold | ⏸ |
| paused | dim | ⏸ |
| stopped | dim | ■ |
| time_limit | yellow | ⏱ |

Gate display order follows the execution pipeline (changed in `f02a385`):
Test → Build → Review → Verify. Display as `T✓ B✗ R- V-` etc.

### D5: Atomic checkpoint approval

Same mechanism as `wt-orchestrate approve`:
1. Read orchestration-state.json
2. Set `checkpoints[-1]["approved"] = True` and `approved_at`
3. Write to temp file in same directory
4. `os.rename()` temp to state file (atomic on same filesystem)

### D6: Log tail strategy

Read the last 200 lines of `.claude/orchestration.log` on each refresh. Track the file position (byte offset) between refreshes to only read new lines. Parse log level from `[INFO]`/`[WARN]`/`[ERROR]` markers and apply Rich styling.

### D7: Iteration progress from loop-state.json

For running changes, read `{worktree_path}/.claude/loop-state.json` to get current iteration (`iteration`) and max (`max_iterations`). Display as "5/30". If loop-state.json doesn't exist or isn't readable, show "-".

## Risks / Trade-offs

**[Terminal compatibility]** Textual requires a modern terminal (256-color, Unicode).
→ Mitigation: All target environments (local terminal, SSH) support this. Textual degrades gracefully.

**[Stale state on crash]** If the orchestrator crashes, state file shows "running" but nothing is happening.
→ Mitigation: The existing `cmd_status()` has stale detection (120s mtime check). The TUI can show the same warning.

**[File read race]** Reading state file while orchestrator is writing it could get partial JSON.
→ Mitigation: The orchestrator uses atomic writes (write temp + rename). `json.load()` on the renamed file is always complete. Catch JSONDecodeError and skip that refresh cycle.
