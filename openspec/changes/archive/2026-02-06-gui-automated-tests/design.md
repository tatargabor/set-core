## Architecture

### Test Isolation

```
Production:                          Test:
~/.config/set-core/                  /tmp/pytest-XXXX/config/
├── projects.json                    ├── projects.json (generated)
├── gui-config.json                  ├── gui-config.json (defaults)
└── gui-position.json                └── gui-position.json (empty)

WT_CONFIG_DIR not set                WT_CONFIG_DIR=/tmp/pytest-XXXX/config
→ constants.py uses ~/.config/...    → constants.py uses temp dir
```

### Fixture Hierarchy

```
Session scope (once per test run):
  qapp_cls_scoped        ← QApplication (from pytest-qt, reused)

Module scope (once per test file):
  git_env                ← Bare repo + clone + projects.json
    ├── /tmp/.../origin.git       (bare remote)
    ├── /tmp/.../test-project     (cloned main repo, initial commit)
    └── /tmp/.../config/          (WT_CONFIG_DIR)
        └── projects.json

Function scope (per test):
  control_center         ← ControlCenter window instance
    ├── Uses git_env config
    ├── show() called
    └── close() on teardown
```

### CONFIG_DIR Change

Current (`gui/constants.py:25`):
```python
CONFIG_DIR = Path.home() / ".config" / "set-core"
```

New:
```python
import os
_config_override = os.environ.get("WT_CONFIG_DIR")
CONFIG_DIR = Path(_config_override) if _config_override else Path.home() / ".config" / "set-core"
```

Same pattern for `main_window.py:50` POSITION_FILE - derive from CONFIG_DIR instead of hardcoding.

### Screenshot on Failure

Using pytest's `pytest_runtest_makereport` hook:

```python
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        window = item.funcargs.get("control_center")
        if window:
            path = f"test-results/screenshots/{item.name}.png"
            window.grab().save(path)
```

Screenshots saved to `test-results/screenshots/` (gitignored).

### Dialog Testing Strategy

Modeless dialogs can be tested directly. Modal dialogs (exec()) need a QTimer trick:

```python
def test_settings_dialog(control_center, qtbot):
    # Schedule dialog interaction before opening (modal blocks)
    def interact_with_dialog():
        dialog = control_center.findChild(SettingsDialog)
        if dialog:
            assert dialog.isVisible()
            dialog.reject()  # Close it

    QTimer.singleShot(500, interact_with_dialog)
    control_center.open_settings()
```

### Worktree Operations Testing

For `test_08_worktree_ops.py`, we bypass the modal dialogs and call the underlying commands directly, then verify the GUI reflects the changes:

```
1. subprocess.run(["wt-new", "-p", project, change_id, "--skip-open", "--no-openspec"])
2. control_center.refresh_status()
3. qtbot.waitUntil(lambda: change_id in table_text(), timeout=10000)
4. Assert row exists with correct data
```

This tests the real git operations AND the GUI display, without fighting modal dialog interaction.

### Test Naming Convention

Files are numbered (`test_01_`, `test_02_`, etc.) to ensure a logical execution order when reading output, but tests within each file are independent and can run in any order.
