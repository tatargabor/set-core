"""The wait detector — `set_orch.fleet.wait_detect`.

Driven with the Stop hook's real input shape (measured: `last_assistant_message`,
`stop_hook_active`) and a fake classifier; the classifier's own process handling is tested
with a fake `claude` on PATH, because the subprocess contract is the mechanism.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from set_orch.fleet import question_relay as qr
from set_orch.fleet import wait_detect as wd

WAIT = "1. Open Audio MIDI Setup.\n2. Create a Multi-Output Device.\nThen tell me \"done\"."


def stop_input(message=WAIT, active=False):
    return {"session_id": "cbcc4e64-6d8c", "hook_event_name": "Stop", "cwd": "/x",
            "stop_hook_active": active, "last_assistant_message": message}


def config(**over):
    store = {qr.KEY_ENABLED: "true", qr.KEY_TARGET: "command", qr.KEY_COMMAND: "b", qr.KEY_AUDIENCE: "DEV"}
    store.update(over)
    store = {k: v for k, v in store.items() if v is not None}
    return lambda key, project=None, default=None: store.get(key, default)


@pytest.fixture(autouse=True)
def _state(tmp_path, monkeypatch):
    """Every decision now writes a verdict record: keep it out of the machine's state dir."""
    monkeypatch.setenv("SET_QUESTION_RELAY_DIR", str(tmp_path / "relay-state"))
    return tmp_path / "relay-state"


class Spy:
    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def __call__(self, message):
        self.calls.append(message)
        return self.answer


def test_relay_off_runs_no_classifier():
    """AC-1."""
    spy = Spy("WAITING")
    assert wd.decide(stop_input(), get=config(**{qr.KEY_ENABLED: None}), classifier=spy, env={}) is None
    assert spy.calls == []


def test_relay_on_but_not_ready_runs_no_classifier():
    spy = Spy("WAITING")
    assert wd.decide(stop_input(), get=config(**{qr.KEY_AUDIENCE: None}), classifier=spy, env={}) is None
    assert spy.calls == []


def test_already_continued_once():
    """AC-2 / AC-19: the re-ask's own continuation never converts again — no loop."""
    spy = Spy("WAITING")
    assert wd.decide(stop_input(), get=config(), classifier=spy, env={})["decision"] == "block"
    assert wd.decide(stop_input(active=True), get=config(), classifier=spy, env={}) is None
    assert len(spy.calls) == 1
    assert wd.read_verdict("cbcc4e64-6d8c")["verdict"] == "SKIPPED"


def test_continued_without_any_record_keeps_the_guard():
    spy = Spy("WAITING")
    assert wd.decide(stop_input(active=True), get=config(), classifier=spy, env={}) is None
    assert spy.calls == []


def test_a_turn_woken_from_the_channel_is_classified():
    """AC-18: an asyncRewake wake ends with stop_hook_active true (measured); after DONE it is a new turn."""
    wd.decide(stop_input("All done."), get=config(), classifier=Spy("DONE"), env={})
    spy = Spy("WAITING")
    out = wd.decide(stop_input(active=True), get=config(), classifier=spy, env={})
    assert spy.calls == [WAIT] and out["decision"] == "block"


def test_verdict_record_per_turn(_state):
    """AC-15 / AC-17: DONE is recorded with the turn key; nothing while the relay is off; no text."""
    hook = {**stop_input("Finished the Multi-Output work."), "prompt_id": "8593cae2-d5f3"}
    assert wd.decide(hook, get=config(**{qr.KEY_ENABLED: None}), classifier=Spy("DONE"), env={}) is None
    assert wd.read_verdict("cbcc4e64-6d8c") is None
    assert wd.decide(hook, get=config(), classifier=Spy("DONE"), env={}) is None
    rec = wd.read_verdict("cbcc4e64-6d8c")
    assert rec["verdict"] == "DONE" and rec["turn"] == "8593cae2-d5f3"
    raw = wd.verdict_path("cbcc4e64-6d8c").read_text()
    assert "Multi-Output" not in raw
    wd.decide(hook, get=config(), classifier=Spy(None), env={})
    assert wd.read_verdict("cbcc4e64-6d8c")["verdict"] == "UNKNOWN"


def test_turn_key_falls_back_to_a_message_hash():
    a = wd.turn_key(stop_input("one"))
    assert a.startswith("msg-") and a != wd.turn_key(stop_input("two")) and a == wd.turn_key(stop_input("one"))


def test_inside_the_classifier_session_does_nothing():
    spy = Spy("WAITING")
    assert wd.decide(stop_input(), get=config(), classifier=spy, env={wd.GUARD_ENV: "1"}) is None
    assert spy.calls == []


def test_empty_message_does_nothing():
    spy = Spy("WAITING")
    assert wd.decide(stop_input(message="  "), get=config(), classifier=spy, env={}) is None
    assert spy.calls == []


def test_waiting_turn_is_blocked_with_the_reask_instruction():
    """AC-3."""
    spy = Spy("WAITING")
    out = wd.decide(stop_input(), get=config(), classifier=spy, env={})
    assert out["decision"] == "block"
    assert "AskUserQuestion" in out["reason"] and "options" in out["reason"]
    assert spy.calls == [WAIT]


def test_finished_turn_is_left_alone():
    """AC-4."""
    assert wd.decide(stop_input(), get=config(), classifier=Spy("DONE"), env={}) is None


def test_classifier_failure_lets_the_turn_end():
    """AC-5 at the decision: None from the classifier is not a verdict."""
    assert wd.decide(stop_input(), get=config(), classifier=Spy(None), env={}) is None


def _fake_claude(tmp_path, body):
    exe = tmp_path / "bin" / "claude"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text("#!/bin/sh\n" + body)
    exe.chmod(0o755)
    return str(exe.parent)


@pytest.mark.parametrize("body,expected", [
    ("cat >/dev/null; echo WAITING\n", "WAITING"),
    ("cat >/dev/null; echo ' done.'\n", "DONE"),
    ("cat >/dev/null; echo SELF\n", "SELF"),
    ("cat >/dev/null; echo 'I think it is waiting'\n", None),   # not exactly one of the words
    ("cat >/dev/null; echo WAITING; exit 3\n", None),   # a valid word from a failed run is not a verdict
])
def test_classify_parses_only_the_three_words(tmp_path, monkeypatch, body, expected):
    monkeypatch.setenv("PATH", _fake_claude(tmp_path, body) + os.pathsep + os.environ["PATH"])
    assert wd.classify("x", get=config()) == expected


def test_classify_times_out(tmp_path, monkeypatch):
    """AC-5."""
    monkeypatch.setenv("PATH", _fake_claude(tmp_path, "sleep 5\n") + os.pathsep + os.environ["PATH"])
    monkeypatch.setattr(wd, "CLASSIFY_TIMEOUT_S", 0.5)
    assert wd.classify("x", get=config()) is None


def test_classify_runs_headless_without_hooks_and_with_the_guard(tmp_path, monkeypatch):
    seen = tmp_path / "seen"
    body = f'echo "$@" > {seen}; env | grep -c {wd.GUARD_ENV} >> {seen}; cat >/dev/null; echo DONE\n'
    monkeypatch.setenv("PATH", _fake_claude(tmp_path, body) + os.pathsep + os.environ["PATH"])
    wd.classify("x", get=config(**{wd.KEY_MODEL: "tiny"}))
    args, guard = seen.read_text().splitlines()
    assert "-p" in args and "--model tiny" in args and "--no-session-persistence" in args
    assert '"disableAllHooks": true' in args
    assert guard == "1"


def test_logs_carry_no_message_text(tmp_path, monkeypatch, caplog):
    caplog.set_level("DEBUG", logger="set_orch.fleet.wait_detect")
    monkeypatch.setenv("PATH", _fake_claude(tmp_path, "cat >/dev/null; echo 'Multi-Output weird'\n")
                       + os.pathsep + os.environ["PATH"])
    wd.classify(WAIT, get=config())
    wd.decide(stop_input(), get=config(), classifier=Spy("WAITING"), env={})
    assert caplog.records
    assert "Multi-Output" not in caplog.text and "Audio MIDI" not in caplog.text


def test_deploy_adds_one_detector(tmp_path):
    """AC-6."""
    root = Path(__file__).resolve().parents[2]
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps(
        {"hooks": {"Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "own-stop"}]}]}}))
    for _ in range(2):
        subprocess.run([str(root / "bin" / "set-deploy-hooks"), "--quiet", str(tmp_path)], check=True)
    stop = json.loads((tmp_path / ".claude" / "settings.json").read_text())["hooks"]["Stop"]
    cmds = [h["command"] for e in stop for h in e["hooks"]]
    assert cmds.count("set-hook-wait-detect") == 1 and "own-stop" in cmds


def test_hook_script_is_silent_when_relay_off(tmp_path):
    root = Path(__file__).resolve().parents[2]
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "SET_CONFIG_DIR": str(tmp_path / "cfg")}
    res = subprocess.run([str(root / "bin" / "set-hook-wait-detect")], input=json.dumps(stop_input()),
                         capture_output=True, text=True, env=env)
    assert res.returncode == 0 and res.stdout == ""


def test_the_prompt_scopes_waiting_to_this_agent_and_frees_status_reports():
    """Measured 2026-11-24: 159 WAITING vs 127 DONE over the relay log, and status reports
    that only LISTED questions waiting in other sessions were classified WAITING, so the
    agent was told to ask the owner something it had no need to ask. Re-run on the two real
    messages with the sharper wording: both DONE, while 'tell me when it's done' and an open
    either/or question stayed WAITING."""
    from set_orch.fleet import wait_detect as wd
    assert "THIS agent's own next step is blocked" in wd.PROMPT
    assert "lists things that wait for the user ELSEWHERE" in wd.PROMPT


def test_a_turn_waiting_on_its_own_work_is_not_reasked(tmp_path):
    """Measured 2026-11-24: "Once the verify result arrives I'll commit" (a subagent of its own)
    was classified WAITING and the agent was told to ask the user a question it did not have.
    The three-word prompt (3 samples x 8 messages: 24/24 against 17/24) names it SELF: the turn
    ends, the verdict is recorded, and the continuation (DONE only) leaves it alone."""
    assert "SELF —" in wd.PROMPT and "WAITING, SELF or DONE" in wd.PROMPT
    hook = stop_input("Once the verify result arrives I'll commit and archive.")
    assert wd.decide(hook, get=config(), classifier=Spy("SELF"), env={}, base=tmp_path) is None
    assert wd.read_verdict(hook["session_id"], tmp_path)["verdict"] == "SELF"


def _dictation(tmp_path, pid):
    folder = tmp_path / ".set" / "copilot" / "cbcc4e64-6d8c"
    folder.mkdir(parents=True)
    (folder / "capture.pid").write_text(f"{pid}\n")
    data = stop_input("🔴 Dictation active (30 min limit). `/dd` to finish.")
    data["cwd"] = str(tmp_path)
    return data


def test_a_live_dictation_in_this_session_is_not_reasked(tmp_path):
    """B-219: while the session's capture runs, the user is at the mic and types /dd here."""
    data = _dictation(tmp_path, os.getpid())
    asked = []
    out = wd.decide(data, get=config(), classifier=lambda m: asked.append(m) or "WAITING")
    assert out is None and asked == []


def test_a_dead_capture_pid_does_not_silence_the_detector(tmp_path):
    proc = subprocess.Popen(["true"]); proc.wait()
    data = _dictation(tmp_path, proc.pid)
    out = wd.decide(data, get=config(), classifier=lambda m: "WAITING")
    assert out == {"decision": "block", "reason": wd.REASON}
