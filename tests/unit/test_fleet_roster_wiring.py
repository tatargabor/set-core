"""The roster write, where discovery's answer must not notice it.

A record is for the NEXT boot; the agent list is for now. If saving the first
can damage the second, the feature has made the screen less reliable in order to
make a future reboot recoverable, which is a bad trade nobody agreed to.

The assertion that matters is not "the route returned 200". It is that the
answer is **byte-identical** with a writable store and an unwritable one — a
200 is compatible with a truncated project list, a dropped agent, or a state
that silently became unknown.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

import pytest

from set_orch.api import fleet as fleet_api
from set_orch.fleet.state import AgentState
from set_orch.fleet import roster


class _Agent:
    """The narrow shape both `_record_roster` and the payload builders read."""

    def __init__(self, pid: int, cwd: str, session_id: str, name: str):
        self.pid = pid
        self.cwd = cwd
        self.project_root = cwd
        self.project_name = os.path.basename(cwd)
        self.branch = None
        self.session_id = session_id
        self.session_log = None
        self.name = name
        self.kind = "interactive"
        self.sources = ["process"]
        self.binding_confirmed = True
        self.record = None
        self.sources_missing = []
        self.is_interactive = True


def _stub_discovery(monkeypatch, agents: List[_Agent]) -> None:
    """Everything the route consults, held still, so the only variable is the store."""
    monkeypatch.setattr(fleet_api, "_load_projects", lambda: [])
    monkeypatch.setattr(fleet_api, "_safe_messaging", lambda: [])
    monkeypatch.setattr(fleet_api, "discover_agents", lambda **kw: agents)
    monkeypatch.setattr(fleet_api, "read_state", lambda *a, **k: AgentState(state="quiet"))
    monkeypatch.setattr(fleet_api, "_owned_by_pid", lambda: {})
    monkeypatch.setattr(fleet_api.fleet_instruct, "seats_cached", lambda: {})

    class _P:
        def __init__(self, agent):
            self.root = agent.cwd
            self.name = agent.project_name
            self.sources = ["process"]
            self.agent_pids = [agent.pid]
            self.archived = False

    monkeypatch.setattr(fleet_api, "discover_projects", lambda agents, **kw: [_P(a) for a in agents])


def test_an_unwritable_store_leaves_the_agent_list_byte_identical(monkeypatch, tmp_path, caplog):
    """AC-10, and task 4.3 — asserted as EQUALITY of the two answers.

    A 200 is not the property under test: the route can answer 200 with an agent
    missing. The two runs differ in exactly one thing, so any difference in the
    payload is caused by the roster write.
    """
    agents = [_Agent(1, str(tmp_path / "proj"), "S1", "proj-1")]
    _stub_discovery(monkeypatch, agents)

    good = tmp_path / "good" / "fleet-roster.json"
    monkeypatch.setattr(roster, "default_roster_path", lambda: str(good))
    with_store = fleet_api.fleet_agents()

    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    os.chmod(bad_dir, 0o500)
    monkeypatch.setattr(roster, "default_roster_path", lambda: str(bad_dir / "fleet-roster.json"))
    try:
        with caplog.at_level(logging.WARNING):
            without_store = fleet_api.fleet_agents()
    finally:
        os.chmod(bad_dir, 0o700)

    assert json.dumps(with_store, sort_keys=True, default=str) == \
           json.dumps(without_store, sort_keys=True, default=str), \
           "the roster write changed what the screen shows"
    assert "roster not recorded" in caplog.text, "a swallowed failure must still be stated"


def test_the_route_actually_writes_the_roster(monkeypatch, tmp_path):
    """The negative control for the test above.

    Two identical answers prove nothing if the write never happens — the test
    would compare a no-op with a no-op and pass forever. So: assert the file
    exists and holds the session that was discovered.
    """
    agents = [_Agent(1, str(tmp_path / "proj"), "S1", "proj-1")]
    _stub_discovery(monkeypatch, agents)
    store = tmp_path / "store" / "fleet-roster.json"
    monkeypatch.setattr(roster, "default_roster_path", lambda: str(store))

    fleet_api.fleet_agents()

    assert store.exists(), "the route did not write the roster at all"
    document = json.loads(store.read_text())
    assert "S1" in json.dumps(document)


def test_recording_happens_for_the_default_listing_not_only_with_oneshots(monkeypatch, tmp_path):
    """The default call is the one the screen makes every few seconds. If the
    write hung off the `include_oneshot` path, the roster would fill only when
    somebody asked a question nobody asks.
    """
    agents = [_Agent(1, str(tmp_path / "proj"), "S1", "proj-1")]
    _stub_discovery(monkeypatch, agents)
    store = tmp_path / "store" / "fleet-roster.json"
    monkeypatch.setattr(roster, "default_roster_path", lambda: str(store))

    fleet_api.fleet_agents()  # no arguments — exactly what the screen calls
    assert store.exists()
