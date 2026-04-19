"""Tests for set_orch web API write endpoints (approve, stop, skip)."""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from tests.lib import test_paths as tp

from fastapi.testclient import TestClient
from set_orch.server import create_app
from set_orch import api as api_module


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temp project with checkpoint state."""
    orch_dir = tmp_path / "set" / "orchestration"
    orch_dir.mkdir(parents=True)
    return tmp_path, orch_dir


def _write_state(orch_dir, state_dict):
    (tp.state_file(orch_dir)).write_text(json.dumps(state_dict))


def _read_state(orch_dir):
    return json.loads((tp.state_file(orch_dir)).read_text())


@pytest.fixture
def client(monkeypatch, tmp_path, tmp_project):
    project_path, orch_dir = tmp_project
    pf = tmp_path / "projects.json"
    pf.write_text(json.dumps([{"name": "test-proj", "path": str(project_path)}]))
    monkeypatch.setattr(api_module, "PROJECTS_FILE", pf)
    app = create_app(web_dist_dir=None)
    return TestClient(app), orch_dir


def test_approve_checkpoint(client):
    tc, orch_dir = client
    _write_state(orch_dir, {
        "plan_version": 1,
        "status": "checkpoint",
        "changes": [],
        "checkpoints": [{"phase": "test", "approved": False}],
    })
    resp = tc.post("/api/test-proj/approve")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    state = _read_state(orch_dir)
    assert state["checkpoints"][-1]["approved"] is True


def test_approve_not_checkpoint(client):
    tc, orch_dir = client
    _write_state(orch_dir, {
        "plan_version": 1,
        "status": "running",
        "changes": [],
    })
    resp = tc.post("/api/test-proj/approve")
    assert resp.status_code == 409


def test_skip_pending_change(client):
    tc, orch_dir = client
    _write_state(orch_dir, {
        "plan_version": 1,
        "status": "running",
        "changes": [{"name": "change-a", "status": "pending"}],
    })
    resp = tc.post("/api/test-proj/changes/change-a/skip")
    assert resp.status_code == 200

    state = _read_state(orch_dir)
    assert state["changes"][0]["status"] == "skipped"


def test_skip_running_change_rejected(client):
    tc, orch_dir = client
    _write_state(orch_dir, {
        "plan_version": 1,
        "status": "running",
        "changes": [{"name": "change-a", "status": "running"}],
    })
    resp = tc.post("/api/test-proj/changes/change-a/skip")
    assert resp.status_code == 409


def test_skip_nonexistent_change(client):
    tc, orch_dir = client
    _write_state(orch_dir, {
        "plan_version": 1,
        "status": "running",
        "changes": [],
    })
    resp = tc.post("/api/test-proj/changes/nope/skip")
    assert resp.status_code == 404


def test_stop_not_running(client):
    tc, orch_dir = client
    _write_state(orch_dir, {
        "plan_version": 1,
        "status": "completed",
        "changes": [],
    })
    resp = tc.post("/api/test-proj/stop")
    assert resp.status_code == 409
