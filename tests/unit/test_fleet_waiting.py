"""The owner's queue — change `fleet-waiting-on-you`, tasks 1.1–1.4, 2.1–2.2, 4.2–4.3.

Every test here is about a DISTINCTION the queue would otherwise collapse: a
source that could not be read versus one that holds nothing, one relayed
question versus the same question counted twice, an entry addressed to the owner
versus one that merely mentions the owner in its text.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from set_orch.fleet import discovery as fleet_discovery
from set_orch.fleet import state as fleet_state
from set_orch.fleet import waiting
from set_orch.fleet.waiting import SOURCES, SourceResult, build_queue

NOW = 1_800_000_000.0


def _items(source, n, *, since=None):
    return [
        {"source": source, "id": f"{source}:{i}", "project": "p", "kind": "k",
         "title": None, "since": since, "session_id": None, "agent": None,
         "room": None, "link": None}
        for i in range(n)
    ]


def _fixed(name, n=0, *, measured=True, reason=None, since=None):
    return lambda now: SourceResult(name, measured, reason, _items(name, n, since=since))


def _by_name(q):
    return {s["name"]: s for s in q["sources"]}


# --------------------------------------------------------------------------- #
# 1.1 — the aggregator
# --------------------------------------------------------------------------- #

def test_an_unreadable_source_is_not_a_zero():
    """AC-1: the bus cannot be read, the other three hold 4 items → total 4, one
    source unmeasured with its reason. The bus's failure must not read as 0."""
    q = build_queue(NOW, adapters={
        "agent-questions": _fixed("agent-questions", 2),
        "run-state": _fixed("run-state", 2),
        "project-questions": _fixed("project-questions", 0),
        "bus-owner": _fixed("bus-owner", 3, measured=False, reason="bus owner view exited 2"),
    })
    assert q["total"] == 4
    assert q["unmeasured"] == 1
    bus = _by_name(q)["bus-owner"]
    assert bus["measured"] is False
    assert bus["reason"] == "bus owner view exited 2"
    # An unmeasured source carries no items — a partial list next to
    # "unmeasured" would be counted by somebody.
    assert bus["count"] == 0
    assert not [i for i in q["items"] if i["source"] == "bus-owner"]


def test_sources_are_not_merged_into_one_count():
    """AC-2 and AC-10: every source is named, in order, with its own count."""
    q = build_queue(NOW, adapters={
        "agent-questions": _fixed("agent-questions", 2),
        "run-state": _fixed("run-state", 3),
        "project-questions": _fixed("project-questions", 0),
        "bus-owner": _fixed("bus-owner", 0),
    })
    assert [s["name"] for s in q["sources"]] == list(SOURCES)
    assert list(SOURCES) == ["agent-questions", "run-state", "project-questions", "bus-owner"]
    counts = {s["name"]: s["count"] for s in q["sources"]}
    assert counts == {"agent-questions": 2, "run-state": 3,
                      "project-questions": 0, "bus-owner": 0}
    assert q["total"] == 5
    for s in q["sources"]:
        assert set(s) >= {"name", "measured", "reason", "count"}


def test_an_adapter_that_raises_is_unmeasured_and_named_in_a_warning(caplog):
    def boom(now):
        raise RuntimeError("secret detail")

    caplog.set_level(logging.DEBUG)
    q = build_queue(NOW, adapters={
        "agent-questions": boom,
        "run-state": _fixed("run-state", 1),
        "project-questions": _fixed("project-questions"),
        "bus-owner": _fixed("bus-owner"),
    })
    src = _by_name(q)["agent-questions"]
    assert src["measured"] is False and src["count"] == 0
    assert "RuntimeError" in src["reason"]
    assert q["total"] == 1 and q["unmeasured"] == 1
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("agent-questions" in r.getMessage() for r in warnings)
    # The type, never the message — a message can quote the content that failed.
    assert "secret detail" not in caplog.text


def test_a_missing_adapter_is_unmeasured_not_absent():
    q = build_queue(NOW, adapters={"run-state": _fixed("run-state", 1)})
    assert [s["name"] for s in q["sources"]] == list(SOURCES)
    assert q["unmeasured"] == 3
    assert q["total"] == 1


def test_items_are_oldest_first_and_unknown_starts_go_last():
    def agents(now):
        return SourceResult("agent-questions", True, None, [
            {**_items("agent-questions", 1)[0], "id": "new", "since": NOW - 10},
            {**_items("agent-questions", 1)[0], "id": "nostart", "since": None},
        ])

    def bus(now):
        return SourceResult("bus-owner", True, None, [
            {**_items("bus-owner", 1)[0], "id": "old", "since": NOW - 1000},
        ])

    q = build_queue(NOW, adapters={
        "agent-questions": agents, "run-state": _fixed("run-state"),
        "project-questions": _fixed("project-questions"), "bus-owner": bus,
    })
    assert [i["id"] for i in q["items"]] == ["old", "new", "nostart"]


def test_project_questions_is_unmeasured_until_agreed():
    """Tasks 4.1/4.4 are not done: the source must say so, not report zero."""
    r = waiting.collect_project_questions(NOW)
    assert r.measured is False
    assert r.reason == "not agreed yet"


# --------------------------------------------------------------------------- #
# 1.2 — agent questions
# --------------------------------------------------------------------------- #

def _agent(pid, session, project, name=None):
    return fleet_discovery.Agent(pid=pid, cwd="/x", project_name=project,
                                 session_id=session, name=name)


def _wire_agents(monkeypatch, agents, states):
    monkeypatch.setattr(fleet_discovery, "discover_agents", lambda **k: agents)
    monkeypatch.setattr(
        fleet_state, "read_state",
        lambda log, record=None, now=None, **k: states[next(a.pid for a in agents
                                                              if a.session_log == log)])


def _relay_record(tmp_path, monkeypatch, session, project, started):
    monkeypatch.setenv("SET_QUESTION_RELAY_DIR", str(tmp_path / "relay"))
    folder = tmp_path / "relay" / "waiting"
    folder.mkdir(parents=True, exist_ok=True)
    # No pid: a record without one is trusted (it predates B-159), so the real
    # `list_waiting` reads it rather than pruning it as a dead hook.
    (folder / f"{session}.json").write_text(json.dumps({
        "session_id": session, "id": "relay-x", "project": project,
        "questions": 1, "target": "command", "started": started,
    }))


def test_a_relayed_question_is_listed_once(tmp_path, monkeypatch):
    """AC-3 / design D2: relay record and attention class describe one question."""
    sid = "aaaaaaaa-0000-4000-8000-000000000001"
    _relay_record(tmp_path, monkeypatch, sid, "proj", NOW - 300)
    a = _agent(101, sid, "proj", name="proj-1")
    a.session_log = "/log/101"
    _wire_agents(monkeypatch, [a], {
        101: fleet_state.AgentState(attention=fleet_state.ATTENTION_PROMPT,
                                    input_wait_seconds=5.0),
    })
    r = waiting.collect_agent_questions(NOW)
    assert r.measured is True
    assert len(r.items) == 1
    item = r.items[0]
    assert item["id"] == f"agent:{sid}"
    # The relay record wins: its start, not the attention class's 5 s.
    assert item["since"] == NOW - 300
    assert item["kind"] == "relayed"
    # ...and discovery adds who it is.
    assert item["agent"] == "proj-1"
    assert item["project"] == "proj"


def test_a_waiting_agent_is_listed_with_its_wait(tmp_path, monkeypatch):
    """AC-4: 12 minutes waiting → the item names agent, project and the wait."""
    monkeypatch.setenv("SET_QUESTION_RELAY_DIR", str(tmp_path / "empty-relay"))
    waiting_agent = _agent(201, "s-201", "alpha", name="alpha-3")
    waiting_agent.session_log = "/log/201"
    busy = _agent(202, "s-202", "alpha", name="alpha-4")
    busy.session_log = "/log/202"
    _wire_agents(monkeypatch, [waiting_agent, busy], {
        201: fleet_state.AgentState(attention=fleet_state.ATTENTION_INPUT,
                                    input_wait_seconds=12 * 60.0),
        202: fleet_state.AgentState(attention=fleet_state.ATTENTION_WORKING),
    })
    r = waiting.collect_agent_questions(NOW)
    assert [i["agent"] for i in r.items] == ["alpha-3"]
    item = r.items[0]
    assert item["project"] == "alpha"
    assert item["session_id"] == "s-201"
    assert NOW - item["since"] == pytest.approx(12 * 60.0)


def test_an_agent_question_without_a_waiting_for_takes_the_agents_last_words(tmp_path, monkeypatch):
    """The runtime's waitingFor is usually empty; the agent's own last words are the question.
    A user's last words are not — they are what the agent was asked, not what it asks."""
    monkeypatch.setenv("SET_QUESTION_RELAY_DIR", str(tmp_path / "empty-relay"))
    agents, states = [], {}
    for pid, frm in ((501, "assistant"), (502, "user")):
        a = _agent(pid, f"s-{pid}", "p", name=f"a{pid}")
        a.session_log = f"/log/{pid}"
        agents.append(a)
        states[pid] = fleet_state.AgentState(attention=fleet_state.ATTENTION_INPUT, input_wait_seconds=1.0,
                                             excerpt=f"words {pid}", excerpt_from=frm)
    states[503] = fleet_state.AgentState(attention=fleet_state.ATTENTION_INPUT, input_wait_seconds=1.0,
                                         waiting_for="declared", excerpt="ignored", excerpt_from="assistant")
    a = _agent(503, "s-503", "p", name="a503")
    a.session_log = "/log/503"
    agents.append(a)
    _wire_agents(monkeypatch, agents, states)
    titles = {i["session_id"]: i["title"] for i in waiting.collect_agent_questions(NOW).items}
    assert titles == {"s-501": "words 501", "s-502": None, "s-503": "declared"}


def test_every_waiting_class_counts_and_no_other_does(tmp_path, monkeypatch):
    monkeypatch.setenv("SET_QUESTION_RELAY_DIR", str(tmp_path / "empty-relay"))
    agents, states = [], {}
    for i, cls in enumerate(fleet_state.ATTENTION_CLASSES):
        a = _agent(300 + i, f"s-{i}", "p", name=f"a{i}")
        a.session_log = f"/log/{i}"
        agents.append(a)
        states[300 + i] = fleet_state.AgentState(attention=cls, input_wait_seconds=1.0)
    _wire_agents(monkeypatch, agents, states)
    r = waiting.collect_agent_questions(NOW)
    assert sorted(i["kind"] for i in r.items) == sorted(fleet_state.ATTENTION_WAITING_CLASSES)


# --------------------------------------------------------------------------- #
# 1.3 — run state
# --------------------------------------------------------------------------- #

def _state(data_home, project, changes, **top):
    p = data_home / "set-core" / "runtime" / project / "orchestration" / "state.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"changes": changes, **top}))


def test_a_stalled_change_is_listed_with_its_kind(tmp_path, monkeypatch):
    """AC-5, plus the two exclusions: unverifiable is not waiting, and a project
    with no run state is an unmeasured project, not zero items."""
    data_home = tmp_path / "data"
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    _state(data_home, "one", [
        {"name": "chg-stalled", "status": "stalled"},
        # In flight with no pid anywhere: `unverifiable`, never listed.
        {"name": "chg-unverifiable", "status": "running"},
        {"name": "chg-merged", "status": "merged", "has_manual_tasks": True},
    ])
    monkeypatch.setattr(waiting, "_registered_projects", lambda: [
        {"name": "one", "path": str(tmp_path / "one-root")},
        {"name": "two", "path": str(tmp_path / "two-root")},   # no state file
    ])
    r = waiting.collect_run_state(NOW)
    assert r.measured is True
    assert [(i["project"], i["kind"], i["title"]) for i in r.items] == [
        ("one", "stalled", "chg-stalled"),
    ]
    assert r.items[0]["id"] == "run:one:stalled:chg-stalled"
    assert r.extra["unmeasured_projects"] == 1


def test_a_decision_marker_is_listed_even_without_run_state(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    root = tmp_path / "root"
    tasks = root / "openspec" / "changes" / "chg-q" / "tasks.md"
    tasks.parent.mkdir(parents=True)
    tasks.write_text("- [ ] 2.1 pick a vendor <!-- awaiting: which one? -->\n")
    monkeypatch.setattr(waiting, "_registered_projects",
                        lambda: [{"name": "dec", "path": str(root)}])
    r = waiting.collect_run_state(NOW)
    assert [(i["kind"], i["title"]) for i in r.items] == [("decision", "chg-q#2.1")]
    assert r.extra["unmeasured_projects"] == 1


def test_the_unmeasured_project_count_reaches_the_answer(monkeypatch):
    q = build_queue(NOW, adapters={
        "run-state": lambda now: SourceResult("run-state", True, None, [],
                                              {"unmeasured_projects": 7}),
    })
    assert _by_name(q)["run-state"]["unmeasured_projects"] == 7


# --------------------------------------------------------------------------- #
# 4.2 / 4.3 — the bus source
# --------------------------------------------------------------------------- #

def _fake_sac(monkeypatch, *, stdout="", returncode=0, stderr="", raises=None):
    monkeypatch.setattr(waiting.shutil, "which", lambda b: "/fake/" + b)

    def run(sac_bin):
        if raises is not None:
            raise raises
        return SimpleNamespace(stdout=stdout, returncode=returncode, stderr=stderr)

    monkeypatch.setattr(waiting, "_run_sac_owner", run)


def test_the_bus_view_is_read_as_items(monkeypatch):
    _fake_sac(monkeypatch, stdout=json.dumps({
        "schema": "sac.owner/1", "generatedAt": "x",
        "open": [{"room": "ops", "id": "2026-10-19T10:00:00.000+02:00|watch#1",
                  "ts": "2026-10-19T10:00:00.000+02:00", "type": "QUESTION",
                  "from": "watch#1", "to": ["owner"], "text": "\nApprove it?\nmore",
                  "ageMinutes": 5}],
    }))
    r = waiting.collect_bus_owner(NOW)
    assert r.measured is True
    [item] = r.items
    assert item["id"] == "bus:ops:2026-10-19T10:00:00.000+02:00|watch#1"
    assert item["room"] == "ops" and item["agent"] == "watch#1"
    assert item["kind"] == "question"
    assert item["title"] == "Approve it?"
    # 10:00 at +02:00 is 08:00 UTC.
    assert item["since"] == datetime(2026, 10, 19, 8, 0, tzinfo=timezone.utc).timestamp()


def test_an_empty_bus_view_is_measured_zero(monkeypatch):
    """Design D4: until a writer addresses `owner` the view is legitimately empty."""
    _fake_sac(monkeypatch, stdout=json.dumps({"schema": "sac.owner/1", "open": []}))
    r = waiting.collect_bus_owner(NOW)
    assert r.measured is True and r.items == []


@pytest.mark.parametrize("kwargs,reason_part", [
    (dict(returncode=2, stderr="boom"), "exited 2"),
    (dict(stdout="not json"), "did not parse"),
    (dict(stdout=json.dumps({"schema": "sac.other/9", "open": []})), "sac.owner/1"),
    (dict(stdout=json.dumps({"schema": "sac.owner/1"})), "no open list"),
    (dict(raises=subprocess.TimeoutExpired(cmd="sac", timeout=10)), "timed out"),
    (dict(raises=OSError("nope")), "could not run"),
])
def test_the_bus_view_is_unavailable(monkeypatch, kwargs, reason_part):
    """AC-9: every failing shape is unmeasured with its reason — never zero."""
    _fake_sac(monkeypatch, **kwargs)
    r = waiting.collect_bus_owner(NOW)
    assert r.measured is False
    assert reason_part in r.reason


def test_no_bus_command_is_unmeasured(monkeypatch):
    monkeypatch.setattr(waiting.shutil, "which", lambda b: None)
    r = waiting.collect_bus_owner(NOW)
    assert r.measured is False and "not found" in r.reason


def test_the_bus_binary_can_be_overridden_by_local_config(monkeypatch):
    monkeypatch.setenv("SETCORE_FLEET_SAC_BIN", "/opt/other/sac")
    seen = []
    monkeypatch.setattr(waiting.shutil, "which", lambda b: seen.append(b) or None)
    waiting.collect_bus_owner(NOW)
    assert seen == ["/opt/other/sac"]


@pytest.mark.skipif(not shutil.which("sac"), reason="set-agent-comm (`sac`) not installed")
def test_prose_addressing_is_not_counted_against_a_real_bus(tmp_path, monkeypatch):
    """AC-8, measured against the real bus in an isolated store: a broadcast that
    names the owner only in its TEXT is not listed; an entry addressed `--to
    owner` is. The adapter has no text parser to get this wrong — this proves
    the whole path, sac's view included, keeps the distinction."""
    env = dict(os.environ, SET_AGENT_COMM_DIR=str(tmp_path / "bus"),
               SET_AGENT_TRIAGE="off", SET_AGENT_FLEET_ROSTER=str(tmp_path / "none.json"),
               SET_AGENT_NAME="tester",
               CLAUDE_CODE_SESSION_ID="11111111-0000-4000-8000-000000000001")
    env.pop("SET_AGENT_ROOM", None)

    def sac(*args):
        subprocess.run(["sac", *args], env=env, cwd=tmp_path, check=True,
                       capture_output=True, text=True, timeout=30)

    sac("join", "ops", "--create")
    sac("send", "ops", "REQUEST", "-> owner: please approve the release")
    sac("send", "ops", "QUESTION", "Approve the release?", "--to", "owner")

    for key, value in env.items():
        monkeypatch.setenv(key, value)
    r = waiting.collect_bus_owner(NOW)
    assert r.measured is True
    assert [i["title"] for i in r.items] == ["Approve the release?"]
    assert r.items[0]["kind"] == "question"


# --------------------------------------------------------------------------- #
# 2.1 / 2.2 — the API answer, and what it never logs
# --------------------------------------------------------------------------- #

SENTINEL = "ZZQ-SENTINEL-7f3a"


def test_the_route_is_registered():
    from set_orch.api.fleet import router
    assert "/api/fleet/waiting-on-you" in {getattr(r, "path", None) for r in router.routes}


def test_logs_carry_no_item_content(tmp_path, monkeypatch, caplog):
    """AC-11: build the queue through the ROUTE with sentinel content in every
    source that carries text, at DEBUG for every logger, including failure paths
    whose messages could quote content — and find the sentinel nowhere."""
    from set_orch.api import fleet as fleet_api

    caplog.set_level(logging.DEBUG)

    # agent-questions: the runtime's own "waiting for" text.
    monkeypatch.setenv("SET_QUESTION_RELAY_DIR", str(tmp_path / "relay"))
    a = _agent(401, "s-401", "proj", name="proj-1")
    a.session_log = "/log/401"
    _wire_agents(monkeypatch, [a], {
        401: fleet_state.AgentState(attention=fleet_state.ATTENTION_PROMPT,
                                    input_wait_seconds=60.0,
                                    waiting_for=f"{SENTINEL} agent text"),
    })
    # run-state: a change name.
    data_home = tmp_path / "data"
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    _state(data_home, "proj", [{"name": f"{SENTINEL}-change", "status": "stalled"}])
    monkeypatch.setattr(waiting, "_registered_projects",
                        lambda: [{"name": "proj", "path": str(tmp_path / "root")}])
    # bus-owner: an entry's text.
    _fake_sac(monkeypatch, stdout=json.dumps({"schema": "sac.owner/1", "open": [
        {"room": "ops", "id": "t|f", "ts": "2026-10-19T10:00:00Z", "type": "QUESTION",
         "from": "f", "to": ["owner"], "text": f"{SENTINEL} bus text", "ageMinutes": 1}]}))

    q = fleet_api.fleet_waiting_on_you()
    titles = [i["title"] or "" for i in q["items"]]
    assert sum(SENTINEL in t for t in titles) == 3, titles   # the content IS returned
    assert caplog.records, "no log record was captured — the assertion below would be vacuous"
    assert SENTINEL not in caplog.text

    # The failure paths: a raising adapter whose message quotes content, and a
    # bus whose stderr does.
    caplog.clear()
    _fake_sac(monkeypatch, returncode=1, stderr=f"{SENTINEL} in stderr")
    monkeypatch.setattr(waiting, "_registered_projects",
                        lambda: (_ for _ in ()).throw(ValueError(f"{SENTINEL} in message")))
    q = fleet_api.fleet_waiting_on_you()
    assert _by_name(q)["run-state"]["measured"] is False
    assert _by_name(q)["bus-owner"]["measured"] is False
    assert SENTINEL not in json.dumps(q["sources"])
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert SENTINEL not in caplog.text
