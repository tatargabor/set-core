"""Tests for engine._archive_completed_to_jsonl."""

from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.engine import _archive_completed_to_jsonl
from set_orch.state import init_state


@pytest.fixture
def state_with_completed():
    tmp = tempfile.mkdtemp()
    plan_path = os.path.join(tmp, "plan.json")
    state_path = os.path.join(tmp, "state.json")
    with open(plan_path, "w") as f:
        json.dump(
            {
                "plan_version": 1,
                "brief_hash": "h",
                "plan_phase": "initial",
                "plan_method": "api",
                "changes": [
                    {"name": "foundation", "scope": "s", "complexity": "M", "phase": 0},
                    {"name": "catalog", "scope": "s", "complexity": "M", "phase": 1, "depends_on": ["foundation"]},
                    {"name": "running-one", "scope": "s", "complexity": "S", "phase": 2},
                ],
            },
            f,
        )
    init_state(plan_path, state_path)

    state_obj = json.load(open(state_path))
    for c in state_obj["changes"]:
        if c["name"] == "foundation":
            c["status"] = "merged"
            c["tokens_used"] = 1000
        elif c["name"] == "catalog":
            c["status"] = "skipped"
        else:
            c["status"] = "running"
    with open(state_path, "w") as f:
        json.dump(state_obj, f)

    yield tmp, state_path

    import shutil
    shutil.rmtree(tmp, ignore_errors=True)


def _read_archive(root: str) -> list[dict]:
    path = os.path.join(root, "state-archive.jsonl")
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path).read().splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


class TestArchiveCompletedToJsonl:
    def test_writes_only_terminal_changes(self, state_with_completed):
        tmp, state_path = state_with_completed
        _archive_completed_to_jsonl(state_path)
        entries = _read_archive(tmp)
        names = sorted(e["name"] for e in entries)
        assert names == ["catalog", "foundation"]

    def test_writes_phase_field(self, state_with_completed):
        tmp, state_path = state_with_completed
        _archive_completed_to_jsonl(state_path)
        entries = _read_archive(tmp)
        by_name = {e["name"]: e for e in entries}
        assert by_name["foundation"]["phase"] == 0
        assert by_name["catalog"]["phase"] == 1

    def test_writes_plan_version(self, state_with_completed):
        tmp, state_path = state_with_completed
        _archive_completed_to_jsonl(state_path)
        entries = _read_archive(tmp)
        for e in entries:
            assert "plan_version" in e
            assert isinstance(e["plan_version"], int)

    def test_dedup_on_repeat_call(self, state_with_completed):
        tmp, state_path = state_with_completed
        _archive_completed_to_jsonl(state_path)
        _archive_completed_to_jsonl(state_path)
        entries = _read_archive(tmp)
        names = [e["name"] for e in entries]
        # No duplicates even if called twice.
        assert sorted(names) == ["catalog", "foundation"]

    def test_no_file_when_no_completed(self):
        tmp = tempfile.mkdtemp()
        try:
            plan_path = os.path.join(tmp, "plan.json")
            state_path = os.path.join(tmp, "state.json")
            with open(plan_path, "w") as f:
                json.dump(
                    {
                        "plan_version": 1,
                        "brief_hash": "h",
                        "plan_phase": "initial",
                        "plan_method": "api",
                        "changes": [
                            {"name": "only-running", "scope": "s", "complexity": "S"},
                        ],
                    },
                    f,
                )
            init_state(plan_path, state_path)
            _archive_completed_to_jsonl(state_path)
            assert not os.path.exists(os.path.join(tmp, "state-archive.jsonl"))
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
