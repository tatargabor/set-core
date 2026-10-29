"""The owner-queue adapter (fleet-now-card 2.1–2.4), against a fake declared endpoint.

The fake is a real subprocess speaking the status contract, so the adapter is
exercised through the contract's own reader and writer — not through a mock of
them, which would measure a different system.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.fleet import owner_queue as oq  # noqa: E402
from set_orch.project_status import StatusResult, query, write  # noqa: E402

NOW = 1_800_000_000.0

FAKE = """\
import json, sys, pathlib
here = pathlib.Path(__file__).parent
argv = sys.argv[1:]
(here / "calls.log").open("a").write(json.dumps(argv) + "\\n")
cmd = argv[0]
if cmd == "owner-queue":
    print(json.dumps({"contractVersion": 1, "command": cmd, "ok": True,
                      "data": json.loads((here / "queue.json").read_text())}))
elif cmd == "owner-queue-act":
    payload = json.loads(argv[argv.index("--json") + 1])
    if payload["id"] == "refuse-me":
        sys.stderr.write("that item was already closed by somebody else\\n")
        sys.exit(1)
    print(json.dumps({"contractVersion": 1, "command": cmd, "ok": True,
                      "data": {"outcome": "agent resumed"}}))
"""


def make_project(root: Path, name: str, *, queue=None, write_cmd=True, declare=True) -> Path:
    proj = root / name
    proj.mkdir()
    (proj / "contract.py").write_text(FAKE)
    (proj / "queue.json").write_text(json.dumps(queue or {"items": [], "complete": True}))
    manifest = {"contractVersion": 1, "command": [sys.executable, "contract.py"],
                "commands": ["owner-queue"] if declare else ["other"]}
    if write_cmd:
        manifest["writeCommands"] = ["owner-queue-act"]
    (proj / ".set-endpoint.json").write_text(json.dumps(manifest))
    return proj


def calls(proj: Path):
    log = proj / "calls.log"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


# --------------------------------------------------------------------------- #
# 2.1 publisher choice
# --------------------------------------------------------------------------- #

def test_ac21_the_one_declaring_project_is_the_publisher(tmp_path):
    a = make_project(tmp_path, "a")
    b = make_project(tmp_path, "b", declare=False)
    pub = oq.find_publisher([{"name": "a", "path": str(a)}, {"name": "b", "path": str(b)}], None)
    assert pub.state == "ok" and pub.name == "a" and pub.accepts_actions


def test_ac22_two_declaring_projects_and_no_config_is_ambiguous(tmp_path):
    a = make_project(tmp_path, "a")
    b = make_project(tmp_path, "b")
    reg = [{"name": "a", "path": str(a)}, {"name": "b", "path": str(b)}]
    pub = oq.find_publisher(reg, None)
    assert pub.state == "ambiguous" and pub.name is None
    assert pub.candidates == ["a", "b"] and "now.publisher" in pub.reason
    chosen = oq.find_publisher(reg, "b")
    assert chosen.state == "ok" and chosen.name == "b"


def test_not_declared_is_distinct_from_a_configured_name_that_does_not_declare(tmp_path):
    b = make_project(tmp_path, "b", declare=False)
    reg = [{"name": "b", "path": str(b)}]
    assert oq.find_publisher(reg, None).state == "none"
    missing = oq.find_publisher(reg, "b")
    assert missing.state == "configured-missing" and "does not declare" in missing.reason
    assert oq.find_publisher(reg, "zz").reason.endswith("is not a registered project")


# --------------------------------------------------------------------------- #
# 2.2 the item shape
# --------------------------------------------------------------------------- #

def test_required_fields_are_enforced_and_optional_ones_pass_through(tmp_path):
    queue = {"complete": False, "rankedAt": "2027-01-15T06:00:00+00:00", "items": [
        {"id": "1", "project": "p", "sentence": "Do it", "why": "because"},
        {"id": "2", "project": "p", "sentence": "Pick", "why": "w",
         "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}, {"id": "c", "label": "C"}],
         "delegable": True, "acceptsText": True, "estimateMinutes": 5, "link": "https://x",
         "references": [{"source": "agent-questions", "id": "agent:s"}]},
        {"id": "3", "project": "p", "sentence": "no why"},
        {"id": "1", "project": "p", "sentence": "duplicate id", "why": "w"},
    ]}
    proj = make_project(tmp_path, "a", queue=queue)
    read = oq.parse_queue(query(proj, "owner-queue"), NOW)
    assert read.measured
    assert [i["id"] for i in read.items] == ["1", "2"]
    assert read.malformed == 2
    minimal, rich = read.items
    assert minimal["options"] == [] and not minimal["delegable"] and not minimal["acceptsText"]
    assert len(rich["options"]) == 3                     # AC-24
    assert rich["references"] == [{"source": "agent-questions", "id": "agent:s"}]
    assert read.complete is False
    assert read.ranked_at == "2027-01-15T06:00:00+00:00"
    assert read.ranking_age_s is not None


def test_a_failed_read_is_unmeasured_with_its_reason():
    failed = StatusResult.failure("owner-queue", "timeout", "the project did not answer within 30s")
    read = oq.parse_queue(failed, NOW)
    assert read.measured is False and "did not answer" in read.reason and read.items == []


def test_an_answer_without_items_is_unmeasured_not_empty():
    bad = StatusResult(command="owner-queue", ok=True, data={"nope": 1})
    assert oq.parse_queue(bad, NOW).measured is False


# --------------------------------------------------------------------------- #
# 2.3 the write path
# --------------------------------------------------------------------------- #

def test_ac6_ac26_an_answer_reaches_the_write_command_and_carries_the_outcome(tmp_path):
    proj = make_project(tmp_path, "a")
    payload = oq.act_payload("item-7", "answer", option="b")
    result = oq.interpret_write(write(proj, "owner-queue-act", oq.write_args(payload)))
    assert result.delivered and result.outcome == "agent resumed"
    sent = calls(proj)[-1]
    assert sent[0] == "owner-queue-act" and sent[1] == "--json"
    assert json.loads(sent[2]) == {"id": "item-7", "action": "answer", "option": "b"}


def test_free_text_starting_with_a_dash_still_reaches_the_publisher(tmp_path):
    proj = make_project(tmp_path, "a")
    payload = oq.act_payload("i", "done", reasons=["-not mine to hand off"])
    assert oq.interpret_write(write(proj, "owner-queue-act", oq.write_args(payload))).delivered


def test_ac7_a_refusal_carries_the_projects_reason(tmp_path):
    proj = make_project(tmp_path, "a")
    payload = oq.act_payload("refuse-me", "done")
    result = oq.interpret_write(write(proj, "owner-queue-act", oq.write_args(payload)))
    assert result.delivered is False
    assert "already closed" in result.reason


def test_ac27_without_a_write_command_actions_are_not_accepted(tmp_path):
    proj = make_project(tmp_path, "a", write_cmd=False)
    pub = oq.find_publisher([{"name": "a", "path": str(proj)}], None)
    assert pub.state == "ok" and pub.accepts_actions is False
    result = oq.interpret_write(write(proj, "owner-queue-act", oq.write_args(oq.act_payload("i", "done"))))
    assert result.delivered is False and result.error_class == "not-a-write-command"


def test_exit_zero_without_an_envelope_counts_as_delivered_with_no_outcome():
    unparsed = StatusResult.failure("owner-queue-act", "missing-version", "no version")
    result = oq.interpret_write(unparsed)
    assert result.delivered is True and result.outcome is None


def test_an_unknown_action_is_refused_before_anything_runs():
    with pytest.raises(ValueError):
        oq.act_payload("i", "launch-missiles")
