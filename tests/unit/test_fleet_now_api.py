"""The Now card's API (fleet-now-card 3.1–3.3), end to end through a fake publisher.

The publisher is a real subprocess behind a declared `.set-endpoint.json`, so the
read goes through the status contract's cached reader and the write through its
writer. The framework aggregator and the input reader are replaced, because what
they measure is a live machine.
"""

import datetime as dt
import json
import time
import logging
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from fastapi.testclient import TestClient  # noqa: E402

from set_orch.server import create_app  # noqa: E402
from set_orch.api import helpers as api_helpers  # noqa: E402
from set_orch.api import now as api_now  # noqa: E402
from set_orch.api import project_status as api_status  # noqa: E402

ORIGINAL_FRAMEWORK_QUEUE = api_now._framework_queue

#: Text that must never reach a log record or the state file. Distinctive so a
#: substring search cannot miss it or hit something unrelated.
SECRET_SENTENCE = "Zq7-sentence-call-the-partner"
SECRET_WHY = "Zq7-why-deadline-friday"
SECRET_LABEL = "Zq7-label-approve"
SECRET_ANSWER = "Zq7-answer-text-go-ahead"
SECRET_REASON = "Zq7-reason-only-i-know-the-client"
SECRET_OUTCOME = "Zq7-outcome-agent-resumed"
SECRETS = (SECRET_SENTENCE, SECRET_WHY, SECRET_LABEL, SECRET_ANSWER, SECRET_REASON, SECRET_OUTCOME)

FAKE = """\
import json, sys, pathlib
here = pathlib.Path(__file__).parent
argv = sys.argv[1:]
(here / "calls.log").open("a").write(json.dumps(argv) + "\\n")
cmd = argv[0]
queue = json.loads((here / "queue.json").read_text())
if cmd == "owner-queue":
    if (here / "fail").exists():
        sys.exit(2)
    print(json.dumps({"contractVersion": 1, "command": cmd, "ok": True, "data": queue}))
elif cmd == "owner-queue-act":
    payload = json.loads(argv[argv.index("--json") + 1])
    if payload["id"] == "refuse-me":
        sys.stderr.write("that item was already closed elsewhere\\n")
        sys.exit(1)
    if payload["action"] in ("answer", "done", "delegate"):
        queue["items"] = [i for i in queue["items"] if i["id"] != payload["id"]]
        (here / "queue.json").write_text(json.dumps(queue))
    print(json.dumps({"contractVersion": 1, "command": cmd, "ok": True,
                      "data": {"outcome": OUTCOME}}))
""".replace("OUTCOME", repr(SECRET_OUTCOME))


def item(id_, project="p1", **extra):
    return {"id": id_, "project": project, "sentence": f"{SECRET_SENTENCE}-{id_}",
            "why": SECRET_WHY, **extra}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SET_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("SET_NOW_DIR", str(tmp_path / "now"))
    monkeypatch.setenv("SET_QUESTION_RELAY_DIR", str(tmp_path / "relay"))
    api_status._CACHE.clear()
    pub = tmp_path / "pub"
    pub.mkdir()
    (pub / "contract.py").write_text(FAKE)
    (pub / "queue.json").write_text(json.dumps({"items": [], "complete": True}))
    manifest = {"contractVersion": 1, "command": [sys.executable, "contract.py"],
                "commands": ["owner-queue"], "writeCommands": ["owner-queue-act"]}
    (pub / ".set-endpoint.json").write_text(json.dumps(manifest))
    other = tmp_path / "p1"
    other.mkdir()
    reg = tmp_path / "projects.json"
    reg.write_text(json.dumps([{"name": "pub", "path": str(pub)}, {"name": "p1", "path": str(other)}]))
    monkeypatch.setattr(api_helpers, "PROJECTS_FILE", reg)

    framework = {"sources": [{"name": "agent-questions", "measured": True, "reason": None, "count": 0}],
                 "items": []}
    monkeypatch.setattr(api_now, "_framework_queue",
                        lambda: (framework["sources"], framework["items"]))
    monkeypatch.setattr(api_now, "_owner_inputs", lambda: [])

    class Env:
        root = tmp_path
        publisher = pub
        manifest_ = manifest
        fw = framework
        client = TestClient(create_app(web_dist_dir=None))

        def queue(self, items, **data):
            (pub / "queue.json").write_text(json.dumps({"items": items, "complete": True, **data}))
            api_status._CACHE.clear()

        def calls(self, command=None):
            log = pub / "calls.log"
            rows = [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
            return [r for r in rows if command is None or r[0] == command]

        def get(self):
            resp = self.client.get("/api/fleet/now")
            assert resp.status_code == 200, resp.text
            return resp.json()

        def act(self, **body):
            return self.client.post("/api/fleet/now/act", json=body)

    yield Env()
    api_status._CACHE.clear()


# --------------------------------------------------------------------------- #
# 3.1 GET
# --------------------------------------------------------------------------- #

def test_ac1_five_items_show_the_first_and_count_four_without_titles(env):
    env.queue([item(str(n)) for n in range(5)])
    data = env.get()
    assert data["item"]["id"] == "0"
    assert data["following"] == 4
    text = json.dumps(data)
    for n in range(1, 5):
        assert f"{SECRET_SENTENCE}-{n}" not in text, "another item's title reached the page"


def test_the_card_locale_is_english_unless_local_config_says_hu(env):
    from set_orch import local_config
    assert env.get()["locale"] == "en"
    local_config.set_value("now.locale", "hu")
    assert env.get()["locale"] == "hu"
    local_config.set_value("now.locale", "klingon")
    assert env.get()["locale"] == "en"


def test_ac2_nothing_waiting_with_every_source_measured(env):
    data = env.get()
    assert data["item"] is None and data["unmeasured"] == 0
    assert data["closedToday"] == 0


def test_ac3_an_unreadable_owner_queue_is_counted_and_named(env):
    (env.publisher / "fail").write_text("")
    data = env.get()
    assert data["item"] is None
    assert data["unmeasured"] == 1
    owner = next(s for s in data["sources"] if s["name"] == "owner-queue")
    assert owner["measured"] is False and "exited 2" in owner["reason"]


def test_framework_sources_unmeasured_when_the_aggregator_is_missing(monkeypatch):
    import types
    from set_orch import fleet as fleet_pkg
    monkeypatch.delattr(fleet_pkg, "waiting", raising=False)
    monkeypatch.setitem(sys.modules, "set_orch.fleet.waiting", None)
    sources, items = ORIGINAL_FRAMEWORK_QUEUE()
    assert items == [] and sources == [{"name": "framework", "measured": False,
                                        "reason": "aggregator not available", "count": None}]
    # Present but without the function: the same answer, not an AttributeError.
    monkeypatch.setitem(sys.modules, "set_orch.fleet.waiting", types.ModuleType("waiting"))
    sources, _ = ORIGINAL_FRAMEWORK_QUEUE()
    assert sources[0]["reason"] == "aggregator not available"


def test_ac5_no_publisher_shows_framework_oldest_first_and_says_so(env):
    (env.publisher / ".set-endpoint.json").write_text(json.dumps({**env.manifest_, "commands": ["x"]}))
    env.fw["items"] = [{"source": "agent-questions", "id": "agent:b", "project": "p1", "since": 200,
                        "title": "b", "session_id": "b"},
                       {"source": "agent-questions", "id": "agent:a", "project": "p1", "since": 100,
                        "title": "a", "session_id": "a"}]
    data = env.get()
    assert data["publisher"]["state"] == "none"
    assert data["unmeasured"] == 0, "not published is not a failure"
    assert data["item"]["id"] == "agent:a" and data["following"] == 1
    assert data["item"]["goThere"] == {"kind": "agent", "href": "/?agent=a"}


def test_ac22_ambiguous_publisher_shows_neither(env, tmp_path):
    second = tmp_path / "pub2"
    second.mkdir()
    (second / "contract.py").write_text(FAKE)
    (second / "queue.json").write_text(json.dumps({"items": [item("z")], "complete": True}))
    (second / ".set-endpoint.json").write_text(json.dumps(env.manifest_))
    reg = json.loads(api_helpers.PROJECTS_FILE.read_text()) + [{"name": "pub2", "path": str(second)}]
    api_helpers.PROJECTS_FILE.write_text(json.dumps(reg))
    env.queue([item("y")])
    data = env.get()
    assert data["publisher"]["state"] == "ambiguous"
    assert data["item"] is None and data["unmeasured"] == 1


def test_ac23_ac24_actions_follow_the_item_shape(env):
    env.queue([item("min"), item("opt", options=[{"id": "a", "label": SECRET_LABEL},
                                                  {"id": "b", "label": "B"}, {"id": "c", "label": "C"}],
                                 delegable=True, acceptsText=True)])
    assert env.get()["item"]["actions"] == ["goThere", "done", "later", "recheck", "inProgress"]
    env.act(id="min", source="owner-queue", action="later", laterSeconds=60)
    second = env.get()["item"]
    assert second["id"] == "opt" and len(second["options"]) == 3
    assert set(second["actions"]) == {"goThere", "done", "later", "recheck", "inProgress", "answer", "text", "delegate"}


def test_ac27_no_write_command_offers_go_there_and_later_only(env):
    (env.publisher / ".set-endpoint.json").write_text(
        json.dumps({k: v for k, v in env.manifest_.items() if k != "writeCommands"}))
    env.queue([item("1")])
    data = env.get()
    assert data["publisher"]["acceptsActions"] is False
    assert data["item"]["actions"] == ["goThere", "later"]
    assert env.act(id="1", source="owner-queue", action="done").status_code == 409


def test_ac25_a_stale_ranking_is_marked_and_a_partial_queue_too(env):
    old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=6)).isoformat()
    (env.publisher / "queue.json").write_text(json.dumps(
        {"items": [item("1")], "complete": False, "rankedAt": old}))
    data = env.get()
    assert data["stale"] is True and data["partial"] is True
    assert 5.9 * 3600 < data["rankingAgeSeconds"] < 6.1 * 3600
    assert data["item"]["id"] == "1", "a stale ranking hides nothing"


def test_the_publishers_unread_sources_reach_the_card(env):
    (env.publisher / "queue.json").write_text(json.dumps(
        {"items": [], "complete": True, "unreadSources": ["mailbox"]}))
    data = env.get()
    assert data["unreadSources"] == ["mailbox"]
    assert data["item"] is None


def test_ac18_wind_down_offers_its_actions_and_keeps_the_queue(env):
    env.queue([item("1", delegable=True)])
    evening = dt.datetime.now().replace(hour=23, minute=30).timestamp()
    data = api_now.build_now(now=evening, inputs=[])
    assert data["windDown"]["active"] is True
    assert data["windDown"]["delegableIds"] == ["1"]
    assert data["item"]["id"] == "1"


# --------------------------------------------------------------------------- #
# 3.2 POST act
# --------------------------------------------------------------------------- #

def test_ac6_ac12_an_option_is_delivered_with_its_outcome_and_the_next_item_follows(env):
    env.queue([item("1", options=[{"id": "a", "label": SECRET_LABEL}]), item("2")])
    resp = env.act(id="1", source="owner-queue", action="answer", option="a").json()
    assert resp["delivered"] is True and resp["outcome"] == SECRET_OUTCOME
    assert resp["closedToday"] == 1
    sent = json.loads(env.calls("owner-queue-act")[-1][2])
    assert sent == {"id": "1", "action": "answer", "option": "a"}
    assert env.get()["item"]["id"] == "2", "the read cache must be dropped after a write"


def test_ac7_a_refused_write_shows_the_reason_and_the_item_stays(env):
    env.queue([item("refuse-me")])
    resp = env.act(id="refuse-me", source="owner-queue", action="done").json()
    assert resp["delivered"] is False and "already closed" in resp["reason"]
    assert resp["closedToday"] == 0
    assert env.get()["item"]["id"] == "refuse-me"


def test_an_option_not_offered_is_refused(env):
    env.queue([item("1", options=[{"id": "a", "label": "A"}])])
    assert env.act(id="1", source="owner-queue", action="answer", option="zz").status_code == 400
    assert env.calls("owner-queue-act") == []


def test_ac10_keeping_a_delegable_item_needs_one_or_two_reasons(env):
    env.queue([item("1", delegable=True)])
    assert env.act(id="1", source="owner-queue", action="done").status_code == 400
    assert env.act(id="1", source="owner-queue", action="done",
                   reasons=["a", "b", "c"]).status_code == 400
    resp = env.act(id="1", source="owner-queue", action="done", reasons=[SECRET_REASON])
    assert resp.json()["delivered"] is True
    assert json.loads(env.calls("owner-queue-act")[-1][2])["reasons"] == [SECRET_REASON]


def test_delegate_needs_no_reasons(env):
    env.queue([item("1", delegable=True)])
    assert env.act(id="1", source="owner-queue", action="delegate").json()["delivered"] is True


def test_ac11_later_sends_nothing_and_the_item_returns(env):
    env.queue([item("1"), item("2")])
    resp = env.act(id="1", source="owner-queue", action="later", laterSeconds=7200).json()
    assert resp["sent"] is False
    assert env.calls("owner-queue-act") == []
    assert env.get()["item"]["id"] == "2"
    state = json.loads((env.root / "now" / "state.json").read_text())
    assert state["snoozes"]["1"] > 0


def test_ac19_parking_an_idea_sends_it_and_counts_it(env):
    resp = env.act(id="idea-1", source="owner-queue", action="park-idea", text="an idea").json()
    assert resp["delivered"] is True and resp["parkedIdeas"] == 1
    assert json.loads(env.calls("owner-queue-act")[-1][2])["action"] == "park-idea"
    assert env.get()["parkedIdeas"] == 1


def test_a_framework_item_done_is_dismissed_locally(env):
    env.fw["items"] = [{"source": "run-state", "id": "run:p1:x:y", "project": "p1", "since": 1, "title": "t"}]
    assert env.get()["item"]["id"] == "run:p1:x:y"
    resp = env.act(id="run:p1:x:y", source="run-state", action="done").json()
    assert resp["delivered"] is True and resp["sent"] is False and resp["closedToday"] == 1
    assert env.get()["item"] is None


def test_a_relayed_question_is_answered_through_the_relays_answer_store(env):
    waiting = env.root / "relay" / "waiting"
    waiting.mkdir(parents=True)
    (waiting / "sess1.json").write_text(json.dumps(
        {"session_id": "sess1", "id": "relay-sess1-abcd", "questions": 1}))
    env.fw["items"] = [{"source": "agent-questions", "id": "agent:sess1", "project": "p1",
                        "since": 1, "title": "q", "session_id": "sess1", "kind": "relayed"}]
    first = env.get()["item"]
    assert first["acceptsText"] is True and "text" in first["actions"]
    resp = env.act(id="agent:sess1", source="agent-questions", action="answer",
                   sessionId="sess1", text=SECRET_ANSWER).json()
    assert resp["delivered"] is True
    answer = json.loads((env.root / "relay" / "answers" / "relay-sess1-abcd__Q1.json").read_text())
    assert answer == {"valasz": SECRET_ANSWER}


def test_a_relay_answer_with_nothing_waiting_is_not_delivered(env):
    resp = env.act(id="agent:x", source="agent-questions", action="answer",
                   sessionId="x", text="hi").json()
    assert resp["delivered"] is False and "no relayed question" in resp["reason"]


# --------------------------------------------------------------------------- #
# focus and resume notes
# --------------------------------------------------------------------------- #

def test_ac16_ac17_focus_swap_and_a_local_resume_note(env):
    (env.publisher / ".set-endpoint.json").write_text(json.dumps({**env.manifest_, "commands": ["x"]}))
    client = env.client
    assert client.post("/api/fleet/now/focus", json={"projects": ["p1", "b", "c"]}).json()["ok"]
    refused = client.post("/api/fleet/now/focus", json={"projects": ["p1", "b", "c", "d"]}).json()
    assert refused["swap"] is True
    out = client.post("/api/fleet/now/focus",
                      json={"projects": ["b", "c"], "notes": {"p1": "next: rerun the import"}}).json()
    assert out["notes"]["p1"]["keptLocally"] is True
    client.post("/api/fleet/now/focus", json={"projects": ["b", "p1"]})
    env.fw["items"] = [{"source": "run-state", "id": "run:p1", "project": "p1", "since": 1, "title": "t"}]
    assert env.get()["item"]["resumeNote"] == "next: rerun the import"


def test_a_resume_note_goes_to_the_publisher_when_one_is_declared(env):
    env.client.post("/api/fleet/now/focus", json={"projects": ["p1"]})
    out = env.client.post("/api/fleet/now/focus",
                          json={"projects": [], "notes": {"p1": "note"}}).json()
    assert out["notes"]["p1"]["delivered"] is True
    sent = [json.loads(c[2]) for c in env.calls("owner-queue-act")]
    assert {"id": "project:p1", "action": "resume-note", "text": "note"} in sent
    state = json.loads((env.root / "now" / "state.json").read_text())
    assert "p1" not in state["resumeNotes"]


def test_any_registered_project_is_offered_for_focus_not_only_one_with_a_card(env):
    env.queue([item("a", project="p1")])
    data = env.get()
    assert data["focusCandidates"] == ["p1"]
    # `pub` has no card, and is still pickable — the owner may want to start exactly that one.
    assert data["focusOthers"] == ["pub"]


def test_saving_the_focus_tells_the_publisher(env):
    out = env.client.post("/api/fleet/now/focus", json={"projects": ["pub", "p1"]}).json()
    assert out["ok"] is True
    assert out["publisher"]["delivered"] is True
    assert out["publisher"]["outcome"] == SECRET_OUTCOME
    sent = json.loads(env.calls("owner-queue-act")[-1][2])
    assert sent == {"id": "focus", "action": "focus", "projects": ["pub", "p1"]}


def test_a_focus_without_a_publisher_is_saved_and_says_it_was_not_sent(env):
    (env.publisher / ".set-endpoint.json").write_text(json.dumps({**env.manifest_, "commands": ["x"]}))
    out = env.client.post("/api/fleet/now/focus", json={"projects": ["p1"]}).json()
    assert out["ok"] is True and out["focus"] == ["p1"]
    assert out["publisher"]["delivered"] is False and out["publisher"]["reason"]
    assert env.get()["focus"] == ["p1"]


# --------------------------------------------------------------------------- #
# 3.3 nothing of the item's content in a log or the state file
# --------------------------------------------------------------------------- #

def test_ac20_no_item_text_reaches_a_log_record_or_the_state_file(env, caplog):
    caplog.set_level(logging.DEBUG)
    env.queue([item("1", options=[{"id": "a", "label": SECRET_LABEL}], delegable=True,
                    acceptsText=True), item("2", delegable=True)])
    env.get()
    env.act(id="1", source="owner-queue", action="answer", option="a", reasons=[SECRET_REASON])
    env.get()
    env.act(id="2", source="owner-queue", action="answer", text=SECRET_ANSWER, reasons=[SECRET_REASON])
    env.get()

    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "act id=1 action=answer" in logged, "the action line itself must be there"
    state_text = (env.root / "now" / "state.json").read_text()
    for secret in SECRETS:
        assert secret not in logged, f"{secret} reached a log record"
        assert secret not in state_text, f"{secret} reached the state file"


def test_switching_a_tag_off_hides_its_cards_and_says_how_many(env):
    env.queue([item("1", project="a"), item("2", project="b"), item("3", project="a")])
    data = env.get()
    assert [(g["name"], g["count"], g["muted"]) for g in data["groups"]] == [("a", 2, False), ("b", 1, False)]
    assert env.client.post("/api/fleet/now/groups", json={"muted": ["a"]}).json() == {"ok": True, "muted": ["a"]}
    data = env.get()
    assert data["item"]["id"] == "2"
    assert data["mutedHidden"] == 2
    assert data["following"] == 0
    assert {g["name"]: g["muted"] for g in data["groups"]} == {"a": True, "b": False}
    env.client.post("/api/fleet/now/groups", json={"muted": []})
    assert env.get()["item"]["id"] == "1"


def test_a_ranked_item_without_a_link_has_nowhere_to_go(env):
    """The project's status page says nothing about a ranked task (owner, 2026-10-30)."""
    env.queue([item("1", project="p1"), item("2", project="p1", link="https://admin.example/billing")])
    assert env.get()["item"]["goThere"] is None
    env.act(id="1", source="owner-queue", action="done")
    assert env.get()["item"]["goThere"] == {"kind": "link", "href": "https://admin.example/billing"}


def test_not_needed_with_a_reason_closes_even_a_delegable_item(env):
    env.queue([item("1", delegable=True), item("2")])
    refused = env.act(id="1", source="owner-queue", action="done")
    assert refused.status_code == 400
    ok = env.act(id="1", source="owner-queue", action="done", text="Not needed: we moved the domain").json()
    assert ok["delivered"] is True
    sent = json.loads(env.calls("owner-queue-act")[-1][2])
    assert sent == {"id": "1", "action": "done", "text": "Not needed: we moved the domain"}


def test_a_file_path_link_is_handed_to_the_desktop_not_opened_as_a_page(env):
    env.queue([item("1", link="/home/someone/project/docs/plan.md"), item("2", link="/p/x/status")])
    assert env.get()["item"]["goThere"] == {"kind": "file", "href": "/home/someone/project/docs/plan.md"}
    env.act(id="1", source="owner-queue", action="done")
    assert env.get()["item"]["goThere"] == {"kind": "link", "href": "/p/x/status"}


# --------------------------------------------------------------------------- #
# 7.7 recheck, firstSeen, check
# --------------------------------------------------------------------------- #

def test_ac42_recheck_is_sent_and_the_item_stays(env):
    env.queue([item("1"), item("2")])
    resp = env.act(id="1", source="owner-queue", action="recheck").json()
    assert resp["delivered"] is True and resp["outcome"] == SECRET_OUTCOME
    assert resp["closedToday"] == 0, "a recheck closes nothing"
    sent = json.loads(env.calls("owner-queue-act")[-1][2])
    assert sent == {"id": "1", "action": "recheck"}
    assert env.get()["item"]["id"] == "1"


def test_working_on_it_is_sent_with_note_and_return_time_and_closes_nothing(env):
    env.queue([item("1"), item("2")])
    assert "inProgress" in env.get()["item"]["actions"]
    resp = env.act(id="1", source="owner-queue", action="in-progress",
                   text="  on it now  ", laterSeconds=7200).json()
    assert resp["delivered"] is True and resp["outcome"] == SECRET_OUTCOME
    assert resp["closedToday"] == 0, "working on it closes nothing"
    sent = json.loads(env.calls("owner-queue-act")[-1][2])
    assert sent["id"] == "1" and sent["action"] == "in-progress" and sent["text"] == "on it now"
    # The return time is the card's choice, as an absolute time ~2 h ahead.
    import datetime as dt
    until = dt.datetime.fromisoformat(sent["until"].replace("Z", "+00:00")).timestamp()
    assert 7100 < until - time.time() < 7300


def test_working_on_it_without_a_time_leaves_the_default_to_the_publisher(env):
    env.queue([item("1")])
    env.act(id="1", source="owner-queue", action="in-progress")
    sent = json.loads(env.calls("owner-queue-act")[-1][2])
    assert sent == {"id": "1", "action": "in-progress"}


def test_a_progress_note_reaches_the_card(env):
    env.queue([item("1", progressNote="Jegyzeted (10. 30.): on it")])
    assert env.get()["item"]["progressNote"] == "Jegyzeted (10. 30.): on it"


def test_a_refused_recheck_shows_the_publishers_reason(env):
    env.queue([item("refuse-me")])
    resp = env.act(id="refuse-me", source="owner-queue", action="recheck").json()
    assert resp["delivered"] is False and "already closed" in resp["reason"]


def test_ac43_ac44_first_seen_and_check_reach_the_card(env):
    env.queue([item("1", firstSeen="2026-10-29T13:02:00Z",
                    check={"state": "stale", "startedAt": "2026-10-30T09:00:00Z",
                           "at": "2026-10-30T09:01:00Z", "evidence": "sent on 10-29"})])
    got = env.get()["item"]
    assert got["firstSeen"] == "2026-10-29T13:02:00Z"
    assert got["check"] == {"state": "stale", "startedAt": "2026-10-30T09:00:00Z",
                            "at": "2026-10-30T09:01:00Z", "evidence": "sent on 10-29"}


def test_an_unknown_check_state_and_a_bad_first_seen_are_dropped(env):
    env.queue([item("1", firstSeen="yesterday", check={"state": "maybe"})])
    got = env.get()["item"]
    assert "firstSeen" not in got and "check" not in got
