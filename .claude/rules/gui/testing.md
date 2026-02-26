---
paths:
  - "gui/**"
  - "tests/gui/**"
---

# GUI Testing

When the user says "futtass tesztet", "run tests", "teljes teszt", or similar — run this:
```bash
PYTHONPATH=. python -m pytest tests/gui/ -v --tb=short
```

**Do NOT run tests automatically.** Only run tests when the user explicitly asks for it (e.g. "futtass tesztet", "run tests", "teljes teszt").

When adding new GUI functionality (button, menu, dialog, etc.), add a corresponding test in `tests/gui/test_XX_<feature>.py`. See existing tests for patterns:
- Read-only checks: `test_01_startup.py`, `test_02_window.py`
- Menu interception: `test_04_main_menu.py` (`_MenuCapture` pattern)
- Real git operations: `test_08_worktree_ops.py`
- Worktree + context menu: `test_11_ralph_loop.py`

Fixtures are in `tests/gui/conftest.py`. The `control_center` fixture is module-scoped — restore any state you mutate (re-show window after hide, etc).
