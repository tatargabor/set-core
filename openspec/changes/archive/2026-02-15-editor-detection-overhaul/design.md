## Context

The current system detects editor windows by searching X11 window classes (xdotool --class) and matching window titles against worktree basenames. This works for known IDE classes but breaks when: (a) Zed title contains a filename ("main.py — set-core" vs "^set-core$"), (b) terminals are used instead of IDEs, (c) the editor isn't in the SUPPORTED_EDITORS list. The `wt-work` command has ~160 lines of keystroke injection logic that's fragile and often fails. The `--dangerously-skip-permissions` flag is hardcoded everywhere.

## Goals / Non-Goals

**Goals:**
- Editor-agnostic detection via PPID chain walking (works for any windowed process)
- Support terminal emulators as first-class editors
- Configurable Claude permission mode
- Simplified wt-work (no keystroke injection)
- Works on Linux and macOS

**Non-Goals:**
- Windows support
- tmux/screen detached session management
- Auto-starting Claude Code in editors (user responsibility)
- Changing Ralph loop architecture (only adding permission flag)

## Decisions

### D1: PPID chain walking for detection + focus

**Decision**: Walk the agent's PPID chain until finding a process that owns an X11/macOS window. This gives us both `editor_open` (boolean) and `window_id` (for focus) in one operation.

**Algorithm** (Linux):
```
agent_pid → ppid → ppid → ... until:
  xdotool search --pid $current_pid returns a window
  → editor_open=true, window_id=<found>
  OR pid==1 (init)
  → check TTY: if agent has TTY != "?" → remote session (not orphan, no window)
  → if TTY == "?" → true orphan
```

**Algorithm** (macOS):
```
agent_pid → ppid → ppid → ... until:
  lsappinfo/CGWindowListCopyWindowInfo finds window for pid
  → editor_open=true, window_id=<found>
  OR pid==1
  → same TTY fallback
```

**Why over alternatives:**
- vs class+title matching: works for ANY editor/terminal without maintaining a class list
- vs PID file: no stale state, no "user reopened editor" problem
- vs /proc CWD scan: CWD doesn't reliably point to worktree (Zed CWD = $HOME)

**Trade-off**: Requires agent to be running to detect editor. When no agent exists, we can't use PPID chain → fall back to "idle" (not "idle (IDE)"). This is acceptable since "idle (IDE)" is cosmetic.

### D2: wt-status returns window_id in JSON

**Decision**: Add `window_id` field to each worktree in wt-status JSON output.

```json
{
  "editor_open": true,
  "window_id": "96469037",
  "editor_type": "zed"
}
```

The `window_id` is discovered during PPID chain walking. The GUI `on_focus()` uses it directly: `xdotool windowactivate <window_id>` — no need for a second window search.

**editor_type**: The process name of the window-owning ancestor (e.g., "zed-editor", "gnome-terminal-server", "kitty"). Used for display only.

### D3: Remove keystroke injection, simplify wt-work

**Decision**: `wt-work` does exactly two things:
1. Open the editor/terminal: `<editor-cli> <worktree-path>`
2. Print a tip: "Start Claude Code: Ctrl+Shift+L (Zed) or run `claude` in terminal"

No background subshells, no sleep/retry, no xdotool key injection.

For terminal editors, `wt-work` opens the terminal at the worktree directory:
```bash
kitty --directory "$wt_path"
alacritty --working-directory "$wt_path"
gnome-terminal -- bash -c "cd '$wt_path' && exec bash"
wezterm start --cwd "$wt_path"
```

### D4: Claude permission mode config

**Decision**: New config field `claude.permission_mode` with three values:

| Mode | CLI flag | Description |
|------|----------|-------------|
| `auto-accept` | `--dangerously-skip-permissions` | Full autonomy (current default) |
| `plan` | _(no flag)_ | Interactive, user approves each action |
| `allowedTools` | `--allowedTools "Edit,Write,Bash,Read,Glob,Grep"` | Selective permissions |

**Config schema**:
```json
{
  "editor": { "name": "zed" },
  "claude": { "permission_mode": "auto-accept" }
}
```

**Usage points**:
- `wt-work` (terminal launch tip)
- `wt-loop` (claude invocation): defaults to config value, overridable with `--permission-mode <mode>`
- `install.sh` / `wt-new` (Zed tasks.json, VSCode tasks.json generation)

**Ralph loop**: `--permission-mode plan` is incompatible with Ralph (can't approve interactively). `wt-loop` will warn and refuse to start with `plan` mode unless `--force` is given.

### D5: Extended editor list with terminal emulators

**Decision**: SUPPORTED_EDITORS grows to include terminals:

```bash
SUPPORTED_EDITORS=(
    # IDEs (project-based window)
    "zed:zed:ide"
    "vscode:code:ide"
    "cursor:cursor:ide"
    "windsurf:windsurf:ide"
    # Terminals (directory-based)
    "kitty:kitty:terminal"
    "alacritty:alacritty:terminal"
    "wezterm:wezterm:terminal"
    "gnome-terminal:gnome-terminal:terminal"
    "konsole:konsole:terminal"
    "iterm2:open -a iTerm:terminal"
    "terminal-app:open -a Terminal:terminal"
)
```

The third field changes from `window_class:claude_method` to a simple `type` (ide/terminal). Window class is no longer needed for detection (PPID chain handles it). The `claude_method` (keystroke/terminal) is removed since we no longer auto-launch.

Each terminal type has a known CLI for opening at a directory — this is used by `wt-work`.

### D6: Install and Settings UI editor selection

**Decision**:
- `install.sh`: After basic setup, prompt user to choose editor from detected options + "other terminal". Also prompt for Claude permission mode.
- Settings dialog (GUI): Dropdown for editor selection + radio buttons for permission mode. Changes saved to config.json immediately.

### D7: Focus action (on_focus / double-click)

**Decision**: Two-tier approach:
1. If `window_id` is available in the worktree status data → `xdotool windowactivate` (Linux) / AppleScript (macOS)
2. If no `window_id` (no agent running) → use editor CLI: `zed <path>` / `code <path>` / `kitty --directory <path>` etc.

This eliminates the current find_window_by_title entirely for the focus path.

### D8: Close Editor uses window_id

**Decision**: `on_close_editor()` in the GUI follows the same pattern as focus:
1. If `window_id` is available → `xdotool windowclose` (Linux) / AppleScript close (macOS)
2. If no `window_id` → silent no-op (can't close what we can't find)

This replaces the current `find_window_by_title` + `close_window` approach.

### D9: Ralph terminal focus via loop PID

**Decision**: The "Focus Ralph" context menu action currently searches for window title `"Ralph: {change_id}"`. Replace with: read the Ralph loop PID from `loop-state.json`, use PPID chain walking to find the terminal window owning that process, then focus it. Falls back to opening the Ralph log file if no window found.

### D10: Deprecate bin/wt-focus script

**Decision**: The 460-line `bin/wt-focus` bash script uses class+title-based window search (the old approach). Instead of rewriting it for PPID chain, deprecate it:
- `wt-focus <change-id>` becomes a thin wrapper: calls the editor CLI (`zed <path>`, `code <path>`, etc.) which handles focus-or-open.
- The complex window enumeration logic is removed.
- The GUI never calls wt-focus (uses window_id directly).

### D11: macOS bash PID → window lookup

**Decision**: In the bash `wt-status`, macOS window lookup by PID uses AppleScript:
```bash
osascript -e '
  tell application "System Events"
    set targetProc to first process whose unix id is '$ancestor_pid'
    if (count of windows of targetProc) > 0 then
      return name of targetProc & "|" & (id of first window of targetProc)
    end if
  end tell
' 2>/dev/null
```
This returns the process name and window ID. If no windows, it returns nothing and we continue up the chain. Performance note: each `osascript` call is ~50-100ms, but the PPID chain is typically 3-5 levels, so total is 150-500ms — acceptable since wt-status runs every few seconds.

## Risks / Trade-offs

- **[PPID chain depth]** On some systems, the chain could be long (agent → node → bash → bash → terminal). Mitigate: cap at 20 levels, which is more than enough.
- **[No agent = no detection]** When no agent is running, PPID chain can't determine if editor is open. The "idle (IDE)" display becomes just "idle". This is acceptable — the distinction is cosmetic and the agent-centric model is more accurate.
- **[macOS window lookup by PID]** macOS doesn't have xdotool. Bash wt-status uses AppleScript (`every process whose unix id is <pid>`, check window count). Python GUI layer extends existing AppleScript to find windows by PID. Each osascript call is ~50-100ms; acceptable for 3-5 level PPID chains.
- **[Permission mode migration]** Existing installs have hardcoded `--dangerously-skip-permissions` in Zed/VSCode tasks.json. Install/upgrade needs to offer to update these. Mitigate: `wt-config` can re-generate task files.
- **[Terminal tab ambiguity]** A terminal may have multiple tabs. The PPID chain finds the terminal window, not the specific tab. Focus will bring the window to front, but may not switch to the right tab. Acceptable — same as IDE behavior.
- **[PPID chain performance in wt-status]** Each agent needs a PPID chain walk with xdotool/osascript calls. Typically 3-5 levels × 1-2 agents = 3-10 subprocess calls per refresh. Acceptable since wt-status runs every few seconds. If it becomes a bottleneck, cache window_id for agents whose PID hasn't changed.
- **[wt-focus deprecation]** The 460-line wt-focus script is replaced by a thin editor CLI wrapper. Users who scripted against wt-focus will need to update. Mitigate: keep the command but simplify its internals.

## Open Questions

- Should `wt-work` for terminals auto-run `claude` as the shell command (e.g., `kitty --directory <path> claude ...`), or just open a terminal and let the user start Claude? Current design: user starts Claude. Could be a config option later.
