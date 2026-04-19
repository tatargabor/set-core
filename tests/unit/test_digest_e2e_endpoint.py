"""Tests for Section 12.3 / 12.6 — digest/e2e endpoint aggregates manifest history.

Covers:
  - AC-30: live + history blocks combined, with archived = true on history.
  - AC-31: history file missing → endpoint falls back to live manifests only.
  - AC-41: ?lineage filter scopes blocks to a single lineage.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    import set_orch.paths as paths_mod
    monkeypatch.setattr(paths_mod, "SET_TOOLS_DATA_DIR",
                        str(tmp_path / "xdg" / "set-core"))
    yield


def _seed(tmp_path, *, history=None, changes=None, live_lineage="docs/spec.md"):
    proj = tmp_path / "proj"
    proj.mkdir()

    state_path = proj / "orchestration-state.json"
    state = {
        "plan_version": 1, "brief_hash": "h", "plan_phase": "initial",
        "plan_method": "api", "status": "running", "created_at": "2026-01-01",
        "spec_lineage_id": live_lineage, "sentinel_session_id": "sess-1",
        "changes": changes or [],
    }
    state_path.write_text(json.dumps(state))

    if history:
        history_path = proj / "set" / "orchestration" / "e2e-manifest-history.jsonl"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(history_path, "w") as fh:
            for rec in history:
                fh.write(json.dumps(rec) + "\n")
    return proj


def _patch_resolvers(monkeypatch, proj):
    monkeypatch.setattr(
        "set_orch.api.orchestration._resolve_project", lambda _p: proj,
    )
    monkeypatch.setattr(
        "set_orch.api.orchestration._state_path",
        lambda _p: proj / "orchestration-state.json",
    )


# ---------------------------------------------------------------------------
# AC-30 — combined blocks
# ---------------------------------------------------------------------------


def test_e2e_endpoint_combines_history_and_live_blocks(tmp_path, monkeypatch):
    from set_orch.api.orchestration import get_digest_e2e

    # Live worktree with a fresh (un-archived) manifest.
    wt_live = tmp_path / "wt-live"
    wt_live.mkdir()
    (wt_live / "e2e-manifest.json").write_text(json.dumps({
        "tests": [{"name": "live-test-1", "passed": True}],
    }))

    proj = _seed(
        tmp_path,
        changes=[
            {"name": "live-change", "phase": 1, "status": "running",
             "scope": "s", "complexity": "M",
             "spec_lineage_id": "docs/spec.md",
             "worktree_path": str(wt_live)},
        ],
        history=[
            {"change": "old-change-1", "spec_lineage_id": "docs/spec.md",
             "merged_at": "2026-01-01", "manifest":
                {"tests": [{"name": "old-1", "passed": True}]}},
            {"change": "old-change-2", "spec_lineage_id": "docs/spec.md",
             "merged_at": "2026-01-02", "manifest":
                {"tests": [{"name": "old-2-a", "passed": True},
                           {"name": "old-2-b", "passed": False}]}},
        ],
    )
    _patch_resolvers(monkeypatch, proj)

    result = get_digest_e2e("proj")
    blocks = result["blocks"]
    archived = [b for b in blocks if b["archived"]]
    live = [b for b in blocks if not b["archived"]]
    assert len(archived) == 2
    assert len(live) == 1
    # Total tests counted across all blocks.
    assert result["total_tests"] == 4  # 1 live + 1 + 2
    assert result["total_passed"] == 3  # 3 of 4 pass


def test_e2e_endpoint_skips_already_archived_change_in_live_pass(tmp_path, monkeypatch):
    """If a change appears in BOTH live state and history (which can happen
    during the brief window between archive write and worktree cleanup),
    the live duplicate must be suppressed so the block isn't counted twice."""
    from set_orch.api.orchestration import get_digest_e2e

    wt = tmp_path / "wt-dup"
    wt.mkdir()
    (wt / "e2e-manifest.json").write_text(json.dumps({"tests": [{"passed": True}]}))

    proj = _seed(
        tmp_path,
        changes=[{"name": "dup", "phase": 1, "status": "merged",
                  "scope": "s", "complexity": "M",
                  "spec_lineage_id": "docs/spec.md",
                  "worktree_path": str(wt)}],
        history=[{"change": "dup", "spec_lineage_id": "docs/spec.md",
                  "merged_at": "2026-01-01",
                  "manifest": {"tests": [{"passed": True}]}}],
    )
    _patch_resolvers(monkeypatch, proj)

    result = get_digest_e2e("proj")
    assert len([b for b in result["blocks"] if b["change"] == "dup"]) == 1


# ---------------------------------------------------------------------------
# AC-31 — fallback to live-only when history file missing
# ---------------------------------------------------------------------------


def test_e2e_endpoint_falls_back_to_live_when_history_absent(tmp_path, monkeypatch):
    from set_orch.api.orchestration import get_digest_e2e

    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / "e2e-manifest.json").write_text(json.dumps({
        "tests": [{"name": "only-live", "passed": True}],
    }))
    proj = _seed(
        tmp_path,
        changes=[{"name": "only-live", "phase": 1, "status": "running",
                  "scope": "s", "complexity": "M",
                  "spec_lineage_id": "docs/spec.md",
                  "worktree_path": str(wt)}],
    )
    _patch_resolvers(monkeypatch, proj)

    result = get_digest_e2e("proj")
    assert len(result["blocks"]) == 1
    assert result["blocks"][0]["archived"] is False


def test_e2e_endpoint_returns_empty_when_no_data(tmp_path, monkeypatch):
    from set_orch.api.orchestration import get_digest_e2e
    proj = _seed(tmp_path)
    _patch_resolvers(monkeypatch, proj)
    result = get_digest_e2e("proj")
    assert result["blocks"] == []
    assert result["total_tests"] == 0


# ---------------------------------------------------------------------------
# AC-41 — lineage filter
# ---------------------------------------------------------------------------


def test_e2e_endpoint_filters_by_lineage(tmp_path, monkeypatch):
    from set_orch.api.orchestration import get_digest_e2e
    proj = _seed(
        tmp_path,
        live_lineage="docs/spec-v2.md",
        history=[
            {"change": "v1-block", "spec_lineage_id": "docs/spec-v1.md",
             "merged_at": "2026-01-01",
             "manifest": {"tests": [{"name": "v1-test"}]}},
            {"change": "v2-block", "spec_lineage_id": "docs/spec-v2.md",
             "merged_at": "2026-02-01",
             "manifest": {"tests": [{"name": "v2-test"}]}},
        ],
    )
    _patch_resolvers(monkeypatch, proj)

    v1_result = get_digest_e2e("proj", lineage="docs/spec-v1.md")
    assert [b["change"] for b in v1_result["blocks"]] == ["v1-block"]
    assert v1_result["effective_lineage"] == "docs/spec-v1.md"

    v2_result = get_digest_e2e("proj", lineage="docs/spec-v2.md")
    assert [b["change"] for b in v2_result["blocks"]] == ["v2-block"]


def test_e2e_endpoint_all_lineages_returns_union(tmp_path, monkeypatch):
    from set_orch.api.orchestration import get_digest_e2e
    proj = _seed(
        tmp_path,
        history=[
            {"change": "a", "spec_lineage_id": "docs/spec-v1.md",
             "merged_at": "2026-01", "manifest": {"tests": []}},
            {"change": "b", "spec_lineage_id": "docs/spec-v2.md",
             "merged_at": "2026-02", "manifest": {"tests": []}},
        ],
    )
    _patch_resolvers(monkeypatch, proj)
    result = get_digest_e2e("proj", lineage="__all__")
    names = sorted(b["change"] for b in result["blocks"])
    assert names == ["a", "b"]
