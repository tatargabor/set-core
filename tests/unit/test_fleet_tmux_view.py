"""tmux_view against a REAL tmux server — the measurement, not a mock of it.

The two directions that matter: a process inside a pane is found, and a process
that merely CARRIES a tmux environment (inherited, then escaped) is not. The
second is the claim the module refuses to take on trust.
"""

import os
import shutil
import subprocess
import time

import pytest

from set_orch.fleet import idle_close, tmux_view

pytestmark = pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux not installed")


@pytest.fixture
def server(tmp_path):
    sock = str(tmp_path / "t.sock")
    subprocess.run(["tmux", "-S", sock, "new-session", "-d", "-s", "probe", "sleep 120"], check=True)
    try:
        out = subprocess.run(
            ["tmux", "-S", sock, "display-message", "-p", "-t", "probe", "#{pane_pid} #{pane_id}"],
            check=True, capture_output=True, text=True,
        ).stdout.split()
        yield sock, int(out[0]), out[1]
    finally:
        subprocess.run(["tmux", "-S", sock, "kill-server"], capture_output=True)


def test_a_process_inside_a_pane_is_found(server):
    sock, pane_pid, pane_id = server
    pane = tmux_view.pane_of(pane_pid)
    assert pane is not None
    assert pane.socket == sock
    assert pane.pane == pane_id
    assert tmux_view.session_of(pane) == "probe"
    argv = tmux_view.viewer_argv(pane)
    assert argv is not None and argv[1:] == ["-S", sock, "attach-session", "-t", pane_id]
    assert os.path.isfile(argv[0])


def test_an_inherited_environment_alone_is_not_believed(server):
    sock, pane_pid, pane_id = server
    # Same TMUX/TMUX_PANE a pane would carry, but started OUTSIDE the server.
    server_pid = int(subprocess.run(
        ["tmux", "-S", sock, "display-message", "-p", "#{pid}"],
        check=True, capture_output=True, text=True).stdout.strip())
    env = {**os.environ, "TMUX": f"{sock},{server_pid},0", "TMUX_PANE": pane_id}
    impostor = subprocess.Popen(["sleep", "30"], env=env)
    try:
        time.sleep(0.1)
        assert tmux_view.pane_of(impostor.pid) is None
    finally:
        impostor.kill()
        impostor.wait()


def test_no_tmux_environment_is_none():
    env = {k: v for k, v in os.environ.items() if not k.startswith("TMUX")}
    p = subprocess.Popen(["sleep", "30"], env=env)
    try:
        time.sleep(0.1)
        assert tmux_view.pane_of(p.pid) is None
    finally:
        p.kill()
        p.wait()


def test_idle_close_does_not_count_a_viewer_as_reachable():
    agent = {
        "kind": "interactive", "last_human_input_seconds": 10 * 86400,
        "terminal_label": "tmux-desk", "tmux": {"pane": "%0", "viewer": "tmux-desk"},
    }
    assert idle_close.classify(agent, 3600) == idle_close.UNREACHABLE


def test_recover_refuses_a_scope_the_owner_holds(monkeypatch):
    from set_orch.fleet import owner as owner_mod

    class Held:
        unit = "set-agent-parent.scope"
        label = "parent"

    class FakeOwner:
        def owned(self):
            return [Held()]

    from set_orch.fleet.scopes import _systemd as backend

    stopped = []
    # Patched on the BACKEND: `scopes` delegates at access time, and patching the
    # package would pin the delegate as a real attribute on undo, breaking every
    # later test that swaps backends.
    monkeypatch.setattr(backend, "stop", lambda unit: stopped.append(unit) or True)
    with pytest.raises(owner_mod.OwnerError, match="held here as parent"):
        owner_mod.recover(FakeOwner(), unit="set-agent-parent.scope",
                          session_id="s", cwd="/tmp")
    assert stopped == []


def test_a_child_in_a_held_scope_is_not_reported_orphaned(monkeypatch):
    from set_orch.api import fleet as api

    monkeypatch.setattr(api.fleet_tmux_view, "pane_of", lambda pid: None)
    owned = {111: {"pid": 111, "label": "parent", "unit": "set-agent-parent.scope"}}

    monkeypatch.setattr(api.fleet_scopes, "scope_of", lambda pid: "set-agent-parent.scope")
    population, label, scope, _ = api._terminal_population(222, owned)
    assert (population, label, scope) == ("foreign", None, None)

    # The partner: a framework scope nobody holds IS an orphan, and keeps its scope.
    monkeypatch.setattr(api.fleet_scopes, "scope_of", lambda pid: "set-agent-gone.scope")
    population, label, scope, _ = api._terminal_population(222, owned)
    assert (population, scope) == ("orphaned", "set-agent-gone.scope")


def test_a_held_viewer_is_reported_on_the_foreign_agent(monkeypatch):
    from set_orch.api import fleet as api

    pane = tmux_view.TmuxPane(socket="/s", server_pid=1, pane="%3")
    monkeypatch.setattr(api.fleet_scopes, "scope_of", lambda pid: None)
    monkeypatch.setattr(api.fleet_tmux_view, "pane_of", lambda pid: pane)
    monkeypatch.setattr(api.fleet_tmux_view, "session_of", lambda p: "desk")
    owned = {999: {"pid": 999, "label": "tmux-desk", "unit": "set-agent-tmux-desk.scope"}}
    population, label, scope, row = api._terminal_population(222, owned)
    assert population == "foreign" and label == "tmux-desk"
    assert row == {"pane": "%3", "viewer": "tmux-desk"}
    # No viewer held: the pane is offered, nothing is attachable yet.
    population, label, scope, row = api._terminal_population(222, {})
    assert population == "foreign" and label is None
    assert row == {"pane": "%3", "viewer": None}
