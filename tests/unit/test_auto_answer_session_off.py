"""One agent opted out of automatic answers — fleet-auto-answer-session-off.

The config is the real machine-local layer in a tmp dir (`SET_CONFIG_DIR`); the fleet label
lookup and the process tree are injected.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from set_orch.fleet import auto_answer as aa
from set_orch.fleet import auto_answer_worker as aw
from set_orch.fleet import question_relay as qr

SID = "47f1763f-c5c5-4f3a-9aae-850d27d41dae"
NEW_SID = "99999999-c5c5-4f3a-9aae-850d27d41dae"


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    (tmp_path / "cfg").mkdir()
    monkeypatch.setenv("SET_CONFIG_DIR", str(tmp_path / "cfg"))
    for key in (aa.KEY_ENABLED, aa.KEY_OFF_AGENTS, aa.KEY_FORWARD):
        monkeypatch.delenv(aa.local_config.env_key(key), raising=False)
    aa.local_config.set_value(aa.KEY_ENABLED, True)
    aa.local_config.set_value(aa.KEY_FORWARD, "bridge be --json -")
    return tmp_path


def test_a_label_opt_out_survives_a_clear(cfg):
    """AC-3: the terminal is named, so a new session id in it is still covered."""
    aa.set_agent_off("label:planner", True)
    labels = {SID: "planner", NEW_SID: "planner"}
    assert aa.agent_off(SID, resolve_label=labels.get) == "label:planner"
    assert aa.agent_off(NEW_SID, resolve_label=labels.get) == "label:planner"
    assert aa.agent_off(SID, resolve_label=lambda s: "other") is None


def test_a_session_opt_out_and_clearing_it(cfg):
    """AC-5's data half: clearing the entry makes the agent decided again."""
    aa.set_agent_off(f"session:{SID}", True)
    assert aa.agent_off(SID) == f"session:{SID}"
    aa.set_agent_off(f"session:{SID}", False)
    assert aa.agent_off(SID) is None and aa.off_agents() == []


def test_an_unreadable_label_is_said_not_silently_matched(cfg, caplog):
    aa.set_agent_off("label:planner", True)
    def boom(sid):
        raise ConnectionRefusedError()
    assert aa.agent_off(SID, resolve_label=boom) is None
    assert "cannot hold" in caplog.text


def test_a_malformed_entry_is_refused(cfg):
    with pytest.raises(ValueError):
        aa.set_agent_off("planner", True)


def test_the_outbound_forwards_unchanged_for_an_opted_out_agent(cfg):
    """AC-1: byte for byte, no worker."""
    payload = json.dumps({"questions": [{"id": "relay-x", "key": "Q1", "question": "Ship?", "optionsList": ["Yes", "No"]}]})
    seen = []
    code = aw.outbound(payload, environ={qr.ENV_KIND: "ask", qr.ENV_SESSION: SID, qr.ENV_CWD: "/w"},
                       run=lambda c, p, env=None: seen.append((c, p)) or 0,
                       spawn=lambda *a: pytest.fail("no worker for an opted-out agent"),
                       opted_out=lambda sid: "label:planner" if sid == SID else None)
    assert code == 0 and seen == [("bridge be --json -", payload)]


def test_another_agent_is_still_decided(cfg):
    """AC-2."""
    payload = json.dumps({"questions": [{"id": "relay-x", "key": "Q1", "question": "Ship?", "optionsList": ["Yes", "No"]}]})
    spawned = []
    aw.outbound(payload, environ={qr.ENV_KIND: "ask", qr.ENV_SESSION: NEW_SID, qr.ENV_CWD: "/w"},
                run=lambda *a, **k: pytest.fail("not forwarded raw"), spawn=lambda p, v: spawned.append(v),
                opted_out=lambda sid: "label:planner" if sid == SID else None)
    assert len(spawned) == 1


def test_here_off_on_status_from_inside_a_fleet_terminal(cfg):
    """AC-4."""
    label = lambda sid: "planner"
    code, line = aw.here("off", session_id=SID, resolve_label=label)
    assert code == 0 and "OFF" in line and aa.off_agents() == ["label:planner"]
    assert "OFF" in aw.here("status", session_id=SID, resolve_label=label)[1]
    aw.here("on", session_id=SID, resolve_label=label)
    assert aa.off_agents() == [] and ": on" in aw.here("status", session_id=SID, resolve_label=label)[1]


def test_here_outside_the_fleet_names_the_session(cfg):
    code, line = aw.here("off", session_id=SID, resolve_label=lambda s: None)
    assert aa.off_agents() == [f"session:{SID}"] and "not a fleet terminal" in line


def test_own_session_walks_up_to_the_agent(tmp_path):
    (tmp_path / "300.json").write_text(json.dumps({"sessionId": SID}))
    tree = {100: 200, 200: 300, 300: 1}
    assert aw.own_session(start=100, records=tmp_path, ppid=tree.get) == SID
    assert aw.own_session(start=100, records=tmp_path / "none", ppid=tree.get) is None


def test_no_decide_only_worker_for_an_opted_out_agent(tmp_path, monkeypatch):
    from set_orch.fleet import relay_backfill as rb
    monkeypatch.setattr(qr, "_hook_alive", lambda pid: True)
    base = tmp_path / "state"
    cid = qr.call_id(SID, "toolu_1")
    qr._write_json(qr.waiting_path(SID, base), {"session_id": SID, "id": cid, "questions": 1, "pid": 1})
    spawned = []
    w = rb.World(base=base, spawn_worker=lambda p, v: spawned.append(v), agent_off=lambda sid: "label:planner",
                 get=lambda k, project=None, default=None: default)
    out = rb.undecided_waiting(w)
    assert spawned == [] and "off here" in out["not_decided"][0]["why"]
