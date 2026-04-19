"""Tests for Sections 9 + 10 (backend pieces).

Covers:
  - 9.1 plan_version propagates from archive entry into API response
  - 10.1 token totals include archived-change tokens (already by virtue of
        the archive writer including the token fields; smoke check here)
  - 10.2 /llm-calls emits synthetic archive_summary for archived changes
        whose worktree session dir is gone
  - AC-22 / AC-21
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from tests.lib import test_paths as tp


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    import set_orch.paths as paths_mod
    monkeypatch.setattr(paths_mod, "SET_TOOLS_DATA_DIR",
                        str(tmp_path / "xdg" / "set-core"))
    yield


def _seed(tmp_path, *, archived_summary, worktree_present):
    proj = tmp_path / "proj"
    proj.mkdir()

    # Write a minimal state file.
    state_path = tp.state_file(proj)
    state_path.write_text(json.dumps({
        "plan_version": 2,
        "brief_hash": "h",
        "plan_phase": "initial",
        "plan_method": "api",
        "status": "running",
        "created_at": "2026-01-01T00:00:00",
        "spec_lineage_id": "docs/spec.md",
        "sentinel_session_id": "sess-1",
        "changes": [],
    }))

    # Write a state-archive.jsonl with one archived change.
    archive_path = tp.state_archive(proj)
    wt_path = str(tmp_path / "wt-archived") if worktree_present else "/tmp/no-such-wt-12345"
    if worktree_present:
        os.makedirs(wt_path, exist_ok=True)
    archive_entry = {
        "name": "archived-change",
        "status": "merged",
        "phase": 1,
        "input_tokens": 1_000_000,
        "output_tokens": 50_000,
        "cache_read_tokens": 900_000,
        "cache_create_tokens": 100_000,
        "tokens_used": 2_050_000,
        "plan_version": 1,
        "archived_at": "2026-02-15T10:00:00+00:00",
        "spec_lineage_id": "docs/spec.md",
        "sentinel_session_id": "sess-archive",
        "worktree_path": wt_path,
        "session_summary": archived_summary,
    }
    with open(archive_path, "w") as fh:
        fh.write(json.dumps(archive_entry) + "\n")
    return proj, archive_entry


# ---------------------------------------------------------------------------
# 10.1 / AC-21 — archive entry tokens flow through to /state response
# ---------------------------------------------------------------------------


def test_state_endpoint_surfaces_archived_change_tokens(tmp_path, monkeypatch):
    from set_orch.api.orchestration import get_state

    proj, _ = _seed(
        tmp_path,
        archived_summary={
            "call_count": 5, "input_tokens": 1000, "output_tokens": 500,
            "cache_read_tokens": 0, "cache_create_tokens": 0,
            "first_call_ts": "2026-02-15T09:00:00+00:00",
            "last_call_ts": "2026-02-15T09:05:00+00:00",
            "total_duration_ms": 5 * 60 * 1000,
        },
        worktree_present=False,
    )
    monkeypatch.setattr(
        "set_orch.api.orchestration._resolve_project", lambda _p: proj,
    )
    monkeypatch.setattr(
        "set_orch.api.orchestration._state_path",
        lambda _p: tp.state_file(proj),
    )

    result = get_state("proj")
    archived_row = next(c for c in result["changes"] if c["name"] == "archived-change")
    # Archive's tokens flow through verbatim — Tokens panel renders them.
    assert archived_row["input_tokens"] == 1_000_000
    assert archived_row["output_tokens"] == 50_000
    assert archived_row["cache_read_tokens"] == 900_000
    assert archived_row["cache_create_tokens"] == 100_000
    # 9.1 — plan_version propagation
    assert archived_row["plan_version"] == 1
    # _archived marker present.
    assert archived_row["_archived"] is True


# ---------------------------------------------------------------------------
# 10.2 / AC-22 — /llm-calls emits archive_summary call when wt dir gone
# ---------------------------------------------------------------------------


def test_llm_calls_synthesizes_archive_summary_when_worktree_missing(tmp_path, monkeypatch):
    from set_orch.api.orchestration import _read_session_calls

    proj, entry = _seed(
        tmp_path,
        archived_summary={
            "call_count": 7, "input_tokens": 2000, "output_tokens": 800,
            "cache_read_tokens": 100, "cache_create_tokens": 50,
            "first_call_ts": "2026-02-15T09:00:00+00:00",
            "last_call_ts": "2026-02-15T09:30:00+00:00",
            "total_duration_ms": 30 * 60 * 1000,
        },
        worktree_present=False,
    )
    calls: list[dict] = []
    _read_session_calls(state=None, project_path=proj, calls=calls)

    # Find the synthetic archive_summary call.
    aggregated = [c for c in calls if c["source"] == "archive_summary"]
    assert len(aggregated) == 1
    a = aggregated[0]
    assert a["change"] == "archived-change"
    assert a["purpose_raw"] == "aggregated"
    assert a["timestamp"] == "2026-02-15T09:30:00+00:00"
    assert a["duration_ms"] == 30 * 60 * 1000
    # input_tokens = input + cache_read + cache_create
    assert a["input_tokens"] == 2000 + 100 + 50
    assert a["output_tokens"] == 800
    assert a["spec_lineage_id"] == "docs/spec.md"


def test_llm_calls_does_not_emit_synthetic_when_worktree_dir_present(tmp_path, monkeypatch):
    from set_orch.api.orchestration import _read_session_calls

    # Create a fake claude session dir that mimics the worktree's claude
    # projects entry, so the synthetic call is suppressed.
    wt = tmp_path / "wt-archived"
    wt.mkdir()
    from set_orch.api.orchestration import _claude_mangle
    mangled = _claude_mangle(str(wt))
    sessions_dir = Path.home() / ".claude" / "projects" / f"-{mangled}"
    # We cannot actually create files under $HOME here without trampling
    # real sessions; instead, monkeypatch Path.home to point into tmp_path.
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    sessions_dir = tmp_path / ".claude" / "projects" / f"-{mangled}"
    sessions_dir.mkdir(parents=True)
    (sessions_dir / "session1.jsonl").write_text("{}\n")

    proj, entry = _seed(
        tmp_path,
        archived_summary={
            "call_count": 1, "input_tokens": 10, "output_tokens": 5,
            "cache_read_tokens": 0, "cache_create_tokens": 0,
            "first_call_ts": "2026-02-15T09:00:00+00:00",
            "last_call_ts": "2026-02-15T09:00:00+00:00",
            "total_duration_ms": 0,
        },
        worktree_present=True,
    )
    # Update the archive entry to point at our worktree.
    archive_path = tp.state_archive(proj)
    entry["worktree_path"] = str(wt)
    archive_path.write_text(json.dumps(entry) + "\n")

    calls: list[dict] = []
    _read_session_calls(state=None, project_path=proj, calls=calls)
    aggregated = [c for c in calls if c["source"] == "archive_summary"]
    # Synthetic call NOT emitted because the worktree session dir exists.
    assert aggregated == []


def test_llm_calls_skips_archived_with_empty_summary(tmp_path):
    from set_orch.api.orchestration import _read_session_calls

    proj, _ = _seed(
        tmp_path,
        archived_summary={
            "call_count": 0, "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_create_tokens": 0,
            "first_call_ts": None, "last_call_ts": None,
            "total_duration_ms": 0,
        },
        worktree_present=False,
    )
    calls: list[dict] = []
    _read_session_calls(state=None, project_path=proj, calls=calls)
    aggregated = [c for c in calls if c["source"] == "archive_summary"]
    # Zero-summary entries don't generate noise rows.
    assert aggregated == []
