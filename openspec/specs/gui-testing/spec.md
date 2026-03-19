## GUI Testing Spec

### Requirements

#### Test Infrastructure
- Tests use pytest + pytest-qt
- Test git repos are created as temp fixtures (bare + clone) per module
- Config isolation via WT_CONFIG_DIR environment variable
- Screenshot captured on any test failure to `test-results/screenshots/`
- Tests runnable with `pytest tests/gui/ -v`

#### Startup Tests
- App starts without exceptions
- Window is visible after show()
- Status label has text content
- Table exists with 6 columns: Project, Change, Status, Skill, Ctx%, J

#### Window Property Tests
- Window has `Qt.WindowStaysOnTopHint` flag (always on top)
- Window has `Qt.FramelessWindowHint` flag
- Window has `Qt.Tool` flag
- Window width matches config `window_width`
- Window title contains "Worktree Control Center"
- Window opacity matches config `opacity_default`
- Position save and restore works (move -> save -> new instance -> verify position)

#### Button Tests
- All buttons exist with correct labels: "+ New", "Work", "Add", "🖥️", "−", "≡"
- Filter button is checkable/toggleable
- Minimize button hides the window
- All buttons are enabled by default

#### Main Menu Tests
- ≡ button opens a QMenu
- Menu contains: Settings..., Minimize to Tray, Restart, Quit
- Settings... opens SettingsDialog
- Minimize to Tray hides window

#### Context Menu Tests
- Right-click on window opens context menu
- Context menu contains: + New Worktree, Work..., ↻ Refresh, Minimize to Tray, Restart, Quit
- Right-click on worktree row opens row context menu (requires worktree fixture)
- Row context menu contains: Focus Window, Open in Terminal, Copy Path, Git submenu, Ralph Loop submenu

#### System Tray Tests
- Tray icon is created and visible
- Tray tooltip is "Worktree Control Center"
- Tray has context menu with: Show, New Worktree, Settings..., Quit

#### Dialog Tests
- SettingsDialog opens and closes without error
- NewWorktreeDialog opens, shows project dropdown and change_id input
- NewWorktreeDialog preview updates when change_id is typed
- WorkDialog opens with Local and Remote tabs

#### Worktree Operation Tests (real git)
- `set-new` creates worktree (verify: git worktree list, directory exists, branch exists)
- Created worktree appears in GUI table after refresh
- Copy Path puts correct path in clipboard
- `set-close` removes worktree (verify: git worktree list, directory gone)

#### Table Tests
- Empty table renders without crash
- Table has correct column count and headers
- With worktree: project header row spans all columns
- Double-click on row doesn't crash

#### Theme Tests
- All 4 themes apply without error: light, dark, gray, high_contrast
- Theme switch updates window stylesheet
- Each theme sets correct background color in stylesheet

#### FeatureWorker Cache Rendering Tests
- Project header with populated feature cache renders without exceptions, Memory [M] and OpenSpec [O] buttons show correct colors
- Project header with empty feature cache shows gray "checking..." state for both buttons

#### Opaque Row Background Tests
- All row backgrounds are opaque (alpha == 255) after `update_status()` processes idle, running, and waiting rows

### Non-Requirements (out of scope)
- Team sync testing
- Chat functionality testing
- CI/CD pipeline configuration
- Visual regression / pixel-level comparison
- Performance testing
