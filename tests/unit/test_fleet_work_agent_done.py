"""fleet-work-agent-done — the done step, the work sweep's decision, and the
human-input measure they both depend on. Every rule is held in both directions."""

import json
import time

import pytest

from set_orch.fleet import mandate, mandate_cli, mandate_delivery, work_close
from set_orch.fleet import state as S


# --------------------------------------------------------------------------- #
# the done step
# --------------------------------------------------------------------------- #

@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    store = mandate.MandateStore()
    calls = []
    monkeypatch.setattr(mandate_cli, "_post_to_requester",
                        lambda who, text: calls.append(("post", who, text)) or None)
    monkeypatch.setattr(mandate_cli, "_stop_label",
                        lambda label: calls.append(("stop", label, store.get(made_id[0])["ended"])) or None)
    made_id = [None]

    def make(**over):
        args = dict(kind="work", goal="answer three questions", project="p", cwd="/x/p",
                    label="p-1", unit="set-agent-p-1.scope", requested_by="other#abcd1234")
        args.update(over)
        rec = store.create(**args)
        made_id[0] = rec["id"]
        monkeypatch.setenv(mandate.ENV_MANDATE, rec["id"])
        return rec
    return store, calls, make


def test_done_posts_then_ends_then_stops(env):
    store, calls, make = env
    rec = make()
    assert mandate_cli.main(["done", "answered all three"]) == 0
    assert [c[0] for c in calls] == ["post", "stop"]
    assert calls[0][1] == "other#abcd1234" and "answered all three" in calls[0][2]
    # The mandate was ALREADY ended when the stop ran — the order the listing race needs.
    assert calls[1][2] and calls[1][2]["reason"] == "agent-done"
    assert store.get(rec["id"])["ended"]["reason"] == "agent-done"


def test_a_failed_post_ends_nothing_and_stops_nothing(env, monkeypatch):
    store, calls, make = env
    rec = make()
    monkeypatch.setattr(mandate_cli, "_post_to_requester", lambda who, text: "bus down")
    assert mandate_cli.main(["done", "x"]) == 1
    assert calls == []
    assert store.get(rec["id"])["ended"] is None


@pytest.mark.parametrize("over", [dict(kind="desk"), dict(requested_by=None)])
def test_only_an_agent_requested_work_mandate_can_be_done(env, over):
    store, calls, make = env
    rec = make(**over)
    assert mandate_cli.main(["done", "x"]) == 2
    assert calls == [] and store.get(rec["id"])["ended"] is None


def test_no_mandate_in_the_environment_is_refused(env, monkeypatch):
    _store, calls, _make = env
    monkeypatch.delenv(mandate.ENV_MANDATE, raising=False)
    assert mandate_cli.main(["done", "x"]) == 2
    assert calls == []


def test_agent_done_is_an_end_reason_and_not_a_fulfilment(env):
    store, _calls, make = env
    rec = make()
    store.end(rec["id"], "agent-done")
    public = mandate.public(store.get(rec["id"]))
    assert public["ended"]["reason"] == "agent-done"
    assert not any("fulfil" in k for k in public)


# --------------------------------------------------------------------------- #
# delivery
# --------------------------------------------------------------------------- #

def _record(**over):
    rec = dict(id="m-1", kind="work", goal="g", project="p", requested_by="other#1")
    rec.update(over)
    return rec


def test_an_agent_requested_work_mandate_is_told_how_to_end():
    assert mandate_delivery.DONE_COMMAND in mandate_delivery.render_context(_record())


@pytest.mark.parametrize("over", [dict(requested_by=None), dict(kind="desk")])
def test_others_are_not_told_to_end_themselves(over):
    assert mandate_delivery.DONE_COMMAND not in mandate_delivery.render_context(_record(**over))


# --------------------------------------------------------------------------- #
# the work sweep's decision
# --------------------------------------------------------------------------- #

NOW = 1_000_000.0
BOUND = 2 * 3600.0


def _row(**over):
    row = {
        "population": "started-here", "terminal_label": "p-1", "state": "quiet",
        "attention": "background", "tool": None, "runtime_status": "shell",
        "last_movement_seconds": 3 * 3600.0,
        # The brief: human input right at the start, 4 h ago.
        "last_human_input_seconds": 4 * 3600.0 - 5,
        "mandate": {"id": "m-1", "kind": "work", "requested_by": "other#1",
                    "ended": None, "declared_at": NOW - 4 * 3600.0},
    }
    for k, v in over.items():
        row[k] = v
    return row


def test_answered_then_forgotten_is_stopped():
    assert work_close.decision(_row(), bound=BOUND, now=NOW) == (work_close.STOP, "work-idle")


@pytest.mark.parametrize("over, why", [
    (dict(last_movement_seconds=600.0), "recent-movement"),
    (dict(last_movement_seconds=None), "movement-unmeasured"),
    (dict(last_human_input_seconds=1800.0), "operator-took-over"),
    (dict(state="asking"), "state-asking"),
    (dict(state="unknown"), "state-unknown"),
    (dict(attention="prompt"), "attention-prompt"),
    (dict(tool="Bash"), "busy"),
    (dict(population="foreign"), "not-a-work-agent"),
])
def test_every_reason_to_keep(over, why):
    assert work_close.decision(_row(**over), bound=BOUND, now=NOW) == (work_close.KEEP, why)


@pytest.mark.parametrize("mandate_over", [dict(kind="desk"), dict(requested_by=None),
                                          dict(ended={"reason": "stopped"})])
def test_only_open_agent_requested_work_mandates_are_swept(mandate_over):
    row = _row()
    row["mandate"] = {**row["mandate"], **mandate_over}
    assert work_close.decision(row, bound=BOUND, now=NOW)[0] == work_close.KEEP


# --------------------------------------------------------------------------- #
# the human-input measure (the root of B-205: harness turns read as a person)
# --------------------------------------------------------------------------- #

def _line(**entry):
    base = {"type": "user", "timestamp": "2026-11-23T18:00:00.000Z",
            "message": {"role": "user", "content": "hello"}}
    base.update(entry)
    return json.dumps(base)


def test_a_person_counts():
    assert S._human_entry_epoch(_line(origin={"kind": "human"})) is not None
    assert S._human_entry_epoch(_line()) is not None  # an older runtime: no origin field


@pytest.mark.parametrize("entry", [
    dict(origin={"kind": "task-notification", "producer": "session-task"}),
    dict(isMeta=True),
])
def test_harness_turns_do_not_count(entry):
    assert S._human_entry_epoch(_line(**entry)) is None
