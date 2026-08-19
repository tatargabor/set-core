"""Group 4 — carrying an instruction out, and reporting what became of it.

Every test here is written against the RESULT rather than the mechanism. A test
asserting that the send call was made passes identically on all four outcomes,
because the call succeeds in every one of them — so the fixture drives the
states apart explicitly and the assertion is on the reported outcome.
"""

from __future__ import annotations

import json
import os
import stat

import pytest

from set_orch.fleet import instruct
from set_orch.fleet import state as agent_state


# --------------------------------------------------------------------------- #
# fixtures — a fake bus and a fake /proc
# --------------------------------------------------------------------------- #


def _fake_sac(tmp_path, stdout: str = "", stderr: str = "", code: int = 0):
    """A `sac` that answers exactly what a case needs, and records its argv."""
    argv_log = tmp_path / "argv.log"
    script = tmp_path / "sac"
    script.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" >> {argv_log}\n'
        f"cat <<'OUT'\n{stdout}\nOUT\n"
        f"cat >&2 <<'ERR'\n{stderr}\nERR\n"
        f"exit {code}\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(script), argv_log


def _proc(tmp_path, pid: int, argv, env: dict | None = None, cwd: str = "/tmp"):
    """One entry in a fake /proc, byte-identical in shape to the real thing."""
    d = tmp_path / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    blob = b"".join(f"{k}={v}".encode() + b"\0" for k, v in (env or {}).items())
    (d / "environ").write_bytes(blob)
    target = tmp_path / f"cwd-{pid}"
    target.mkdir(exist_ok=True)
    os.symlink(target, d / "cwd")
    return d


SEAT = instruct.Seat(seat="proj#aaaa", agent="proj", session="aaaa-1111", liveness="live")


# --------------------------------------------------------------------------- #
# 4.1 — addressed, or refused; never broadcast
# --------------------------------------------------------------------------- #


def test_an_addressed_instruction_names_the_seat_on_the_wire(tmp_path):
    """4.1 — the send is addressed, and the address is the seat, not the project."""
    sac, log = _fake_sac(tmp_path, stdout=json.dumps(
        {"room": "proj", "wakes": ["proj#aaaa"]}))
    report = instruct.send_instruction(SEAT, "csináld meg", sac_bin=sac)
    assert report.accepted is True
    assert "--to proj#aaaa" in log.read_text()


def test_an_unresolvable_addressee_is_refused_and_not_broadcast(tmp_path):
    """4.1 — the channel refuses, and the refusal is carried through unchanged.

    The dangerous repair is the tempting one: drop `--to` and send it to the
    room. That would deliver a message meant for one session to everyone who can
    read it, at exactly the moment the sender was told the address was wrong.
    """
    sac, log = _fake_sac(
        tmp_path, stderr="send: nobody in 'proj' is called 'ismeretlen#dead'", code=1)
    report = instruct.send_instruction(SEAT, "csináld meg", sac_bin=sac)
    assert report.outcome == instruct.REFUSED
    assert report.accepted is False
    assert "nobody in" in (report.reason or "")
    # exactly one send attempt, and it carried an address
    lines = [l for l in log.read_text().splitlines() if l.strip()]
    assert len(lines) == 1, lines
    assert "--to" in lines[0]


def test_an_instruction_defaults_to_a_type_that_claims_attention(tmp_path):
    """A FACT with an errand inside it wakes nobody by the channel's own rule."""
    sac, log = _fake_sac(tmp_path, stdout=json.dumps({"room": "proj", "wakes": []}))
    instruct.send_instruction(SEAT, "csináld meg", sac_bin=sac)
    assert "REQUEST" in log.read_text()


# --------------------------------------------------------------------------- #
# 4.2 / 9.2 — the four outcomes, driven apart
# --------------------------------------------------------------------------- #


def _waiter(session="aaaa-1111", pid=4242):
    return instruct.Waiter(pid=pid, session=session)


def test_a_woken_seat_with_a_live_waiter_arrives_now(tmp_path):
    sac, _ = _fake_sac(tmp_path, stdout=json.dumps({"room": "proj", "wakes": ["proj#aaaa"]}))
    report = instruct.send_instruction(
        SEAT, "x", sac_bin=sac, waiters=[_waiter()], state=agent_state.QUIET)
    assert report.outcome == instruct.ARRIVES_NOW
    assert report.delivered_to_agent is True


def test_a_working_agent_without_a_waiter_arrives_at_the_end_of_the_turn(tmp_path):
    sac, _ = _fake_sac(tmp_path, stdout=json.dumps({"room": "proj", "wakes": ["proj#aaaa"]}))
    report = instruct.send_instruction(
        SEAT, "x", sac_bin=sac, waiters=[], state=agent_state.WORKING)
    assert report.outcome == instruct.AT_TURN_END
    assert report.delivered_to_agent is True


def test_an_idle_agent_without_a_waiter_sits_unread(tmp_path):
    """The one outcome where nothing will happen until a person types."""
    sac, _ = _fake_sac(tmp_path, stdout=json.dumps({"room": "proj", "wakes": ["proj#aaaa"]}))
    report = instruct.send_instruction(
        SEAT, "x", sac_bin=sac, waiters=[], state=agent_state.QUIET)
    assert report.outcome == instruct.SITS_UNREAD
    assert report.delivered_to_agent is False


def test_an_entry_that_wakes_nobody_is_reported_as_such(tmp_path):
    sac, _ = _fake_sac(tmp_path, stdout=json.dumps(
        {"room": "proj", "wakes": [], "notice": ["This wakes NOBODY — 1 live seat(s)…"]}))
    report = instruct.send_instruction(
        SEAT, "x", sac_bin=sac, waiters=[_waiter()], state=agent_state.WORKING)
    assert report.outcome == instruct.WAKES_NOBODY
    assert report.notices and "NOBODY" in report.notices[0]


def test_a_waiter_for_another_session_does_not_count(tmp_path):
    """The join is the session id. A waiter next door is not this agent's waiter."""
    sac, _ = _fake_sac(tmp_path, stdout=json.dumps({"room": "proj", "wakes": ["proj#aaaa"]}))
    report = instruct.send_instruction(
        SEAT, "x", sac_bin=sac, waiters=[_waiter(session="valaki-mas")],
        state=agent_state.QUIET)
    assert report.waiters == 0
    assert report.outcome == instruct.SITS_UNREAD


def test_an_unknown_answer_is_never_upgraded_to_delivered(tmp_path):
    """The call succeeded and said nothing about what it did. That is an admission."""
    sac, _ = _fake_sac(tmp_path, stdout=json.dumps({"room": "proj", "status": "queued"}))
    report = instruct.send_instruction(SEAT, "x", sac_bin=sac)
    assert report.outcome == instruct.UNKNOWN
    assert report.accepted is True
    assert report.delivered_to_agent is False


def test_an_unparseable_answer_is_unknown_rather_than_a_failure(tmp_path):
    sac, _ = _fake_sac(tmp_path, stdout="Sent!")
    report = instruct.send_instruction(SEAT, "x", sac_bin=sac)
    assert report.outcome == instruct.UNKNOWN
    assert report.delivered_to_agent is False


def test_the_send_calls_success_is_not_an_outcome(tmp_path):
    """4.2 — `accepted` and `outcome` are two facts and only one is a delivery."""
    sac, _ = _fake_sac(tmp_path, stdout=json.dumps({"room": "proj"}))
    report = instruct.send_instruction(SEAT, "x", sac_bin=sac)
    assert report.accepted is True and report.delivered_to_agent is False


def test_an_empty_wakes_list_is_not_the_same_as_no_answer(tmp_path):
    """`[]` is a measurement; `None` is an admission. Collapsing them loses the case."""
    sac, _ = _fake_sac(tmp_path, stdout=json.dumps({"room": "proj", "wakes": []}))
    measured = instruct.send_instruction(SEAT, "x", sac_bin=sac)
    other = tmp_path / "b"
    other.mkdir()
    sac2, _ = _fake_sac(other, stdout=json.dumps({"room": "proj"}))
    admitted = instruct.send_instruction(SEAT, "x", sac_bin=sac2)
    assert measured.wakes == [] and admitted.wakes is None
    assert measured.outcome != admitted.outcome


# --------------------------------------------------------------------------- #
# 4.5 — a hold has a clock
# --------------------------------------------------------------------------- #


def test_a_held_message_is_never_counted_as_reaching_the_agent():
    held = instruct.DeliveryReport(outcome=instruct.HELD, accepted=True, seat="proj#aaaa")
    assert held.delivered_to_agent is False


def test_a_hold_is_not_a_resting_state():
    """It expires on its own, so nothing may treat it as settled."""
    held = instruct.DeliveryReport(outcome=instruct.HELD, accepted=True, seat="proj#aaaa")
    assert held.settled is False
    assert instruct.HELD not in instruct.TERMINAL_OUTCOMES


def test_a_lapse_replaces_the_earlier_outcome_rather_than_standing_beside_it():
    """4.5 — the surface that showed `held` must stop showing it."""
    held = instruct.DeliveryReport(outcome=instruct.HELD, accepted=True,
                                   seat="proj#aaaa", room="proj")
    lapsed = held.lapsed()
    assert lapsed.outcome == instruct.EXPIRED
    assert lapsed.superseded == instruct.HELD
    assert lapsed.delivered_to_agent is False
    assert lapsed.settled is True
    assert lapsed.seat == held.seat and lapsed.room == held.room


# --------------------------------------------------------------------------- #
# 4.3 — the bell carries no content
# --------------------------------------------------------------------------- #


def test_the_bell_cannot_carry_a_message_at_all():
    """4.3 — the prohibition is a SIGNATURE, not a rule.

    A rule saying "do not put the text here" is one keyword argument away from
    being broken, and the break would be invisible: the message would arrive and
    the durable record would simply not exist. So the check is that no parameter
    can hold it.
    """
    import inspect
    params = inspect.signature(instruct.ring_mailbox_check).parameters
    assert set(params) == {"seat", "transport"}


def test_with_no_direct_channel_nothing_is_attempted():
    result = instruct.ring_mailbox_check(SEAT)
    assert result.rung is False and "no direct channel" in (result.reason or "")


def test_a_bell_that_throws_does_not_break_the_delivery():
    def broken(_seat):
        raise RuntimeError("a socket nem elérhető")
    result = instruct.ring_mailbox_check(SEAT, transport=broken)
    assert result.rung is False and "refused" in (result.reason or "")


def test_the_bell_receives_the_seat_and_only_the_seat():
    seen = []
    instruct.ring_mailbox_check(SEAT, transport=lambda s: seen.append(s) or True)
    assert seen == ["proj#aaaa"]


# --------------------------------------------------------------------------- #
# 4.4 — an agent that cannot be instructed says why
# --------------------------------------------------------------------------- #


def test_an_agent_without_a_seat_is_observable_but_not_instructable():
    result = instruct.instructability("nincs-ilyen", {})
    assert result.instructable is False
    assert result.reason == instruct.NO_SEAT


def test_no_bus_at_all_is_a_different_reason_from_no_seat():
    """Three negatives, and only one of them is about the agent."""
    assert instruct.instructability("x", None).reason == instruct.BUS_UNREADABLE
    assert instruct.instructability(None, {}).reason == instruct.NO_SESSION
    assert instruct.instructability("x", {}).reason == instruct.NO_SEAT


def test_an_unreadable_bus_is_not_reported_as_an_empty_one(tmp_path):
    """False absence, in the direction that marks every agent unreachable."""
    assert instruct.read_seats(sac_bin=str(tmp_path / "nincs-ilyen-parancs")) is None


def test_a_seat_is_found_by_session_id_and_never_by_name(tmp_path):
    roster = {"agents": [{"agent": "proj", "project": "/p", "rooms": ["proj"], "seats": [
        {"seat": "proj#aaaa", "session": "aaaa-1111", "liveness": "live"},
        {"seat": "proj#bbbb", "session": "bbbb-2222", "liveness": "gone"},
    ]}]}
    sac, _ = _fake_sac(tmp_path, stdout=json.dumps(roster))
    seats = instruct.read_seats(sac_bin=sac)
    assert set(seats) == {"aaaa-1111", "bbbb-2222"}
    assert seats["aaaa-1111"].seat == "proj#aaaa"
    assert instruct.seat_for("aaaa-1111", seats).liveness == "live"
    assert instruct.seat_for("nincs", seats) is None


def test_a_seat_without_a_session_is_not_a_candidate(tmp_path):
    """Several processes share that file; it cannot be addressed as one agent."""
    roster = {"agents": [{"agent": "proj", "seats": [
        {"seat": "proj", "session": None, "liveness": "live"}]}]}
    sac, _ = _fake_sac(tmp_path, stdout=json.dumps(roster))
    assert instruct.read_seats(sac_bin=sac) == {}


# --------------------------------------------------------------------------- #
# 4.6 / 9.14 — orphaned waiters, in the dangerous direction
# --------------------------------------------------------------------------- #

NODE = "/usr/bin/node"
SACJS = "/home/x/set-agent-comm/bin/sac.mjs"


def test_a_waiter_is_an_identity_and_not_a_match_count(tmp_path):
    """9.14 — a candidate produced by the CHECKING command must not be offered.

    The first count of these was too optimistic because the counting command's
    own command line contained the pattern it searched for. Three impostors
    here, all of which a substring test would take:
    """
    _proc(tmp_path, 100, [NODE, SACJS, "wait", "szoba"],
          {"CLAUDE_CODE_SESSION_ID": "elo-1"})
    _proc(tmp_path, 200, ["grep", "-af", "sac.mjs wait"])          # the checker
    _proc(tmp_path, 300, ["/bin/bash", "-c", "pgrep -af 'sac.mjs wait' | wc -l"])
    _proc(tmp_path, 400, ["python3", "-c", "print('sac.mjs wait')"])
    found = instruct.live_waiters(proc_root=str(tmp_path))
    assert [w.pid for w in found] == [100]


def test_a_bare_substring_check_would_not_have_caught_it(tmp_path):
    """Held so a 'simplification' back to `"sac.mjs wait" in cmdline` fails here.

    A comment asks to be believed; a test refuses to be reverted.
    """
    _proc(tmp_path, 200, ["grep", "-af", "sac.mjs wait"])
    naive = "sac.mjs wait" in " ".join(["grep", "-af", "sac.mjs wait"])
    assert naive is True                       # what the wrong check would say
    assert instruct.live_waiters(proc_root=str(tmp_path)) == []   # what this one says


def test_only_a_dead_session_is_offered(tmp_path):
    """9.14 — one dead, one live, one undeterminable; only the first is offered."""
    _proc(tmp_path, 100, [NODE, SACJS, "wait"], {"CLAUDE_CODE_SESSION_ID": "halott"})
    _proc(tmp_path, 200, [NODE, SACJS, "wait"], {"CLAUDE_CODE_SESSION_ID": "elo"})
    _proc(tmp_path, 300, [NODE, SACJS, "wait"], {})               # no session at all
    waiters = instruct.live_waiters(proc_root=str(tmp_path))
    orphans = instruct.orphaned_waiters(waiters, live_sessions=["elo"])
    assert [w.pid for w in orphans] == [100]


def test_undeterminable_liveness_offers_nothing_rather_than_everything(tmp_path):
    """The fail direction is not symmetric, so an unanswerable question removes none."""
    _proc(tmp_path, 100, [NODE, SACJS, "wait"], {"CLAUDE_CODE_SESSION_ID": "barmi"})
    waiters = instruct.live_waiters(proc_root=str(tmp_path))
    assert instruct.orphaned_waiters(waiters, live_sessions=None) == []


def test_an_unreadable_proc_is_not_no_waiters(tmp_path):
    assert instruct.live_waiters(proc_root=str(tmp_path / "nincs")) is None


def test_one_session_may_own_several_waiters(tmp_path):
    """Measured: a session owned four at once, so presence is counted, not tested."""
    for pid in (100, 200, 300, 400):
        _proc(tmp_path, pid, [NODE, SACJS, "wait"], {"CLAUDE_CODE_SESSION_ID": "egy"})
    waiters = instruct.live_waiters(proc_root=str(tmp_path))
    assert len(instruct.waiters_for_session("egy", waiters)) == 4


def test_removal_refuses_a_live_session(tmp_path):
    _proc(tmp_path, 100, [NODE, SACJS, "wait"], {"CLAUDE_CODE_SESSION_ID": "elo"})
    killed = []
    result = instruct.remove_waiter(
        100, live_sessions=["elo"], proc_root=str(tmp_path),
        kill=lambda p, s: killed.append(p))
    assert result["removed"] is False and killed == []
    assert "alive" in result["reason"]


def test_removal_refuses_when_liveness_is_undeterminable(tmp_path):
    _proc(tmp_path, 100, [NODE, SACJS, "wait"], {"CLAUDE_CODE_SESSION_ID": "barmi"})
    killed = []
    result = instruct.remove_waiter(
        100, live_sessions=None, proc_root=str(tmp_path), kill=lambda p, s: killed.append(p))
    assert result["removed"] is False and killed == []


def test_removal_refuses_a_pid_that_is_not_a_waiter(tmp_path):
    """The candidate is re-resolved at removal time, because a pid is recycled."""
    _proc(tmp_path, 100, ["/usr/bin/gedit", "levél.txt"])
    killed = []
    result = instruct.remove_waiter(
        100, live_sessions=[], proc_root=str(tmp_path), kill=lambda p, s: killed.append(p))
    assert result["removed"] is False and killed == []
    assert "not a waiter" in result["reason"]


def test_removal_of_a_named_orphan_signals_that_one_process(tmp_path):
    _proc(tmp_path, 100, [NODE, SACJS, "wait"], {"CLAUDE_CODE_SESSION_ID": "halott"})
    _proc(tmp_path, 200, [NODE, SACJS, "wait"], {"CLAUDE_CODE_SESSION_ID": "halott"})
    killed = []
    result = instruct.remove_waiter(
        100, live_sessions=["elo"], proc_root=str(tmp_path),
        kill=lambda p, s: killed.append((p, s)))
    assert result["removed"] is True
    assert killed == [(100, 15)]          # exactly one process, and only the named one


def test_there_is_no_bulk_removal_entry_point():
    """A cleanup that takes a list is one mistaken list away from killing live waiters."""
    bulk = [n for n in dir(instruct)
            if n.startswith("remove") and n != "remove_waiter"]
    assert bulk == []


# --------------------------------------------------------------------------- #
# 4.7 — an answer goes to the connector
# --------------------------------------------------------------------------- #


def _real_writer():
    """The engine's own connector, imported HERE and never from `set_orch`.

    `tests/` is outside the scanned corpus on purpose, and this is exactly the
    seam D10 draws: the test may know both packages, the orchestration core may
    know only the port.
    """
    from set_workcycle.connector import write_answer
    return write_answer


def test_an_answer_is_keyed_to_what_it_answers(tmp_path):
    recorded = instruct.record_decision_answer(
        str(tmp_path), "fleet-view", "4.7", "igen, menjen", writer=_real_writer())
    assert recorded.change == "fleet-view" and recorded.task == "4.7"
    written = json.loads((tmp_path / "set/runtime/work-cycle/answers"
                          / os.path.basename(recorded.path)).read_text())
    assert written["change"] == "fleet-view" and written["task"] == "4.7"
    assert written["answer"] == "igen, menjen"


def test_orchestration_never_imports_the_connector_itself(tmp_path):
    """4.7 — the writer is injected, and the absence of one is a first-class answer.

    The first version of this function imported `set_workcycle.connector`
    directly. `test_workcycle_dependency_direction.py` failed it — which is the
    guard working, and worth a test of its own so the import cannot come back
    through a default argument.
    """
    import inspect
    sig = inspect.signature(instruct.record_decision_answer)
    assert sig.parameters["writer"].default is inspect.Parameter.empty
    calls = []
    instruct.record_decision_answer(
        str(tmp_path), "c", "1.1", "a",
        writer=lambda *a, **k: calls.append((a, k)) or tmp_path / "x.json")
    assert len(calls) == 1


def test_no_connector_installed_is_none_rather_than_an_error():
    """Design §8.1 — where there is no engine an answer has nowhere keyed to go,
    so the control is not offered. A machine with none is the normal case today."""
    assert instruct.resolve_answer_writer(group="nincs.ilyen.csoport") is None


def test_recorded_is_not_received(tmp_path):
    """The word matters: nothing has read it yet, and the read may be hours away."""
    recorded = instruct.record_decision_answer(
        str(tmp_path), "c", "1.1", "a", writer=_real_writer())
    assert recorded.outcome == "recorded"
    # The word is asserted on the OUTCOME, not on the whole dict: `path` carries
    # a temporary directory named after this test, so a substring sweep over the
    # payload would be measuring the fixture. The measurement inside its own
    # corpus, in miniature — and it fired on the first run.
    assert "receiv" not in recorded.outcome


def test_the_asking_session_is_never_consulted(tmp_path):
    """4.7 — an answer must be accepted whether or not that session still exists.

    Asserted on the SIGNATURE rather than on a happy path: a liveness parameter
    here could only ever refuse something that should succeed, so the check is
    that there is nowhere to pass one.
    """
    import inspect
    params = set(inspect.signature(instruct.record_decision_answer).parameters)
    assert params == {"tree", "change", "task", "answer", "source", "writer"}


# --------------------------------------------------------------------------- #
# 4.3 — the whole act, and the order inside it
# --------------------------------------------------------------------------- #

SEATS = {"aaaa-1111": SEAT}


def test_the_durable_send_happens_before_any_bell(tmp_path):
    """4.3 — a bell that cannot ring degrades to having no bell at all."""
    sac, log = _fake_sac(tmp_path, stdout=json.dumps({"room": "proj", "wakes": ["proj#aaaa"]}))

    def refusing_bell(_seat):
        raise RuntimeError("nincs socket")

    out = instruct.instruct_agent(
        "aaaa-1111", "x", seats=SEATS, waiters=[], state=agent_state.QUIET,
        bell=refusing_bell, sac_bin=sac)
    assert out["delivery"]["outcome"] == instruct.SITS_UNREAD   # the message IS on disk
    assert out["bell"]["rung"] is False
    assert "--to proj#aaaa" in log.read_text()


def test_no_bell_is_rung_when_nothing_was_sent(tmp_path):
    """A refused send must not be followed by a prompt to read a message that does not exist."""
    sac, _ = _fake_sac(tmp_path, stderr="send: nobody is called that", code=1)
    rung = []
    out = instruct.instruct_agent(
        "aaaa-1111", "x", seats=SEATS, bell=lambda s: rung.append(s) or True, sac_bin=sac)
    assert out["delivery"]["outcome"] == instruct.REFUSED
    assert rung == []


def test_the_bell_is_offered_only_where_nothing_would_start_a_turn(tmp_path):
    """Ringing a session that already has a waiter interrupts it for nothing."""
    sac, _ = _fake_sac(tmp_path, stdout=json.dumps({"room": "proj", "wakes": ["proj#aaaa"]}))
    rung = []
    out = instruct.instruct_agent(
        "aaaa-1111", "x", seats=SEATS, waiters=[_waiter()], state=agent_state.QUIET,
        bell=lambda s: rung.append(s) or True, sac_bin=sac)
    assert out["delivery"]["outcome"] == instruct.ARRIVES_NOW
    assert rung == []


def test_an_agent_with_no_seat_is_reported_rather_than_sent_to(tmp_path):
    sac, log = _fake_sac(tmp_path, stdout=json.dumps({"room": "proj", "wakes": []}))
    out = instruct.instruct_agent("nincs-ilyen", "x", seats=SEATS, sac_bin=sac)
    assert out["instructable"] is False
    assert out["reason"] == instruct.NO_SEAT
    assert not log.exists()          # nothing was sent anywhere


def test_a_held_message_is_a_modelled_outcome_and_not_a_manufactured_one(tmp_path):
    """4.2 — held is representable; nothing fabricates it from a durable send.

    The durable channel has no hold. A `held` read off a field it never sets
    would be a false value in the one place that looks like caution — so the
    producer is a caller listening to the runtime's asynchronous notice, and the
    durable path is asserted here to never reach that outcome.
    """
    report = instruct.held("proj#aaaa", room="proj")
    assert report.outcome == instruct.HELD
    assert report.accepted is True and report.delivered_to_agent is False
    assert report.settled is False

    for n, answer in enumerate(({"room": "proj", "wakes": ["proj#aaaa"]},
                                {"room": "proj", "wakes": []},
                                {"room": "proj", "held": True})):
        box = tmp_path / f"case{n}"
        box.mkdir()
        sac, _ = _fake_sac(box, stdout=json.dumps(answer))
        got = instruct.send_instruction(SEAT, "x", sac_bin=sac)
        assert got.outcome != instruct.HELD


# --------------------------------------------------------------------------- #
# 3.4 / 3.5 — what the agent DECLARED, kept apart from what was measured
# --------------------------------------------------------------------------- #


def _roster(focus):
    return {"agents": [{"agent": "proj", "rooms": ["proj"], "seats": [
        {"seat": "proj#aaaa", "session": "s-1", "liveness": "live", "focus": focus}]}]}


def test_a_declared_phase_is_carried_verbatim(tmp_path):
    sac, _ = _fake_sac(tmp_path, stdout=json.dumps(_roster(
        {"text": "a kapuréteget írom", "files": ["a.py"], "phase": "apply",
         "ts": "2026-08-19T10:00:00+02:00"})))
    seat = instruct.read_seats(sac_bin=sac)["s-1"]
    assert seat.phase == "apply"
    assert seat.focus_files == ("a.py",)
    assert seat.focus_at == "2026-08-19T10:00:00+02:00"


def test_an_undeclared_phase_stays_none_and_is_never_defaulted(tmp_path):
    """3.4 — none is not a phase.

    The bus's own rule is that a re-declaration without a phase CLEARS it rather
    than carrying the old one over. Substituting any value here would resurrect
    a phase the agent deliberately dropped.
    """
    for focus in ({"text": "csinálom", "phase": None}, {"text": "csinálom"}, {}, None):
        box = tmp_path / f"c{abs(hash(str(focus)))}"
        box.mkdir()
        sac, _ = _fake_sac(box, stdout=json.dumps(_roster(focus)))
        seat = instruct.read_seats(sac_bin=sac)["s-1"]
        assert seat.phase is None, focus
        assert seat.declared_blocked is False


def test_blocked_is_a_declaration_and_does_not_touch_the_measured_state(tmp_path):
    """3.5 — blocked-while-busy must be REPRESENTABLE, which is the whole task.

    Folding the two into one field is what makes "working, but stuck on an
    answer for three hours" unsayable — and that pair is the case the surface
    exists to show.
    """
    sac, _ = _fake_sac(tmp_path, stdout=json.dumps(_roster(
        {"text": "várok egy válaszra", "phase": "blocked"})))
    seat = instruct.read_seats(sac_bin=sac)["s-1"]
    assert seat.declared_blocked is True
    # and nothing about the measurement moved: the two are separate objects
    assert not hasattr(seat, "state")


def test_a_measured_wait_is_not_a_declared_blockage(tmp_path):
    """3.5's negative half. A quiet agent may simply have finished a turn."""
    sac, _ = _fake_sac(tmp_path, stdout=json.dumps(_roster({"text": "kész", "phase": "verify"})))
    assert instruct.read_seats(sac_bin=sac)["s-1"].declared_blocked is False


def test_the_declaration_carries_its_own_age(tmp_path):
    """A declaration does not expire on its own, so its age is what weighs it."""
    sac, _ = _fake_sac(tmp_path, stdout=json.dumps(_roster(
        {"text": "x", "ts": "2026-08-01T00:00:00+02:00"})))
    assert instruct.read_seats(sac_bin=sac)["s-1"].focus_at == "2026-08-01T00:00:00+02:00"


def test_a_malformed_focus_does_not_take_the_roster_down(tmp_path):
    """A bus that answers oddly must cost the fleet its declarations, not its inventory."""
    sac, _ = _fake_sac(tmp_path, stdout=json.dumps(_roster("nem objektum")))
    seat = instruct.read_seats(sac_bin=sac)["s-1"]
    assert seat.seat == "proj#aaaa" and seat.phase is None and seat.focus_text is None
