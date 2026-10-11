"""The question relay's decisions — `set_orch.fleet.question_relay.relay`.

Driven with the hook's real input shape (measured on the runtime) and fakes for the
outbound, the clock and the configuration; the state directory is a real tmp_path tree,
because the waiting record and the answer files ARE the mechanism the fleet and the chat
bridge use.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from set_orch.fleet import question_relay as qr

SESSION = "1bf7b969-5208-4020-9aae-850d27d41dae"
SECRET = "Should we drop the customers table?"


def hook_input(questions=None):
    return {
        "session_id": SESSION,
        "tool_use_id": "toolu_01ABC",
        "cwd": "/somewhere/project",
        "tool_name": "AskUserQuestion",
        "tool_input": {"questions": questions or [{
            "question": SECRET, "header": "Drop table",
            "options": [{"label": "Yes", "description": "d"}, {"label": "No", "description": "d"}],
            "multiSelect": False,
        }]},
    }


def config(**over):
    base = {qr.KEY_ENABLED: "true", qr.KEY_TARGET: "command",
            qr.KEY_COMMAND: "bridge be --json -", qr.KEY_AUDIENCE: "DEV"}
    base.update(over)
    store = {k: v for k, v in base.items() if v is not None}

    def get(key, project=None, default=None):
        return store.get(key, default)
    get.store = store
    return get


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def answer(base: Path, envelope: dict, key: str, text: str):
    q = next(q for q in envelope["questions"] if q["key"] == key)
    d = Path(q["valasz_tar"])
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{q['id']}__{key}.json").write_text(json.dumps({"valasz": text}), encoding="utf-8")


def run_relay(tmp_path, get, *, run=None, post=None, on_sleep=None, inp=None):
    clock = Clock()
    seen = {}

    def default_run(cmd, payload):
        seen["cmd"], seen["envelope"] = cmd, json.loads(payload)
        return 0

    def sleep(s):
        clock.sleep(s)
        if on_sleep:
            on_sleep(seen, clock)

    out = qr.relay(inp or hook_input(), get=get, run=run or default_run,
                   post=post or (lambda url, content: seen.setdefault("posts", []).append((url, content))),
                   project_name=lambda cwd: "proj", clock=clock, wall=lambda: 1000.0 + clock.t,
                   sleep=sleep, base=tmp_path)
    return out, seen, clock


def test_off_releases_without_running_anything(tmp_path):
    """AC-1."""
    ran = []
    out, _, _ = run_relay(tmp_path, config(**{qr.KEY_ENABLED: None}), run=lambda c, p: ran.append(1) or 0)
    assert out is None and ran == []
    assert not (tmp_path / "waiting").exists()


def test_other_tools_are_ignored(tmp_path):
    inp = hook_input()
    inp["tool_name"] = "Bash"
    out, seen, _ = run_relay(tmp_path, config(), inp=inp)
    assert out is None and "envelope" not in seen


def test_missing_audience_releases_and_is_named(tmp_path):
    """AC-2: the framework does not supply an audience."""
    get = config(**{qr.KEY_AUDIENCE: None})
    out, seen, _ = run_relay(tmp_path, get)
    assert out is None and "envelope" not in seen
    assert qr.readiness(get)["missing"] == [qr.KEY_AUDIENCE]


def test_unknown_target_is_not_ready(tmp_path):
    get = config(**{qr.KEY_TARGET: "carrier-pigeon"})
    assert qr.readiness(get)["missing"] == [qr.KEY_TARGET]
    assert run_relay(tmp_path, get)[0] is None


def test_envelope_shape(tmp_path):
    def on_sleep(seen, clock):
        answer(tmp_path, seen["envelope"], "Q1", "No")
    out, seen, _ = run_relay(tmp_path, config(), on_sleep=on_sleep)
    [q] = seen["envelope"]["questions"]
    assert q["key"] == "Q1" and q["id"].startswith("relay-1bf7b969-")
    assert q["optionsList"] == ["Yes", "No"]          # structured, never joined
    assert q["multi"] is False and q["audience"] == "DEV"
    assert q["question"] == SECRET
    assert q["source"] == "proj · 1bf7b969"
    assert Path(q["valasz_tar"]) == tmp_path / "answers"


def test_answered_on_the_channel(tmp_path):
    """AC-3: allow + the original input + answers keyed by question text."""
    def on_sleep(seen, clock):
        answer(tmp_path, seen["envelope"], "Q1", "No")
    out, seen, _ = run_relay(tmp_path, config(), on_sleep=on_sleep)
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse" and hso["permissionDecision"] == "allow"
    assert hso["updatedInput"]["answers"] == {SECRET: "No"}
    assert hso["updatedInput"]["questions"] == hook_input()["tool_input"]["questions"]
    assert list((tmp_path / "answers").glob("*.json")) == []      # used answers are removed
    assert not (tmp_path / "waiting").exists() or list((tmp_path / "waiting").iterdir()) == []


def test_waits_for_every_question(tmp_path):
    """AC-4: one of two answers is not an answer."""
    qs = [{"question": "A?", "header": "a", "options": [{"label": "x"}]},
          {"question": "B?", "header": "b", "options": [{"label": "y"}]}]
    polls = []

    def on_sleep(seen, clock):
        polls.append(clock.t)
        if len(polls) == 1:
            answer(tmp_path, seen["envelope"], "Q1", "x")
        if len(polls) == 4:
            answer(tmp_path, seen["envelope"], "Q2", "y")
    out, _, _ = run_relay(tmp_path, config(), on_sleep=on_sleep, inp=hook_input(qs))
    assert len(polls) == 4
    assert out["hookSpecificOutput"]["updatedInput"]["answers"] == {"A?": "x", "B?": "y"}


def test_outbound_failure_releases_at_once(tmp_path):
    """AC-5."""
    out, _, clock = run_relay(tmp_path, config(), run=lambda c, p: 3)
    assert out is None and clock.t == 0
    assert not (tmp_path / "waiting").exists()


def test_outbound_that_cannot_start_releases(tmp_path):
    def boom(cmd, payload):
        raise FileNotFoundError(cmd)
    assert run_relay(tmp_path, config(), run=boom)[0] is None


def test_switch_off_while_waiting_releases(tmp_path):
    """AC-6."""
    get = config()

    def on_sleep(seen, clock):
        if clock.t >= 9:
            get.store[qr.KEY_ENABLED] = "false"
    out, _, clock = run_relay(tmp_path, get, on_sleep=on_sleep)
    assert out is None and clock.t == pytest.approx(9)


def test_release_from_the_fleet(tmp_path):
    """AC-7."""
    def on_sleep(seen, clock):
        assert qr.request_release(SESSION, tmp_path) is True
    out, _, clock = run_relay(tmp_path, config(), on_sleep=on_sleep)
    assert out is None and clock.t == pytest.approx(qr.POLL_S)
    assert list((tmp_path / "waiting").iterdir()) == []


def test_timeout_releases_and_a_late_answer_is_never_used(tmp_path):
    out, seen, clock = run_relay(tmp_path, config(**{qr.KEY_TIMEOUT: "30"}))
    assert out is None and 30 <= clock.t < 30 + qr.POLL_S + 0.001   # on time, not merely eventually
    answer(tmp_path, seen["envelope"], "Q1", "Yes")       # arrives after the release
    assert list((tmp_path / "waiting").iterdir()) == []   # nothing left that would read it


def test_timeout_cannot_exceed_the_hook_ceiling():
    assert qr.timeout_s(config(**{qr.KEY_TIMEOUT: "99999"})) == qr.DEFAULT_TIMEOUT_S
    assert qr.timeout_s(config(**{qr.KEY_TIMEOUT: "soon"})) == qr.DEFAULT_TIMEOUT_S


def test_waiting_record_lifecycle_without_text(tmp_path):
    """AC-8: the record exists while waiting, holds no question text, and goes away."""
    snapshots = []

    def on_sleep(seen, clock):
        snapshots.append(qr.list_waiting(tmp_path))
        if len(snapshots) == 2:
            answer(tmp_path, seen["envelope"], "Q1", "Yes")
    run_relay(tmp_path, config(), on_sleep=on_sleep)
    [rec] = snapshots[0]
    assert rec["session_id"] == SESSION and rec["questions"] == 1 and rec["project"] == "proj"
    raw = (tmp_path / "waiting").glob("*")
    assert list(raw) == []
    assert SECRET not in json.dumps(snapshots) and "Yes" not in json.dumps(snapshots)


def test_log_lines_carry_no_question_text(tmp_path, caplog):
    caplog.set_level("DEBUG", logger="set_orch.fleet.question_relay")
    run_relay(tmp_path, config(**{qr.KEY_TIMEOUT: "6"}))
    run_relay(tmp_path, config(), run=lambda c, p: 1)
    assert caplog.records and SECRET not in caplog.text


def test_webhook_minimal_notifies_and_releases(tmp_path):
    """AC-9: project, agent and header only."""
    get = config(**{qr.KEY_TARGET: "webhook", qr.KEY_WEBHOOK: "https://hook.example/x",
                    qr.KEY_COMMAND: None, qr.KEY_AUDIENCE: None})
    out, seen, clock = run_relay(tmp_path, get)
    assert out is None and clock.t == 0
    [(url, content)] = seen["posts"]
    assert url == "https://hook.example/x"
    assert "proj" in content and "1bf7b969" in content and "Drop table" in content
    assert SECRET not in content and "Yes" not in content


def test_webhook_full_carries_the_text(tmp_path):
    get = config(**{qr.KEY_TARGET: "webhook", qr.KEY_WEBHOOK: "https://hook.example/x",
                    qr.KEY_DETAIL: "full"})
    _, seen, _ = run_relay(tmp_path, get)
    assert SECRET in seen["posts"][0][1] and "Yes" in seen["posts"][0][1]


def test_webhook_failure_still_releases(tmp_path):
    get = config(**{qr.KEY_TARGET: "webhook", qr.KEY_WEBHOOK: "https://hook.example/x"})

    def bad_post(url, content):
        raise OSError("down")
    assert run_relay(tmp_path, get, post=bad_post)[0] is None


def test_set_enabled_refuses_when_not_ready(monkeypatch):
    """AC-11: turning on an incomplete relay is refused, naming the key."""
    written = []
    monkeypatch.setattr(qr.local_config, "set_value", lambda k, v, project=None: written.append((k, v)))
    with pytest.raises(ValueError, match=qr.KEY_AUDIENCE):
        qr.set_enabled(True, get=config(**{qr.KEY_AUDIENCE: None}))
    assert written == []
    qr.set_enabled(True, get=config())
    assert written == [(qr.KEY_ENABLED, True)]


def test_deploy_adds_the_relay_entry_once(tmp_path):
    """AC-13."""
    root = Path(__file__).resolve().parents[2]
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps(
        {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "own-guard"}]}]}}))
    for _ in range(2):
        subprocess.run([str(root / "bin" / "set-deploy-hooks"), "--quiet", str(tmp_path)], check=True)
    pre = json.loads((tmp_path / ".claude" / "settings.json").read_text())["hooks"]["PreToolUse"]
    relay = [h for e in pre if e.get("matcher") == "AskUserQuestion" for h in e["hooks"]
             if h["command"] == "set-hook-question-relay"]
    assert len(relay) == 1 and relay[0]["timeout"] == 3600
    assert any(h["command"] == "own-guard" for e in pre for h in e["hooks"])


def test_hook_script_is_silent_when_off(tmp_path):
    """The carrier: off → exit 0, nothing on stdout."""
    root = Path(__file__).resolve().parents[2]
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "SET_CONFIG_DIR": str(tmp_path / "cfg")}
    res = subprocess.run([str(root / "bin" / "set-hook-question-relay")], input=json.dumps(hook_input()),
                         capture_output=True, text=True, env=env)
    assert res.returncode == 0 and res.stdout == ""


def test_hook_script_answers_end_to_end(tmp_path):
    """The carrier, on: a fake outbound that answers at once; stdout is the answer JSON."""
    root = Path(__file__).resolve().parents[2]
    fake = tmp_path / "fake-bridge"
    fake.write_text("#!/usr/bin/env python3\nimport json,sys,os\n"
                    "e=json.load(sys.stdin)\n"
                    "for q in e['questions']:\n"
                    "    os.makedirs(q['valasz_tar'],exist_ok=True)\n"
                    "    open(os.path.join(q['valasz_tar'],q['id']+'__'+q['key']+'.json'),'w').write(json.dumps({'valasz':'No'}))\n")
    fake.chmod(0o755)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "config.json").write_text(json.dumps({qr.KEY_ENABLED: "true", qr.KEY_TARGET: "command",
                                                 qr.KEY_COMMAND: str(fake), qr.KEY_AUDIENCE: "DEV"}))
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "SET_CONFIG_DIR": str(cfg),
           "SET_QUESTION_RELAY_DIR": str(tmp_path / "state")}
    res = subprocess.run([str(root / "bin" / "set-hook-question-relay")], input=json.dumps(hook_input()),
                         capture_output=True, text=True, env=env, timeout=30)
    assert res.returncode == 0
    assert json.loads(res.stdout)["hookSpecificOutput"]["updatedInput"]["answers"] == {SECRET: "No"}
    assert SECRET not in (tmp_path / "state" / "relay.log").read_text()


def test_api_toggle_and_release(tmp_path, monkeypatch):
    """AC-10 / AC-11 / AC-12 at the route: on is refused while not ready, waiting is counted,
    and a release reaches the record the hook polls."""
    from fastapi import HTTPException
    from set_orch.api import fleet as api

    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SET_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("SET_QUESTION_RELAY_DIR", str(tmp_path / "state"))
    (cfg / "config.json").write_text(json.dumps({qr.KEY_TARGET: "command", qr.KEY_COMMAND: "x"}))

    with pytest.raises(HTTPException) as refused:
        api.fleet_question_relay_toggle(api.RelayToggleBody(enabled=True))
    assert refused.value.status_code == 409 and qr.KEY_AUDIENCE in refused.value.detail
    assert api.fleet_question_relay()["enabled"] is False

    qr.local_config.set_value(qr.KEY_AUDIENCE, "DEV")
    assert api.fleet_question_relay_toggle(api.RelayToggleBody(enabled=True))["enabled"] is True

    for sid in ("aaaaaaaa-1", "bbbbbbbb-2"):
        qr._write_json(qr.waiting_path(sid), {"session_id": sid, "project": "p", "questions": 1,
                                              "target": "command", "started": 0})
    payload = api.fleet_question_relay()
    assert len(payload["waiting"]) == 2 and payload["waiting"][0]["seconds"] > 0

    assert api.fleet_question_relay_release("aaaaaaaa-1")["waiting"][0]["release_requested"] is True
    with pytest.raises(HTTPException) as missing:
        api.fleet_question_relay_release("nobody")
    assert missing.value.status_code == 404


def test_a_bridge_that_leaves_a_child_running_does_not_block_the_hand_off(tmp_path):
    """Measured on the first live run: a pipe held by the bridge's background child made
    the hand-off wait for the child, so nothing ever waited in the fleet's record."""
    bridge = tmp_path / "bridge"
    bridge.write_text("#!/bin/sh\ncat >/dev/null\n(sleep 5) &\nexit 0\n")
    bridge.chmod(0o755)
    import time as _t
    t0 = _t.monotonic()
    assert qr._run_command(str(bridge), "{}") == 0
    assert _t.monotonic() - t0 < 3
