"""The decider's outbound and worker — `set_orch.fleet.auto_answer_worker` (group 3).

The worker is driven with a fake clock, a recording forward command and an injected
decision; the relay's side — its waiting record and its answer files — is the real file
layout in a tmp tree, because those files ARE the contract the relay, the bridge and the
fleet share. One test runs the real `bin/set-auto-answer` as a process, because "the relay
is not held" is a property of a real exit, not of a function return.
"""

from __future__ import annotations

import json
import logging
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from set_orch.fleet import auto_answer as aa
from set_orch.fleet import auto_answer_worker as aw
from set_orch.fleet import question_relay as qr

SID = "47f1763f-c5c5-4f3a-9aae-850d27d41dae"
CID = "relay-47f1763f-0123456789ab"
SECRET = "Which release colour should the banner use?"
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def live_hook(monkeypatch):
    """The waiting record names this test's pid; the relay would read it as an orphan."""
    monkeypatch.setattr(qr, "_hook_alive", lambda pid: True)


def cfg(**over):
    store = {aa.KEY_ENABLED: "true", aa.KEY_FORWARD: "bridge be --json -", aa.KEY_WINDOW: "60",
             qr.KEY_TIMEOUT: "600"}
    store.update(over)
    store = {k: v for k, v in store.items() if v is not None}
    return lambda key, project=None, default=None: store.get(key, default)


def envelope(base: Path, text=SECRET, options=("TEAL", "ORANGE"), keys=("Q1",)):
    return {"questions": [{"id": CID, "key": k, "question": text, "optionsList": list(options), "multi": False,
                           "audience": "DEV", "source": "proj · 47f1763f", "valasz_tar": str(base / "answers")}
                          for k in keys]}


def answer(choice="TEAL", tier="decided", conf=0.95, refs=None, outward=False):
    refs = refs if refs is not None else [aa.Reference("operator", "the release colour is TEAL", checked=True)]
    a = aa.Answer(key="Q1", choice=choice, claimed_tier=tier, confidence=conf, outward=outward, references=refs)
    a.tier = tier
    return a


class Relay:
    """The world around one worker: the clock, the forward, the relay's files, a human."""

    def __init__(self, base: Path, decision: aa.Decision, *, get=None, code=0, human_at=None,
                 human_text="ORANGE", events=None, record=True):
        self.base, self.decision, self.code = base, decision, code
        self.get = get or cfg()
        self.t = 1_800_000_000.0
        self.start = self.t
        self.forwarded, self.forward_env = [], []
        self.human_at, self.human_text = human_at, human_text
        self.events = events or {}
        self.log = base / "log" / "decisions.jsonl"
        (base / "answers").mkdir(parents=True, exist_ok=True)
        if record:
            qr._write_json(qr.waiting_path(SID, base), {"session_id": SID, "id": CID, "pid": os.getpid(),
                                                         "questions": 1, "target": "command"})

    def wall(self):
        return self.t

    def sleep(self, s):
        self.t += s
        elapsed = self.t - self.start
        if self.human_at is not None and elapsed >= self.human_at and not getattr(self, "_answered", False):
            self._answered = True
            qr._write_json(qr.answer_file(self.base / "answers", CID, "Q1"), {"valasz": self.human_text})
        for at, fn in list(self.events.items()):
            if elapsed >= at:
                self.events.pop(at)
                fn(self)
        # the relay consumes the answers and clears its record once every key is answered
        if all(qr.answer_file(self.base / "answers", CID, f"Q{i}").exists() for i in (1,)) and \
                getattr(self, "consume", True):
            qr._write_json(self.base / "consumed.json", {"at": elapsed})
            qr.waiting_path(SID, self.base).unlink(missing_ok=True)

    def run(self, cmd, payload, env=None):
        self.forwarded.append(json.loads(payload))
        self.forward_env.append(env)
        return self.code

    def work(self, kind="ask", payload=None):
        world = aw.World(get=self.get, decide=lambda *a, **k: self.decision, run=self.run, wall=self.wall,
                         sleep=self.sleep, log=self.log)
        payload = payload or json.dumps(envelope(self.base), ensure_ascii=False)
        return aw.work(payload, {qr.ENV_KIND: kind, qr.ENV_SESSION: SID, qr.ENV_CWD: str(self.base)}, world)

    def records(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()]

    def answer_text(self):
        f = qr.answer_file(self.base / "answers", CID, "Q1")
        return json.loads(f.read_text())["valasz"] if f.exists() else None


def decided():
    return aa.Decision({"Q1": answer()}, {}, "fork", ["kb: 0 hit(s)"], {"cache_read_input_tokens": 9}, "anthropic/x")


# --------------------------------------------------------------------------- 3.1 the outbound

def test_switch_off_forwards_byte_for_byte(tmp_path):
    """AC-1."""
    seen = []
    payload = json.dumps(envelope(tmp_path), ensure_ascii=False)
    code = aw.outbound(payload, get=cfg(**{aa.KEY_ENABLED: "false"}),
                       environ={qr.ENV_KIND: "ask", qr.ENV_SESSION: SID, qr.ENV_CWD: "/x"},
                       run=lambda c, p, env=None: seen.append((c, p, env)) or 7,
                       spawn=lambda *a: pytest.fail("no worker while off"))
    assert code == 7 and seen == [("bridge be --json -", payload,
                                   {qr.ENV_KIND: "ask", qr.ENV_SESSION: SID, qr.ENV_CWD: "/x"})]
    assert not list((tmp_path / "answers").glob("*")) if (tmp_path / "answers").exists() else True


def test_switch_off_without_a_forward_fails_so_the_relay_releases(tmp_path):
    assert aw.outbound("{}", get=cfg(**{aa.KEY_ENABLED: "false", aa.KEY_FORWARD: None}),
                       run=lambda *a, **k: pytest.fail("nothing to run")) == 1


def test_switch_on_spawns_and_returns(tmp_path):
    spawned = []
    payload = json.dumps(envelope(tmp_path))
    assert aw.outbound(payload, get=cfg(), environ={qr.ENV_KIND: "ask"},
                       run=lambda *a, **k: pytest.fail("the worker forwards, not the outbound"),
                       spawn=lambda p, v: spawned.append((p, v))) == 0
    assert spawned and spawned[0][0] == payload and spawned[0][1][qr.ENV_KIND] == "ask"


def test_the_real_cli_returns_at_once_with_a_slow_model(tmp_path):
    """AC-2: the relay is not held — `bin/set-auto-answer` exits before the decision."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name, body in (("claude", "import time; time.sleep(60)"), ("set-kb", "import sys; sys.exit(2)")):
        (bindir / name).write_text(f"#!{sys.executable}\n{body}\n")
        (bindir / name).chmod(0o755)
    state = tmp_path / "state"
    env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
           "SET_QUESTION_RELAY_DIR": str(state), "XDG_DATA_HOME": str(tmp_path / "data"),
           aa.local_config.env_key(aa.KEY_ENABLED): "true",
           aa.local_config.env_key(aa.KEY_FORWARD): "",
           aa.local_config.env_key(aa.KEY_DECIDE_TIMEOUT): "5",
           qr.ENV_KIND: "ask", qr.ENV_SESSION: SID, qr.ENV_CWD: str(tmp_path)}
    t0 = time.monotonic()
    res = subprocess.run([str(REPO / "bin" / "set-auto-answer")], input=json.dumps(envelope(state)),
                         text=True, env=env, timeout=30)
    took = time.monotonic() - t0
    assert res.returncode == 0 and took < 2.0, f"took {took:.1f} s"
    # Let the detached worker finish (decision bound 5 s, record wait 15 s) so nothing leaks.
    log = tmp_path / "data" / "set-core" / "auto-answer" / "decisions.jsonl"
    deadline = time.monotonic() + 40
    while not log.exists() and time.monotonic() < deadline:
        time.sleep(0.5)
    assert log.exists(), "the worker never closed its decision"
    rec = json.loads(log.read_text().splitlines()[-1])
    assert rec["outcome"] == "no-decision" and "timed out" in rec["reason"]


# --------------------------------------------------------------------------- 3.2 the window

def test_nobody_answers_so_it_is_written_after_the_window(tmp_path):
    """AC-10, AC-16."""
    r = Relay(tmp_path, decided())
    out = r.work()
    assert out == {"Q1": "written"} and r.answer_text() == "TEAL"
    shown = r.forwarded[0]["questions"][0]["question"]
    assert shown.startswith(SECRET) and "Auto-answer: «TEAL» — decided" in shown and "Written at" in shown
    assert "your words: “the release colour is TEAL”" in shown
    assert r.forward_env[0] == {qr.ENV_KIND: "ask", qr.ENV_SESSION: SID, qr.ENV_CWD: str(tmp_path)}
    assert 60 <= r.t - r.start < 63, "written only once the 60 s window was over"
    rec = r.records()[0]
    assert rec["outcome"] == "written" and rec["question"] == SECRET and rec["options"] == ["TEAL", "ORANGE"]
    assert rec["choice"] == "TEAL" and rec["tier"] == "decided" and rec["references"][0]["checked"] is True
    assert rec["human_answer"] is None and rec["method"] == "fork"
    assert not aw.pending_path(tmp_path, CID).exists()


def test_the_operator_answers_first(tmp_path):
    """AC-11, AC-17: nothing written, the human file untouched, the log says overtaken."""
    r = Relay(tmp_path, decided(), human_at=20, human_text="ORANGE")
    r.consume = False
    r.events = {25: lambda rl: qr.waiting_path(SID, rl.base).unlink(missing_ok=True)}
    out = r.work()
    assert out == {"Q1": "overtaken"} and r.answer_text() == "ORANGE"
    rec = r.records()[0]
    assert rec["outcome"] == "overtaken" and rec["human_answer"] == "ORANGE" and rec["choice"] == "TEAL"


def test_a_human_file_that_appears_at_the_last_moment_is_never_overwritten(tmp_path):
    """D7: the exclusive create loses to an answer that is already there."""
    answers = tmp_path / "answers"
    answers.mkdir()
    qr._write_json(qr.answer_file(answers, CID, "Q1"), {"valasz": "human"})
    assert aw._write_answer(answers, CID, "Q1", "TEAL") is False
    assert json.loads(qr.answer_file(answers, CID, "Q1").read_text())["valasz"] == "human"
    assert [p.name for p in answers.iterdir()] == [f"{CID}__Q1.json"], "no temp file left behind"


def test_cancelled_from_the_fleet(tmp_path):
    """AC-18 (the worker's half): cancelled → nothing written, still waiting, logged cancelled."""
    r = Relay(tmp_path, decided(), events={10: lambda rl: aw.cancel(CID, rl.base),
                                           100: lambda rl: qr.waiting_path(SID, rl.base).unlink()})
    out = r.work()
    assert out == {"Q1": "cancelled"} and r.answer_text() is None
    assert r.records()[0]["outcome"] == "cancelled"


def test_cancel_refuses_what_is_not_a_live_proposal(tmp_path):
    assert aw.cancel("relay-nope", tmp_path) is False


def test_the_question_ends_elsewhere_before_the_window(tmp_path):
    r = Relay(tmp_path, decided(), events={10: lambda rl: qr.request_release(SID, rl.base)})
    assert r.work() == {"Q1": "released"} and r.answer_text() is None


def test_a_proposal_whose_question_ended_stops_at_once_not_at_the_window(tmp_path):
    """Measured live 2026-11-24: a continuation superseded by a typed prompt at +10 s stayed
    'proposed' — on the panel and the tile, counting down to a write that could not happen —
    until the window ran out at +60 s. The pending record must go the moment the question ends."""
    seen = {}

    def ended(rl):
        qr.waiting_path(SID, rl.base).unlink()

    def look(rl):
        seen["pending_at_20s"] = aw.read_pending(rl.base, CID)

    r = Relay(tmp_path, decided(), events={10: ended, 20: look})
    assert r.work() == {"Q1": "released"} and r.answer_text() is None
    assert r.t - r.start < 30, f"the worker held on for {r.t - r.start:.0f} s after the question ended"
    assert seen.get("pending_at_20s") in (None, {}) or seen["pending_at_20s"].get("state") != "proposed"


# --------------------------------------------------------------------------- exclusions and the bar

def test_a_push_question_is_forwarded_with_a_recommendation_not_written(tmp_path):
    """AC-7."""
    d = aa.Decision({"Q1": answer(choice="Yes", refs=[aa.Reference("operator", "push it, as always", checked=True)])},
                    {}, "fork")
    r = Relay(tmp_path, d, events={30: lambda rl: qr.waiting_path(SID, rl.base).unlink()})
    payload = json.dumps(envelope(tmp_path, text="May I push the 11 commits?", options=("Yes", "No")))
    assert r.work(payload=payload) == {"Q1": "excluded"} and r.answer_text() is None
    shown = r.forwarded[0]["questions"][0]["question"]
    assert "Recommendation (not written automatically — outward step: publish): «Yes»" in shown
    assert "push it, as always" in shown
    assert r.records()[0]["outcome"] == "excluded"


def test_a_permission_prompt_is_never_written(tmp_path):
    """AC-8."""
    d = aa.Decision({"Q1": answer(choice="Allow")}, {}, "fork")
    r = Relay(tmp_path, d, events={30: lambda rl: qr.waiting_path(SID, rl.base).unlink()})
    payload = json.dumps(envelope(tmp_path, text="proj · s wants to run Bash: ls", options=("Allow", "Deny")))
    assert r.work(kind="permission", payload=payload) == {"Q1": "excluded"} and r.answer_text() is None


def test_the_model_says_inward_but_the_question_deploys(tmp_path):
    """AC-9."""
    d = aa.Decision({"Q1": answer(choice="Yes", outward=False)}, {}, "fork")
    r = Relay(tmp_path, d, events={30: lambda rl: qr.waiting_path(SID, rl.base).unlink()})
    payload = json.dumps(envelope(tmp_path, text="Deploy the fix to staging?", options=("Yes", "No")))
    assert r.work(payload=payload) == {"Q1": "excluded"} and r.answer_text() is None


def test_likely_below_the_bar(tmp_path):
    """AC-12."""
    d = aa.Decision({"Q1": answer(tier="likely", conf=0.6, refs=[])}, {}, "fork")
    r = Relay(tmp_path, d, events={30: lambda rl: qr.waiting_path(SID, rl.base).unlink()})
    assert r.work() == {"Q1": "below-bar"} and r.answer_text() is None
    assert "likely 0.60 below 0.80" in r.forwarded[0]["questions"][0]["question"]


def test_likely_at_the_bar_is_written(tmp_path):
    d = aa.Decision({"Q1": answer(tier="likely", conf=0.8, refs=[])}, {}, "fork")
    r = Relay(tmp_path, d)
    assert r.work() == {"Q1": "written"} and r.answer_text() == "TEAL"


@pytest.mark.parametrize("decision,reason", [
    (aa.Decision({}, {"Q1": "choice outside the options"}, "fork"), "choice outside the options"),
    (aa.Decision({}, {"Q1": "timed out after 120 s"}, "fork"), "timed out after 120 s"),
])
def test_no_decision_forwards_unchanged(tmp_path, decision, reason):
    """AC-5, AC-6: the operator gets the envelope exactly as the relay built it."""
    r = Relay(tmp_path, decision, events={30: lambda rl: qr.waiting_path(SID, rl.base).unlink()})
    payload = json.dumps(envelope(tmp_path), ensure_ascii=False)
    assert r.work(payload=payload) == {"Q1": "no-decision"} and r.answer_text() is None
    assert r.forwarded == [json.loads(payload)]
    assert r.records()[0]["reason"] == reason


# --------------------------------------------------------------------------- 3.3 release

def test_no_forward_and_no_answer_releases_to_the_terminal(tmp_path):
    """AC-13."""
    d = aa.Decision({"Q1": answer(choice="Allow")}, {}, "fork")
    r = Relay(tmp_path, d, get=cfg(**{aa.KEY_FORWARD: None}))
    payload = json.dumps(envelope(tmp_path, options=("Allow", "Deny")))
    assert r.work(kind="permission", payload=payload) == {"Q1": "excluded"}
    assert qr.release_path(SID, tmp_path).exists() and r.forwarded == []


def test_a_forward_that_fails_releases_and_writes_nothing(tmp_path):
    r = Relay(tmp_path, decided(), code=5)
    assert r.work() == {"Q1": "forward-failed"} and r.answer_text() is None
    assert qr.release_path(SID, tmp_path).exists()


# --------------------------------------------------------------------------- 3.4 the log

def test_the_log_is_private_and_pruned(tmp_path):
    log = tmp_path / "d" / "decisions.jsonl"
    now = 2_000_000_000.0
    aw.append_log([{"ts": now - 100 * 86400, "id": "old"}], path=log, now=now - 100 * 86400, get=cfg())
    aw.append_log([{"ts": now, "id": "new"}], path=log, now=now, get=cfg())
    assert [r["id"] for r in aw.read_log(path=log)] == ["new"]
    assert stat.S_IMODE(log.stat().st_mode) == 0o600 and stat.S_IMODE(log.parent.stat().st_mode) == 0o700
    aw.append_log([{"ts": now, "id": "newer"}], path=log, now=now, get=cfg(**{aa.KEY_LOG_DAYS: "200"}))
    assert [r["id"] for r in aw.read_log(path=log)] == ["newer", "new"]


def test_no_question_or_answer_text_in_the_logs(tmp_path, caplog):
    """D9: the relay journal and the service log carry ids, tiers and outcomes, never text."""
    caplog.set_level(logging.DEBUG)
    d = aa.Decision({"Q1": answer(choice="TEAL-SECRET-CHOICE")}, {}, "fork")
    payload = json.dumps(envelope(tmp_path, options=("TEAL-SECRET-CHOICE", "ORANGE")))
    Relay(tmp_path, d).work(payload=payload)
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert text and SECRET not in text and "TEAL-SECRET-CHOICE" not in text and "release colour" not in text


def test_pending_records_are_private_and_pruned(tmp_path):
    aw._private_write(aw.pending_path(tmp_path, CID), {"id": CID, "state": "proposed"})
    p = aw.pending_path(tmp_path, CID)
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    os.utime(p, (1, 1))
    assert aw.prune_pending(tmp_path, time.time()) == 1 and not p.exists()


def test_the_pending_record_shows_the_proposal_while_it_waits(tmp_path):
    seen = {}
    r = Relay(tmp_path, decided(), events={5: lambda rl: seen.update(p=aw.list_pending(rl.base))})
    r.work()
    p = seen["p"][0]
    assert p["state"] == "proposed" and p["write_at"] == pytest.approx(r.start + 60, abs=1)
    assert p["questions"][0]["choice"] == "TEAL" and p["questions"][0]["tier"] == "decided"
