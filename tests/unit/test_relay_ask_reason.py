"""The asking hook's reason in the permission post (change relay-permission-reason, B-188 a).

The runtime's PermissionRequest payload carries no word from the PreToolUse hook that raised
the `ask`, so the hook hands its reason over through `set-hook-notify-relay --ask-reason`, and
the permission post for exactly that call shows it. Payload shapes are the measured ones:
PreToolUse input (session_id, tool_name, tool_input) plus the hook's reason.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path

from set_orch.fleet import question_relay as qr

SESSION = "215ec2b5-9e2b-4096-94b2-6b1f99bef416"
CMD = {"command": "node review.mjs --change scheduled-publish --out x.md", "description": "review"}
REASON = "release publish must run as one bare command"
ROOT = Path(__file__).resolve().parents[2]


def hook_input(**over):
    d = {"session_id": SESSION, "tool_name": "Bash", "tool_input": dict(CMD), "reason": REASON,
         "source": "bash-guard", "hook_event_name": "PreToolUse", "cwd": "/x"}
    d.update(over)
    return d


def perm_input(tool_input=None):
    return {"session_id": SESSION, "hook_event_name": "PermissionRequest", "cwd": "/x",
            "transcript_path": "/t.jsonl", "tool_name": "Bash",
            "tool_input": dict(CMD) if tool_input is None else tool_input}


def records(base: Path):
    return sorted((base / "ask-reasons").glob("*.json")) if (base / "ask-reasons").is_dir() else []


# ── the store ────────────────────────────────────────────────────────────────


def test_a_fresh_matching_reason_appears_in_the_post_and_is_consumed(tmp_path):
    """AC-5"""
    assert qr.store_ask_reason(hook_input(), tmp_path, wall=lambda: 1000.0)
    assert len(records(tmp_path)) == 1
    text = qr.permission_question("proj", SESSION[:8], perm_input(), tmp_path, wall=lambda: 1030.0)
    assert f"Why it asks (bash-guard): {REASON}" in text
    assert records(tmp_path) == []
    again = qr.permission_question("proj", SESSION[:8], perm_input(), tmp_path, wall=lambda: 1031.0)
    assert "Why it asks" not in again, "a reason is used once"


def test_key_order_in_the_input_does_not_matter(tmp_path):
    qr.store_ask_reason(hook_input(tool_input={"description": "review", "command": CMD["command"]}),
                        tmp_path, wall=lambda: 1000.0)
    assert "Why it asks" in qr.permission_question("proj", "s", perm_input(), tmp_path, wall=lambda: 1001.0)


def test_a_reason_for_another_command_is_not_shown(tmp_path):
    """AC-6"""
    qr.store_ask_reason(hook_input(tool_input={"command": "aiplus-release publish v1"}), tmp_path,
                        wall=lambda: 1000.0)
    text = qr.permission_question("proj", "s", perm_input(), tmp_path, wall=lambda: 1001.0)
    assert "Why it asks" not in text


def test_a_reason_from_another_session_is_not_shown(tmp_path):
    qr.store_ask_reason(hook_input(session_id="aaaaaaaa-other"), tmp_path, wall=lambda: 1000.0)
    assert "Why it asks" not in qr.permission_question("proj", "s", perm_input(), tmp_path, wall=lambda: 1001.0)


def test_a_stale_reason_is_not_shown_and_is_removed(tmp_path):
    """AC-7"""
    qr.store_ask_reason(hook_input(), tmp_path, wall=lambda: 1000.0)
    late = 1000.0 + qr.ASK_REASON_WINDOW_S + 1
    for p in records(tmp_path):
        os.utime(p, (1000.0, 1000.0))
    text = qr.permission_question("proj", "s", perm_input(), tmp_path, wall=lambda: late)
    assert "Why it asks" not in text
    assert records(tmp_path) == []


def test_no_reason_keeps_the_post_without_a_why_line(tmp_path):
    """AC-8"""
    text = qr.permission_question("proj", "47f1763f", perm_input(), tmp_path, wall=lambda: 1.0)
    assert "Why it asks" not in text
    assert text.startswith("🔐 Permission asked — proj · 47f1763f\nBash: node review.mjs")
    assert text.endswith("passes your words to the agent.")


def test_stale_records_are_pruned_on_the_next_write(tmp_path):
    """AC-11"""
    qr.store_ask_reason(hook_input(tool_input={"command": "old"}), tmp_path, wall=lambda: 1000.0)
    old = records(tmp_path)[0]
    os.utime(old, (1000.0, 1000.0))
    qr.store_ask_reason(hook_input(), tmp_path, wall=lambda: 1000.0 + qr.ASK_REASON_WINDOW_S + 5)
    assert not old.exists() and len(records(tmp_path)) == 1


def test_incomplete_input_stores_nothing(tmp_path):
    for bad in (hook_input(reason=""), hook_input(session_id=""), hook_input(tool_name=None)):
        assert not qr.store_ask_reason(bad, tmp_path)
    assert not qr.store_ask_reason(["not", "a", "dict"], tmp_path)  # type: ignore[arg-type]
    assert records(tmp_path) == []


def test_the_log_carries_no_command_or_reason(tmp_path, caplog):
    """AC-4"""
    caplog.set_level(logging.DEBUG)
    qr.store_ask_reason(hook_input(), tmp_path)
    qr.store_ask_reason(hook_input(reason=""), tmp_path)
    qr.permission_question("proj", "s", perm_input(), tmp_path)
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "stored" in logged and SESSION[:8] in logged
    assert REASON not in logged and "scheduled-publish" not in logged


# ── the command bound ────────────────────────────────────────────────────────


def test_a_long_bash_command_is_cut_with_a_marker(tmp_path):
    """AC-9"""
    text = qr.permission_question("proj", "s", perm_input({"command": "x" * 1500}), tmp_path)
    line = text.split("\n")[1]
    assert line == "Bash: " + "x" * 1200 + "… [+300 chars cut]"


def test_a_short_bash_command_is_shown_whole(tmp_path):
    """AC-10"""
    cmd = "y" * 200
    text = qr.permission_question("proj", "s", perm_input({"command": cmd}), tmp_path)
    assert text.split("\n")[1] == "Bash: " + cmd and "chars cut" not in text


def test_the_relayed_post_carries_the_reason_end_to_end(tmp_path):
    """The permission carrier itself puts the reason in the envelope it hands over."""
    qr.store_ask_reason(hook_input(), tmp_path, wall=lambda: 1000.0)
    sent = []
    store = {qr.KEY_ENABLED: "true", qr.KEY_TARGET: "command", qr.KEY_COMMAND: "bridge be", qr.KEY_AUDIENCE: "DEV"}
    t = [0.0]

    def sleep(s):
        t[0] += s
        q = sent[-1]["questions"][0]
        (Path(q["valasz_tar"]) / f"{q['id']}__Q1.json").write_text(json.dumps({"valasz": "Deny"}))

    qr.permission(perm_input(), get=lambda k, project=None, default=None: store.get(k, default),
                  run=lambda cmd, payload: sent.append(json.loads(payload)) or 0,
                  project_name=lambda c: "proj", clock=lambda: t[0], wall=lambda: 1010.0, sleep=sleep,
                  read_entries=lambda p: [], base=tmp_path)
    assert f"Why it asks (bash-guard): {REASON}" in sent[0]["questions"][0]["question"]


# ── the carrier, end to end ──────────────────────────────────────────────────


def carrier(tmp_path: Path, enabled: str, stdin: str):
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    (tmp_path / "cfg" / "config.json").write_text(json.dumps({qr.KEY_ENABLED: enabled}))
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "SET_CONFIG_DIR": str(tmp_path / "cfg"),
           "SET_QUESTION_RELAY_DIR": str(tmp_path / "state")}
    return subprocess.run([str(ROOT / "bin" / "set-hook-notify-relay"), "--ask-reason"], input=stdin,
                          capture_output=True, text=True, env=env, timeout=30)


def test_the_carrier_stores_while_on(tmp_path):
    """AC-1"""
    res = carrier(tmp_path, "true", json.dumps(hook_input()))
    assert res.returncode == 0 and res.stdout == "" and res.stderr == ""
    assert len(records(tmp_path / "state")) == 1
    log = (tmp_path / "state" / "relay.log").read_text()
    assert REASON not in log and "scheduled-publish" not in log


def test_the_carrier_stores_nothing_while_off(tmp_path):
    """AC-2"""
    res = carrier(tmp_path, "false", json.dumps(hook_input()))
    assert res.returncode == 0 and res.stdout == ""
    assert records(tmp_path / "state") == []


def test_the_carrier_ignores_malformed_input(tmp_path):
    """AC-3"""
    for stdin in ("not json", "[1,2]", json.dumps(hook_input(reason=""))):
        res = carrier(tmp_path, "true", stdin)
        assert res.returncode == 0 and res.stdout == ""
    assert records(tmp_path / "state") == []
