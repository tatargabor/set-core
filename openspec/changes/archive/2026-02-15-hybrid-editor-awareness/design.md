## Context

After the `fix-editor-open-tty-fallback` change, `is_editor_open()` no longer uses the TTY fallback for IDE configs. However, the PPID chain still finds the terminal window (e.g., gnome-terminal) that hosts a terminal-based Claude session. This is correct — there IS a window — but the GUI doesn't distinguish between "agent in the configured IDE" and "agent in a plain terminal."

The wt-status JSON already provides all necessary data:
- `editor_open: true/false`
- `editor_type: "gnome-terminal-"` or `"zed"` or `null`
- `window_id: 77594625` or `null`

The GUI's `_get_editor_app_name()` returns the configured editor name (e.g., `"Zed"`). The configured editors are mapped in `SUPPORTED_EDITORS` as `name:command:type` where type is `ide` or `terminal`.

## Goals / Non-Goals

**Goals:**
- GUI visually distinguishes terminal-based agents from IDE-based agents
- Focus action works correctly for both IDE and terminal windows without wasted searches
- No wt-status changes required — pure GUI-side change

**Non-Goals:**
- Changing how wt-status reports `editor_open` or `editor_type` — those are correct
- Adding new wt-status fields
- Changing agent status determination (running/waiting/orphan)

## Decisions

### Decision 1: Detect "terminal agent" in the GUI by comparing editor_type

**Choice**: In `_render_worktree_row()`, compare the worktree's `editor_type` against a set of known IDE process names (`{"zed", "Zed", "code", "Code", "cursor", "Cursor", "windsurf", "Windsurf"}`). If `editor_type` is truthy but NOT in the IDE set, the agent is in a terminal.

**Alternative considered**: Read the set-core config and compare against the configured editor name. Rejected because the PPID chain returns the process name (e.g., `gnome-terminal-`), not the config name. A simple IDE-set check is more robust than trying to match config name ↔ process name.

### Decision 2: Terminal-waiting display — dimmed "waiting" instead of new status

**Choice**: When an agent is "waiting" and the `editor_type` is a terminal (not IDE), display the same `⚡ waiting` text but with muted/dimmed colors — similar to how idle worktrees are dimmed. No new status enum needed.

**Rationale**: A terminal-based waiting agent is still "waiting" — it's just less noteworthy than one in the IDE. Dimming communicates "this is expected, not requiring attention" without introducing a new concept.

The row background and text colors for terminal-waiting will reuse the existing `row_idle` / `text_muted` palette to signal "nothing to worry about."

### Decision 3: Focus short-circuit for terminal editor_type

**Choice**: In `on_focus()`, before the title-based search, check if the worktree's `editor_type` is in the known-IDE set. If NOT (i.e., it's a terminal), skip straight to the `window_id` fallback. This avoids the slow xdotool title search that will always fail for terminal windows.

**Fallback**: If `window_id` is also missing, fall through to the existing "open new editor" logic.

## Risks / Trade-offs

- **Risk**: Hardcoded IDE process name set may miss future editors.
  → **Mitigation**: The set maps to the same editors as `SUPPORTED_EDITORS` with `type=ide`. Easy to extend. Also, unrecognized process names default to the dimmed treatment, which is the safer visual.

- **Risk**: A terminal-based agent that needs attention (e.g., error state) may be overlooked because it's dimmed.
  → **Mitigation**: The "running" status still shows as green regardless of editor type. Only "waiting" is dimmed. Agents actively doing work remain prominent.
