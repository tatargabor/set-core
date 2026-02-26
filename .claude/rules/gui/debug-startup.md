---
paths:
  - "gui/**"
---

# GUI Debug Log

The GUI writes a rotating debug log to `/tmp/wt-control.log` (macOS/Linux) or `%TEMP%\wt-control.log` (Windows). **When debugging or fixing GUI bugs, always check this log first.** It contains:

- All user actions (`on_double_click`, `on_focus`, git ops) with parameters
- All platform calls (`find_window_by_title`, `focus_window`) with inputs and results
- All subprocess invocations with commands and return codes
- Exceptions caught by `@log_exceptions` in Qt signal handlers

```bash
# View the log
cat /tmp/wt-control.log

# Follow live
tail -f /tmp/wt-control.log
```

Rotation: 5 MB max, 3 backups. Setup: `gui/logging_setup.py`. Each module uses `logging.getLogger("wt-control.<module>")`.

# GUI Startup

To start the Control Center GUI:

```bash
# Recommended - uses wrapper script with correct paths
wt-control

# Or run directly with PYTHONPATH (from project root)
PYTHONPATH=. python gui/main.py
```

To kill and restart:
```bash
pkill -f "python.*gui/main.py" 2>/dev/null; sleep 1
wt-control &
```

## Troubleshooting

**Import errors**: If you see `ImportError: attempted relative import`, make sure PYTHONPATH includes the project root:
```bash
PYTHONPATH=/path/to/wt-tools python gui/main.py
```

**Qt/conda conflicts on Linux**: Set QT_PLUGIN_PATH:
```bash
QT_PLUGIN_PATH="$(python -c 'import PySide6; print(PySide6.__path__[0])')/Qt/plugins" wt-control
```
