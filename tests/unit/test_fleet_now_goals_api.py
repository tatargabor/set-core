"""The Goals tab's API (fleet-now-card 7.3), end to end through a fake publisher.

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

#: Text that must never reach a log record. Distinctive so a substring search cannot miss.
SECRET_TITLE = "Zq8-title-win-the-tender"
SECRET_WHY = "Zq8-why-the-board-asked"
SECRET_SENTENCE = "Zq8-sentence-merge-two-goals"
SECRET_RENAME = "Zq8-rename-ship-the-pilot"
SECRET_OUTCOME = "Zq8-outcome-goal-confirmed"
SECRETS = (SECRET_TITLE, SECRET_WHY, SECRET_SENTENCE, SECRET_RENAME, SECRET_OUTCOME)

FAKE = """\
import json, sys, pathlib
here = pathlib.Path(__file__).parent
argv = sys.argv[1:]
(here / "calls.log").open("a").write(json.dumps(argv) + "\\n")
cmd = argv[0]
answer = json.loads((here / "goals.json").read_text())
if cmd == "owner-goals":
    if (here / "fail").exists():
        sys.exit(2)
    print(json.dumps({"contractVersion": 1, "command": cmd, "ok": True, "data": answer}))
elif cmd == "owner-goals-act":
    payload = json.loads(argv[argv.index("--json") + 1])
    if payload["id"] == "refuse-me":
        sys.stderr.write("that goal was merged elsewhere\\n")
        sys.exit(1)
    for g in answer["goals"]:
        if g["id"] == payload["id"] and payload["action"] == "keep":
            g["status"] = "confirmed"
    (here / "goals.json").write_text(json.dumps(answer))
    print(json.dumps({"contractVersion": 1, "command": cmd, "ok": True,
                      "data": {"outcome": OUTCOME}}))
""".replace("OUTCOME", repr(SECRET_OUTCOME))


def goal(id_, status="proposed", **extra):
    return {"id": id_, "title": f"{SECRET_TITLE}-{id_}", "status": status, "why": SECRET_WHY, **extra}


def advice(id_, kind="merge"):
    return {"id": id_, "kind": kind, "sentence": f"{SECRET_SENTENCE}-{id_}", "why": SECRET_WHY}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SET_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("SET_NOW_DIR", str(tmp_path / "now"))
    api_status._CACHE.clear()
    pub = tmp_path / "pub"
    pub.mkdir()
    (pub / "contract.py").write_text(FAKE)
    (pub / "goals.json").write_text(json.dumps({"goals": [], "advice": [], "complete": True}))
    manifest = {"contractVersion": 1, "command": [sys.executable, "contract.py"],
                "commands": ["owner-goals"], "writeCommands": ["owner-goals-act"]}
    (pub / ".set-endpoint.json").write_text(json.dumps(manifest))
    other = tmp_path / "p1"
    other.mkdir()
    reg = tmp_path / "projects.json"
    reg.write_text(json.dumps([{"name": "pub", "path": str(pub)}, {"name": "p1", "path": str(other)}]))
    monkeypatch.setattr(api_helpers, "PROJECTS_FILE", reg)

    class Env:
        publisher = pub
        client = TestClient(create_app(web_dist_dir=None))

        def answer(self, goals, advice_=(), **data):
            body = {"goals": goals, "advice": list(advice_), "complete": True, **data}
            (pub / "goals.json").write_text(json.dumps(body))
            api_status._CACHE.clear()

        def manifest(self, **changes):
            (pub / ".set-endpoint.json").write_text(json.dumps({**manifest, **changes}))

        def calls(self, command=None):
            log = pub / "calls.log"
            rows = [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
            return [r for r in rows if command is None or r[0] == command]

        def get(self, refresh=False):
            resp = self.client.get("/api/fleet/now/goals" + ("?refresh=true" if refresh else ""))
            assert resp.status_code == 200, resp.text
            return resp.json()

        def act(self, **body):
            return self.client.post("/api/fleet/now/goals/act", json=body)

    yield Env()
    api_status._CACHE.clear()


# --------------------------------------------------------------------------- #
# GET
# --------------------------------------------------------------------------- #

def test_ac33_ac41_goals_and_advice_with_the_proposed_count(env):
    env.answer([goal("g1"), goal("g2", "confirmed"), goal("g3"), goal("g4")],
               [advice("a1"), advice("a2", "neglected")])
    data = env.get()
    assert data["publisher"]["state"] == "ok" and data["measured"] is True
    assert [g["id"] for g in data["goals"]] == ["g1", "g2", "g3", "g4"]
    assert data["proposedCount"] == 3
    assert [a["id"] for a in data["advice"]] == ["a1", "a2"]
    assert data["acceptsVerdicts"] is True
    assert data["partial"] is False and data["stale"] is False


def test_ac34_no_project_declares_goals(env):
    env.manifest(commands=["owner-queue"], writeCommands=["owner-queue-act"])
    data = env.get()
    assert data["publisher"]["state"] == "none"
    assert data["measured"] is None                      # not declared is not a failure
    assert data["goals"] == [] and data["acceptsVerdicts"] is False
    assert "no goal list is published" in data["reason"]


def test_ac37_a_failed_read_is_unmeasured_with_its_reason(env):
    env.answer([goal("g1")])
    (env.publisher / "fail").write_text("")
    data = env.get(refresh=True)
    assert data["measured"] is False and data["reason"]
    assert data["goals"] == [] and data["proposedCount"] == 0


def test_partial_stale_and_malformed_are_marked_not_hidden(env):
    old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=40)).isoformat()
    env.answer([goal("g1"), {"id": "bad"}], [advice("a1"), {"id": "bad-advice"}],
               complete=False, synthesizedAt=old, unreadSources=["mailbox"])
    data = env.get()
    assert [g["id"] for g in data["goals"]] == ["g1"]
    assert data["malformedGoals"] == 1 and data["malformedAdvice"] == 1
    assert data["partial"] is True and data["unreadSources"] == ["mailbox"]
    assert data["stale"] is True and data["ageSeconds"] > 39 * 3600
    assert data["synthesizedAt"] == old


def test_the_goals_payload_carries_the_card_locale(env):
    from set_orch import local_config
    env.answer([goal("g1")])
    assert env.get()["locale"] == "en"
    local_config.set_value("now.locale", "hu")
    data = env.get()
    assert data["locale"] == "hu"
    # The publisher's text is never translated — the title arrives as written.
    assert data["goals"][0]["title"] == f"{SECRET_TITLE}-g1"


def test_the_stale_threshold_is_configurable(env, tmp_path):
    from set_orch import local_config
    recent = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=5)).isoformat()
    env.answer([goal("g1")], synthesizedAt=recent)
    assert env.get()["stale"] is False
    local_config.set_value("now.stale_goals_hours", "4")
    assert env.get()["stale"] is True


def test_ac39_without_the_write_command_the_goals_are_read_only(env):
    env.manifest(writeCommands=[])
    env.answer([goal("g1")])
    data = env.get()
    assert data["measured"] is True and data["acceptsVerdicts"] is False
    resp = env.act(id="g1", action="keep")
    assert resp.status_code == 409 and "accepts no verdicts" in resp.json()["detail"]
    assert env.calls("owner-goals-act") == []


# --------------------------------------------------------------------------- #
# POST
# --------------------------------------------------------------------------- #

def test_ac38_keep_sends_id_and_action_and_the_next_read_is_fresh(env):
    env.answer([goal("g1")])
    assert env.get()["proposedCount"] == 1
    resp = env.act(id="g1", action="keep")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"delivered": True, "outcome": SECRET_OUTCOME, "reason": None, "errorClass": None}
    sent = env.calls("owner-goals-act")[-1]
    assert sent[1] == "--json" and json.loads(sent[2]) == {"id": "g1", "action": "keep"}
    # The read cache was dropped on delivery: the same non-refresh GET sees the change.
    assert env.get()["proposedCount"] == 0


def test_rename_sends_the_text_and_needs_it(env):
    env.answer([goal("g1")])
    assert env.act(id="g1", action="rename").status_code == 400
    assert env.act(id="g1", action="rename", text="  ").status_code == 400
    resp = env.act(id="g1", action="rename", text=SECRET_RENAME)
    assert resp.status_code == 200 and resp.json()["delivered"]
    assert json.loads(env.calls("owner-goals-act")[-1][2]) == {
        "id": "g1", "action": "rename", "text": SECRET_RENAME}


def test_advice_verdicts_need_an_advice_id_and_goal_verdicts_a_goal_id(env):
    env.answer([goal("g1")], [advice("a1")])
    assert env.act(id="g1", action="accept").status_code == 409
    assert env.act(id="a1", action="keep").status_code == 409
    for action in ("accept", "decline"):
        resp = env.act(id="a1", action=action)
        assert resp.status_code == 200 and resp.json()["delivered"]
    assert [json.loads(c[2]) for c in env.calls("owner-goals-act")] == [
        {"id": "a1", "action": "accept"}, {"id": "a1", "action": "decline"}]


def test_an_unknown_action_is_400_and_a_vanished_id_is_409(env):
    env.answer([goal("g1")])
    assert env.act(id="g1", action="launch").status_code == 400
    assert env.act(id="gone", action="drop").status_code == 409
    assert env.calls("owner-goals-act") == []


def test_no_publisher_is_409(env):
    env.manifest(commands=["something-else"])
    resp = env.act(id="g1", action="keep")
    assert resp.status_code == 409 and "owner-goals" in resp.json()["detail"]


def test_a_refusal_carries_the_projects_reason(env):
    env.answer([goal("refuse-me")])
    body = env.act(id="refuse-me", action="drop").json()
    assert body["delivered"] is False and "merged elsewhere" in body["reason"]


def test_no_goal_text_reaches_a_log_record(env, caplog):
    caplog.set_level(logging.DEBUG)
    env.answer([goal("g1"), goal("g2")], [advice("a1")])
    env.get()
    env.act(id="g1", action="rename", text=SECRET_RENAME)
    env.act(id="a1", action="accept")
    env.act(id="g2", action="keep")
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "goals act id=g1 action=rename status=delivered" in logged
    for secret in SECRETS:
        assert secret not in logged, f"{secret} reached a log record"
