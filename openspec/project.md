# Project Context

## Purpose
set-core - Git worktree management tools with Control Center GUI.
Manages multiple worktrees for parallel AI agent development.

## Tech Stack
- Bash scripts (bin/wt-*)
- Python 3 with PySide6 for GUI (gui/main.py)
- OpenSpec for spec-driven development

## Project Conventions

### Code Style
- Bash: Use `local` for function variables, error handling with `|| exit 1`
- Python: PySide6/Qt patterns, snake_case for functions

### Architecture Patterns
- CLI tools in `bin/` directory, symlinked to PATH via install.sh
- Common functions in `bin/wt-common.sh`
- GUI is a single-file PySide6 application

### Testing Strategy
- **GUI tests**: pytest-qt automated tests in `tests/gui/`
- Run all: `PYTHONPATH=. python -m pytest tests/gui/ -v --tb=short`
- 49 tests, ~28 seconds on macOS
- Module-scoped fixtures for performance (one ControlCenter per test file)
- Real git repos via `git_env` fixture (no mocks)
- `_MenuCapture` pattern for QMenu.exec() interception (PySide6 C++ slot)
- Screenshots on failure saved to `test-results/screenshots/`
- New GUI feature = new test file: `tests/gui/test_XX_<feature>.py`
- Debug logging to `/tmp/wt-*.log` when needed

### Git Workflow
- Branch naming: `change/<change-id>`
- Commit messages: imperative mood, Co-Authored-By for AI commits

## Development Commands

### Start/Restart GUI
```bash
# Stop existing GUI
pkill -9 -f "python.*gui/main.py" 2>/dev/null
sleep 1

# Start GUI and verify
python gui/main.py &
GUI_PID=$!
sleep 2
if ps -p $GUI_PID > /dev/null 2>&1; then
    echo "GUI running with PID $GUI_PID"
    xdotool search --name "Worktree" windowactivate 2>/dev/null
else
    echo "GUI failed to start"
fi
```

### Check if GUI is Running
```bash
ps aux | grep -E "python.*gui" | grep -v grep
```

### Check GUI Log
```bash
cat /tmp/wt-gui.log
```

## Domain Context
- Worktrees allow parallel development on multiple changes
- Each worktree has a change-id (e.g., `add-feature`, `fix-bug`)
- Configurable editor support with Claude Code integration

## Supported Editors
- **Zed** (recommended) - Native Claude Code ACP integration, keystroke launch
- **VS Code** - Claude Code extension + terminal integration
- **Cursor** - VS Code fork with Claude Code VSIX support
- **Windsurf** - Cascade AI with Claude API support

Configure with: `wt-config editor set <name>` or `wt-config editor list`

## Important Constraints
- Linux primary (uses xdotool, /proc filesystem for window focus)
- macOS supported (AppleScript for window management)
- Windows partial (no xdotool equivalent for window focus)
- Requires at least one supported editor with Claude Code

## External Dependencies
- One of: Zed, VS Code, Cursor, or Windsurf editor
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)
- xdotool (Linux, for window automation)
