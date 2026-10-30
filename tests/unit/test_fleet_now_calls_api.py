"""The Calls tab's API (fleet-now-card section 9), end to end through a fake publisher.

The publisher is a real subprocess behind a declared `.set-endpoint.json`, so the read
goes through the status contract's cached reader and the write through its writer.
"""

import datetime as dt
import json
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from fastapi.testclient import TestClient  # noqa: E402

from set_orch.server import create_app  # noqa: E402
from set_orch.api import helpers as api_helpers  # noqa: E402
from set_orch.api import project_status as api_status  # noqa: E402
from set_orch.fleet import owner_calls as oc  # noqa: E402
from set_orch.project_status import StatusResult  # noqa: E402

#: Text that must never reach a log record. Distinctive so a substring search cannot miss.
SECRET_WHO = "Zq9-who-the-supplier-contact"
SECRET_ABOUT = "Zq9-about-the-delayed-order"
SECRET_PHONE = "+36-Zq9-555-0101"
SECRET_NOTE = "Zq9-note-they-will-send-it-monday"
SECRET_OUTCOME = "Zq9-outcome-call-recorded"
SECRETS = (SECRET_WHO, SECRET_ABOUT, SECRET_PHONE, SECRET_NOTE, SECRET_OUTCOME)

FAKE = """\
import json, sys, pathlib
here = pathlib.Path(__file__).parent
argv = sys.argv[1:]
(here / "calls.log").open("a").write(json.dumps(argv) + "\\n")
cmd = argv[0]
answer = json.loads((here / "calls.json").read_text())
if cmd == "owner-calls":
    if (here / "fail").exists():
        sys.exit(2)
    print(json.dumps({"contractVersion": 1, "command": cmd, "ok": True, "data": answer}))
elif cmd == "owner-calls-act":
    payload = json.loads(argv[argv.index("--json") + 1])
    if payload["id"] == "refuse-me":
        sys.stderr.write("that call was already made from another device\\n")
        sys.exit(1)
    if payload["action"] in ("called", "not-needed"):
        answer["calls"] = [c for c in answer["calls"] if c["id"] != payload["id"]]
    (here / "calls.json").write_text(json.dumps(answer))
    print(json.dumps({"contractVersion": 1, "command": cmd, "ok": True,
                      "data": {"outcome": OUTCOME}}))
""".replace("OUTCOME", repr(SECRET_OUTCOME))


def call(id_, kind="promised", **extra):
    return {"id": id_, "who": f"{SECRET_WHO}-{id_}", "about": SECRET_ABOUT, "kind": kind,
            "phone": SECRET_PHONE, **extra}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SET_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("SET_NOW_DIR", str(tmp_path / "now"))
    api_status._CACHE.clear()
    pub = tmp_path / "pub"
    pub.mkdir()
    (pub / "contract.py").write_text(FAKE)
    (pub / "calls.json").write_text(json.dumps({"calls": [], "complete": True}))
    manifest = {"contractVersion": 1, "command": [sys.executable, "contract.py"],
                "commands": ["owner-calls"], "writeCommands": ["owner-calls-act"]}
    (pub / ".set-endpoint.json").write_text(json.dumps(manifest))
    reg = tmp_path / "projects.json"
    reg.write_text(json.dumps([{"name": "pub", "path": str(pub)}]))
    monkeypatch.setattr(api_helpers, "PROJECTS_FILE", reg)

    class Env:
        publisher = pub
        client = TestClient(create_app(web_dist_dir=None))

        def answer(self, calls, **data):
            (pub / "calls.json").write_text(json.dumps({"calls": calls, "complete": True, **data}))
            api_status._CACHE.clear()

        def manifest(self, **changes):
            (pub / ".set-endpoint.json").write_text(json.dumps({**manifest, **changes}))

        def calls(self, command=None):
            log = pub / "calls.log"
            rows = [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
            return [r for r in rows if command is None or r[0] == command]

        def get(self, refresh=False):
            resp = self.client.get("/api/fleet/now/calls" + ("?refresh=true" if refresh else ""))
            assert resp.status_code == 200, resp.text
            return resp.json()

        def act(self, **body):
            return self.client.post("/api/fleet/now/calls/act", json=body)

    yield Env()
    api_status._CACHE.clear()


# --------------------------------------------------------------------------- #
# parse
# --------------------------------------------------------------------------- #

def test_a_call_needs_id_who_about_and_a_known_kind():
    assert oc.parse_call(call("c1"))["phone"] == SECRET_PHONE
    assert oc.parse_call({**call("c1"), "kind": "gossip"}) is None
    assert oc.parse_call({**call("c1"), "who": "  "}) is None
    assert oc.parse_call({**call("c1"), "about": None}) is None
    assert oc.parse_call({**call("c1"), "id": "Bad Id"}) is None
    for kind in oc.CALL_KINDS:
        assert oc.parse_call(call("c1", kind))["kind"] == kind


def test_a_bad_optional_field_is_dropped_not_the_call():
    parsed = oc.parse_call(call("c1", due="next week", attempts=-1, lastAttempt="soon",
                                evidence=[{"link": "/x"}, {"label": "mail 10-29", "link": "/m"}] * 3))
    assert parsed is not None
    assert "due" not in parsed and "attempts" not in parsed and "lastAttempt" not in parsed
    assert parsed["evidence"] == [{"label": "mail 10-29", "link": "/m"}] * 3
    assert len(oc.parse_call(call("c2", evidence=[{"label": "x"}] * 9))["evidence"]) == 4


def test_parse_counts_malformed_and_duplicates():
    read = oc.parse_calls(StatusResult(command="owner-calls", ok=True, data={"calls": [call("c1"), call("c1"), {"id": "x"}],
                                                      "complete": True}), now=0)
    assert [c["id"] for c in read.calls] == ["c1"] and read.malformed == 2


def test_act_payload_shapes():
    assert oc.act_payload("c1", "called") == {"id": "c1", "action": "called"}
    assert oc.act_payload("c1", "called", text="  ok  ") == {"id": "c1", "action": "called", "text": "ok"}
    assert oc.act_payload("c1", "later", until="2026-11-01T08:00:00Z")["until"] == "2026-11-01T08:00:00Z"
    with pytest.raises(ValueError):
        oc.act_payload("c1", "later")
    with pytest.raises(ValueError):
        oc.act_payload("c1", "dial")


# --------------------------------------------------------------------------- #
# GET
# --------------------------------------------------------------------------- #

def test_calls_in_order_with_overdue_marked(env):
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    today = dt.date.today().isoformat()
    an_hour_ago = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).isoformat()
    env.answer([call("c1", due=yesterday), call("c2", "retry", due=today, attempts=2),
                call("c3", "missed", due=an_hour_ago), call("c4", "follow-up")])
    data = env.get()
    assert data["publisher"]["state"] == "ok" and data["measured"] is True
    assert [c["id"] for c in data["calls"]] == ["c1", "c2", "c3", "c4"]
    # A bare date is due all day: today's is not overdue yet, yesterday's is.
    assert [c["overdue"] for c in data["calls"]] == [True, False, True, False]
    assert data["overdueCount"] == 2
    assert data["calls"][1]["attempts"] == 2
    assert data["acceptsActions"] is True and data["partial"] is False


def test_no_project_declares_calls(env):
    env.manifest(commands=["owner-queue"], writeCommands=["owner-queue-act"])
    data = env.get()
    assert data["publisher"]["state"] == "none"
    assert data["measured"] is None                      # not declared is not a failure
    assert data["calls"] == [] and data["acceptsActions"] is False
    assert "no call list is published" in data["reason"]


def test_a_failed_read_is_unmeasured_with_its_reason(env):
    env.answer([call("c1")])
    (env.publisher / "fail").write_text("")
    data = env.get(refresh=True)
    assert data["measured"] is False and data["reason"]
    assert data["calls"] == []


def test_partial_stale_and_malformed_are_marked_not_hidden(env):
    old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=9)).isoformat()
    env.answer([call("c1"), {"id": "bad"}], complete=False, rankedAt=old, unreadSources=["mailbox"])
    data = env.get()
    assert [c["id"] for c in data["calls"]] == ["c1"] and data["malformed"] == 1
    assert data["partial"] is True and data["unreadSources"] == ["mailbox"]
    assert data["stale"] is True and data["rankedAt"] == old


def test_the_calls_payload_carries_the_card_locale(env):
    from set_orch import local_config
    env.answer([call("c1")])
    assert env.get()["locale"] == "en"
    local_config.set_value("now.locale", "hu")
    data = env.get()
    assert data["locale"] == "hu" and data["calls"][0]["who"] == f"{SECRET_WHO}-c1"


# --------------------------------------------------------------------------- #
# POST
# --------------------------------------------------------------------------- #

def test_called_sends_id_action_and_note_and_the_next_read_is_fresh(env):
    env.answer([call("c1"), call("c2")])
    assert len(env.get()["calls"]) == 2
    resp = env.act(id="c1", action="called", text=SECRET_NOTE)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"delivered": True, "outcome": SECRET_OUTCOME, "reason": None, "errorClass": None}
    sent = env.calls("owner-calls-act")[-1]
    assert sent[1] == "--json" and json.loads(sent[2]) == {"id": "c1", "action": "called", "text": SECRET_NOTE}
    # The read cache was dropped on delivery: the same non-refresh GET sees the change.
    assert [c["id"] for c in env.get()["calls"]] == ["c2"]


def test_each_action_sends_its_body(env):
    env.answer([call("c1")])
    until = "2026-11-02T08:00:00+00:00"
    assert env.act(id="c1", action="no-answer").json()["delivered"]
    assert env.act(id="c1", action="later", until=until).json()["delivered"]
    assert env.act(id="c1", action="not-needed").json()["delivered"]
    assert [json.loads(c[2]) for c in env.calls("owner-calls-act")] == [
        {"id": "c1", "action": "no-answer"},
        {"id": "c1", "action": "later", "until": until},
        {"id": "c1", "action": "not-needed"}]


def test_bad_requests_are_refused_before_the_publisher(env):
    env.answer([call("c1")])
    assert env.act(id="c1", action="dial").status_code == 400
    assert env.act(id="c1", action="later").status_code == 400
    assert env.act(id="gone", action="called").status_code == 409
    assert env.calls("owner-calls-act") == []


def test_without_the_write_command_the_calls_are_read_only(env):
    env.manifest(writeCommands=[])
    env.answer([call("c1")])
    assert env.get()["acceptsActions"] is False
    resp = env.act(id="c1", action="called")
    assert resp.status_code == 409 and "accepts no answers" in resp.json()["detail"]
    assert env.calls("owner-calls-act") == []


def test_no_publisher_is_409(env):
    env.manifest(commands=["something-else"])
    resp = env.act(id="c1", action="called")
    assert resp.status_code == 409 and "owner-calls" in resp.json()["detail"]


def test_a_refusal_carries_the_projects_reason(env):
    env.answer([call("refuse-me")])
    body = env.act(id="refuse-me", action="called").json()
    assert body["delivered"] is False and "another device" in body["reason"]


def test_no_call_text_reaches_a_log_record(env, caplog):
    caplog.set_level(logging.DEBUG)
    env.answer([call("c1"), call("c2"), {"id": "bad", "who": SECRET_WHO}])
    env.get()
    env.act(id="c1", action="called", text=SECRET_NOTE)
    env.act(id="c2", action="no-answer")
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "calls act id=c1 action=called status=delivered" in logged
    for secret in SECRETS:
        assert secret not in logged, f"{secret} reached a log record"
