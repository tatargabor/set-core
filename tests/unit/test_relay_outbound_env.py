"""The relay tells its outbound what it is asking about (fleet-auto-answer, task 1.1, AC-3).

Each carrier — `AskUserQuestion`, the permission prompt, the continuation question —
runs the configured outbound. The outbound now receives `SET_RELAY_KIND`,
`SET_RELAY_SESSION` and `SET_RELAY_CWD` in its environment, and the envelope it reads on
standard input is byte-for-byte what it was before: a chat bridge posts that envelope, so a
new field in it would carry a local path into a channel.

The byte-equality is measured against a two-argument runner — the shape every runner had
before this change — so "unchanged" is compared with the old contract, not asserted.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from set_orch.fleet import continuation as ct
from set_orch.fleet import question_relay as qr
from set_orch.fleet import wait_detect as wd

SID = "47f1763f-c5c5-4f3a-9aae-850d27d41dae"
CWD = "/somewhere/project"


def config(command="bridge be --json -"):
    store = {qr.KEY_ENABLED: "true", qr.KEY_TARGET: "command", qr.KEY_COMMAND: command, qr.KEY_AUDIENCE: "DEV"}
    return lambda key, project=None, default=None: store.get(key, default)


def answer_first(envelopes, text):
    q = envelopes[-1]["questions"][0]
    (Path(q["valasz_tar"]) / f"{q['id']}__Q1.json").write_text(json.dumps({"valasz": text}))


class Recorder:
    """Two runners side by side: the old two-argument one and one that takes `env`."""

    def __init__(self):
        self.payloads, self.envs = [], []

    def old(self, cmd, payload):
        self.payloads.append(payload)
        return 0

    def new(self, cmd, payload, env=None):
        self.payloads.append(payload)
        self.envs.append(env)
        return 0


def ask(tmp_path, run):
    envelopes = []

    def runner(*a, **k):
        code = run(*a, **k)
        envelopes.append(json.loads(a[1]))
        return code

    # keep the runner's own signature visible to the relay
    if "env" in run.__code__.co_varnames:
        def wrapped(cmd, payload, env=None):
            return runner(cmd, payload, env=env)
    else:
        def wrapped(cmd, payload):
            return runner(cmd, payload)

    t = {"now": 0.0}

    def sleep(s):
        t["now"] += s
        answer_first(envelopes, "Yes")

    inp = {"session_id": SID, "tool_use_id": "toolu_01", "cwd": CWD, "tool_name": "AskUserQuestion",
           "tool_input": {"questions": [{"question": "Q?", "header": "h", "multiSelect": False,
                                         "options": [{"label": "Yes", "description": ""}, {"label": "No", "description": ""}]}]}}
    return qr.relay(inp, get=config(), run=wrapped, project_name=lambda c: "proj",
                    clock=lambda: t["now"], wall=lambda: 1000.0, sleep=sleep, base=tmp_path)


def permission(tmp_path, run):
    envelopes = []

    def keep(payload):
        envelopes.append(json.loads(payload))

    if "env" in run.__code__.co_varnames:
        def wrapped(cmd, payload, env=None):
            keep(payload)
            return run(cmd, payload, env=env)
    else:
        def wrapped(cmd, payload):
            keep(payload)
            return run(cmd, payload)

    t = {"now": 0.0}

    def sleep(s):
        t["now"] += s
        answer_first(envelopes, "Allow")

    inp = {"session_id": SID, "prompt_id": "36bda264", "cwd": CWD, "transcript_path": "/t.jsonl",
           "tool_name": "Bash", "tool_input": {"command": "ls", "description": "list"}}
    return qr.permission(inp, get=config(), run=wrapped, project_name=lambda c: "proj",
                         clock=lambda: t["now"], wall=lambda: 1000.0, sleep=sleep,
                         read_entries=lambda p: [], base=tmp_path)


def continuation(tmp_path, run):
    envelopes = []

    if "env" in run.__code__.co_varnames:
        def wrapped(cmd, payload, env=None):
            envelopes.append(json.loads(payload))
            return run(cmd, payload, env=env)
    else:
        def wrapped(cmd, payload):
            envelopes.append(json.loads(payload))
            return run(cmd, payload)

    inp = {"session_id": SID, "prompt_id": "8593cae2", "hook_event_name": "Stop", "cwd": CWD,
           "stop_hook_active": False, "last_assistant_message": "Done.", "transcript_path": "/t.jsonl"}
    qr._write_json(wd.verdict_path(SID, tmp_path), {"turn": "8593cae2", "verdict": "DONE", "at": 1000.0})
    t = {"now": 0.0}

    def sleep(s):
        t["now"] += s
        if envelopes:
            answer_first(envelopes, "→ Next")

    return ct.continue_turn(inp, get=config(), run=wrapped, project_name=lambda c: "proj",
                            suggester=lambda m: ("Summary.", ["Next"]),
                            clock=lambda: t["now"], wall=lambda: 1000.0, sleep=sleep,
                            read_entries=lambda p: [], env={}, base=tmp_path)


@pytest.mark.parametrize("carrier,kind", [(ask, "ask"), (permission, "permission"), (continuation, "continuation")])
def test_outbound_environment_names_the_call(tmp_path, carrier, kind):
    """AC-3 (and its two siblings): kind, session id and working directory reach the outbound."""
    rec = Recorder()
    assert carrier(tmp_path, rec.new) is not None, "the carrier did not complete the round trip"
    assert rec.envs == [{"SET_RELAY_KIND": kind, "SET_RELAY_SESSION": SID, "SET_RELAY_CWD": CWD}]


@pytest.mark.parametrize("carrier", [ask, permission, continuation])
def test_envelope_bytes_are_unchanged(tmp_path, carrier):
    """The envelope a runner with `env` receives equals the one the old two-argument runner gets."""
    old, new = Recorder(), Recorder()
    carrier(tmp_path / "old", old.old)
    carrier(tmp_path / "new", new.new)
    assert len(old.payloads) == len(new.payloads) == 1
    # The answer directory differs only because the two runs use two state trees.
    normalise = lambda p, root: p.replace(str(root), "<base>")
    assert normalise(old.payloads[0], tmp_path / "old") == normalise(new.payloads[0], tmp_path / "new")
    env = new.envs[0]
    assert not set(json.loads(new.payloads[0])) - {"questions"}
    for q in json.loads(new.payloads[0])["questions"]:
        assert CWD not in json.dumps(q) and SID not in json.dumps(q)
        assert set(q) == {"id", "key", "question", "optionsList", "multi", "audience", "source", "valasz_tar"}
    assert env["SET_RELAY_CWD"] == CWD


def test_the_real_runner_puts_the_variables_in_the_process_environment(tmp_path):
    """`_run_command` is what production uses: a real child process sees the variables and the bytes."""
    out = tmp_path / "seen.json"
    script = tmp_path / "outbound.py"
    script.write_text(
        "import json, os, sys\n"
        f"open({str(out)!r}, 'w').write(json.dumps({{'stdin': sys.stdin.read(), "
        "'env': {k: os.environ.get(k) for k in ('SET_RELAY_KIND', 'SET_RELAY_SESSION', 'SET_RELAY_CWD', 'PATH')}}))\n")
    code = qr._run_command(f"{sys.executable} {script}", '{"questions": []}',
                           env=qr.relay_env("permission", SID, CWD))
    assert code == 0
    seen = json.loads(out.read_text())
    assert seen["stdin"] == '{"questions": []}'
    assert seen["env"]["SET_RELAY_KIND"] == "permission"
    assert seen["env"]["SET_RELAY_SESSION"] == SID and seen["env"]["SET_RELAY_CWD"] == CWD
    assert seen["env"]["PATH"] == os.environ.get("PATH"), "the rest of the environment must be inherited"


def test_the_real_runner_without_env_inherits_unchanged(tmp_path, monkeypatch):
    monkeypatch.delenv("SET_RELAY_KIND", raising=False)
    out = tmp_path / "seen.txt"
    script = tmp_path / "outbound.py"
    script.write_text(f"import os\nopen({str(out)!r}, 'w').write(os.environ.get('SET_RELAY_KIND', '<none>'))\n")
    assert qr._run_command(f"{sys.executable} {script}", "{}") == 0
    assert out.read_text() == "<none>"
