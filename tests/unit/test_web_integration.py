"""Integration test — start server, verify basic endpoints and SPA serving."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from fastapi.testclient import TestClient
from set_orch.server import create_app
from set_orch import api as api_module


@pytest.fixture
def client(monkeypatch, tmp_path):
    pf = tmp_path / "projects.json"
    pf.write_text(json.dumps([]))
    monkeypatch.setattr(api_module, "PROJECTS_FILE", pf)

    # Create a fake dist dir with index.html
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>set-web</body></html>")

    app = create_app(web_dist_dir=str(dist))
    return TestClient(app)


def test_projects_endpoint(client):
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    assert resp.json() == []


def test_spa_serves_index_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "set-web" in resp.text


def test_unknown_project_404(client):
    resp = client.get("/api/unknown/state")
    assert resp.status_code == 404
