"""
GUI Test Fixtures - Isolated test environment with real git repos
"""

import json
import os
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def git_env(tmp_path_factory):
    """Create an isolated git environment with bare repo + clone + config.

    Module-scoped: created once per test file for speed.
    Sets SET_CONFIG_DIR so GUI uses temp config instead of ~/.config/set-core.
    """
    base = tmp_path_factory.mktemp("wt-gui-test")

    # Create bare repo (simulates remote origin)
    origin = base / "origin.git"
    subprocess.run(["git", "init", "--bare", str(origin)], capture_output=True, check=True)

    # Clone to create main project
    project = base / "test-project"
    subprocess.run(["git", "clone", str(origin), str(project)], capture_output=True, check=True)

    # Create initial commit (git needs at least one commit for worktrees)
    readme = project / "README.md"
    readme.write_text("# Test Project\n")
    git_env_vars = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@test.com",
        "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@test.com",
    }
    subprocess.run(["git", "-C", str(project), "add", "."], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(project), "commit", "-m", "Initial commit"],
        capture_output=True, check=True, env=git_env_vars,
    )

    # Detect default branch name and push
    branch_result = subprocess.run(
        ["git", "-C", str(project), "branch", "--show-current"],
        capture_output=True, text=True, check=True,
    )
    default_branch = branch_result.stdout.strip()
    subprocess.run(
        ["git", "-C", str(project), "push", "origin", default_branch],
        capture_output=True, check=True,
    )

    # Create config directory
    config_dir = base / "config"
    config_dir.mkdir()

    # Create projects.json
    projects_json = {
        "default": "test-project",
        "projects": {
            "test-project": {
                "path": str(project),
                "addedAt": datetime.now().isoformat(),
                "worktrees": {},
            }
        },
    }
    (config_dir / "projects.json").write_text(json.dumps(projects_json, indent=2))

    # Create empty gui-config.json (use defaults)
    (config_dir / "gui-config.json").write_text("{}")

    # Set environment variable for test isolation
    old_config_dir = os.environ.get("SET_CONFIG_DIR")
    os.environ["SET_CONFIG_DIR"] = str(config_dir)

    # We need to reload constants since CONFIG_DIR is set at import time
    import gui.constants
    original_config_dir = gui.constants.CONFIG_DIR
    original_config_file = gui.constants.CONFIG_FILE
    original_state_file = gui.constants.STATE_FILE
    original_session_file = gui.constants.CLAUDE_SESSION_FILE

    gui.constants.CONFIG_DIR = config_dir
    gui.constants.CONFIG_FILE = config_dir / "gui-config.json"
    gui.constants.STATE_FILE = config_dir / "gui-state.json"
    gui.constants.CLAUDE_SESSION_FILE = config_dir / "claude-session.json"

    yield {
        "base": base,
        "origin": origin,
        "project": project,
        "config_dir": config_dir,
    }

    # Restore
    gui.constants.CONFIG_DIR = original_config_dir
    gui.constants.CONFIG_FILE = original_config_file
    gui.constants.STATE_FILE = original_state_file
    gui.constants.CLAUDE_SESSION_FILE = original_session_file

    if old_config_dir is not None:
        os.environ["SET_CONFIG_DIR"] = old_config_dir
    else:
        os.environ.pop("SET_CONFIG_DIR", None)


@pytest.fixture(scope="module")
def control_center(git_env, qapp):
    """Create a ControlCenter window instance for testing.

    Module-scoped: one window shared across all tests in a file for speed.
    Tests that mutate state should restore it (re-show window, clear table, etc).
    Uses qapp (session-scoped) instead of qtbot (function-scoped).
    """
    # Import here to pick up the patched constants
    from gui.control_center.main_window import ControlCenter

    window = ControlCenter()
    window.show()
    qapp.processEvents()

    # Stop background workers and disconnect their signals to prevent
    # them from overwriting test data. Tests call update_status() directly.
    for attr, signal_name in [
        ("worker", "status_updated"),
        ("usage_worker", "usage_updated"),
        ("team_worker", "team_updated"),
        ("chat_worker", "unread_count_changed"),
        ("feature_worker", "features_updated"),
    ]:
        w = getattr(window, attr, None)
        if w:
            # Disconnect signal first so queued emissions don't fire
            sig = getattr(w, signal_name, None)
            if sig:
                try:
                    sig.disconnect()
                except RuntimeError:
                    pass
            w._running = False
            w.quit()
            w.wait(1000)

    # Flush any pending events from worker signals
    qapp.processEvents()

    yield window

    _cleanup_window(window)


def _cleanup_window(window):
    """Stop all workers, timers, tray, and hide the window."""
    # Stop all timers first (they may trigger worker interactions)
    for attr in ("blink_timer", "pulse_timer", "chat_blink_timer"):
        timer = getattr(window, attr, None)
        if timer:
            timer.stop()

    # Signal all workers to stop first (parallel signal)
    workers = []
    for attr in ("worker", "usage_worker", "team_worker", "chat_worker"):
        w = getattr(window, attr, None)
        if w:
            if hasattr(w, "stop"):
                w.stop()
            w._running = False
            w.quit()
            workers.append(w)

    # Then wait briefly for all to finish, terminate stragglers
    for w in workers:
        if not w.wait(500):
            w.terminate()
            w.wait(200)

    # Hide tray icon explicitly (closeEvent is overridden to minimize-to-tray)
    if hasattr(window, 'tray'):
        window.tray.hide()
        window.tray.setVisible(False)

    window.hide()


# --- Screenshot on failure ---

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture screenshot when a test fails."""
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        window = item.funcargs.get("control_center")
        if window:
            screenshot_dir = Path("test-results/screenshots")
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{item.name}_{timestamp}.png"
            window.grab().save(str(screenshot_dir / filename))
