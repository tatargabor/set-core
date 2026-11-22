"""The permission carrier — `question_relay.permission` (B-188).

Driven with the `PermissionRequest` payload shape measured on Claude Code 2.1.330
(`session_id`, `prompt_id`, `tool_name`, `tool_input`, `transcript_path`, `cwd`), a fake
outbound that records the envelope, and an injected transcript reader standing in for the
terminal: a `tool_result` for the pending call appearing there means the terminal answered.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from set_orch.fleet import question_relay as qr

CMD = {"command": "psql prod -c 'drop table x'", "description": "drop"}


def perm_input(tool="Bash", tool_input=None):
    return {"session_id": "47f1763f-c5c5-4f3a", "prompt_id": "36bda264", "hook_event_name": "PermissionRequest",
            "cwd": "/x", "transcript_path": "/t.jsonl", "tool_name": tool,
            "tool_input": CMD if tool_input is None else tool_input}


def config(**over):
    store = {qr.KEY_ENABLED: "true", qr.KEY_TARGET: "command", qr.KEY_COMMAND: "bridge be", qr.KEY_AUDIENCE: "DEV"}
    store.update(over)
    store = {k: v for k, v in store.items() if v is not None}
    return lambda key, project=None, default=None: store.get(key, default)


def tool_use(i, inp=CMD, name="Bash"):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": i, "name": name, "input": inp}]}}


def tool_result(i, error=False):
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": i, "is_error": error}]}}


class World:
    """The outbound, the clock and the terminal, all under the test's control."""

    def __init__(self, base: Path, answer=None, answer_after=0, terminal_after=None, code=0,
                 history=()):
        self.base, self.answer, self.answer_after = base, answer, answer_after
        self.terminal_after, self.code = terminal_after, code
        self.entries = list(history) + [tool_use("pending")]
        self.envelopes, self.t, self.polls = [], 0.0, 0

    def run(self, cmd, payload):
        self.envelopes.append(json.loads(payload))
        return self.code

    def clock(self):
        return self.t

    def sleep(self, s):
        self.t += s
        self.polls += 1
        if self.answer is not None and self.polls == self.answer_after:
            q = self.envelopes[-1]["questions"][0]
            path = Path(q["valasz_tar"]) / f"{q['id']}__Q1.json"
            path.write_text(json.dumps({"valasz": self.answer}))
        if self.terminal_after is not None and self.polls == self.terminal_after:
            self.entries.append(tool_result("pending"))

    def read(self, _path):
        return list(self.entries)

    def decide(self, get=None, inp=None):
        return qr.permission(inp or perm_input(), get=get or config(), run=self.run,
                             project_name=lambda c: "proj", clock=self.clock, wall=lambda: 1000.0,
                             sleep=self.sleep, read_entries=self.read, base=self.base)


def decision(out):
    return out["hookSpecificOutput"]["decision"]


def test_allowed_on_the_channel(tmp_path):
    """AC-1: the literal Allow option allows; the envelope is the bridge's shape."""
    w = World(tmp_path, answer="Allow", answer_after=1)
    out = w.decide()
    assert out["hookSpecificOutput"]["hookEventName"] == "PermissionRequest"
    assert decision(out) == {"behavior": "allow"}
    q = w.envelopes[0]["questions"][0]
    assert q["optionsList"] == ["Allow", "Deny"] and q["key"] == "Q1" and q["audience"] == "DEV"
    assert "psql prod" in q["question"] and "proj" in q["question"] and q["id"].startswith("relay-47f1763f-")
    assert not qr.waiting_path("47f1763f-c5c5-4f3a", tmp_path).exists()


def test_deny_option(tmp_path):
    out = World(tmp_path, answer="Deny", answer_after=1).decide()
    assert decision(out)["behavior"] == "deny" and "relay channel" in decision(out)["message"]


@pytest.mark.parametrize("text", ["use the staging database instead", "yes", "allow", "Allow · megjegyzés: ok"])
def test_free_text_is_a_refusal_with_the_owners_words(tmp_path, text):
    """AC-2: fail closed — anything but the literal option denies, and carries the words."""
    out = World(tmp_path, answer=text, answer_after=1).decide()
    assert decision(out)["behavior"] == "deny" and text in decision(out)["message"]


def test_webhook_target_leaves_it_to_the_terminal(tmp_path):
    """AC-4."""
    w = World(tmp_path, answer="Allow", answer_after=1)
    assert w.decide(get=config(**{qr.KEY_TARGET: "webhook", qr.KEY_WEBHOOK: "https://h"})) is None
    assert w.envelopes == []


def test_relay_off_does_nothing(tmp_path):
    w = World(tmp_path)
    assert w.decide(get=config(**{qr.KEY_ENABLED: None})) is None and w.envelopes == []


def test_the_question_tool_is_not_ours(tmp_path):
    w = World(tmp_path)
    assert w.decide(inp=perm_input(tool="AskUserQuestion", tool_input={"questions": []})) is None
    assert w.envelopes == []


def test_outbound_failure_releases_at_once(tmp_path):
    """AC-6."""
    w = World(tmp_path, code=3)
    assert w.decide() is None and w.polls == 0
    assert not qr.waiting_path("47f1763f-c5c5-4f3a", tmp_path).exists()


def test_answered_in_the_terminal_first(tmp_path):
    """AC-5: the result appearing in the transcript releases; a later channel answer acts on nothing."""
    w = World(tmp_path, answer="Allow", answer_after=5, terminal_after=2)
    assert w.decide() is None
    assert w.polls == 2
    assert not qr.waiting_path("47f1763f-c5c5-4f3a", tmp_path).exists()


def test_answer_racing_the_terminal_is_dropped(tmp_path):
    """The answer file and the terminal result land in the same poll: the terminal wins."""
    w = World(tmp_path, answer="Allow", answer_after=2, terminal_after=2)
    assert w.decide() is None


def test_an_earlier_identical_call_is_not_this_one(tmp_path):
    """The same command allowed an hour ago already has a result; that is the baseline, not a signal."""
    w = World(tmp_path, answer="Allow", answer_after=2, history=[tool_use("old"), tool_result("old")])
    assert decision(w.decide()) == {"behavior": "allow"}


def test_timeout_releases(tmp_path):
    w = World(tmp_path)
    assert w.decide(get=config(**{qr.KEY_TIMEOUT: "9"})) is None
    assert w.t >= 9


def test_waiting_record_shape_while_waiting(tmp_path):
    """The bridge reads this record; its removal is the release that closes the post."""
    seen = {}
    w = World(tmp_path, answer="Deny", answer_after=1)
    orig = w.sleep

    def sleep(s):
        seen.update(json.loads(qr.waiting_path("47f1763f-c5c5-4f3a", tmp_path).read_text()))
        orig(s)
    w.sleep = sleep
    w.decide()
    assert seen["kind"] == "permission" and seen["questions"] == 1 and seen["target"] == "command"
    assert seen["id"].startswith("relay-47f1763f-") and "pid" in seen
    assert "psql" not in json.dumps(seen)


def test_logs_carry_no_command_text(tmp_path, caplog):
    caplog.set_level("DEBUG", logger="set_orch.fleet.question_relay")
    World(tmp_path, answer="use staging", answer_after=1).decide()
    assert caplog.records and "psql" not in caplog.text and "staging" not in caplog.text


def test_carrier_is_silent_when_relay_off(tmp_path):
    import subprocess
    root = Path(__file__).resolve().parents[2]
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "SET_CONFIG_DIR": str(tmp_path / "cfg")}
    res = subprocess.run([str(root / "bin" / "set-hook-permission-relay")], input=json.dumps(perm_input()),
                         capture_output=True, text=True, env=env)
    assert res.returncode == 0 and res.stdout == "" and res.stderr == ""


def test_terminal_answer_between_reading_the_answer_and_acting_on_it(tmp_path):
    """The re-check after the answer arrived: the terminal result lands right after the
    answer file was consumed — the decision must still be dropped."""
    w = World(tmp_path, answer="Allow", answer_after=1)
    orig = w.read

    def read(path):
        q = w.envelopes[-1]["questions"][0] if w.envelopes else None
        if q and w.polls >= 1 and not (Path(q["valasz_tar"]) / f"{q['id']}__Q1.json").exists():
            if tool_result("pending") not in w.entries:
                w.entries.append(tool_result("pending"))
        return orig(path)
    w.read = read
    assert w.decide() is None


@pytest.mark.parametrize("carrier", ["set-hook-permission-relay", "set-hook-continue-relay"])
def test_the_fleet_keeps_a_live_carriers_record(tmp_path, carrier):
    """`list_waiting` drops a record whose pid is not a relay carrier (B-159). A new carrier
    missing from that list would have its record removed mid-wait — and the bridge reads a
    removed record as a release and closes the post."""
    import subprocess
    import sys
    live = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)", carrier])
    try:
        qr._write_json(qr.waiting_path("s-1", tmp_path), {"session_id": "s-1", "pid": live.pid, "kind": "permission",
                                                          "questions": 1, "started": 0})
        assert [r["session_id"] for r in qr.list_waiting(tmp_path)] == ["s-1"]
    finally:
        live.kill()
        live.wait()


@pytest.mark.parametrize("sig", ["SIGTERM", "SIGHUP"])
def test_a_carrier_killed_mid_wait_removes_its_record(tmp_path, sig):
    """Measured 2026-11-22: closing the session kills a waiting carrier, and a default
    signal death skips `finally:` — the record stayed, so the bridge would keep its post open."""
    import os
    import signal
    import subprocess
    import time
    root = Path(__file__).resolve().parents[2]
    bridge = tmp_path / "bridge.sh"
    bridge.write_text("#!/bin/sh\ncat >/dev/null\n")
    bridge.chmod(0o755)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "config.json").write_text(json.dumps({
        "question_relay.enabled": True, "question_relay.target": "command",
        "question_relay.command": str(bridge), "question_relay.audience": "DEV"}))
    state = tmp_path / "state"
    env = {**os.environ, "SET_CONFIG_DIR": str(cfg), "SET_QUESTION_RELAY_DIR": str(state)}
    proc = subprocess.Popen([str(root / "bin" / "set-hook-permission-relay")], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    proc.stdin.write(json.dumps({**perm_input(), "transcript_path": str(tmp_path / "none.jsonl")}))
    proc.stdin.close()
    record = qr.waiting_path("47f1763f-c5c5-4f3a", state)
    for _ in range(100):
        if record.exists():
            break
        time.sleep(0.05)
    assert record.exists(), "the carrier never started waiting"
    proc.send_signal(getattr(signal, sig))
    assert proc.wait(timeout=10) == 0
    assert proc.stdout.read() == ""
    assert not record.exists()
