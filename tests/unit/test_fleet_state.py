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
    # Added 2026-08-19 for task 9.4: a log that EXISTS and cannot be read is a
    # fourth way of knowing nothing, and it is the one an agent hits in practice
    # — a permission or a filesystem error, not an absent file. Without it the
    # parametrisation named three causes and covered three of four.
    ("unreadable", "could not be read"),
])
def test_a_state_that_cannot_be_determined_is_unknown_never_idle(tmp_path, case, reason_fragment):
    """Four different ways of knowing nothing, and none of them may collapse to
    a calm answer. `quiet` claims the log was read and no call was outstanding;
    saying that about a log that does not exist is a false value, and its fail
    direction is the reassuring one — someone leaves the agent alone.

    The fourth case, `unreadable`, was added for task 9.4 and is the one an agent
    actually hits: the file exists and a permission or filesystem error stops the
    read. A file that is absent and a file that cannot be read take different
    code paths, and only one of them was covered.
    """
    if case == "absent":
        log = None
    elif case == "missing":
        log = str(tmp_path / "nope.jsonl")
    elif case == "unreadable":
        log = _log(tmp_path, [])
        Path(log).write_text('{"type": "assistant"}\n')
        os.chmod(log, 0o000)
        if os.geteuid() == 0:
            pytest.skip("running as root, the permission cannot be made to fail")
    else:
        log = _log(tmp_path, [])
        Path(log).write_text("not json at all\n")

    try:
        st = state.read_state(log)
    finally:
        if case == "unreadable":
            os.chmod(log, 0o644)
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


# --------------------------------------------------------------------------- #
# the tile's excerpt — task 7.3
# --------------------------------------------------------------------------- #

def _line(role, content):
    return json.dumps({"type": role, "message": {"role": role, "content": content}})


def test_the_excerpt_is_the_last_thing_actually_said():
    from set_orch.fleet.state import _last_text
    lines = [
        _line("user", [{"type": "text", "text": "az első kérdés"}]),
        _line("assistant", [{"type": "text", "text": "a válasz"}]),
        _line("assistant", [{"type": "text", "text": "a LEGUTOLSÓ mondat"}]),
    ]
    assert _last_text(lines) == ("a LEGUTOLSÓ mondat", "agent")


def test_tool_traffic_is_skipped_rather_than_shown():
    """A tile showing `Bash` tells the reader nothing the state line does not
    already say, and a thinking block shows something the conversation never
    contained. So the newest entries here are deliberately not text.
    """
    from set_orch.fleet.state import _last_text
    lines = [
        _line("assistant", [{"type": "text", "text": "amit mondott"}]),
        _line("assistant", [{"type": "thinking", "thinking": "belső gondolat"}]),
        _line("assistant", [{"type": "tool_use", "name": "Bash", "input": {}}]),
        _line("user", [{"type": "tool_result", "content": "kimenet"}]),
    ]
    assert _last_text(lines) == ("amit mondott", "agent")


def test_a_tail_with_no_text_is_ABSENT_not_empty():
    """The false-absence rule, applied to the tile: a tail made entirely of tool
    traffic means *nothing was said recently*. An empty string would render as
    *nothing was ever said*, which is a different claim and a wrong one.
    """
    from set_orch.fleet.state import _last_text
    lines = [_line("assistant", [{"type": "tool_use", "name": "Bash", "input": {}}])]
    assert _last_text(lines) == (None, None)


def test_the_speaker_is_carried_because_the_same_sentence_means_two_things():
    from set_orch.fleet.state import _last_text
    assert _last_text([_line("user", [{"type": "text", "text": "csináld meg"}])]) == (
        "csináld meg", "user",
    )


def test_a_plain_string_content_is_read_too():
    """Both shapes occur in a real log; reading only the block shape would drop
    every plain-text entry and report ABSENT for a session full of them.
    """
    from set_orch.fleet.state import _last_text
    assert _last_text([_line("user", "sima szöveg")]) == ("sima szöveg", "user")


def test_a_long_utterance_is_cut_and_says_so():
    from set_orch.fleet.state import EXCERPT_CHARS, _last_text
    text, who = _last_text([_line("assistant", [{"type": "text", "text": "x" * 5000}])])
    assert who == "agent"
    assert len(text) == EXCERPT_CHARS
    assert text.endswith("…"), "a cut that does not show it is a cut reads as the whole sentence"


def test_unparsable_and_foreign_lines_do_not_stop_the_search():
    """A tail is cut at an arbitrary byte and holds whatever the runtime wrote,
    so a broken line is ordinary. Stopping at the first one would make the
    excerpt depend on where the tail happened to start.
    """
    from set_orch.fleet.state import _last_text
    lines = [
        _line("assistant", [{"type": "text", "text": "a keresett mondat"}]),
        '{"type":"summary","summary":"nem üzenet"}',
        '{"broken json',
        "",
    ]
    assert _last_text(lines) == ("a keresett mondat", "agent")


def test_whitespace_is_collapsed_so_a_tile_stays_one_line():
    from set_orch.fleet.state import _last_text
    text, _ = _last_text([_line("assistant", [{"type": "text", "text": "első\n\n  második\ttab"}])])
    assert text == "első második tab"


def test_read_state_carries_the_excerpt_on_a_quiet_agent(tmp_path):
    """The excerpt comes from the SAME read the state pass already does — this
    asserts it arrives through `read_state`, not only from the helper.
    """
    from set_orch.fleet.state import read_state
    log = tmp_path / "s.jsonl"
    log.write_text(_line("assistant", [{"type": "text", "text": "készen vagyok"}]) + "\n")
    st = read_state(str(log))
    assert st.state == "quiet"
    assert (st.excerpt, st.excerpt_from) == ("készen vagyok", "agent")


# --------------------------------------------------------------------------- #
# blocked on a person — the structural floor under PM mode
# --------------------------------------------------------------------------- #

def _text(role: str, text: str, ts: str, sidechain: bool = False) -> dict:
    return {"type": role, "isSidechain": sidechain, "timestamp": ts,
            "message": {"role": role, "content": [{"type": "text", "text": text}]}}


@pytest.mark.parametrize("tool", sorted(state.QUESTION_TOOLS))
def test_an_outstanding_question_tool_is_asking_not_work(tmp_path, tool):
    """The whole finding: this call is outstanding while the PERSON thinks.

    Measured 2026-08-20 on a real log — the `tool_use` lands 8m13s, 9m32s and
    1m43s before its `tool_result`. Until this test the state was `working`,
    which is the reassuring direction: the one blockage a reader can clear
    immediately rendered as the case that needs nothing from them.
    """
    log = _log(tmp_path, [_assistant("q1", tool, "2026-08-20T08:00:00.000Z")])
    st = read_state(log, now=_epoch_of("2026-08-20T08:05:00.000Z"))
    assert st.state == state.ASKING
    assert st.state != state.WORKING
    assert st.tool == tool
    assert st.tool_elapsed == pytest.approx(300, abs=2)


@pytest.mark.parametrize("tool", sorted(state.QUESTION_TOOLS))
def test_a_question_tool_that_has_been_answered_is_not_a_blockage(tmp_path, tool):
    log = _log(tmp_path, [
        _assistant("q1", tool, "2026-08-20T08:00:00.000Z"),
        _result("q1", "2026-08-20T08:01:00.000Z"),
    ])
    assert read_state(log).state == state.QUIET


def test_an_undeclared_tool_is_work_whatever_it_is_named(tmp_path):
    """The list is a list, and nothing is inferred from a name.

    `Bash` is the case that makes it matter: a permission prompt and a slow
    command are the SAME log entry, so anything that promoted `Bash` by elapsed
    time would queue every long-running command.
    """
    log = _log(tmp_path, [_assistant("t1", "Bash", "2026-08-20T08:00:00.000Z")])
    assert read_state(log).state == state.WORKING


def test_the_question_tool_is_named_even_when_an_older_call_is_open(tmp_path):
    """Naming the oldest call would describe a fact that is not the reason."""
    log = _log(tmp_path, [
        _assistant("t1", "Bash", "2026-08-20T08:00:00.000Z"),
        _assistant("q1", "AskUserQuestion", "2026-08-20T08:00:30.000Z"),
    ])
    st = read_state(log)
    assert st.state == state.ASKING
    assert st.tool == "AskUserQuestion"
    assert "Bash" in st.other_tools


def test_a_record_saying_waiting_is_not_a_conflict_with_asking(tmp_path):
    """`waiting` AGREES with `blocked`; only `working` contradicts it."""
    log = _log(tmp_path, [_assistant("q1", "AskUserQuestion", "2026-08-20T08:00:00.000Z")])
    st = read_state(log, record={"status": "waiting"})
    assert st.state == state.ASKING
    assert st.declaration_ignored is None


# --------------------------------------------------------------------------- #
# resumed_since — and why a user entry proves nothing
# --------------------------------------------------------------------------- #

def _epoch_of(iso: str) -> float:
    from datetime import datetime
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


POINT = "2026-08-20T08:00:00.000Z"


def test_an_interrupt_is_not_a_resumption(tmp_path):
    """MEASURED SHAPE, not an invented one.

    `itline-web/349ee01c…jsonl`, 2026-08-19: interrupting a session writes a
    `user` entry whose text is exactly this. A reader that treats "a new user
    entry appeared" as an answer therefore advances the queue on Esc — the
    freeze this exists to provide, broken by the obvious implementation.
    """
    log = _log(tmp_path, [
        _text("assistant", "Shall I go ahead?", "2026-08-20T07:59:00.000Z"),
        _text("user", "[Request interrupted by user]", "2026-08-20T08:01:00.000Z"),
    ])
    assert state.resumed_since(log, POINT) == state.NOT_RESUMED


def test_a_bare_user_entry_check_would_not_have_caught_it(tmp_path):
    """Holds the REFUTED pattern, so reverting to it fails instead of looking equal.

    Any repair that recognises the runtime's synthetic markers by their text is
    a second copy of somebody else's format. This asserts the shape that such a
    repair would get wrong: an ordinary-looking user message, with no marker in
    it at all, is still not a resumption — because resumption is about the
    AGENT moving, not about the person speaking.
    """
    log = _log(tmp_path, [
        _text("assistant", "Shall I go ahead?", "2026-08-20T07:59:00.000Z"),
        _text("user", "yes please", "2026-08-20T08:01:00.000Z"),
    ])
    assert state.resumed_since(log, POINT) == state.NOT_RESUMED


def test_a_new_assistant_utterance_is_a_resumption(tmp_path):
    log = _log(tmp_path, [
        _text("assistant", "Shall I go ahead?", "2026-08-20T07:59:00.000Z"),
        _text("user", "yes please", "2026-08-20T08:01:00.000Z"),
        _text("assistant", "Right — starting now.", "2026-08-20T08:01:30.000Z"),
    ])
    assert state.resumed_since(log, POINT) == state.RESUMED


def test_a_new_tool_call_is_a_resumption(tmp_path):
    log = _log(tmp_path, [
        _text("assistant", "Shall I go ahead?", "2026-08-20T07:59:00.000Z"),
        _assistant("t9", "Bash", "2026-08-20T08:02:00.000Z"),
    ])
    assert state.resumed_since(log, POINT) == state.RESUMED


def test_an_unreadable_log_does_not_report_resumption(tmp_path):
    assert state.resumed_since(str(tmp_path / "nope.jsonl"), POINT) == state.RESUMPTION_UNKNOWN
    assert state.resumed_since(None, POINT) == state.RESUMPTION_UNKNOWN


def test_an_unparsable_point_is_unknown_not_negative(tmp_path):
    log = _log(tmp_path, [_text("assistant", "hi", "2026-08-20T08:01:00.000Z")])
    assert state.resumed_since(log, None) == state.RESUMPTION_UNKNOWN
    assert state.resumed_since(log, "not-a-timestamp") == state.RESUMPTION_UNKNOWN


def test_a_point_older_than_the_tail_is_unknown_not_not_resumed(tmp_path):
    """A negative needs the boundary in view; a positive does not."""
    log = _log(tmp_path, [_text("user", "later", "2026-08-20T09:00:00.000Z")])
    assert state.resumed_since(log, POINT) == state.RESUMPTION_UNKNOWN


def test_a_sub_agent_s_turn_is_not_the_parent_resuming(tmp_path):
    log = _log(tmp_path, [
        _text("assistant", "Shall I go ahead?", "2026-08-20T07:59:00.000Z"),
        _assistant("s1", "Bash", "2026-08-20T08:02:00.000Z", sidechain=True),
    ])
    assert state.resumed_since(log, POINT) == state.NOT_RESUMED
