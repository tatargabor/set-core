# Fix Installation and Startup Issues

## Summary
Fix Python import errors, desktop entry, and improve robustness of the set-core installation and GUI startup process.

## Problem
1. **Relative import error**: `gui/main.py` uses relative imports (`from .control_center import ControlCenter`) but is executed as a script via `wt-control`, causing `ImportError: attempted relative import with no known parent package`
2. **Symlink path resolution**: The `wt-control` script resolves paths via symlinks but doesn't ensure Python can find the `gui` package
3. **Desktop entry broken**: `wt-control.desktop` uses direct `python3 gui/main.py` which has the same import issue
4. **No error handling for startup failures**: When the GUI fails to start, there's no diagnostic output to help users troubleshoot

## Solution
1. Fix `gui/main.py` to work both as a script (when run directly) and as a module (when imported)
2. Update `bin/wt-control` to run the GUI as a Python module with proper PYTHONPATH
3. Fix desktop entry to use proper launch mechanism with PYTHONPATH
4. Add startup validation and error reporting
5. Add install verification that tests GUI can actually start

## Scope
- `gui/main.py` - Fix import handling
- `bin/wt-control` - Improve launch mechanism
- `install.sh` - Fix desktop entry generation, add verification step

## Out of Scope
- macOS-specific fixes (will be addressed separately)
- GUI functionality changes
