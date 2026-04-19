"""Tests for Sections 11.3, 11.6, 4b.4, 4b.7, 4b.8 — digest endpoint
lineage routing + archived REQ attribution.

Covers:
  - 11.3 / 11.6 / AC-26: Digest reports archived attribution for REQs
    only present in spec-coverage-history.jsonl.
  - AC-27: REQ neither in live plan nor history → marked uncovered
    (no attribution applied).
  - 4b.4 / AC-27c: lineage with no saved digest → API returns explicit
    unavailable response.
  - 4b.7 / AC-27b: ?lineage=v1 after v2 takeover routes to digest-<v1-slug>/.
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


def _seed(tmp_path, *, with_live_digest=True, with_v1_digest=False,
          history_records=None, requirements=None,
          live_lineage="docs/spec-v2.md"):
    proj = tmp_path / "proj"
    proj.mkdir()

    # Live state for sentinel/lineage-resolution wiring.
    state_path = proj / "orchestration-state.json"
    state_path.write_text(json.dumps({
        "plan_version": 1, "brief_hash": "h", "plan_phase": "initial",
        "plan_method": "api", "status": "running", "created_at": "2026-01-01",
        "spec_lineage_id": live_lineage, "sentinel_session_id": "sess-1",
        "changes": [],
    }))

    # Live digest dir + requirements payload.
    if with_live_digest:
        digest_live = proj / "set" / "orchestration" / "digest"
        digest_live.mkdir(parents=True, exist_ok=True)
        with open(digest_live / "requirements.json", "w") as fh:
            json.dump({"requirements": requirements or []}, fh)

    # Per-lineage v1 digest dir.
    if with_v1_digest:
        from set_orch.types import slug
        digest_v1 = proj / "set" / "orchestration" / f"digest-{slug('docs/spec-v1.md')}"
        digest_v1.mkdir(parents=True, exist_ok=True)
        with open(digest_v1 / "requirements.json", "w") as fh:
            json.dump({"requirements": [
                {"id": "REQ-V1-1", "title": "v1 only requirement"},
            ]}, fh)

    if history_records:
        history = proj / "set" / "orchestration" / "spec-coverage-history.jsonl"
        history.parent.mkdir(parents=True, exist_ok=True)
        with open(history, "w") as fh:
            for rec in history_records:
                fh.write(json.dumps(rec) + "\n")

    return proj


# ---------------------------------------------------------------------------
# AC-26 — REQ covered by archived change shows merged_by_archived = true
# ---------------------------------------------------------------------------


def test_digest_attributes_req_to_archived_change(tmp_path, monkeypatch):
    from set_orch.api.orchestration import get_digest

    proj = _seed(
        tmp_path,
        requirements=[
            {"id": "REQ-LIVE", "title": "live requirement"},
            {"id": "REQ-ARCHIVED", "title": "covered only by archived"},
        ],
        history_records=[
            {"change": "v2-foundation", "spec_lineage_id": "docs/spec-v2.md",
             "merged_at": "2026-02-01T10:00:00",
             "reqs": ["REQ-ARCHIVED"]},
        ],
    )
    monkeypatch.setattr(
        "set_orch.api.orchestration._resolve_project", lambda _p: proj,
    )
    monkeypatch.setattr(
        "set_orch.api.orchestration._state_path",
        lambda _p: proj / "orchestration-state.json",
    )

    result = get_digest("proj")
    reqs = result["requirements"]["requirements"]
    archived_req = next(r for r in reqs if r["id"] == "REQ-ARCHIVED")
    assert archived_req["merged_by"] == "v2-foundation"
    assert archived_req["merged_by_archived"] is True
    assert "merged_at" in archived_req


def test_digest_does_not_attribute_when_req_not_in_history(tmp_path, monkeypatch):
    from set_orch.api.orchestration import get_digest

    proj = _seed(
        tmp_path,
        requirements=[
            {"id": "REQ-NOT-COVERED", "title": "no one covered me"},
        ],
        history_records=[
            {"change": "other", "spec_lineage_id": "docs/spec-v2.md",
             "merged_at": "2026-02-01T10:00:00",
             "reqs": ["REQ-DIFFERENT"]},
        ],
    )
    monkeypatch.setattr("set_orch.api.orchestration._resolve_project", lambda _p: proj)
    monkeypatch.setattr(
        "set_orch.api.orchestration._state_path",
        lambda _p: proj / "orchestration-state.json",
    )
    result = get_digest("proj")
    reqs = result["requirements"]["requirements"]
    req = reqs[0]
    assert "merged_by" not in req
    assert "merged_by_archived" not in req


def test_digest_history_filters_by_lineage(tmp_path, monkeypatch):
    """A v1 history entry should NOT attribute REQs when ?lineage=v2."""
    from set_orch.api.orchestration import get_digest

    proj = _seed(
        tmp_path,
        requirements=[{"id": "REQ-X", "title": "x"}],
        history_records=[
            {"change": "v1-old", "spec_lineage_id": "docs/spec-v1.md",
             "merged_at": "2026-01-01T10:00:00", "reqs": ["REQ-X"]},
        ],
    )
    monkeypatch.setattr("set_orch.api.orchestration._resolve_project", lambda _p: proj)
    monkeypatch.setattr(
        "set_orch.api.orchestration._state_path",
        lambda _p: proj / "orchestration-state.json",
    )
    result = get_digest("proj", lineage="docs/spec-v2.md")
    req = result["requirements"]["requirements"][0]
    # v1 entry doesn't contribute under v2 query.
    assert "merged_by" not in req


def test_digest_history_picks_most_recent_attribution(tmp_path, monkeypatch):
    from set_orch.api.orchestration import get_digest

    proj = _seed(
        tmp_path,
        requirements=[{"id": "REQ-X", "title": "x"}],
        history_records=[
            {"change": "first", "spec_lineage_id": "docs/spec-v2.md",
             "merged_at": "2026-01-01T10:00:00", "reqs": ["REQ-X"]},
            {"change": "second", "spec_lineage_id": "docs/spec-v2.md",
             "merged_at": "2026-02-01T10:00:00", "reqs": ["REQ-X"]},
        ],
    )
    monkeypatch.setattr("set_orch.api.orchestration._resolve_project", lambda _p: proj)
    monkeypatch.setattr(
        "set_orch.api.orchestration._state_path",
        lambda _p: proj / "orchestration-state.json",
    )
    result = get_digest("proj")
    req = result["requirements"]["requirements"][0]
    assert req["merged_by"] == "second"
    assert req["merged_at"] == "2026-02-01T10:00:00"


# ---------------------------------------------------------------------------
# AC-27c / 4b.4 — lineage with no saved digest returns unavailable
# ---------------------------------------------------------------------------


def test_digest_returns_unavailable_when_lineage_has_no_digest(tmp_path, monkeypatch):
    from set_orch.api.orchestration import get_digest

    proj = _seed(tmp_path, with_live_digest=False, with_v1_digest=False)
    monkeypatch.setattr("set_orch.api.orchestration._resolve_project", lambda _p: proj)
    monkeypatch.setattr(
        "set_orch.api.orchestration._state_path",
        lambda _p: proj / "orchestration-state.json",
    )
    result = get_digest("proj", lineage="docs/spec-v3.md")
    assert result["exists"] is False
    assert result.get("lineage_unavailable") is True
    assert result["effective_lineage"] == "docs/spec-v3.md"


# ---------------------------------------------------------------------------
# AC-27b / 4b.7 — ?lineage=v1 routes to digest-<v1-slug>/
# ---------------------------------------------------------------------------


def test_v2_lineage_uses_v2_spec_as_denominator(tmp_path, monkeypatch):
    """AC-49: v2 spec declares 3 REQs, v2 change covers all 3 → 3/3.
    v1's 120 REQs do NOT contaminate v2's response."""
    from set_orch.api.orchestration import get_digest

    # v2 digest has only 3 REQs.
    proj = _seed(
        tmp_path,
        with_live_digest=True,
        requirements=[
            {"id": "REQ-V2-A", "title": "v2 a"},
            {"id": "REQ-V2-B", "title": "v2 b"},
            {"id": "REQ-V2-C", "title": "v2 c"},
        ],
        history_records=[
            {"change": "v2-cover-all", "spec_lineage_id": "docs/spec-v2.md",
             "merged_at": "2026-02", "reqs": ["REQ-V2-A", "REQ-V2-B", "REQ-V2-C"]},
            # v1 history has many other REQs — must not appear in v2 response.
            *[{"change": f"v1-{i}", "spec_lineage_id": "docs/spec-v1.md",
               "merged_at": "2026-01", "reqs": [f"REQ-V1-{i}"]} for i in range(120)],
        ],
    )
    monkeypatch.setattr("set_orch.api.orchestration._resolve_project", lambda _p: proj)
    monkeypatch.setattr(
        "set_orch.api.orchestration._state_path",
        lambda _p: proj / "orchestration-state.json",
    )

    result = get_digest("proj")  # default = live = docs/spec-v2.md
    reqs = result["requirements"]["requirements"]
    # v2's denominator is 3 — v1's 120 REQs absent.
    assert len(reqs) == 3
    ids = {r["id"] for r in reqs}
    assert ids == {"REQ-V2-A", "REQ-V2-B", "REQ-V2-C"}
    # All three carry archived attribution from history.
    assert all(r.get("merged_by") == "v2-cover-all" for r in reqs)


def test_v1_only_reqs_absent_from_v2_response(tmp_path, monkeypatch):
    """AC-51: v1 spec defined A,B,C; v2 spec defines only B → v2 response
    has only B, A+C don't appear at all."""
    from set_orch.api.orchestration import get_digest

    # v2's digest declares only B.
    proj = _seed(
        tmp_path,
        with_live_digest=True,
        requirements=[{"id": "REQ-B", "title": "b only"}],
        history_records=[
            {"change": "v1-old", "spec_lineage_id": "docs/spec-v1.md",
             "merged_at": "2026-01",
             "reqs": ["REQ-A", "REQ-B", "REQ-C"]},
        ],
    )
    monkeypatch.setattr("set_orch.api.orchestration._resolve_project", lambda _p: proj)
    monkeypatch.setattr(
        "set_orch.api.orchestration._state_path",
        lambda _p: proj / "orchestration-state.json",
    )
    result = get_digest("proj")  # default = v2 (live)
    reqs = result["requirements"]["requirements"]
    # Only REQ-B (in v2's digest) shows up.  REQ-A and REQ-C from v1 history
    # do NOT bleed into v2's response — they're not in v2's denominator.
    ids = {r["id"] for r in reqs}
    assert ids == {"REQ-B"}


def test_digest_routes_to_lineage_specific_dir(tmp_path, monkeypatch):
    from set_orch.api.orchestration import get_digest

    proj = _seed(
        tmp_path,
        requirements=[{"id": "REQ-V2-LIVE", "title": "v2 live"}],
        with_v1_digest=True,
    )
    monkeypatch.setattr("set_orch.api.orchestration._resolve_project", lambda _p: proj)
    monkeypatch.setattr(
        "set_orch.api.orchestration._state_path",
        lambda _p: proj / "orchestration-state.json",
    )

    # Default (live) → returns v2's REQ-V2-LIVE.
    live_result = get_digest("proj")
    assert any(r["id"] == "REQ-V2-LIVE" for r in live_result["requirements"]["requirements"])

    # ?lineage=v1 → routes to digest-<v1-slug>/, returns v1's REQs.
    v1_result = get_digest("proj", lineage="docs/spec-v1.md")
    assert v1_result["exists"] is True
    assert v1_result["effective_lineage"] == "docs/spec-v1.md"
    v1_reqs = v1_result["requirements"]["requirements"]
    assert any(r["id"] == "REQ-V1-1" for r in v1_reqs)
    # v2-only REQ should NOT appear.
    assert not any(r["id"] == "REQ-V2-LIVE" for r in v1_reqs)
