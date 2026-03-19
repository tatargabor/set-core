## Context

The Control Center GUI has 123 action functions across 16 files with zero logging. When UI actions fail silently (e.g., subprocess calls with DEVNULL, AppleScript errors swallowed by try/except, Qt signal-slot exception suppression), there is no diagnostic trail. The codebase already uses Python's standard library extensively, making `logging` the natural choice.

Current GUI file structure:
- `gui/main.py` — entry point
- `gui/control_center/main_window.py` — main window setup
- `gui/control_center/mixins/handlers.py` — user action handlers (34 functions)
- `gui/control_center/mixins/menus.py` — menu actions (15 functions)
- `gui/control_center/mixins/table.py` — table rendering
- `gui/platform/macos.py`, `linux.py`, `windows.py` — platform abstraction (18 functions)
- `gui/workers/*.py` — background polling threads (4 workers)
- `gui/dialogs/*.py` — dialog windows with subprocess calls

## Goals / Non-Goals

**Goals:**
- Persistent rotating log file at a known location for post-mortem debugging
- Log all user-triggered UI actions with their key parameters and outcomes
- Log all platform calls (window find/focus/close) with inputs and results
- Log all subprocess invocations with command, return code, and stderr
- Catch and log exceptions that Qt signal-slot would otherwise swallow silently

**Non-Goals:**
- Structured logging (JSON lines) — plain text is easier for humans to read
- Log viewer in the GUI — users share the log file directly
- Configurable log levels via settings UI — hardcoded DEBUG level to /tmp is sufficient
- Logging in test code
- Performance metrics or timing data

## Decisions

### 1. Python standard `logging` with `RotatingFileHandler`

Use `logging.getLogger("wt-control")` hierarchy with per-module child loggers.

**Why**: stdlib, no dependencies, built-in rotation, well-understood format. Alternative considered: custom file writer — rejected because it would need to reimplement rotation, formatting, and thread safety that `logging` provides for free.

### 2. Log file location: platform temp directory

- macOS/Linux: `/tmp/wt-control.log`
- Windows: `%TEMP%\wt-control.log`

Use `tempfile.gettempdir()` for cross-platform resolution. Rotation: 5 MB max, keep 3 backup files (15 MB total worst case).

**Why**: `/tmp` survives app restarts but not reboots (on macOS), is always writable, and users can find it easily. Alternative considered: `~/.config/set-core/logs/` — rejected because config dir is for persistent data, not ephemeral debug logs.

### 3. Centralized setup in `gui/logging_setup.py`

One function `setup_logging()` called from `gui/main.py` at startup. Each module gets its own logger:

```python
# In each gui module:
import logging
logger = logging.getLogger("wt-control.handlers")
```

### 4. Three logging tiers

| Tier | Level | What | Example |
|------|-------|------|---------|
| User actions | INFO | Every on_* handler entry, menu action, dialog open | `on_double_click: project=mediapipe change=master` |
| Platform/subprocess | DEBUG | Window find/focus, subprocess calls, AppleScript results | `find_window_by_title: title='foo' app='Zed' → None` |
| Errors | ERROR | Caught exceptions, subprocess failures, worker errors | `focus_window failed: AppleScript error -1` |

### 5. Exception wrapper for Qt signal handlers

Qt swallows exceptions in signal-connected slots. Wrap critical handlers with a decorator that catches and logs exceptions:

```python
def log_exceptions(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.exception(f"Exception in {func.__name__}")
            raise
    return wrapper
```

Apply to all `on_*` handlers in `handlers.py`.

## Risks / Trade-offs

- **[Disk usage]** → 5 MB × 4 files = 20 MB max via RotatingFileHandler. Negligible.
- **[Performance]** → Logging adds microseconds per call. GUI actions are human-speed, so no impact.
- **[Sensitive data in logs]** → Log file paths and command args only, never file contents or credentials. Session keys are already handled in separate config, not passed through logged functions.
- **[Log file permissions on /tmp]** → On shared systems, `/tmp/wt-control.log` is world-readable. Acceptable for debug logs containing only paths and UI actions.
