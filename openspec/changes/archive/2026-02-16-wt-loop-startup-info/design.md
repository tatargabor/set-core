## Context

`wt-loop` spawns a terminal and runs Claude Code in iterations. The startup banner (lines 576-581) shows worktree name, truncated task, and loop parameters. The terminal title uses ANSI escape `\033]0;...\007` which works cross-platform. On macOS the AppleScript block does not set an explicit tab title.

When running parallel benchmark instances (Run A baseline vs Run B with memory), both terminals show identical banners and titles because worktree name and task are the same.

## Goals / Non-Goals

**Goals:**
- Add `--label` flag so users can tag loop instances with an identifier
- Show richer context in the startup banner (path, branch, label, memory status, timestamp)
- Include label in terminal title for taskbar/tab differentiation
- Store label in `loop-state.json` for downstream consumers (MCP, `wt-loop status`)
- Set explicit macOS Terminal.app tab title via AppleScript

**Non-Goals:**
- GUI `start_ralph_loop_dialog` changes (separate change)
- Changing iteration progress output format
- Auto-detecting benchmark run type (A vs B)

## Decisions

### 1. `--label` as a free-text optional flag

**Choice**: `--label <text>` parsed alongside existing flags in `cmd_start`.

**Rationale**: A free-text label is the most flexible approach — works for benchmarks (`"Run A (baseline)"`), multi-project setups (`"frontend"`), or any user context. No auto-detection magic needed.

**Alternative considered**: Auto-detect from path (parent dir name) — too fragile and benchmark-specific.

### 2. Banner layout

**Choice**: Expand the box with conditional lines:

```
╔════════════════════════════════════════════════════════════════╗
║  Ralph Loop: <worktree_name>
║  Label: <label>                          ← only if --label set
║  Path: <wt_path>
║  Branch: <git branch>
║  Task: <full task, word-wrapped>
║  ──────────────────────────────────────────────────────────────
║  Mode: <perm_mode> | Max: <N> | Stall: <N> | Timeout: <N>m
║  Memory: active / inactive
║  Started: <YYYY-MM-DD HH:MM:SS>
╚════════════════════════════════════════════════════════════════╝
```

**Rationale**: Show everything useful at a glance. Task is NOT truncated (it's the startup, verbosity is fine). The separator line groups config vs. identity info. Memory status is detected via `set-memory health`.

### 3. Terminal title format

**Choice**: `Ralph: <worktree_name> (<label>) [iter/max]` — label in parens, omit parens if no label.

Examples:
- With label: `Ralph: craftbazaar (Run A) [3/30]`
- Without label: `Ralph: craftbazaar [3/30]` (unchanged)

### 4. macOS title fix

**Choice**: Add `set custom title of theTab to "$terminal_title"` in the AppleScript block after `do script`.

### 5. State file extension

**Choice**: Add `"label": "<text>"` (or `null` if not set) to `loop-state.json` in `init_loop_state`.

## Risks / Trade-offs

- **`set-memory health` call at startup**: Adds ~200ms to banner display. Acceptable for a one-time startup cost. → Run it once and cache the result.
- **Long labels**: Could break box alignment. → No box-width enforcement; the box grows. The `║` chars are decorative, not aligned to a fixed width currently anyway.
- **macOS AppleScript compatibility**: `set custom title` requires Terminal.app preferences to not override custom titles. → Document as a known limitation.
