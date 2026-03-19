# Tasks: Worktree Control Center

## Phase 1: Core Status Command (CLI) ✓

- [x] 1.1 Create `bin/wt-status` script skeleton
- [x] 1.2 Implement worktree collection (reuse wt-list logic)
- [x] 1.3 Implement Claude process detection (`pgrep` + `/proc/PID/cwd`)
- [x] 1.4 Implement process state detection (running vs waiting)
- [x] 1.5 Implement `--json` output format
- [x] 1.6 Implement `--compact` one-liner output
- [x] 1.7 Add to `install.sh` scripts list

## Phase 2: Window Focus (CLI) ✓

- [x] 2.1 Implement Zed window discovery (`xdotool search`)
- [x] 2.2 Create `wt-focus <change-id>` command
- [x] 2.3 Match windows to worktrees by path in title

## Phase 3: GUI Application (Python + PySide6)

### 3.1 Project Setup
- [x] Create `gui/` directory structure
- [x] Create `requirements.txt` (PySide6, psutil)
- [x] Create `main.py` entry point
- [x] Add GUI launch script to `bin/wt-control-gui`

### 3.2 Main Window
- [x] Create main window with worktree table
- [x] Implement status icons (running/waiting/idle/done)
- [x] Add toolbar buttons (New, Work, Close) - Focus removed, double-click only
- [x] Frameless window, always on top, drag-to-move
- [x] Menu button (≡) with Minimize/Quit options
- [x] Auto-size window height to content (no scrollbars)
- [x] Position window at top-right corner (saved between sessions)
- [x] Window transparency (50% default, 100% on hover)
- [x] Display context usage % per worktree
- [x] JIRA button to open project/story in browser
- [x] Single instance enforcement (auto-kill old on restart)
- [x] Row blinking on running→waiting transition (until focused)

### 3.3 Background Status Polling
- [x] Create QThread worker for `wt-status --json` polling
- [x] Update table on status change
- [x] Handle errors gracefully

### 3.4 System Tray
- [x] Create system tray icon
- [x] Dynamic icon color based on status
- [x] Left-click: show/hide window
- [x] Right-click: context menu (New, Refresh, Quit)
- [x] Minimize to tray on close

### 3.5 Actions
- [x] Double-click row: focus Zed window
- [x] New button: spawn wt-new dialog
- [x] Work button: open worktree dialog (local + remote tabs, sorted by date)
- [x] Close button: confirm and close worktree
- [x] Refresh button: force status update

### 3.6 Cross-Platform Support
- [x] Linux: xdotool for window focus
- [ ] macOS: osascript for window focus
- [ ] Windows: pywin32 for window focus
- [x] Cross-platform process detection via psutil

### 3.7 Notifications
- [x] Desktop notification when agent status changes
- [ ] Configurable notification settings

## Phase 4: Installation & Polish

- [ ] 4.1 Add GUI to install.sh (pip install dependencies)
- [ ] 4.2 Create desktop entry (.desktop file) for Linux
- [ ] 4.3 Create app bundle for macOS
- [ ] 4.4 Update README with GUI docs
- [ ] 4.5 Add configuration options (refresh interval, auto-focus, etc.)

## Legacy (bash TUI - kept for fallback)

The bash-based `wt-control` TUI remains as a lightweight fallback for systems without GUI support.

## Pending Decisions

### Status naming (TODO)
Current names are unclear. Proposed rename:
- `running` → `working` (actively processing)
- `waiting` → `ready` (Claude open, waiting for user input)
- `idle` → `offline` (no Claude process)

Need to update: wt-status, gui/main.py (STATUS_ICONS, TRAY_COLORS)

## Recent Changes (uncommitted)

### Added Features
- [x] Row blinking when running→waiting (until focused)
- [x] Auto-register project when running wt-new in unregistered git repo
- [x] `--skip-fetch` option for wt-new
- [x] 10s timeout on git fetch
- [x] wt-focus pipeline bug fix
- [x] Status detection via session file mtime (<10s = running)
- [x] Focus button removed (double-click only)
- [x] Window position persistence (save/restore between sessions)
- [x] Window transparency (50% default, 100% on hover)
- [x] Frameless window with drag-to-move
- [x] Menu button (≡) for Minimize/Quit
- [x] Right-click context menu

### Known Issues (FIXED)
- [x] Ctx% disappears intermittently - fixed: now searches last 50KB for usage info
- [x] JIRA button in "J" column - opens project/story in browser if .set-core/jira.json exists

## Dependencies

- Phase 3 depends on Phase 1 (wt-status --json)
- Phase 4 depends on Phase 3
- GUI uses CLI tools as backend
