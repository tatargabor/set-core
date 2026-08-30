"""The stage field on the fleet agent payload — additive, resolved, unwritten.

Two things here are not happy-path assertions. The additive one asserts the
field never disturbs what was there before it (a consumer reading the payload
without knowing `stage` must keep working, byte for byte on every other
field); the persistence one hashes the project tree before and after a
resolution and asserts NOTHING changed — the boundary is persistence, not
naming, and an in-memory memo holding a slug for seconds is documented on the
module, while anything reaching DISK is a defect.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from set_orch.api import fleet as fleet_api
from set_orch.fleet import stage as fleet_stage
from set_orch.fleet.purpose import Purpose


class _Agent:
    """The same stand-in `test_fleet_api.py` uses, pointed at a real root."""

    def __init__(self, pid, root=None, session=None, log=None):
        self.pid = pid
        self.name = self.project_name = "p"
        self.project_root = root
        self.cwd = root or "x"
        self.branch = None
        self.session_id = session
        self.session_log = log
        self.binding_confirmed = True
        self.sources = ["process"]
        self.sources_missing = []
        self.kind = "interactive"
        self.record = None


def _State():
    from set_orch.fleet.state import AgentState
    return AgentState(state="quiet", last_movement_age=1.0)


def _change(tmp_path, name, tasks):
    d = tmp_path / "openspec" / "changes" / name
    d.mkdir(parents=True)
    (d / "tasks.md").write_text(tasks, encoding="utf-8")


def _tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        h.update(str(p.relative_to(root)).encode())
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# additive
# --------------------------------------------------------------------------- #


def test_the_stage_field_is_present_and_named_on_every_agent(tmp_path):
    payload = fleet_api._agent_payload(_Agent(7), _State(), {})
    assert "stage" in payload
    assert set(payload["stage"]) == {"state", "flow", "position", "reason", "source", "outside"}


def test_an_agent_with_no_resolution_keeps_every_existing_field(tmp_path):
    # The field set every pre-stage consumer depended on. If the stage work
    # renamed or dropped one of these, the payload broke backwards.
    payload = fleet_api._agent_payload(_Agent(7), _State(), {7: {"label": "mine"}})
    for key in ("pid", "name", "project", "project_root", "cwd", "branch", "session_id",
                "state", "attention", "population", "terminal_label", "sources",
                "sources_missing", "kind", "declared", "purpose", "survives", "parent"):
        assert key in payload, key


def test_a_resolved_stage_reaches_the_payload_through_the_join(tmp_path):
    _change(tmp_path, "live-a", "- [ ] 1.1 one\n")
    purposes = []
    p = Purpose(change="live-a", pid=7, status="running")
    p.session_id = "s7"
    purposes.append(p)
    payload = fleet_api._agent_payload(
        _Agent(7, root=str(tmp_path), session="s7"), _State(), {}, purposes=purposes)
    assert payload["stage"]["state"] == "resolved"
    assert payload["stage"]["position"] == "apply"
    assert payload["stage"]["source"] == "derived"
    assert payload["stage"]["flow"] == list(fleet_stage.DEFAULT_FLOW)


def test_a_declared_flow_replaces_the_derived_one_on_the_payload(tmp_path):
    declared = (["triage", "fixing"], {"triage-1": "fixing"})
    p = Purpose(change="triage-1", pid=7, status="running")
    p.session_id = "s7"
    payload = fleet_api._agent_payload(
        _Agent(7, root=str(tmp_path), session="s7"), _State(), {}, purposes=[p],
        declared=declared)
    assert payload["stage"]["flow"] == ["triage", "fixing"]
    assert payload["stage"]["position"] == "fixing"
    assert payload["stage"]["source"] == "declared"


# --------------------------------------------------------------------------- #
# nothing derived is written down
# --------------------------------------------------------------------------- #


def test_a_resolution_writes_nothing_to_the_project_tree(tmp_path):
    """sha256 of every path under the project, before and after a full resolve.

    The stage is derived from this tree; a resolution that flipped a byte — a
    cache, a marker, a 'seen' file — would be the framework writing into a
    consumer's checkout, which is the one direction with no forgiveness.
    """
    _change(tmp_path, "live-a", "- [ ] 1.1 one\n")
    log = tmp_path / "session.jsonl"
    log.write_text('{"content": "/opsx:apply live-a"}\n', encoding="utf-8")
    before = _tree_hash(tmp_path)
    purposes = []
    p = Purpose(change="live-a", pid=7, status="running")
    p.session_id = "s7"
    purposes.append(p)
    fleet_stage.resolve_stage(str(tmp_path), purposes, 7, "s7", str(log))
    fleet_stage.resolve_stage(str(tmp_path), None, 8, None, str(log))
    assert _tree_hash(tmp_path) == before


def test_the_payload_path_writes_nothing_and_logs_no_values(tmp_path, caplog):
    _change(tmp_path, "live-a", "- [ ] 1.1 one\n")
    before = _tree_hash(tmp_path)
    purposes = []
    p = Purpose(change="live-a", pid=7, status="running")
    p.session_id = "s7"
    purposes.append(p)
    with caplog.at_level("DEBUG"):
        fleet_api._agent_payload(
            _Agent(7, root=str(tmp_path), session="s7"), _State(), {}, purposes=purposes)
    assert _tree_hash(tmp_path) == before
    # A change name is the consumer's own planning vocabulary: it reaches the
    # payload because the payload exists to carry it, never a log line.
    assert "live-a" not in caplog.text


def test_the_inference_memo_holds_the_slug_not_the_record(tmp_path):
    """The one in-memory cache, inspected: a slug and a timestamp, nothing else.

    Same precedent as the status contract's answer cache. If this ever starts
    holding transcript content, it becomes the confidentiality carrier the
    repo's rules describe — so the shape is asserted, not assumed.
    """
    fleet_stage._INFERENCE_MEMO.clear()
    log = tmp_path / "s.jsonl"
    log.write_text(json.dumps({"content": "private words /opsx:apply memo-x"}), encoding="utf-8")
    fleet_stage.infer_change_from_session(str(log))
    assert len(fleet_stage._INFERENCE_MEMO) == 1
    (stamp, value), = fleet_stage._INFERENCE_MEMO.values()
    # a candidate list (most recent first) plus per-slug tail-mention COUNTS —
    # weights, not words: a count per slug is exactly the "count, not content"
    # the module's confidentiality line allows, and the archive-anchor rule in
    # resolve_stage reads it (2026-08-30). No transcript text may appear here.
    assert value == (["memo-x"], {"memo-x": 1})
    assert isinstance(stamp, float)
