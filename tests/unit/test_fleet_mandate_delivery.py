"""Telling an agent its mandate: the launch additions, the delivered text, the hook, the owner.

What is being guarded, in the order it can go wrong: the carrier must add a hook and nothing
that could replace a project's own setting; no caller text may reach the argv; the hook must
never fail a session start; and the owner must stay a process that persists nothing.
"""

from __future__ import annotations

import asyncio
import json
import os

import pytest

from set_orch.fleet import mandate, mandate_delivery
from set_orch.fleet import owner as owner_mod
from set_orch.fleet import owner_client as client_mod
from set_orch.fleet import ownerd as ownerd_mod
from set_orch.fleet import scopes as scopes_mod
from set_orch.fleet.mandate import MandateStore

MARKER = "ZZ-GOAL-MARKER-ZZ"


@pytest.fixture
def store(tmp_path):
    return MandateStore(str(tmp_path / "state" / "fleet-mandates.json"))


def _work(store, **over):
    args = dict(kind="work", goal="ship the importer", project="proj-a", cwd="/x/proj-a",
                label="proj-a-1200", requested_by="proj-b#12ab34cd", done_when="tests pass",
                scope={"paths": ["src/import/"], "change": "importer"}, carrier=True)
    args.update(over)
    return store.create(**args)


# -- the launch additions ---------------------------------------------------------------


def test_the_settings_carry_one_session_start_hook_and_no_other_key(monkeypatch):
    monkeypatch.setenv(mandate_delivery.ENV_HOOK_BIN, "/opt/fw/bin/set-fleet-mandate")
    settings = json.loads(mandate_delivery.launch_settings())
    # A scalar key here would REPLACE the project's own (statusLine was measured to).
    assert list(settings) == ["hooks"]
    assert list(settings["hooks"]) == ["SessionStart"]
    hooks = settings["hooks"]["SessionStart"]
    assert hooks == [{"hooks": [{"type": "command", "command": "/opt/fw/bin/set-fleet-mandate hook"}]}]


def test_the_hook_command_quotes_a_path_with_a_space(monkeypatch):
    monkeypatch.setenv(mandate_delivery.ENV_HOOK_BIN, "/opt/my tools/set-fleet-mandate")
    assert mandate_delivery.hook_command() == "'/opt/my tools/set-fleet-mandate' hook"


@pytest.mark.parametrize("kind,by_agent,expected", [
    ("desk", True, mandate_delivery.OPENING_DESK),
    ("desk", False, mandate_delivery.OPENING_DESK),
    ("work", True, mandate_delivery.OPENING_WORK),
    ("work", False, None),  # a person will type the first turn
])
def test_the_opening_line_is_chosen_by_kind(kind, by_agent, expected):
    assert mandate_delivery.opening_line(kind, requested_by_agent=by_agent) == expected


def test_launch_additions_put_the_id_in_the_environment_and_the_prompt_last():
    env, tail = mandate_delivery.launch_additions(
        "m-abc", label="proj-a-desk", kind="desk", requested_by_agent=True)
    assert env == {mandate.ENV_MANDATE: "m-abc", mandate.ENV_LABEL: "proj-a-desk"}
    assert tail[0] == "--settings"
    assert json.loads(tail[1])["hooks"]["SessionStart"]
    assert tail[-1] == mandate_delivery.OPENING_DESK
    assert len(tail) == 3


def test_a_person_s_start_gets_the_carrier_and_no_prompt():
    _env, tail = mandate_delivery.launch_additions("m-abc", label="x", kind="work")
    assert len(tail) == 2 and tail[0] == "--settings"


# -- the delivered text -----------------------------------------------------------------


def test_a_work_mandate_reads_goal_scope_requester_and_the_standing_rule(store):
    text = mandate_delivery.render_context(_work(store))
    assert "ship the importer" in text
    assert "src/import/" in text and "importer" in text
    assert "tests pass" in text
    assert "proj-b#12ab34cd" in text and "not verified" in text
    # The standing rule names the desk and the command that reaches it.
    assert "decline it once" in text
    assert 'set-fleet-ask proj-a "<request>"' in text
    assert "proj-a-desk" in text


def test_a_mandate_from_the_operator_says_so(store):
    text = mandate_delivery.render_context(_work(store, requested_by=None))
    assert "Requested by: the operator" in text
    assert "not verified" not in text


def test_a_desk_mandate_is_told_to_answer_with_a_linked_reply(store):
    text = mandate_delivery.render_context(
        _work(store, kind="desk", goal="Answer requests addressed to proj-a", label="proj-a-desk"))
    assert "You are the desk of proj-a" in text
    assert "`re:`" in text and "unlinked reply does not close" in text
    # A desk IS the place outside requests go; it is not told to turn them away.
    assert "decline it once" not in text


def test_absent_optional_fields_leave_no_empty_lines(store):
    text = mandate_delivery.render_context(_work(store, scope=None, done_when=None))
    assert "Scope:" not in text and "Change:" not in text and "Done when:" not in text
    assert "None" not in text


# -- the hook ---------------------------------------------------------------------------


def test_the_hook_delivers_marks_delivered_and_records_the_session(store):
    made = _work(store)
    out = mandate_delivery.hook_output(
        {mandate.ENV_MANDATE: made["id"]}, json.dumps({"session_id": "sess-1", "source": "startup"}),
        store)
    payload = json.loads(out)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "ship the importer" in payload["hookSpecificOutput"]["additionalContext"]
    record = store.get(made["id"])
    assert record["delivered"] is True
    assert record["session_ids"] == ["sess-1"]


def test_a_clear_rotates_the_session_and_the_hook_records_the_new_one(store):
    made = _work(store)
    for sid in ("sess-1", "sess-2", "sess-2"):
        assert mandate_delivery.hook_output(
            {mandate.ENV_MANDATE: made["id"]}, json.dumps({"session_id": sid}), store)
    assert store.get(made["id"])["session_ids"] == ["sess-1", "sess-2"]


@pytest.mark.parametrize("environ", [{}, {mandate.ENV_MANDATE: ""}, {mandate.ENV_MANDATE: "m-unknown"}])
def test_the_hook_prints_nothing_when_there_is_no_mandate(store, environ):
    _work(store)
    assert mandate_delivery.hook_output(environ, "{}", store) is None


def test_the_hook_survives_garbage_on_stdin(store):
    made = _work(store)
    out = mandate_delivery.hook_output({mandate.ENV_MANDATE: made["id"]}, "not json at all", store)
    assert out is not None and store.get(made["id"])["session_ids"] == []


def test_a_broken_store_costs_the_agent_nothing(store):
    made = _work(store)
    with open(store.path, "w") as handle:
        handle.write("{ truncated")
    # No exception, no output: the session starts without a mandate rather than not at all.
    assert mandate_delivery.hook_output({mandate.ENV_MANDATE: made["id"]}, "{}", store) is None


def test_the_cli_hook_always_exits_zero(monkeypatch, capsys, tmp_path):
    from set_orch.fleet import mandate_cli

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setenv(mandate.ENV_MANDATE, "m-nothing")
    monkeypatch.setattr("sys.stdin", open(os.devnull))
    assert mandate_cli.main(["hook"]) == 0
    assert capsys.readouterr().out == ""

    def boom(*a, **k):
        raise RuntimeError("store exploded")

    monkeypatch.setattr(mandate_delivery, "hook_output", boom)
    assert mandate_cli.main(["hook"]) == 0


# -- the owner --------------------------------------------------------------------------


class _FakeOwner:
    def __init__(self):
        self.calls = []

    def owned(self):
        return []

    def start(self, argv, **kw):
        self.calls.append({"argv": list(argv), **kw})
        return owner_mod.OwnedAgent(
            label=kw["label"], unit=scopes_mod.unit_name(kw["label"]),
            pid=4243, cwd=kw["cwd"], master_fd=-1,
        )


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _daemon(monkeypatch, tmp_path):
    owner = _FakeOwner()
    daemon = ownerd_mod.OwnerDaemon(str(tmp_path / "owner.sock"), owner=owner)
    monkeypatch.setattr(daemon, "_attach_drain", lambda agent: None)
    return daemon, owner


def _files(root):
    return sorted(os.path.relpath(os.path.join(d, f), root)
                  for d, _dirs, fs in os.walk(root) for f in fs)


def test_a_start_with_a_mandate_gets_the_id_the_carrier_and_the_opening_line(monkeypatch, tmp_path):
    daemon, owner = _daemon(monkeypatch, tmp_path)
    _run(daemon._do_start({
        "label": "proj-a-desk", "cwd": "/tmp", "mandate_id": "m-abc",
        "mandate_kind": "desk", "requested_by": "proj-b#12ab34cd",
    }))
    call = owner.calls[0]
    assert call["env"][mandate.ENV_MANDATE] == "m-abc"
    assert call["env"][mandate.ENV_LABEL] == "proj-a-desk"
    assert call["argv"][:2] == list(ownerd_mod.DEFAULT_AGENT_ARGV)
    assert call["argv"][2] == "--settings"
    assert call["argv"][-1] == mandate_delivery.OPENING_DESK


def test_a_start_without_a_mandate_is_exactly_what_it_was(monkeypatch, tmp_path):
    daemon, owner = _daemon(monkeypatch, tmp_path)
    _run(daemon._do_start({"label": "plain", "cwd": "/tmp"}))
    call = owner.calls[0]
    assert call["argv"] == list(ownerd_mod.DEFAULT_AGENT_ARGV)
    assert not call["env"]


def test_the_goal_never_reaches_the_owner_s_argv_or_environment(monkeypatch, tmp_path):
    """The owner is handed an id and a kind. A request that smuggles text in is not honoured."""
    daemon, owner = _daemon(monkeypatch, tmp_path)
    _run(daemon._do_start({
        "label": "a", "cwd": "/tmp", "mandate_id": "m-abc", "mandate_kind": "work",
        "requested_by": "proj-b#12ab34cd",
        "goal": MARKER, "mandate": {"goal": MARKER}, "opening": MARKER,
    }))
    call = owner.calls[0]
    assert MARKER not in json.dumps(call["argv"])
    assert MARKER not in json.dumps(call["env"])


def test_the_owner_still_writes_no_file_for_a_mandate(monkeypatch, tmp_path):
    state = tmp_path / "state"
    data = tmp_path / "data"
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    (tmp_path / "run").mkdir()
    daemon, _owner = _daemon(monkeypatch, tmp_path / "run")
    before = _files(str(tmp_path))
    _run(daemon._do_start({"label": "a", "cwd": "/tmp", "mandate_id": "m-abc", "mandate_kind": "desk"}))
    assert _files(str(tmp_path)) == before


def test_a_recovery_with_a_mandate_resumes_with_the_carrier_and_no_prompt(monkeypatch, tmp_path):
    passed = {}
    monkeypatch.setattr(ownerd_mod.provider_record, "get", lambda unit: None)
    monkeypatch.setattr(ownerd_mod, "recover",
                        lambda owner, **kw: passed.update(kw) or owner_mod.OwnedAgent(
                            label="a6", unit="set-agent-a6.scope", pid=1, cwd="/tmp", master_fd=-1))
    daemon, _ = _daemon(monkeypatch, tmp_path)
    _run(daemon._do_recover({
        "unit": "set-agent-a6.scope", "session_id": "sess-1", "cwd": "/tmp",
        "label": "a6", "mandate_id": "m-abc",
    }))
    argv = passed["resume_argv"]
    assert argv[:4] == ["claude", "--dangerously-skip-permissions", "--resume", "sess-1"]
    assert argv[4] == "--settings" and len(argv) == 6  # no positional prompt on a restore
    assert passed["env"][mandate.ENV_MANDATE] == "m-abc"


def test_a_recovery_without_a_mandate_is_untouched(monkeypatch, tmp_path):
    passed = {}
    monkeypatch.setattr(ownerd_mod.provider_record, "get", lambda unit: None)
    monkeypatch.setattr(ownerd_mod, "recover",
                        lambda owner, **kw: passed.update(kw) or owner_mod.OwnedAgent(
                            label="a6", unit="set-agent-a6.scope", pid=1, cwd="/tmp", master_fd=-1))
    daemon, _ = _daemon(monkeypatch, tmp_path)
    _run(daemon._do_recover({"unit": "set-agent-a6.scope", "session_id": "sess-1", "cwd": "/tmp"}))
    assert passed["resume_argv"] is None and passed["env"] is None


def test_the_owner_declares_the_mandate_feature():
    assert "mandate" in ownerd_mod.FEATURES


class _OldOwnerClient(client_mod.OwnerClient):
    """A client talking to an owner that predates the mandate parameter."""

    def __init__(self, features):
        self._features = features
        self.sent = []

    def health(self):
        return {"features": list(self._features)}

    def request(self, method, params=None):
        self.sent.append((method, params))
        return {"label": (params or {}).get("label")}


def test_an_owner_too_old_for_a_mandate_is_refused_before_anything_is_sent():
    client = _OldOwnerClient({"provider-selection", "unit-origin"})
    with pytest.raises(client_mod.OwnerClientError) as err:
        client.start(label="a", cwd="/tmp", mandate_id="m-abc", mandate_kind="work")
    assert getattr(err.value, "kind", None) == "owner-too-old"
    assert client.sent == []
    with pytest.raises(client_mod.OwnerClientError):
        client.recover(unit="u", session_id="s", cwd="/tmp", mandate_id="m-abc")
    assert client.sent == []


def test_a_current_owner_is_sent_the_id_and_the_kind():
    client = _OldOwnerClient({"provider-selection", "unit-origin", "mandate"})
    client.start(label="a", cwd="/tmp", mandate_id="m-abc", mandate_kind="desk")
    method, params = client.sent[0]
    assert method == "start"
    assert params["mandate_id"] == "m-abc" and params["mandate_kind"] == "desk"
    # And a start with no mandate asks no question and sends no field.
    client.start(label="b", cwd="/tmp")
    assert "mandate_id" not in client.sent[1][1]
