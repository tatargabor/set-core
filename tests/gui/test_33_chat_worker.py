"""
Chat Worker Tests - the team-enabled gate the chat poll loop depends on.

The team settings are stored per remote URL (`TeamSettingsDialog` writes
`team["projects"][remote_url]`, and `TeamMixin` reads them back the same
way), so the worker has to be given the remote URL beside the project name
to find its own switch.
"""

import json
from unittest.mock import MagicMock, patch


class _FakeConfig:
    """Minimal stand-in for `Config` — the worker only reads `config.team`."""

    def __init__(self, team):
        self.team = team


def _prepare_chat_env(tmp_path, monkeypatch):
    """Build the on-disk state the chat poll loop needs.

    Returns the project directory whose `.set-control` worktree holds the
    chat messages.
    """
    from gui.workers import chat as chat_module

    project_dir = tmp_path / "repo"
    control_dir = project_dir / ".set-control"
    (control_dir / "chat").mkdir(parents=True)
    (control_dir / "chat" / "messages.jsonl").write_text("")

    # Where the worker looks the project path up.
    (tmp_path / "projects.json").write_text(
        json.dumps({"projects": {"repo": {"path": str(project_dir)}}})
    )
    monkeypatch.setattr(chat_module, "CONFIG_DIR", tmp_path)
    return project_dir


def _fake_chat_run():
    """A `subprocess.run` stand-in that answers the chat read with one message."""

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = json.dumps([
            {
                "id": "1",
                "ts": "2026-02-08T10:00:00Z",
                "from": "peer@remote",
                "to": "me@host",
                "enc": "x",
                "nonce": "y",
            }
        ])
        result.stderr = ""
        return result

    return fake_run


def test_chat_worker_polls_when_team_enabled_for_remote_url(tmp_path, monkeypatch):
    """Team enabled under the remote-URL key must start the chat poll loop.

    The switch lives under the project's remote URL, not under its name, so a
    worker that looks it up by project name never finds it: the poll loop
    never runs, no message is ever fetched, and the unread badge stays at zero.
    """
    from gui.workers import chat as chat_module
    from gui.workers.chat import ChatWorker

    _prepare_chat_env(tmp_path, monkeypatch)

    remote_url = "https://github.com/org/repo.git"
    config = _FakeConfig({"projects": {remote_url: {"enabled": True}}})

    worker = ChatWorker(config)
    # The worker is told the project's name AND its remote URL — the key the
    # team settings are stored under.
    worker.current_project = "repo"
    worker.current_remote_url = remote_url

    emitted = []
    worker.messages_updated.connect(emitted.extend)

    def fake_sleep(ms):
        worker._running = False

    worker.msleep = fake_sleep

    with patch.object(chat_module.subprocess, "run", side_effect=_fake_chat_run()):
        worker.run()

    assert emitted, "chat poll loop never started: no messages were emitted"


def test_set_project_keeps_the_remote_url():
    """`set_project` must keep the remote URL beside the project name.

    The project name is what the chat CLI and projects.json are addressed by;
    the remote URL is what the team settings are stored under. Neither one
    stands in for the other.
    """
    from gui.workers.chat import ChatWorker

    worker = ChatWorker(_FakeConfig({"projects": {}}))
    worker.set_project("repo", "https://github.com/org/repo.git")

    assert worker.current_project == "repo"
    assert worker.current_remote_url == "https://github.com/org/repo.git"


def test_set_project_without_remote_url_leaves_it_empty():
    """No remote URL means no remote URL — the worker falls back to the name."""
    from gui.workers.chat import ChatWorker

    worker = ChatWorker(_FakeConfig({"projects": {}}))
    worker.set_project("repo")

    assert worker.current_project == "repo"
    assert worker.current_remote_url == ""


def test_control_center_hands_the_chat_worker_the_remote_url():
    """The Control Center must give the worker the key its settings live under.

    The team settings are keyed by the remote URL, so a Control Center that
    passes only the project name leaves the worker unable to find them.
    """
    from gui.control_center.mixins.team import TeamMixin
    from gui.workers.chat import ChatWorker

    class _Label:
        def setText(self, text):
            pass

        def setVisible(self, visible):
            pass

        def setStyleSheet(self, style):
            pass

        def setTextFormat(self, fmt):
            pass

    class _Host(TeamMixin):
        """The slice of the Control Center the chat worker is wired from."""

        def __init__(self, config, chat_worker):
            self.config = config
            self.chat_worker = chat_worker
            self.worktrees = [
                {
                    "project": "repo",
                    "remote_url": "https://github.com/org/repo.git",
                    "path": "/tmp/repo",
                }
            ]
            self.team_data = {}
            self.team_filter_state = {}
            self.team_label = _Label()

        def get_color(self, key):
            return "#000000"

    worker = ChatWorker(_FakeConfig({"projects": {}}))
    host = _Host(_FakeConfig({"projects": {}}), worker)

    host.update_team_display()

    assert host.chat_worker.current_project == "repo"
    assert host.chat_worker.current_remote_url == "https://github.com/org/repo.git"
