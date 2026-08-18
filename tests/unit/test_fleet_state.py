"""What an agent is doing — the measured state, and the one thing only the record knows.

Split out of `test_fleet_discovery.py` on 2026-08-19: state tests had accumulated
in a file named for discovery, which is the name-broader-than-the-content defect
this change keeps finding elsewhere. Discovery answers WHO is running; this
answers WHAT they are doing, and the two read different sources on purpose.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from set_orch.fleet import state
from set_orch.fleet.state import read_state


# --------------------------------------------------------------------------- #
# state
# --------------------------------------------------------------------------- #

def _log(tmp_path: Path, entries: list[dict]) -> str:
    p = tmp_path / "session.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return str(p)


def _assistant(tool_id: str, name: str, ts: str, sidechain: bool = False) -> dict:
    return {"type": "assistant", "isSidechain": sidechain, "timestamp": ts,
            "message": {"content": [{"type": "tool_use", "id": tool_id, "name": name}]}}


def _result(tool_id: str, ts: str, sidechain: bool = False) -> dict:
    return {"type": "user", "isSidechain": sidechain, "timestamp": ts,
            "message": {"content": [{"type": "tool_result", "tool_use_id": tool_id}]}}


def test_an_outstanding_tool_call_is_what_working_means(tmp_path):
    log = _log(tmp_path, [
        _assistant("t1", "Read", "2026-08-18T08:00:00.000Z"),
        _result("t1", "2026-08-18T08:00:01.000Z"),
        _assistant("t2", "Bash", "2026-08-18T08:00:02.000Z"),
    ])
    st = state.read_state(log)
    assert st.state == "working"
    assert st.tool == "Bash"


def test_a_closed_call_is_quiet_not_working(tmp_path):
    log = _log(tmp_path, [
        _assistant("t1", "Bash", "2026-08-18T08:00:00.000Z"),
        _result("t1", "2026-08-18T08:00:01.000Z"),
    ])
    assert state.read_state(log).state == "quiet"


def test_a_sub_agent_s_call_does_not_make_the_parent_working(tmp_path):
    """A session's own task children are out of this capability's scope. Counting
    their calls would report the parent as working on a tool it never invoked.
    """
    log = _log(tmp_path, [
        _assistant("t1", "Bash", "2026-08-18T08:00:00.000Z"),
        _result("t1", "2026-08-18T08:00:01.000Z"),
        _assistant("t9", "Grep", "2026-08-18T08:00:02.000Z", sidechain=True),
    ])
    assert state.read_state(log).state == "quiet"


@pytest.mark.parametrize("case,reason_fragment", [
    ("absent", "no session log"),
    ("missing", "does not exist"),
    ("empty", "no parsable entry"),
])
def test_a_state_that_cannot_be_determined_is_unknown_never_idle(tmp_path, case, reason_fragment):
    """Three different ways of knowing nothing, and none of them may collapse to
    a calm answer. `quiet` claims the log was read and no call was outstanding;
    saying that about a log that does not exist is a false value, and its fail
    direction is the reassuring one — someone leaves the agent alone.
    """
    if case == "absent":
        log = None
    elif case == "missing":
        log = str(tmp_path / "nope.jsonl")
    else:
        log = _log(tmp_path, [])
        Path(log).write_text("not json at all\n")

    st = state.read_state(log)
    assert st.state == "unknown"
    assert st.state != "idle"
    assert st.reason and reason_fragment in st.reason


def test_last_movement_comes_from_the_log_not_from_a_status_field(tmp_path):
    """Measured 2026-08-18 across 23 live sessions: the runtime's `status` field
    had a median age of 11 hours and a maximum of 83, while the log's mtime is
    the moment itself.

    ⚠ **NARROWED 2026-08-19, and the narrowing is the point rather than a
    concession.** This used to assert that the string `status` appeared nowhere
    in `state.py` at all — a whole-module ban, which is a blunt instrument that
    happens to work until the module legitimately needs the word. Task 3.8 is
    exactly that case: the log cannot tell *stopped at a prompt* from *finished
    its turn*, so `waiting` can only come from the record's declared status.

    So the ban is now on the thing it was protecting: **no measured value may be
    derived from the declaration.** Movement comes from the mtime and working
    comes from the log's structure, both with a record present that says
    something else entirely — which is a stronger check than the string ban was,
    because it survives a rename.
    """
    log = _log(tmp_path, [_assistant("t1", "Bash", "2026-08-18T08:00:00.000Z")])
    old = time.time() - 600
    os.utime(log, (old, old))

    lying = {"status": "idle", "statusUpdatedAt": 0, "waitingFor": "nothing"}
    st = state.read_state(log, record=lying)
    assert st.last_movement_age is not None
    assert 570 < st.last_movement_age < 630, "movement was taken from the record"
    assert st.state == "working", "an outstanding call was overruled by a declaration"
    assert st.tool == "Bash"
    assert st.waiting_for is None, "a reason leaked from a record that did not claim waiting"


def test_listing_does_not_read_a_whole_log(tmp_path):
    """Task 3.6 — the list path is stat + a bounded tail. A fleet of 20 agents
    with multi-megabyte transcripts must not become a full parse per row.
    """
    p = tmp_path / "big.jsonl"
    filler = json.dumps({"type": "system", "message": {"content": []}})
    with open(p, "w") as fh:
        for _ in range(60000):
            fh.write(filler + "\n")
        fh.write(json.dumps(_assistant("t1", "Bash", "2026-08-18T08:00:00.000Z")) + "\n")
    assert p.stat().st_size > state.TAIL_BYTES * 2
    lines = state._tail(str(p))
    assert len(lines) < 60000
    assert state.read_state(str(p)).state == "working"

# --------------------------------------------------------------------------- #
# waiting for a person — task 3.8
# --------------------------------------------------------------------------- #

def _finished_turn(tmp_path):
    path = tmp_path / "finished.jsonl"
    path.write_text(json.dumps(
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "done"}]}}
    ) + "\n", encoding="utf-8")
    return str(path)


def _mid_call(tmp_path):
    path = tmp_path / "working.jsonl"
    path.write_text(json.dumps({
        "type": "assistant", "timestamp": "2026-08-19T00:00:00.000Z",
        "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Bash"}]},
    }) + "\n", encoding="utf-8")
    return str(path)


def test_waiting_comes_from_the_record_because_the_log_cannot_produce_it(tmp_path):
    """The division of labour, and it is the finding rather than the code.

    The log tells working from not-working structurally. It cannot tell *stopped
    at a prompt* from *finished its turn* — both are a turn that ended — so a
    surface reading only the log renders a person-blocking agent as quiet, which
    is the reading someone acts on by leaving it alone.
    """
    log = _finished_turn(tmp_path)
    assert read_state(log).state == "quiet"
    state = read_state(log, record={"status": "waiting", "waitingFor": "input needed"})
    assert state.state == "waiting"
    assert state.waiting_for == "input needed"


def test_a_record_claiming_waiting_while_a_call_is_outstanding_is_ignored(tmp_path):
    """The measurement wins, and the disagreement is CARRIED rather than dropped.

    This is the staleness that actually fires: measured 2026-08-19 on 22 live
    records, one still said `busy` while its log showed no outstanding call. A
    contradiction the surface cannot see is one nobody will ever fix.
    """
    state = read_state(_mid_call(tmp_path), record={"status": "waiting"})
    assert state.state == "working"
    assert state.declaration_ignored == "waiting"


def test_no_record_is_not_the_same_as_not_waiting(tmp_path):
    """An agent nobody could ask about must not be reported as one that answered.
    """
    state = read_state(_finished_turn(tmp_path), record=None)
    assert state.state == "quiet"
    assert state.waiting_for is None


def test_a_waiting_record_without_a_reason_still_reports_waiting(tmp_path):
    """The reason is what the runtime happened to write. Requiring it would drop
    the state itself whenever the field is absent — losing the more important
    half to keep the decorative one.
    """
    state = read_state(_finished_turn(tmp_path), record={"status": "waiting"})
    assert state.state == "waiting"
    assert state.waiting_for is None


def test_a_record_saying_anything_else_does_not_become_waiting(tmp_path):
    """Measured on this machine: `idle` 11, `shell` 9, `busy` 1, `waiting` 1.
    Only one of those is a claim about a PERSON being needed, and treating the
    others as waiting would put a permanent false alarm on the screen.
    """
    for status in ("idle", "shell", "busy", "", None):
        state = read_state(_finished_turn(tmp_path), record={"status": status})
        assert state.state == "quiet", status
