"""Pulling in the questions already open at switch-on — `set_orch.fleet.relay_backfill`.

Transcripts are real-shaped JSONL files in a tmp tree, and the relay's waiting records and
answer files are the real layout, because those files are the contract the relay, the
decider and the bridge share. The fleet's terminal list, the outbound and the typing are
injected.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from set_orch.fleet import question_relay as qr
from set_orch.fleet import relay_backfill as rb

SID = "735ae75b-4192-4d24-9b10-81f34fdbacc7"
OTHER = "11111111-2222-3333-4444-555555555555"
TOOL_ID = "toolu_01ABC"
SECRET = "Which banner colour should ship?"


@pytest.fixture(autouse=True)
def live_hook(monkeypatch):
    monkeypatch.setattr(qr, "_hook_alive", lambda pid: True)


def cfg(**over):
    store = {qr.KEY_ENABLED: "true", qr.KEY_TARGET: "command", qr.KEY_COMMAND: "set-auto-answer",
             qr.KEY_AUDIENCE: "DEV", qr.KEY_TIMEOUT: "600"}
    store.update(over)
    return lambda key, project=None, default=None: store.get(key, default)


def ask(tool_id=TOOL_ID, questions=None):
    questions = questions or [{"question": SECRET, "header": "Banner", "multiSelect": False,
                               "options": [{"label": "TEAL"}, {"label": "ORANGE"}]}]
    return {"type": "assistant", "timestamp": "2026-11-24T12:01:26.628Z",
            "message": {"content": [{"type": "tool_use", "id": tool_id, "name": "AskUserQuestion",
                                     "input": {"questions": questions}}]}}


def result(tool_id=TOOL_ID):
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tool_id,
                                                     "content": "answered"}]}}


def transcript(path: Path, *entries) -> str:
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return str(path)


def world(tmp_path, *, fleet=None, others=None, logs=None, get=None, launched=None, ran=None, spawned=None):
    records = tmp_path / "sessions"
    records.mkdir(exist_ok=True)
    for agent in fleet or []:
        (records / f"{agent['pid']}.json").write_text(json.dumps({"sessionId": agent["sid"], "cwd": "/w/proj"}))
    logs = logs or {}
    return rb.World(
        get=get or cfg(), fleet_agents=lambda: [{"label": a["label"], "pid": a["pid"]} for a in fleet or []],
        other_agents=lambda: others or [], log_for=lambda sid: logs.get(sid),
        run=lambda cmd, payload, env=None: (ran.append((cmd, json.loads(payload), env)) if ran is not None else None) or 0,
        records=records, base=tmp_path / "state", project_name=lambda cwd: "proj",
        launch=(launched.append if launched is not None else None),
        spawn_worker=(lambda p, v: spawned.append((json.loads(p), v))) if spawned is not None else None,
    )


# --------------------------------------------------------------------------- 1.1 finding

def test_open_calls_are_the_unanswered_questions_outside_sidechains():
    side = {**ask("toolu_side"), "isSidechain": True}
    calls = rb.open_calls([ask("toolu_done"), result("toolu_done"), side, ask()])
    assert [c["tool_use_id"] for c in calls] == [TOOL_ID]


def test_a_fleet_held_open_question_is_found_with_its_label(tmp_path):
    t = transcript(tmp_path / "a.jsonl", ask())
    w = world(tmp_path, fleet=[{"label": "proj-1", "pid": 4242, "sid": SID}], logs={SID: t})
    found = rb.open_questions(w)
    assert len(found) == 1 and found[0].label == "proj-1" and found[0].tool_use_id == TOOL_ID


def test_a_session_the_relay_already_holds_is_not_found_again(tmp_path):
    """AC-3."""
    t = transcript(tmp_path / "a.jsonl", ask())
    w = world(tmp_path, fleet=[{"label": "proj-1", "pid": 4242, "sid": SID}], logs={SID: t})
    qr._write_json(qr.waiting_path(SID, w.base), {"session_id": SID, "id": "relay-x", "pid": os.getpid()})
    assert rb.open_questions(w) == []


# --------------------------------------------------------------------------- 1.4 the pull-in

def test_switch_on_pulls_in_a_fleet_question_and_names_a_plain_terminal_one(tmp_path):
    """AC-1 (the job), AC-9."""
    t1 = transcript(tmp_path / "a.jsonl", ask())
    t2 = transcript(tmp_path / "b.jsonl", ask("toolu_02"))
    launched = []
    w = world(tmp_path, fleet=[{"label": "proj-1", "pid": 4242, "sid": SID}],
              others=[SimpleNamespace(session_id=OTHER, cwd="/w/other", session_log=t2)],
              logs={SID: t1}, launched=launched)
    report = rb.pull_in("relay-on", w)
    assert [j["label"] for j in launched] == ["proj-1"] and launched[0]["tool_use_id"] == TOOL_ID
    assert [p["session"] for p in report["pulled"]] == [SID[:8]]
    assert [p["session"] for p in report["not_fleet_held"]] == [OTHER[:8]]


def test_nothing_open_pulls_in_nothing(tmp_path):
    """AC-2."""
    t = transcript(tmp_path / "a.jsonl", ask(), result())
    launched = []
    w = world(tmp_path, fleet=[{"label": "proj-1", "pid": 4242, "sid": SID}], logs={SID: t}, launched=launched)
    report = rb.pull_in("relay-on", w)
    assert launched == [] and report["pulled"] == [] and report["not_fleet_held"] == []


def test_with_the_relay_off_nothing_is_pulled_in(tmp_path):
    """AC-10."""
    t = transcript(tmp_path / "a.jsonl", ask())
    launched = []
    w = world(tmp_path, fleet=[{"label": "proj-1", "pid": 4242, "sid": SID}], logs={SID: t}, launched=launched,
              get=cfg(**{qr.KEY_ENABLED: "false"}))
    report = rb.pull_in("by-hand", w)
    assert launched == [] and report["skipped"][0]["why"].startswith("the relay is off")


def test_a_failing_fleet_list_is_reported_not_raised(tmp_path):
    w = world(tmp_path)
    w.fleet_agents = lambda: (_ for _ in ()).throw(ConnectionRefusedError())
    w.other_agents = lambda: (_ for _ in ()).throw(RuntimeError())
    assert rb.pull_in("relay-on", w)["pulled"] == []


# --------------------------------------------------------------------------- 1.2 hand-over

def test_the_hand_over_matches_what_the_hook_would_have_made(tmp_path):
    t = transcript(tmp_path / "a.jsonl", ask())
    ran = []
    w = world(tmp_path, fleet=[{"label": "proj-1", "pid": 4242, "sid": SID}], logs={SID: t}, ran=ran)
    q = rb.open_questions(w)[0]
    rec = rb.hand_over(q, w, carrier_pid=777)
    cid = qr.call_id(SID, TOOL_ID)
    assert rec["id"] == cid and rec["pid"] == 777 and rec["backfill"] and rec["label"] == "proj-1"
    cmd, env_payload, env = ran[0]
    assert cmd == "set-auto-answer" and env_payload["questions"][0]["id"] == cid
    assert env == qr.relay_env(qr.KIND_ASK, SID, "/w/proj")
    assert qr.waiting_record(SID, w.base)["id"] == cid


def test_a_failing_outbound_hands_nothing_over(tmp_path):
    t = transcript(tmp_path / "a.jsonl", ask())
    w = world(tmp_path, fleet=[{"label": "proj-1", "pid": 4242, "sid": SID}], logs={SID: t})
    w.run = lambda cmd, payload, env=None: 3
    assert rb.hand_over(rb.open_questions(w)[0], w) is None
    assert not qr.waiting_path(SID, w.base).exists()


# --------------------------------------------------------------------------- 1.3 carrying

class Carry:
    def __init__(self, tmp_path, *, entries=None, events=None, get=None):
        self.tmp = tmp_path
        self.base = tmp_path / "state"
        self.path = tmp_path / "t.jsonl"
        transcript(self.path, *(entries or [ask()]))
        self.get = get or cfg()
        self.typed = []
        self.t = 0.0
        self.events = events or {}
        self.record = {"session_id": SID, "id": qr.call_id(SID, TOOL_ID), "pid": os.getpid(), "questions": 1,
                       "target": "command", "backfill": True, "tool_use_id": TOOL_ID, "label": "proj-1",
                       "transcript": str(self.path)}
        qr._write_json(qr.waiting_path(SID, self.base), self.record)

    def answer(self, text="ORANGE"):
        qr._write_json(qr.answer_file(self.base / "answers", self.record["id"], "Q1"), {"valasz": text})

    def sleep(self, s):
        self.t += s
        for at, fn in list(self.events.items()):
            if self.t >= at:
                self.events.pop(at)
                fn(self)

    def run(self, label_live=lambda label: True):
        return rb.carry(self.record, get=self.get, base=self.base, clock=lambda: self.t, sleep=self.sleep,
                        label_live=label_live, type_line=lambda label, line: self.typed.append((label, line)))


def test_a_channel_answer_is_typed_into_the_terminal(tmp_path):
    """AC-4: the record is gone before the line is typed, and the line carries the answer."""
    c = Carry(tmp_path, events={5: lambda c: c.answer("ORANGE")})
    record_when_typed = []
    outcome = rb.carry(c.record, get=c.get, base=c.base, clock=lambda: c.t, sleep=c.sleep,
                       label_live=lambda label: True,
                       type_line=lambda label, line: (record_when_typed.append(qr.waiting_path(SID, c.base).exists()),
                                                      c.typed.append((label, line))))
    assert outcome == "typed"
    (label, line), = c.typed
    assert label == "proj-1" and "“Banner”: ORANGE" in line and record_when_typed == [False]
    assert not qr.answer_file(c.base / "answers", c.record["id"], "Q1").exists()


def test_answered_in_the_terminal_first_types_nothing(tmp_path):
    """AC-6."""
    c = Carry(tmp_path, events={5: lambda c: transcript(c.path, ask(), result())})
    assert c.run() == "answered in the terminal" and c.typed == []
    assert not qr.waiting_path(SID, c.base).exists()


def test_an_answer_that_races_a_terminal_answer_types_nothing(tmp_path):
    c = Carry(tmp_path, events={5: lambda c: (c.answer(), transcript(c.path, ask(), result()))})
    assert c.run() == "answered in the terminal" and c.typed == []


def test_to_terminal_ends_the_carrier(tmp_path):
    """AC-7."""
    c = Carry(tmp_path, events={5: lambda c: qr.request_release(SID, c.base)})
    assert c.run() == "handed back to the terminal" and c.typed == []


def test_the_switch_going_off_ends_the_carrier(tmp_path):
    """AC-8."""
    store = {"on": True}
    get = lambda key, project=None, default=None: ("true" if store["on"] else "false") if key == qr.KEY_ENABLED \
        else cfg()(key, project, default)
    c = Carry(tmp_path, get=get, events={5: lambda c: store.update(on=False)})
    assert c.run() == "switch turned off" and c.typed == []


def test_a_gone_terminal_ends_the_carrier(tmp_path):
    c = Carry(tmp_path)
    assert c.run(label_live=lambda label: False) == "its fleet terminal is gone" and c.typed == []


def test_no_text_in_the_logs(tmp_path, caplog):
    caplog.set_level("INFO")
    c = Carry(tmp_path, events={5: lambda c: c.answer("ORANGE-SECRET-ANSWER")})
    c.run()
    assert SECRET not in caplog.text and "ORANGE-SECRET-ANSWER" not in caplog.text


def test_the_line_names_every_question_of_a_call():
    qs = [{"question": "First?", "header": "One"}, {"question": "x" * 200}]
    line = rb.answer_line({"questions": qs}, ["A", "B\nmore"])
    assert "Q1 “One”: A" in line and "Q2 “" in line and "B more" in line and "\n" not in line
    assert "these answers" in line


# --------------------------------------------------------------------------- 2.2 decide-only

def test_relay_held_questions_without_a_decider_get_a_decide_only_worker(tmp_path):
    """AC-11 (the start)."""
    t = transcript(tmp_path / "a.jsonl", ask())
    spawned = []
    w = world(tmp_path, logs={SID: t}, spawned=spawned)
    cid = qr.call_id(SID, TOOL_ID)
    qr._write_json(qr.waiting_path(SID, w.base), {"session_id": SID, "id": cid, "pid": os.getpid(),
                                                   "questions": 1, "project": "proj", "cwd": "/w/proj"})
    out = rb.undecided_waiting(w)
    assert [d["session"] for d in out["decided"]] == [SID[:8]]
    payload, relay_vars = spawned[0]
    assert payload["questions"][0]["id"] == cid and relay_vars[rb.ENV_NO_FORWARD] == "1"


def test_a_question_the_decider_already_saw_is_left_alone(tmp_path):
    from set_orch.fleet import auto_answer_worker as aw
    t = transcript(tmp_path / "a.jsonl", ask())
    spawned = []
    w = world(tmp_path, logs={SID: t}, spawned=spawned)
    cid = qr.call_id(SID, TOOL_ID)
    qr._write_json(qr.waiting_path(SID, w.base), {"session_id": SID, "id": cid, "pid": os.getpid(), "questions": 1})
    aw._private_write(aw.pending_path(w.base, cid), {"id": cid, "state": "forwarded"})
    assert rb.undecided_waiting(w)["decided"] == [] and spawned == []


# --------------------------------------------------------------------------- parked questions (M3)

def park(tmp_path, base, sid=SID, tool_id=TOOL_ID, transcript_path=""):
    qr.park({"tool_name": "AskUserQuestion", "session_id": sid, "tool_use_id": tool_id, "cwd": "/w/proj",
             "transcript_path": transcript_path,
             "tool_input": {"questions": [{"question": SECRET, "header": "Banner",
                                           "options": [{"label": "TEAL"}, {"label": "ORANGE"}]}]}}, base)


def test_a_parked_question_is_pulled_in_though_the_transcript_does_not_hold_it(tmp_path):
    """M3: on runtime 2.1.331 the open call is not in the transcript; the parked record is."""
    t = transcript(tmp_path / "a.jsonl", {"type": "user", "message": {"content": "start"}})
    launched = []
    w = world(tmp_path, fleet=[{"label": "proj-1", "pid": 4242, "sid": SID}], logs={SID: t}, launched=launched)
    park(tmp_path, w.base, transcript_path=t)
    report = rb.pull_in("relay-on", w)
    assert [j["tool_use_id"] for j in launched] == [TOOL_ID] and launched[0]["label"] == "proj-1"
    assert launched[0]["tool_input"]["questions"][0]["header"] == "Banner"
    assert len(report["pulled"]) == 1


def test_a_parked_question_of_a_session_that_ended_is_dropped(tmp_path):
    launched = []
    w = world(tmp_path, launched=launched)
    park(tmp_path, w.base)
    assert rb.pull_in("relay-on", w)["pulled"] == [] and launched == []
    assert qr.list_parked(w.base) == []


def test_a_parked_question_answered_since_is_dropped(tmp_path):
    t = transcript(tmp_path / "a.jsonl", ask(), result())
    launched = []
    w = world(tmp_path, fleet=[{"label": "proj-1", "pid": 4242, "sid": SID}], logs={SID: t}, launched=launched)
    park(tmp_path, w.base, transcript_path=t)
    assert rb.pull_in("relay-on", w)["pulled"] == [] and qr.list_parked(w.base) == []


def test_a_parked_question_in_a_plain_terminal_is_named(tmp_path):
    w = world(tmp_path, others=[SimpleNamespace(session_id=SID, cwd="/w/proj", session_log=None)])
    park(tmp_path, w.base)
    report = rb.pull_in("relay-on", w)
    assert [p["session"] for p in report["not_fleet_held"]] == [SID[:8]]


def test_the_carrier_keeps_a_call_open_that_the_transcript_does_not_show_yet(tmp_path):
    """M3/M4: absence of the tool_use is not an answer; only a tool_result is."""
    c = Carry(tmp_path, entries=[{"type": "user", "message": {"content": "start"}}],
              events={5: lambda c: c.answer("ORANGE")})
    assert c.run() == "typed" and len(c.typed) == 1


def test_an_answer_the_decider_writes_is_typed_the_same_way(tmp_path):
    """AC-5: the decider writes through its exclusive create into the same answer store."""
    from set_orch.fleet import auto_answer_worker as aw
    c = Carry(tmp_path, events={5: lambda c: aw._write_answer(c.base / "answers", c.record["id"], "Q1", "TEAL")})
    assert c.run() == "typed" and "“Banner”: TEAL" in c.typed[0][1]


def test_an_answer_far_above_the_tail_still_closes_the_call(tmp_path):
    """Measured 2026-11-25: a 5.9 MB transcript held the call's result at byte 4.6 MB, the tail
    reader saw only the last 256 KB, and the answered call was pulled in at switch-on — its
    answer was typed into the working agent a second time. The whole file is searched now."""
    from set_orch.fleet import question_relay as qr
    tid = "toolu_far_above_the_tail"
    path = tmp_path / "session.jsonl"
    lines = [json.dumps({"type": "assistant", "message": {"content": [
                 {"type": "tool_use", "id": tid, "name": "AskUserQuestion", "input": {"questions": []}}]}}),
             json.dumps({"type": "user", "message": {"content": [
                 {"type": "tool_result", "tool_use_id": tid, "content": "answered"}]}})]
    filler = json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "x" * 1000}]}})
    lines += [filler] * (qr.TRANSCRIPT_TAIL // 1000 + 50)
    path.write_text("\n".join(lines) + "\n")
    assert path.stat().st_size > qr.TRANSCRIPT_TAIL
    assert rb.call_is_open(str(path), tid) is False
    assert rb.call_is_open(str(path), "toolu_never_answered") is True
    assert rb.has_result(str(tmp_path / "missing.jsonl"), tid) is None
    assert rb.call_is_open(None, tid) is True, "no transcript to read: still named as open, as before"


def test_a_carrier_outlasts_the_hooks_limit(tmp_path):
    """fleet-relay-board, 2026-11-26: the carrier copied the hook's 55 min and dropped a
    pulled-in question off the relay a second time. It now waits while the question is open."""
    late = qr.DEFAULT_TIMEOUT_S * 3
    c = Carry(tmp_path, events={late: lambda c: c.answer("ORANGE")})
    assert c.run() == "typed" and c.t >= late


def test_help_pulls_nothing_in(capsys, monkeypatch):
    """Measured 2026-11-26: `set-relay-backfill --help` ran a real pull-in."""
    monkeypatch.setattr(rb, "pull_in", lambda *a, **k: (_ for _ in ()).throw(AssertionError("pulled in")))
    assert rb.main(["--help"]) == 0 and "usage:" in capsys.readouterr().out
    assert rb.main(["--bogus"]) == 2


def test_repull_after_timeout_is_a_pull_in(monkeypatch):
    seen = []
    monkeypatch.setattr(rb, "pull_in", lambda trigger, *a, **k: seen.append(trigger) or {})
    rb.repull_after_timeout("sid")
    assert seen == ["hook-timeout"]



# --------------------------------------------------------------------------- B-250 next steps

NEXT_Q = "✅ Finished, waiting for the next instruction — proj · 735ae75b"


def cjob(**over):
    job = {"kind": qr.KIND_CONTINUATION, "session_id": SID, "cwd": "/w/proj", "project": "proj",
           "transcript": None, "armed": 1000.0, "started": 990.0, "prompt_id": "p1",
           "question": NEXT_Q, "options": ["→ Close the PR with thanks", "→ Merge it"], "label": "proj-1"}
    job.update(over)
    return job


class NextStep:
    """A carrier for a finished turn's next step, on a fake clock."""

    def __init__(self, tmp_path, *, entries=(), events=None, get=None):
        self.ran = []
        self.w = world(tmp_path, get=get, ran=self.ran)
        self.w.read = lambda path: list(self.entries)
        self.w.wall = lambda: 1000.0 + 3400 + self.t
        self.base = tmp_path / "state"
        self.entries = list(entries)
        self.events = events or {}
        self.t = 0.0
        self.typed = []

    def answer(self, text):
        rec = qr.waiting_record(SID, self.base)
        qr._write_json(qr.answer_file(self.base / "answers", rec["id"], "Q1"), {"valasz": text})

    def sleep(self, s):
        self.t += s
        for at, fn in list(self.events.items()):
            if self.t >= at:
                self.events.pop(at)
                fn(self)

    def run(self, job=None, label_live=lambda label: True):
        return rb.run_continuation(job or cjob(), self.w, clock=lambda: self.t, sleep=self.sleep,
                                   label_live=label_live, type_line=lambda label, line: self.typed.append((label, line)))


def test_a_next_step_past_the_hooks_limit_stays_on_the_board_and_is_typed_in(tmp_path):
    """B-250: measured 2026-11-26 21:54, a next step dropped off the board at 3300 s. The
    carrier posts it again, keeps the age the operator sees, waits past the hook's limit,
    and types the channel's answer into the idle session."""
    late = qr.DEFAULT_TIMEOUT_S * 3
    seen = {}

    def on_board(c):
        seen["record"] = qr.waiting_record(SID, c.base)
        c.answer("→ Close the PR with thanks")

    n = NextStep(tmp_path, events={late: on_board})
    assert n.run() == "typed" and n.t >= late
    rec = seen["record"]
    assert rec["kind"] == qr.KIND_CONTINUATION and rec["started"] == 990.0, "the board keeps the original age"
    (_cmd, envelope, _env), = n.ran
    q = envelope["questions"][0]
    assert NEXT_Q in json.dumps(envelope, ensure_ascii=False) and "Merge it" in json.dumps(q, ensure_ascii=False)
    (label, line), = n.typed
    assert label == "proj-1" and line.endswith("Close the PR with thanks")
    assert not qr.waiting_path(SID, n.base).exists(), "the record is gone once answered"


def test_a_next_step_the_operator_typed_past_is_not_carried(tmp_path):
    """The session produced a newer turn (a wake, a typed prompt) after this one ended."""
    newer = {"type": "assistant", "timestamp": "1970-01-01T00:16:41Z", "message": {"content": []}}
    n = NextStep(tmp_path, entries=[newer])
    from set_orch.fleet import continuation as ct
    assert ct.moved_on(n.entries, 1000.0), "fixture: the entry is newer than the armed time"
    assert n.run() == "the session moved on to a newer turn" and n.ran == [] and n.typed == []


def test_a_next_step_superseded_while_carried_types_nothing(tmp_path):
    from set_orch.fleet import continuation as ct
    n = NextStep(tmp_path, events={5: lambda c: ct.mark_superseded(SID, c.base, wall=lambda: 1500.0)})
    assert n.run() == "released" and n.typed == [] and n.ran, "posted, then let go untyped"
    assert not qr.waiting_path(SID, n.base).exists()


def test_a_next_step_is_not_carried_over_a_question_the_relay_holds(tmp_path):
    n = NextStep(tmp_path)
    qr._write_json(qr.waiting_path(SID, n.base), {"session_id": SID, "id": "relay-other", "pid": os.getpid()})
    assert n.run() == "already-held" and n.ran == []


def test_a_next_step_in_a_gone_terminal_types_nothing(tmp_path):
    n = NextStep(tmp_path)
    assert n.run(label_live=lambda label: False) == "its fleet terminal is gone" and n.typed == []


def test_repull_continuation_carries_only_a_fleet_held_session(tmp_path):
    launched = []
    w = world(tmp_path, fleet=[{"label": "proj-1", "pid": 4242, "sid": SID}], launched=launched)
    job = cjob(label=None)
    assert rb.repull_continuation(job, w) == "launched"
    (sent,), = [launched]
    assert sent["label"] == "proj-1" and sent["kind"] == qr.KIND_CONTINUATION and sent["question"] == NEXT_Q
    w2 = world(tmp_path, fleet=[], launched=launched)
    assert rb.repull_continuation(job, w2) == "not fleet-held" and len(launched) == 1


def test_the_carrier_job_routes_a_next_step(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(rb, "run_continuation", lambda job, w=None: seen.append(job["kind"]) or "typed")
    assert rb.run_job(cjob(), world(tmp_path)) == "typed" and seen == [qr.KIND_CONTINUATION]
