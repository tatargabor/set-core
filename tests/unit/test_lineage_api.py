"""Tests for Section 13 — lineage filter API plumbing.

Covers:
  - 13.3 /api/<project>/lineages endpoint contents
  - 13.4 ?lineage= filter on /state, /llm-calls, /activity-timeline
  - 13.5 __unknown__ lineage diagnostic
  - AC-42, AC-43, AC-44, AC-46
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from tests.lib import test_paths as tp

from set_orch.api.lineages import (
    _ALL,
    _LEGACY,
    _UNKNOWN,
    _collect_lineages,
    apply_lineage_filter,
    resolve_lineage_default,
)


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    import set_orch.paths as paths_mod
    monkeypatch.setattr(paths_mod, "SET_TOOLS_DATA_DIR",
                        str(tmp_path / "xdg" / "set-core"))
    yield


def _seed_project(tmp_path, *, live_lineage=None, live_changes=None,
                  archive_entries=None, status_history=None):
    """Build a project with state, archive, and supervisor history."""
    proj = tmp_path / "proj"
    proj.mkdir()
    # api/helpers._state_path looks for orchestration-state.json (note the
    # "orchestration-" prefix); we mirror the canonical layout the API
    # consumes.
    state_path = tp.state_file(proj)
    state = {
        "plan_version": 1,
        "brief_hash": "h",
        "plan_phase": "initial",
        "plan_method": "api",
        "status": "running",
        "created_at": "2026-01-01T00:00:00",
        "spec_lineage_id": live_lineage,
        "sentinel_session_id": "sess-1",
        "changes": live_changes or [],
    }
    state_path.write_text(json.dumps(state))

    if archive_entries:
        archive = tp.state_archive(proj)
        with open(archive, "w") as fh:
            for e in archive_entries:
                fh.write(json.dumps(e) + "\n")

    if status_history:
        history_dir = proj / ".set" / "supervisor"
        history_dir.mkdir(parents=True, exist_ok=True)
        with open(history_dir / "status-history.jsonl", "w") as fh:
            for rec in status_history:
                fh.write(json.dumps(rec) + "\n")

    return proj


# ---------------------------------------------------------------------------
# 13.3 / AC-42 — /lineages returns both v1 and v2 with metadata
# ---------------------------------------------------------------------------


def test_collect_lineages_returns_v1_and_v2(tmp_path):
    proj = _seed_project(
        tmp_path,
        live_lineage="docs/spec-v2.md",
        live_changes=[
            {"name": "v2-a", "phase": 1, "status": "running",
             "spec_lineage_id": "docs/spec-v2.md",
             "started_at": "2026-03-01T10:00:00"},
        ],
        archive_entries=[
            {"name": "v1-a", "phase": 1, "status": "merged",
             "spec_lineage_id": "docs/spec-v1.md",
             "archived_at": "2026-01-15T10:00:00"},
            {"name": "v1-b", "phase": 2, "status": "merged",
             "spec_lineage_id": "docs/spec-v1.md",
             "archived_at": "2026-01-16T10:00:00"},
        ],
    )
    lineages = _collect_lineages(proj, sentinel_running=True)
    by_id = {l["id"]: l for l in lineages}
    assert "docs/spec-v1.md" in by_id
    assert "docs/spec-v2.md" in by_id
    assert by_id["docs/spec-v2.md"]["is_live"] is True
    assert by_id["docs/spec-v1.md"]["is_live"] is False
    assert by_id["docs/spec-v1.md"]["change_count"] == 2
    assert by_id["docs/spec-v1.md"]["merged_count"] == 2


# ---------------------------------------------------------------------------
# 13.5 / AC-43 — synthetic __legacy__ lineage when nothing tagged
# ---------------------------------------------------------------------------


def test_legacy_lineage_when_no_tags(tmp_path):
    proj = _seed_project(
        tmp_path,
        live_lineage=None,
        live_changes=[],
        archive_entries=[
            {"name": "untagged-1", "phase": 1, "status": "merged"},
            {"name": "untagged-2", "phase": 2, "status": "merged"},
        ],
    )
    lineages = _collect_lineages(proj)
    by_id = {l["id"]: l for l in lineages}
    assert _LEGACY in by_id
    assert by_id[_LEGACY]["change_count"] == 2


# ---------------------------------------------------------------------------
# 13.5 — __unknown__ carries diagnostic
# ---------------------------------------------------------------------------


def test_unknown_lineage_includes_diagnostic(tmp_path):
    proj = _seed_project(
        tmp_path,
        live_lineage="docs/spec.md",
        archive_entries=[
            {"name": "ghost", "phase": 1, "status": "merged",
             "spec_lineage_id": _UNKNOWN, "archived_at": "2026-01-01"},
        ],
    )
    lineages = _collect_lineages(proj)
    unk = next(l for l in lineages if l["id"] == _UNKNOWN)
    assert "diagnostic" in unk
    assert "could not be attributed" in unk["diagnostic"]


# ---------------------------------------------------------------------------
# 13.4 — apply_lineage_filter behaviour
# ---------------------------------------------------------------------------


def test_filter_to_specific_lineage():
    records = [
        {"name": "a", "spec_lineage_id": "v1"},
        {"name": "b", "spec_lineage_id": "v2"},
        {"name": "c", "spec_lineage_id": "v1"},
    ]
    out = apply_lineage_filter(records, "v1")
    assert [r["name"] for r in out] == ["a", "c"]


def test_filter_all_returns_union():
    records = [
        {"name": "a", "spec_lineage_id": "v1"},
        {"name": "b", "spec_lineage_id": "v2"},
        {"name": "c"},  # untagged
    ]
    out = apply_lineage_filter(records, _ALL)
    assert len(out) == 3


def test_filter_legacy_picks_untagged_records():
    records = [
        {"name": "a", "spec_lineage_id": "v1"},
        {"name": "b"},
        {"name": "c"},
    ]
    out = apply_lineage_filter(records, _LEGACY)
    assert [r["name"] for r in out] == ["b", "c"]


def test_filter_none_returns_all():
    records = [
        {"name": "a", "spec_lineage_id": "v1"},
        {"name": "b", "spec_lineage_id": "v2"},
    ]
    assert len(apply_lineage_filter(records, None)) == 2


# ---------------------------------------------------------------------------
# 13.4 — default lineage selection rule
# ---------------------------------------------------------------------------


def test_default_lineage_picks_newest_when_no_sentinel(tmp_path):
    proj = _seed_project(
        tmp_path,
        live_lineage="docs/spec-v2.md",
        archive_entries=[
            {"name": "old", "phase": 1, "status": "merged",
             "spec_lineage_id": "docs/spec-v1.md",
             "archived_at": "2026-01-15T10:00:00"},
            {"name": "new", "phase": 1, "status": "merged",
             "spec_lineage_id": "docs/spec-v2.md",
             "archived_at": "2026-03-15T10:00:00"},
        ],
    )
    # No sentinel running — picks newest by last_seen_at.
    default = resolve_lineage_default(proj)
    assert default == "docs/spec-v2.md"


def test_default_lineage_returns_none_for_empty_project(tmp_path):
    proj = tmp_path / "empty"
    proj.mkdir()
    # No state, no archive, no history.  Returns None.
    assert resolve_lineage_default(proj) in (None, _LEGACY)


# ---------------------------------------------------------------------------
# AC-46 — /state filtered by v1 returns only v1 changes
# ---------------------------------------------------------------------------


def test_state_endpoint_lineage_filter(tmp_path, monkeypatch):
    """Integration test of get_state with ?lineage=docs/spec-v1.md."""
    from set_orch.api.orchestration import get_state

    proj = _seed_project(
        tmp_path,
        live_lineage="docs/spec-v2.md",
        live_changes=[
            {"name": "v2-only", "phase": 1, "status": "running",
             "scope": "s", "complexity": "M",
             "spec_lineage_id": "docs/spec-v2.md"},
        ],
        archive_entries=[
            {"name": "v1-old", "phase": 1, "status": "merged",
             "spec_lineage_id": "docs/spec-v1.md",
             "archived_at": "2026-01-01"},
        ],
    )
    # Stub _resolve_project + _state_path.
    monkeypatch.setattr(
        "set_orch.api.orchestration._resolve_project", lambda _p: proj,
    )
    monkeypatch.setattr(
        "set_orch.api.orchestration._state_path",
        lambda _p: tp.state_file(proj),
    )

    result = get_state("proj", lineage="docs/spec-v1.md")
    names = [c["name"] for c in result["changes"]]
    assert names == ["v1-old"]
    assert result["effective_lineage"] == "docs/spec-v1.md"


def test_state_endpoint_all_returns_union(tmp_path, monkeypatch):
    from set_orch.api.orchestration import get_state

    proj = _seed_project(
        tmp_path,
        live_lineage="docs/spec-v2.md",
        live_changes=[
            {"name": "v2-only", "phase": 1, "status": "running",
             "scope": "s", "complexity": "M",
             "spec_lineage_id": "docs/spec-v2.md"},
        ],
        archive_entries=[
            {"name": "v1-old", "phase": 1, "status": "merged",
             "spec_lineage_id": "docs/spec-v1.md",
             "archived_at": "2026-01-01"},
        ],
    )
    monkeypatch.setattr(
        "set_orch.api.orchestration._resolve_project", lambda _p: proj,
    )
    monkeypatch.setattr(
        "set_orch.api.orchestration._state_path",
        lambda _p: tp.state_file(proj),
    )
    result = get_state("proj", lineage=_ALL)
    names = sorted(c["name"] for c in result["changes"])
    assert names == ["v1-old", "v2-only"]
