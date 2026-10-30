"""The owner-goals adapter (fleet-now-card 7.1–7.2), against a fake declared endpoint.

The fake is a real subprocess speaking the status contract, so discovery, the read and
the write go through the contract's own reader and writer — the same arrangement as
`test_fleet_owner_queue.py`.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.fleet import owner_goals as og  # noqa: E402
from set_orch.fleet import owner_queue as oq  # noqa: E402
from set_orch.project_status import StatusResult, query, write  # noqa: E402

NOW = 1_800_000_000.0

FAKE = """\
import json, sys, pathlib
here = pathlib.Path(__file__).parent
argv = sys.argv[1:]
(here / "calls.log").open("a").write(json.dumps(argv) + "\\n")
cmd = argv[0]
if cmd in ("owner-goals", "owner-queue"):
    print(json.dumps({"contractVersion": 1, "command": cmd, "ok": True,
                      "data": json.loads((here / "answer.json").read_text())}))
elif cmd == "owner-goals-act":
    payload = json.loads(argv[argv.index("--json") + 1])
    if payload["id"] == "refuse-me":
        sys.stderr.write("that goal was merged into another one\\n")
        sys.exit(1)
    print(json.dumps({"contractVersion": 1, "command": cmd, "ok": True,
                      "data": {"outcome": "goal confirmed"}}))
"""


def make_project(root: Path, name: str, *, answer=None, reads=("owner-goals",),
                 writes=("owner-goals-act",)) -> Path:
    proj = root / name
    proj.mkdir()
    (proj / "contract.py").write_text(FAKE)
    (proj / "answer.json").write_text(json.dumps(answer or {"goals": [], "advice": [], "complete": True}))
    manifest = {"contractVersion": 1, "command": [sys.executable, "contract.py"],
                "commands": list(reads)}
    if writes:
        manifest["writeCommands"] = list(writes)
    (proj / ".set-endpoint.json").write_text(json.dumps(manifest))
    return proj


def calls(proj: Path):
    log = proj / "calls.log"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def find(reg, configured=None):
    return oq.find_publisher(reg, configured, read_command=og.READ_COMMAND,
                             write_command=og.WRITE_COMMAND, published="goal list")


# --------------------------------------------------------------------------- #
# 7.1 discovery by command name
# --------------------------------------------------------------------------- #

def test_ac33_the_queue_publisher_that_also_declares_goals_is_found_for_both(tmp_path):
    pub = make_project(tmp_path, "pub", reads=("owner-queue", "owner-goals"),
                       writes=("owner-queue-act", "owner-goals-act"))
    other = make_project(tmp_path, "other", reads=("something-else",), writes=())
    reg = [{"name": "pub", "path": str(pub)}, {"name": "other", "path": str(other)}]
    goals = find(reg)
    assert goals.state == "ok" and goals.name == "pub" and goals.accepts_actions
    queue = oq.find_publisher(reg, None)
    assert queue.state == "ok" and queue.name == "pub"


def test_ac34_no_project_declares_goals_while_the_queue_is_declared(tmp_path):
    pub = make_project(tmp_path, "pub", reads=("owner-queue",), writes=("owner-queue-act",))
    reg = [{"name": "pub", "path": str(pub)}]
    goals = find(reg)
    assert goals.state == "none"
    assert "'owner-goals'" in goals.reason and "no goal list is published" in goals.reason
    assert oq.find_publisher(reg, None).state == "ok"   # the queue is unaffected


def test_accepts_actions_checks_the_write_command_paired_with_the_read(tmp_path):
    # Declares the QUEUE's write command only: the queue accepts actions, the goals do not.
    pub = make_project(tmp_path, "pub", reads=("owner-queue", "owner-goals"),
                       writes=("owner-queue-act",))
    reg = [{"name": "pub", "path": str(pub)}]
    assert oq.find_publisher(reg, None).accepts_actions is True
    goals = find(reg)
    assert goals.state == "ok" and goals.accepts_actions is False


def test_the_now_publisher_override_applies_to_goals_too(tmp_path):
    a = make_project(tmp_path, "a")
    b = make_project(tmp_path, "b")
    reg = [{"name": "a", "path": str(a)}, {"name": "b", "path": str(b)}]
    amb = find(reg)
    assert amb.state == "ambiguous" and "'owner-goals'" in amb.reason
    assert find(reg, "b").name == "b"
    c = make_project(tmp_path, "c", reads=("owner-queue",))
    missing = find(reg + [{"name": "c", "path": str(c)}], "c")
    assert missing.state == "configured-missing" and "does not declare 'owner-goals'" in missing.reason


# --------------------------------------------------------------------------- #
# 7.2 the shapes
# --------------------------------------------------------------------------- #

def goal(id_, status="proposed", **extra):
    return {"id": id_, "title": f"title {id_}", "status": status, **extra}


def advice(id_, kind="add", **extra):
    return {"id": id_, "kind": kind, "sentence": f"sentence {id_}", "why": f"why {id_}", **extra}


def test_goals_and_advice_parse_in_order_with_optional_fields(tmp_path):
    answer = {
        "complete": True, "synthesizedAt": "2027-01-15T06:00:00+00:00",
        "goals": [
            goal("g1", "confirmed", why="w", serves="the parent", deadline="2027-02-01",
                 progress={"text": "3 of 5 shipped", "done": 3, "total": 5},
                 projects=["publisher-app", "", 7], openItems=4,
                 evidence=[{"label": "plan", "link": "/x/plan.md"}, {"label": "note"}, {"link": "no-label"}]),
            goal("g2"),
        ],
        "advice": [advice("a1", goalId="g2"), advice("a2", "neglected")],
    }
    proj = make_project(tmp_path, "pub", answer=answer)
    read = og.parse_goals(query(proj, "owner-goals"), NOW)
    assert read.measured and read.malformed_goals == 0 and read.malformed_advice == 0
    assert [g["id"] for g in read.goals] == ["g1", "g2"]
    rich, minimal = read.goals
    assert rich["progress"] == {"text": "3 of 5 shipped", "done": 3, "total": 5}
    assert rich["projects"] == ["publisher-app"]
    assert rich["evidence"] == [{"label": "plan", "link": "/x/plan.md"}, {"label": "note"}]
    assert rich["openItems"] == 4 and rich["serves"] == "the parent"
    assert minimal == {"id": "g2", "title": "title g2", "status": "proposed",
                       "projects": [], "evidence": []}
    assert read.advice[0] == {"id": "a1", "kind": "add", "sentence": "sentence a1",
                              "why": "why a1", "goalId": "g2"}
    assert read.complete is True and read.synthesized_at == "2027-01-15T06:00:00+00:00"
    assert read.age_s is not None


def test_malformed_and_duplicate_entries_are_skipped_and_counted_separately():
    data = {"complete": True,
            "goals": [goal("g1"), goal("g2", status="maybe"), {"id": "g3", "status": "proposed"},
                      goal("g1"), "not a dict", goal("g4", progress={"done": 1})],
            "advice": [advice("a1"), advice("a2", kind="shout"), {"id": "a3", "kind": "add",
                                                                   "sentence": "s"}]}
    read = og.parse_goals(StatusResult(command="owner-goals", ok=True, data=data), NOW)
    assert [g["id"] for g in read.goals] == ["g1", "g4"]
    assert "progress" not in read.goals[1]          # a bad optional field drops the field only
    assert read.malformed_goals == 4
    assert [a["id"] for a in read.advice] == ["a1"]
    assert read.malformed_advice == 2


def test_partial_answer_carries_unread_sources_with_the_queue_normalisation():
    data = {"complete": False, "goals": [goal("g1")],
            "unreadSources": ["mailbox", {"name": "calendar", "reason": "token expired"}, 7]}
    read = og.parse_goals(StatusResult(command="owner-goals", ok=True, data=data), NOW)
    assert read.complete is False
    assert read.unread_sources == ["mailbox", "calendar — token expired"]


def test_advice_that_is_not_a_list_is_counted_not_shown_as_no_suggestions():
    data = {"complete": True, "goals": [goal("g1")], "advice": {"oops": 1}}
    read = og.parse_goals(StatusResult(command="owner-goals", ok=True, data=data), NOW)
    assert read.measured and read.advice == [] and read.malformed_advice == 1


def test_missing_advice_is_an_empty_list():
    read = og.parse_goals(StatusResult(command="owner-goals", ok=True,
                                       data={"complete": True, "goals": []}), NOW)
    assert read.measured and read.advice == [] and read.malformed_advice == 0


def test_a_failed_read_or_an_answer_without_goals_is_unmeasured_not_empty():
    failed = StatusResult.failure("owner-goals", "timeout", "the project did not answer within 30s")
    read = og.parse_goals(failed, NOW)
    assert read.measured is False and "did not answer" in read.reason and read.goals == []
    bad = og.parse_goals(StatusResult(command="owner-goals", ok=True, data={"advice": []}), NOW)
    assert bad.measured is False and "'goals'" in bad.reason


# --------------------------------------------------------------------------- #
# 7.2 the write shape
# --------------------------------------------------------------------------- #

def test_ac38_keep_reaches_the_write_command_as_one_json_argument(tmp_path):
    proj = make_project(tmp_path, "pub")
    result = og.interpret_write(write(proj, "owner-goals-act",
                                      og.write_args(og.act_payload("g1", "keep"))))
    assert result.delivered and result.outcome == "goal confirmed"
    sent = calls(proj)[-1]
    assert sent[0] == "owner-goals-act" and sent[1] == "--json"
    assert json.loads(sent[2]) == {"id": "g1", "action": "keep"}


def test_rename_carries_its_text_even_when_it_starts_with_a_dash(tmp_path):
    proj = make_project(tmp_path, "pub")
    payload = og.act_payload("g1", "rename", text="  -lower the cost  ")
    assert payload == {"id": "g1", "action": "rename", "text": "-lower the cost"}
    assert og.interpret_write(write(proj, "owner-goals-act", og.write_args(payload))).delivered
    assert json.loads(calls(proj)[-1][2])["text"] == "-lower the cost"


def test_a_refusal_carries_the_projects_reason(tmp_path):
    proj = make_project(tmp_path, "pub")
    result = og.interpret_write(write(proj, "owner-goals-act",
                                      og.write_args(og.act_payload("refuse-me", "drop"))))
    assert result.delivered is False and "merged into another" in result.reason


def test_ac39_without_the_write_command_the_write_is_refused_by_the_contract(tmp_path):
    proj = make_project(tmp_path, "pub", writes=())
    assert find([{"name": "pub", "path": str(proj)}]).accepts_actions is False
    result = og.interpret_write(write(proj, "owner-goals-act",
                                      og.write_args(og.act_payload("g1", "keep"))))
    assert result.delivered is False and result.error_class == "not-a-write-command"


@pytest.mark.parametrize("action,text", [("launch", None), ("rename", None), ("rename", "   ")])
def test_unknown_actions_and_an_empty_rename_are_refused_before_anything_runs(action, text):
    with pytest.raises(ValueError):
        og.act_payload("g1", action, text=text)
