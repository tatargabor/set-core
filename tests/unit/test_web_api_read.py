"""Tests for set_orch web API read endpoints."""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from fastapi.testclient import TestClient
from set_orch.server import create_app
from set_orch import api as api_module


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temp project directory with orchestration state."""
    orch_dir = tmp_path / "wt" / "orchestration"
    orch_dir.mkdir(parents=True)

    state = {
        "plan_version": 2,
        "status": "running",
        "changes": [
            {"name": "change-a", "status": "completed"},
            {"name": "change-b", "status": "running"},
        ],
    }
    (orch_dir / "orchestration-state.json").write_text(json.dumps(state))
    (orch_dir / "orchestration.log").write_text("line1\nline2\nline3\n")
    return tmp_path


@pytest.fixture
def projects_file(tmp_path, tmp_project):
    """Create a projects.json pointing to the temp project."""
    pf = tmp_path / "projects.json"
    pf.write_text(json.dumps([{"name": "test-proj", "path": str(tmp_project)}]))
    return pf


@pytest.fixture
def client(monkeypatch, projects_file):
    """TestClient with mocked projects path."""
    monkeypatch.setattr(api_module, "PROJECTS_FILE", projects_file)
    app = create_app(web_dist_dir=None)
    return TestClient(app)


def test_list_projects(client):
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "test-proj"
    assert data[0]["status"] == "running"


def test_get_state(client):
    resp = client.get("/api/test-proj/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert len(data["changes"]) == 2


def test_get_state_404(client):
    resp = client.get("/api/nonexistent/state")
    assert resp.status_code == 404


def test_list_changes(client):
    resp = client.get("/api/test-proj/changes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "change-a"


def test_list_changes_filter(client):
    resp = client.get("/api/test-proj/changes?status=running")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "change-b"


def test_get_single_change(client):
    resp = client.get("/api/test-proj/changes/change-a")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "change-a"
    assert data["status"] == "completed"


def test_get_single_change_404(client):
    resp = client.get("/api/test-proj/changes/nonexistent")
    assert resp.status_code == 404


def test_get_log(client):
    resp = client.get("/api/test-proj/log")
    assert resp.status_code == 200
    data = resp.json()
    assert "lines" in data
    assert len(data["lines"]) == 3


def test_get_log_no_state(client):
    resp = client.get("/api/nonexistent/log")
    assert resp.status_code == 404
