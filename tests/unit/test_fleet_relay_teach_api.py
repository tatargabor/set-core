"""fleet-relay-teach routes: Details and Teach, through the route functions with the real state
layout in a tmp tree (`SET_QUESTION_RELAY_DIR`) and a real git repository as the project."""
from __future__ import annotations

import json
import os
import subprocess
import time

import pytest
from fastapi import HTTPException

from set_orch.fleet import auto_answer_worker as aw
from set_orch.fleet import question_relay as qr
from set_orch.fleet import relay_teach as rt

CID = "relay-47f1763f-0123456789ab"
SID = "47f1763f-c5c5-4f3a-9aae-850d27d41dae"


@pytest.fixture
def world(tmp_path, monkeypatch):
    for var, sub in (("SET_CONFIG_DIR", "cfg"), ("SET_QUESTION_RELAY_DIR", "state"), ("XDG_DATA_HOME", "data")):
        (tmp_path / sub).mkdir()
        monkeypatch.setenv(var, str(tmp_path / sub))
    for k in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(k, "t")
    for k in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(k, "t@t")
    monkeypatch.setattr(qr, "_hook_alive", lambda pid: True)
    proj = tmp_path / "proj"
    subprocess.run(["git", "init", "-q", "-b", "main", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "commit", "-q", "--allow-empty", "-m", "init"], check=True)
    return tmp_path


def wait(world, **over):
    rec = {"session_id": SID, "id": CID, "project": "proj", "cwd": str(world / "proj"), "questions": 1,
           "target": "command", "started": time.time() - 120, "pid": os.getpid(), **over}
    qr._write_json(qr.waiting_path(SID, world / "state"), rec)


def pending(world, outcome="no-decision", **q):
    aw._private_write(aw.pending_path(world / "state", CID), {
        "id": CID, "session_id": SID, "kind": "ask", "source": "proj · 47f1763f", "project": "proj",
        "cwd": str(world / "proj"), "created": time.time() - 100, "write_at": None, "state": "forwarded",
        "cancelled": False,
        "questions": [{"key": "Q1", "question": "Mehet élesbe a weboldal?", "options": ["Igen", "Még ne"],
                       "outcome": outcome, "reason": "abstained: the sources do not settle it", **q}]})


def test_detail_of_an_abstained_question(world):
    """AC-1 (the data half; the overlay is checked in the browser, task 4.4)."""
    from set_orch.api import fleet_relay_teach as api
    wait(world)
    pending(world)
    d = api.question_relay_detail(CID)
    assert d["kind"] == "question" and d["waits_for"] == "answer" and d["seconds"] >= 119
    q = d["decider"]["questions"][0]
    assert q["question"] == "Mehet élesbe a weboldal?" and q["options"] == ["Igen", "Még ne"]
    assert q["outcome"] == "no-decision" and "do not settle" in q["reason"]
    assert d["teach"]["allowed"] is True


def test_detail_without_a_decider_record_is_outline_only_and_not_teachable(world):
    """AC-2."""
    from set_orch.api import fleet_relay_teach as api
    wait(world)
    d = api.question_relay_detail(CID)
    assert d["decider"] is None and d["questions"] == 1
    assert d["teach"]["allowed"] is False and "no record" in d["teach"]["reason"]


def test_detail_of_a_permission_prompt_says_why_it_cannot_be_taught(world):
    """AC-5."""
    from set_orch.api import fleet_relay_teach as api
    wait(world, kind="permission")
    pending(world)
    d = api.question_relay_detail(CID)
    assert d["teach"]["allowed"] is False and "permission prompt" in d["teach"]["reason"]
    with pytest.raises(HTTPException) as e:
        api.question_relay_teach(CID, api.TeachBody(answer="Allow"))
    assert e.value.status_code == 409


def test_detail_of_a_call_that_is_not_waiting_is_404(world):
    from set_orch.api import fleet_relay_teach as api
    with pytest.raises(HTTPException) as e:
        api.question_relay_detail(CID)
    assert e.value.status_code == 404


def test_teach_answers_and_commits(world):
    """AC-3 through the route."""
    from set_orch.api import fleet_relay_teach as api
    wait(world)
    pending(world, choice="Igen", tier="likely")
    assert api.question_relay_detail(CID)["teach"]["prefill"] == "Igen"
    res = api.question_relay_teach(CID, api.TeachBody(answer="Igen", explanation="ha le van ellenőrizve"))
    assert res["answered"] and res["written"] and res["commit"]["sha"] and res["commit"]["branch"] == "main"
    ans = qr.answer_file(world / "state" / "answers", CID, "Q1")
    assert json.loads(ans.read_text())["valasz"] == "Igen"
    body = (world / "proj" / rt.RULES_REL).read_text()
    assert "Mehet élesbe a weboldal?" in body and "ha le van ellenőrizve" in body


def test_the_route_is_registered_before_the_project_families():
    """CB-16: a /api/fleet/... route registered after /api/{project}/... is answered as a project."""
    from set_orch.api import router
    paths = [getattr(r, "path", "") for r in router.routes]
    i = paths.index("/api/fleet/question-relay/{call_id}/detail")
    j = next(k for k, p in enumerate(paths) if p.startswith("/api/{project}"))
    assert i < j
