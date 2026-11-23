"""The mandate record: why an agent was started, kept where an owner restart cannot reach it.

The properties under test are the ones a reader of the fleet screen relies on without being
able to check: a recorded goal is the goal that was given, an agent with no record has no
goal invented for it, an ended mandate is never called fulfilled, and the operator's own
words never reach a log.
"""

from __future__ import annotations

import json
import logging
import os
import stat
import threading

import pytest

from set_orch.fleet import mandate
from set_orch.fleet.mandate import MandateError, MandateStore, MandateStoreUnreadable

MARKER = "ZZ-GOAL-MARKER-ZZ"


@pytest.fixture
def store(tmp_path):
    return MandateStore(str(tmp_path / "state" / "fleet-mandates.json"))


def _make(store, **over):
    args = dict(kind="work", goal="ship the importer", project="proj-a", cwd="/x/proj-a",
                label="proj-a-1200", unit="set-agent-proj-a-1200.scope")
    args.update(over)
    return store.create(**args)


# -- the record -----------------------------------------------------------------------


def test_a_start_with_a_goal_leaves_a_record(store):
    made = _make(store, requested_by="proj-b#1234abcd", done_when="tests pass",
                 scope={"paths": ["src/import/"], "change": "importer"})
    again = MandateStore(store.path).get(made["id"])
    assert again["goal"] == "ship the importer"
    assert again["kind"] == "work"
    assert again["label"] == "proj-a-1200"
    assert again["requested_by"] == "proj-b#1234abcd"
    assert again["done_when"] == "tests pass"
    assert again["scope"] == {"paths": ["src/import/"], "change": "importer"}
    assert again["source"] == "start"
    assert again["ended"] is None


def test_the_requester_is_always_a_claim(store):
    made = _make(store, requested_by="proj-b#1234abcd")
    assert made["requester_is_claim"] is True
    # Even a stored record that says otherwise is read back as a claim: nothing verifies it.
    raw = json.loads(open(store.path).read())
    raw["mandates"][made["id"]]["requester_is_claim"] = False
    open(store.path, "w").write(json.dumps(raw))
    assert store.get(made["id"])["requester_is_claim"] is True


@pytest.mark.parametrize("goal", [None, "", "   "])
def test_a_mandate_without_a_goal_is_refused_and_nothing_is_written(store, goal):
    with pytest.raises(MandateError) as err:
        _make(store, goal=goal)
    assert err.value.kind == "no-goal"
    assert not os.path.exists(store.path)


def test_an_unknown_kind_is_refused(store):
    with pytest.raises(MandateError) as err:
        _make(store, kind="chore")
    assert err.value.kind == "unknown-kind"


def test_the_store_is_owner_only(store):
    _make(store)
    mode = stat.S_IMODE(os.stat(store.path).st_mode)
    assert mode == 0o600, oct(mode)


def test_remove_takes_back_a_start_that_did_not_happen(store):
    made = _make(store)
    assert store.remove(made["id"]) is True
    assert store.get(made["id"]) is None
    assert store.remove(made["id"]) is False


# -- absence --------------------------------------------------------------------------


def test_absence_names_a_reason_and_never_a_goal():
    foreign = mandate.absence(started_here=False)
    ours = mandate.absence(started_here=True)
    assert foreign == {"reason": "not-started-here"}
    assert ours == {"reason": "not-declared"}
    assert "goal" not in foreign and "goal" not in ours


def test_a_descriptive_label_is_not_a_mandate(store):
    # Another agent has a record; this one has only a label that reads like a goal.
    _make(store, label="other", unit="set-agent-other.scope")
    found = mandate.join(store.all(), pid=None, unit="set-agent-fix-the-login-bug.scope",
                         session_id="s-none")
    assert found is None


# -- ending ---------------------------------------------------------------------------


def test_an_ended_mandate_is_kept_and_carries_a_reason(store):
    made = _make(store)
    ended = store.end(made["id"], "stopped")
    assert ended["ended"]["reason"] == "stopped"
    assert store.get(made["id"])["goal"] == "ship the importer"


def test_no_end_reason_means_fulfilled(store):
    made = _make(store)
    for word in ("fulfilled", "done", "complete"):
        assert word not in mandate.END_REASONS
        with pytest.raises(MandateError):
            store.end(made["id"], word)
    assert store.get(made["id"])["ended"] is None


def test_ending_twice_keeps_the_first_reason(store):
    made = _make(store)
    store.end(made["id"], "desk-quiet")
    store.end(made["id"], "stopped")
    assert store.get(made["id"])["ended"]["reason"] == "desk-quiet"


def test_end_missing_ends_only_started_mandates_whose_agent_is_gone(tmp_path):
    now = [1000.0]
    store = MandateStore(str(tmp_path / "m.json"), clock=lambda: now[0])
    alive = _make(store, label="a", unit="u-a")
    gone = _make(store, label="b", unit="u-b")
    declared = _make(store, label="c", unit=None, source="declared")
    now[0] += 30
    young = _make(store, label="d", unit="u-d")
    now[0] += 100  # alive/gone/declared are 130 s old, young is 100 s old
    ended = store.end_missing([alive["id"]], grace_seconds=120.0)
    assert ended == [gone["id"]]
    assert store.get(gone["id"])["ended"]["reason"] == "ended"
    assert store.get(alive["id"])["ended"] is None
    # A mandate declared for a hand-opened agent is not tied to a process we can watch.
    assert store.get(declared["id"])["ended"] is None
    # An agent that may not be visible yet is not reported gone.
    assert store.get(young["id"])["ended"] is None


def test_ended_mandates_are_pruned_after_retention_and_open_ones_never(tmp_path):
    now = [1000.0]
    store = MandateStore(str(tmp_path / "m.json"), clock=lambda: now[0])
    old = _make(store, label="old")
    keep = _make(store, label="keep")
    store.end(old["id"], "stopped")
    now[0] += mandate.RETENTION_SECONDS + 1
    _make(store, label="new")  # any write prunes
    assert store.get(old["id"]) is None
    assert store.get(keep["id"]) is not None


# -- restore --------------------------------------------------------------------------


def test_a_restored_agent_continues_the_mandate_its_session_held(store):
    made = _make(store)
    store.observe_session(made["id"], "sess-1")
    store.end(made["id"], "ended")  # the machine rebooted; the process is gone
    resumed = store.resume("sess-1", label="proj-a-restored", unit="set-agent-proj-a-restored.scope")
    assert resumed["id"] == made["id"]
    assert resumed["goal"] == "ship the importer"
    assert resumed["ended"] is None
    assert resumed["label"] == "proj-a-restored"
    store.observe_session(made["id"], "sess-2")
    assert store.get(made["id"])["session_ids"] == ["sess-1", "sess-2"]


def test_restoring_a_session_that_never_had_a_mandate_invents_none(store):
    _make(store)
    assert store.resume("sess-unknown", label="x", unit="u") is None


# -- the join -------------------------------------------------------------------------


def test_join_prefers_the_id_the_process_carries(store):
    a = _make(store, label="a", unit="u-a")
    b = _make(store, label="b", unit="u-b")
    # The unit says b; the process itself carries a's id. The process wins.
    found = mandate.join(store.all(), pid=42, unit="u-b", session_id=None,
                         env_reader=lambda pid: a["id"])
    assert found["id"] == a["id"]
    assert b["id"] != a["id"]


def test_join_survives_an_owner_restart_by_unit_and_by_session(store):
    made = _make(store, label="a", unit="set-agent-a.scope")
    store.observe_session(made["id"], "sess-9")
    records = store.all()
    nothing = lambda pid: None  # noqa: E731 — the owner is gone and the env is unreadable
    assert mandate.join(records, pid=7, unit="set-agent-a.scope", env_reader=nothing)["id"] == made["id"]
    assert mandate.join(records, pid=7, unit=None, session_id="sess-9", env_reader=nothing)["id"] == made["id"]
    assert mandate.join(records, pid=7, unit="other", session_id="sess-x", env_reader=nothing) is None


def test_join_by_unit_ignores_an_ended_mandate(store):
    made = _make(store, label="a", unit="u-a")
    store.end(made["id"], "stopped")
    # A new agent reusing the label and unit must not inherit the old goal.
    assert mandate.join(store.all(), pid=None, unit="u-a", env_reader=lambda pid: None) is None


def test_mandate_id_of_pid_reads_the_process_environment(tmp_path):
    proc = tmp_path / "proc" / "4242"
    proc.mkdir(parents=True)
    (proc / "environ").write_bytes(b"HOME=/h\0SET_FLEET_MANDATE=m-abc123\0TERM=xterm\0")
    assert mandate.mandate_id_of_pid(4242, proc_root=str(tmp_path / "proc")) == "m-abc123"
    assert mandate.mandate_id_of_pid(1, proc_root=str(tmp_path / "proc")) is None
    (proc / "environ").write_bytes(b"HOME=/h\0NOT_SET_FLEET_MANDATE=m-zzz\0")
    assert mandate.mandate_id_of_pid(4242, proc_root=str(tmp_path / "proc")) is None


# -- robustness -----------------------------------------------------------------------


def test_an_unreadable_store_is_an_error_and_never_an_empty_store(store):
    _make(store)
    with open(store.path, "w") as handle:
        handle.write('{"version": 1, "mandates": {"m-1": {"id": "m-1", "go')  # truncated
    with pytest.raises(MandateStoreUnreadable):
        store.all()
    # And a write must not paper over it: the truncated file is still there afterwards.
    with pytest.raises(MandateStoreUnreadable):
        _make(store)
    assert open(store.path).read().endswith('"go')


def test_concurrent_writers_lose_nothing(store):
    errors = []

    def writer(n):
        try:
            for i in range(8):
                _make(MandateStore(store.path), label=f"w{n}-{i}", unit=f"u-{n}-{i}")
        except Exception as exc:  # pragma: no cover - the assertion below reports it
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(store.all()) == 48


def test_update_refuses_text_fields(store):
    made = _make(store)
    with pytest.raises(MandateError):
        store.update(made["id"], goal="something else")
    assert store.get(made["id"])["goal"] == "ship the importer"


def test_public_carries_no_store_internals(store):
    made = _make(store)
    shown = mandate.public(store.get(made["id"]))
    assert shown["goal"] == "ship the importer"
    for internal in ("unit", "session_ids", "cwd", "carrier"):
        assert internal not in shown


# -- the operator's words never reach a log ---------------------------------------------


def test_goal_text_reaches_no_log_record_and_no_exception(store, caplog):
    caplog.set_level(logging.DEBUG)
    made = _make(store, goal=f"do the {MARKER} thing", done_when=f"when {MARKER} holds",
                 scope={"paths": [f"src/{MARKER}/"], "change": MARKER})
    store.observe_session(made["id"], "sess-1")
    store.mark_delivered(made["id"])
    store.update(made["id"], label="renamed")
    store.end(made["id"], "stopped")
    store.resume("sess-1", label="again", unit="u2")
    store.end_missing([])
    with pytest.raises(MandateError) as err:
        store.update(made["id"], goal=MARKER)
    assert caplog.records, "nothing was logged, so this test would prove nothing"
    for record in caplog.records:
        assert MARKER not in record.getMessage()
    assert MARKER not in str(err.value)
