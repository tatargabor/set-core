# Design: Worktree Control Center

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     wt-status (CLI)                         │
│  - Collects worktree info from all projects                 │
│  - Detects Claude processes                                 │
│  - Outputs JSON for GUI consumption                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│               wt-control-gui (Python + PySide6)             │
│  - Cross-platform (Linux, macOS, Windows)                   │
│  - System tray icon with quick status                       │
│  - Always-on-top floating panel                             │
│  - Native look and feel                                     │
└─────────────────────────────────────────────────────────────┘
```

## Claude Process Detection

### Linux `/proc` Approach
```bash
# Find claude processes
pgrep -a claude

# Get working directory of PID
readlink /proc/$PID/cwd

# Check if process is waiting for input (interruptible sleep)
cat /proc/$PID/stat | awk '{print $3}'
# S = sleeping (waiting), R = running, D = disk sleep
```

### Process States
- **running**: Claude process exists, actively consuming CPU
- **waiting**: Claude process exists, sleeping (waiting for user input)
- **idle**: No Claude process in worktree
- **done**: No process, but recent git activity (commit in last 5 min)

## Data Model

```json
{
  "worktrees": [
    {
      "project": "aitools-specdriven",
      "change_id": "add-control-center",
      "path": "/home/tg/wt/aitools-specdriven/add-control-center",
      "branch": "change/add-control-center",
      "agent": {
        "status": "running|waiting|idle|done",
        "pid": 12345,
        "uptime_seconds": 3600,
        "last_activity": "2026-01-24T12:00:00Z"
      },
      "zed": {
        "window_id": "0x12345",
        "focused": false
      },
      "jira": {
        "key": "PROJ-123",
        "status": "In Progress"
      },
      "git": {
        "last_commit": "2026-01-24T11:30:00Z",
        "uncommitted_changes": true
      }
    }
  ],
  "summary": {
    "total": 5,
    "running": 2,
    "waiting": 1,
    "idle": 2
  }
}
```

## GUI Design (PySide6/Qt)

### Main Window
```
┌─ Worktree Control Center ──────────────────────── _ □ ✕ ─┐
│ ┌───────────────────────────────────────────────────────┐ │
│ │  PROJECT            CHANGE             STATUS    ⚙   │ │
│ ├───────────────────────────────────────────────────────┤ │
│ │  aitools-specdriven add-control-center ⚡ waiting     │ │
│ │  my-project       fix-login-bug      ● running      │ │
│ │  my-project       add-feature-x      ○ idle         │ │
│ │  mediapipe-python   experiment-1       ✓ done         │ │
│ └───────────────────────────────────────────────────────┘ │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────────────┐ │
│ │  + New  │ │  Focus  │ │  Close  │ │ ☐ Always on Top  │ │
│ └─────────┘ └─────────┘ └─────────┘ └──────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### System Tray
- Icon color indicates status (green/yellow/gray)
- Tooltip: "wt: 3 active | ●1 | ⚡1 | ○1"
- Left-click: Show/hide main window
- Right-click: Quick menu (New, Refresh, Quit)

### Status Icons
- `●` running (green) - agent actively working
- `⚡` waiting (yellow/orange) - agent needs input
- `○` idle (gray) - no agent running
- `✓` done (blue) - recently completed

### Features
- **Always on Top** toggle - keeps window above others
- **Auto-refresh** - polls wt-status every 2s
- **Double-click row** - focus that worktree's Zed window
- **Minimize to tray** - keeps running in background
- **Notifications** - desktop notification when agent finishes

## Cross-Platform Considerations

### Window Focus
| Platform | Method |
|----------|--------|
| Linux | `xdotool windowactivate` or D-Bus |
| macOS | `osascript` / AppleScript |
| Windows | `pywin32` or `ctypes` |

### Process Detection
| Platform | Method |
|----------|--------|
| Linux | `/proc/PID/cwd`, `pgrep` |
| macOS | `lsof -p PID`, `pgrep` |
| Windows | `psutil` library |

### System Tray
- PySide6 `QSystemTrayIcon` works on all platforms
- May need special handling for macOS menu bar

## Technology Stack

```
wt-control-gui/
├── main.py              # Entry point
├── control_center.py    # Main window
├── system_tray.py       # Tray icon
├── status_worker.py     # Background polling (QThread)
├── platform_utils.py    # Cross-platform helpers
├── resources/
│   ├── icon.png
│   ├── icon_running.png
│   ├── icon_waiting.png
│   └── icon_idle.png
└── requirements.txt     # PySide6, psutil
```

## Dependencies

```
PySide6>=6.5.0
psutil>=5.9.0
```

### Installation
```bash
pip install PySide6 psutil
# or
uv pip install PySide6 psutil
```

## Configuration

Add to `~/.config/set-core/config.json`:
```json
{
  "controlCenter": {
    "refreshInterval": 2,
    "autoFocus": false,
    "notifications": true,
    "miniPanelFormat": "wt: {total} | {running} running | {waiting} waiting"
  }
}
```

## Dependencies

- `pgrep` - process search (standard)
- `xdotool` - window management (already in install.sh)
- `jq` - JSON processing (already required)
- Optional: `notify-send` for desktop notifications

## Implementation Notes

### TUI Framework Options
1. **Pure bash + tput** - simple, no deps, limited features
2. **dialog/whiptail** - basic TUI, available on most systems
3. **gum** (charmbracelet) - modern, pretty, but external dep
4. **fzf** - could use for selection, already common

Recommendation: Start with pure bash + tput for maximum compatibility,
consider gum for better UX in v2.

### Refresh Strategy
- TUI: redraw on keypress or every N seconds
- Mini: use `watch` command or status bar integration
- JSON API: on-demand, no caching
