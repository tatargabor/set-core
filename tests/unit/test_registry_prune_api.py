"""The overview's side of archiving: hidden entries stay counted.

`ui-quality.md` — compacting must never hide a failure. Dropping archived
projects from the list is exactly the kind of tidying that creates a place for a
broken thing to sit unseen, so the count of what was omitted travels with the
response.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from fastapi.testclient import TestClient  # noqa: E402

from set_orch.api import helpers as api_helpers  # noqa: E402
from set_orch.server import create_app  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    live = tmp_path / "live"
    archived = tmp_path / "archived"
    live.mkdir()
    archived.mkdir()

    registry = tmp_path / "projects.json"
    registry.write_text(json.dumps({"projects": {
        "live": {"path": str(live)},
        "archived-run": {"path": str(archived), "archived": True,
                         "archivedAt": "2026-07-24T10:00:00+00:00"},
    }}))
    monkeypatch.setattr(api_helpers, "PROJECTS_FILE", registry)
    return TestClient(create_app(web_dist_dir=None))


def test_archived_projects_are_omitted_but_counted(client):
    """AC-21. Omission without a count is the failure mode this guards against:
    a shorter list reads as "that is everything"."""
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert names == ["live"]
    assert resp.headers["X-Archived-Count"] == "1"


def test_archived_projects_on_request(client):
    """AC-22."""
    resp = client.get("/api/projects", params={"include_archived": "true"})
    assert resp.status_code == 200
    by_name = {p["name"]: p for p in resp.json()}
    assert set(by_name) == {"live", "archived-run"}
    assert by_name["archived-run"]["archived"] is True
    assert by_name["archived-run"]["archivedAt"] == "2026-07-24T10:00:00+00:00"
    assert "archived" not in by_name["live"]


def test_a_registry_with_no_archived_entries_reports_zero(tmp_path, monkeypatch):
    """The header is always present, so a reader never has to distinguish
    "no archived projects" from "this build does not report it"."""
    live = tmp_path / "live"
    live.mkdir()
    registry = tmp_path / "projects.json"
    registry.write_text(json.dumps({"projects": {"live": {"path": str(live)}}}))
    monkeypatch.setattr(api_helpers, "PROJECTS_FILE", registry)

    resp = TestClient(create_app(web_dist_dir=None)).get("/api/projects")
    assert resp.headers["X-Archived-Count"] == "0"
    assert [p["name"] for p in resp.json()] == ["live"]


def test_the_registry_round_trips_the_archive_fields(tmp_path, monkeypatch):
    """`_save_projects` preserves unknown fields today; if that ever narrows to a
    known-key allowlist, archiving silently stops persisting."""
    registry = tmp_path / "projects.json"
    registry.write_text(json.dumps({"projects": {
        "x": {"path": "/nowhere", "archived": True, "archivedAt": "2026-07-24T10:00:00+00:00"},
    }}))
    monkeypatch.setattr(api_helpers, "PROJECTS_FILE", registry)

    loaded = api_helpers._load_projects()
    assert loaded[0]["archived"] is True
    api_helpers._save_projects(loaded)
    again = api_helpers._load_projects()
    assert again[0]["archived"] is True
    assert again[0]["archivedAt"] == "2026-07-24T10:00:00+00:00"
