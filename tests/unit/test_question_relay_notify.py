"""The notify relay's decisions — `set_orch.fleet.question_relay.notify`.

One-way by contract: the outbound is called once with the envelope on stdin, the
hook exits 0 whatever happens, and nothing derived from the message persists.
The drop reasons are the acceptance surface — a notify that fails silently is the
defect this exists to end (B-184), so every drop names itself in the log.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from set_orch.fleet import question_relay as qr

SESSION = "33cb8017-d1e5-41a4-bbb6-4e522ca4f648"
MESSAGE = "Claude needs your permission to use Bash"


def event(message=MESSAGE):
    return {"session_id": SESSION, "cwd": "/somewhere/project", "message": message}


def config(**over):
    base = {qr.KEY_ENABLED: "true", qr.KEY_TARGET: "command",
            qr.KEY_COMMAND: "bridge be --json -", qr.KEY_AUDIENCE: "DEV",
            qr.KEY_NOTIFY_COMMAND: "bridge notify -"}
    base.update(over)
    store = {k: v for k, v in base.items() if v is not None}

    def get(key, project=None, default=None):
        return store.get(key, default)
    return get


def test_delivered_once_with_the_envelope_on_stdin():
    calls = []

    def run(command, payload):
        calls.append((command, json.loads(payload)))
        return 0

    assert qr.notify(event(), get=config(), run=run) is None
    assert len(calls) == 1
    command, envelope = calls[0]
    assert command == "bridge notify -"
    assert envelope["kind"] == "notification"
    assert envelope["message"] == MESSAGE
    assert envelope["session_id"] == SESSION
    assert envelope["project"] and envelope["agent"]


def test_switch_off_touches_nothing():
    calls = []
    assert qr.notify(event(), get=config(**{qr.KEY_ENABLED: "false"}),
                     run=lambda c, p: calls.append(c) or 0) is None
    assert calls == []


def test_no_message_is_dropped_and_named():
    calls = []
    reason = qr.notify(event(message=""), get=config(),
                       run=lambda c, p: calls.append(c) or 0)
    assert reason == "nothing to say: no message and no pending call readable"
    assert calls == []  # nothing ran


def test_missing_notify_outbound_is_dropped_with_the_key_named():
    get = config(**{qr.KEY_NOTIFY_COMMAND: None})
    assert qr.notify(event(), get=get) == f"missing {qr.KEY_NOTIFY_COMMAND}"
    state = qr.readiness(get)
    assert state["notify_missing"] == [qr.KEY_NOTIFY_COMMAND]
    assert state["ready"] is True  # questions must not be gated by notify config


def test_notify_failure_is_one_attempt_and_a_named_reason():
    calls = []

    def boom(command, payload):
        calls.append(command)
        raise OSError("no bridge")

    reason = qr.notify(event(), get=config(), run=boom)
    assert calls == ["bridge notify -"]  # one attempt, no retry
    assert "outbound could not run" in reason


def test_nonzero_exit_is_a_named_reason():
    assert qr.notify(event(), get=config(), run=lambda c, p: 3) == "outbound exited 3"


def test_webhook_fallback_notifies_one_way():
    posts = []
    get = config(**{qr.KEY_NOTIFY_COMMAND: None, qr.KEY_WEBHOOK: "https://hooks.example/x"})
    assert qr.notify(event(), get=get, post=lambda url, content: posts.append((url, content))) is None
    assert len(posts) == 1
    assert posts[0][0] == "https://hooks.example/x"
    assert MESSAGE in posts[0][1]


def test_log_lines_carry_no_message_text(caplog):
    calls = []

    def boom(command, payload):
        calls.append(payload)
        return 1

    with caplog.at_level(logging.WARNING, logger="set_orch.fleet.question_relay"):
        qr.notify(event(), get=config(), run=boom)
    assert all(MESSAGE not in r.getMessage() for r in caplog.records)


# ── the carrier, end to end ────────────────────────────────────────────────────

def carrier_env(tmp_path: Path, cfg: dict | None):
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
           "SET_CONFIG_DIR": str(tmp_path / "cfg"),
           "SET_QUESTION_RELAY_DIR": str(tmp_path / "state")}
    if cfg is not None:
        (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
        (tmp_path / "cfg" / "config.json").write_text(json.dumps(cfg))
    return env


def test_carrier_is_silent_when_off(tmp_path):
    root = Path(__file__).resolve().parents[2]
    res = subprocess.run([str(root / "bin" / "set-hook-notify-relay")],
                         input=json.dumps(event()), capture_output=True, text=True,
                         env=carrier_env(tmp_path, {qr.KEY_ENABLED: "false"}), timeout=30)
    assert res.returncode == 0 and res.stdout == ""


def test_carrier_hands_the_envelope_to_the_outbound(tmp_path):
    root = Path(__file__).resolve().parents[2]
    seen = tmp_path / "seen.json"
    fake = tmp_path / "fake-notify"
    fake.write_text("#!/usr/bin/env python3\nimport sys\n"
                    f"open({str(seen)!r},'w').write(sys.stdin.read())\n")
    fake.chmod(0o755)
    env = carrier_env(tmp_path, {qr.KEY_ENABLED: "true", qr.KEY_TARGET: "command",
                                 qr.KEY_COMMAND: "bridge be --json -", qr.KEY_AUDIENCE: "DEV",
                                 qr.KEY_NOTIFY_COMMAND: str(fake)})
    res = subprocess.run([str(root / "bin" / "set-hook-notify-relay")],
                         input=json.dumps(event()), capture_output=True, text=True,
                         env=env, timeout=30)
    assert res.returncode == 0 and res.stdout == ""
    envelope = json.loads(seen.read_text())
    assert envelope["kind"] == "notification"
    assert envelope["message"] == MESSAGE
    log = (tmp_path / "state" / "relay.log").read_text()
    assert MESSAGE not in log  # the log names the delivery, never the text


def test_carrier_malformed_stdin_exits_quietly(tmp_path):
    root = Path(__file__).resolve().parents[2]
    res = subprocess.run([str(root / "bin" / "set-hook-notify-relay")],
                         input="not json at all", capture_output=True, text=True,
                         env=carrier_env(tmp_path, None), timeout=30)
    assert res.returncode == 0 and res.stdout == ""


def test_wire_project_wires_the_notification_hook(tmp_path):
    local = tmp_path / ".claude" / "settings.local.json"
    local.parent.mkdir(parents=True)
    local.write_text("{}")
    qr.wire_project(tmp_path, user_settings=tmp_path / "absent-user.json")
    hooks = json.loads(local.read_text())["hooks"]
    assert any(isinstance(h, dict) and h.get("command") == qr.NOTIFY_HOOK
               for entry in hooks["Notification"] for h in entry.get("hooks", []))


def test_unwired_list_names_the_notification_hook(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / ".claude").mkdir()
    (root / ".claude" / "settings.json").write_text("{}")
    missing = qr.unwired_projects(
        [{"name": "proj", "path": str(root)}],
        user_settings=tmp_path / "absent-user.json")
    assert missing and set(missing[0]["missing"]) == {qr.RELAY_HOOK, qr.WAIT_HOOK, qr.NOTIFY_HOOK}


# ── enrichment: the generic notification text gains WHAT is being asked ───────

def transcript(tmp_path, tool_name, tool_input, eventname="event"):
    lines = [
        json.dumps({"type": "user", "message": {"content": [{"type": "text", "text": "go"}]}}),
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": tool_name, "input": tool_input}]}}),
    ]
    p = tmp_path / f"{eventname}.jsonl"
    p.write_text("\n".join(lines) + "\n")
    return str(p)


def test_enrichment_appends_the_pending_bash_command(tmp_path):
    path = transcript(tmp_path, "Bash", {"command": "git merge origin/dev\n"})
    out = qr.enrich_message({"message": MESSAGE, "transcript_path": path})
    assert out.startswith(MESSAGE)
    assert "Bash: git merge origin/dev" in out


def test_enrichment_covers_an_empty_message_from_the_transcript(tmp_path):
    path = transcript(tmp_path, "Bash", {"command": "git push origin dev"})
    out = qr.enrich_message({"message": "", "transcript_path": path})
    assert out == "Bash: git push origin dev"


def test_enrichment_skips_a_question_tool_and_says_nothing_new(tmp_path):
    path = transcript(tmp_path, "AskUserQuestion", {"questions": [{"question": "x"}]})
    assert qr.enrich_message({"message": MESSAGE, "transcript_path": path}) == MESSAGE


def test_enrichment_falls_back_when_the_transcript_is_unreadable():
    out = qr.enrich_message({"message": MESSAGE,
                             "transcript_path": "/nowhere/at/all.jsonl"})
    assert out == MESSAGE


def test_notify_delivers_the_enriched_message(tmp_path):
    path = transcript(tmp_path, "Bash", {"command": "git merge origin/dev"})
    seen = []

    def run(command, payload):
        seen.append(json.loads(payload))
        return 0

    assert qr.notify({"message": MESSAGE, "session_id": SESSION,
                      "cwd": "/somewhere/project", "transcript_path": path},
                     get=config(), run=run) is None
    assert seen and "git merge origin/dev" in seen[0]["message"]
