"""Tests for Sections 2, 5, 11, 12 — history appenders.

Covers:
  - 2.3 session_summary aggregates from a fixture session dir
  - 2.4 archive writer emits session_summary
  - 2.5 missing session dir → zeros / nulls, no exception
  - 5.5 cleanup appends the JSON line with purged=false
  - 5.6 set-close --purge flips the history flag
  - 11.1/11.5 coverage history line shape and per-merge append
  - 12.1/12.5 e2e manifest history append
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from tests.lib import test_paths as tp

from set_orch.engine import (
    _archive_completed_to_jsonl,
    _claude_mangle_path,
    _compute_session_summary,
)
from set_orch.merger import (
    _append_coverage_history_for_merge,
    _append_e2e_manifest_history_for_merge,
    _append_worktree_history,
    _mark_worktree_purged,
)
from set_orch.state import init_state, load_state, save_state


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    import set_orch.paths as paths_mod
    monkeypatch.setattr(paths_mod, "SET_TOOLS_DATA_DIR",
                        str(tmp_path / "xdg" / "set-core"))
    yield


def _setup_project_with_state(tmp_path, *, with_lineage=True):
    """Project where the orchestration-plan.json AND the SetRuntime state
    are both populated, so helpers that resolve state via SetRuntime see
    the same lineage attribution as the plan/state in the project tree."""
    from set_orch.paths import SetRuntime
    proj = tmp_path / "proj"
    proj.mkdir()
    plan_path = str(tp.plan_file(proj))
    plan = {
        "plan_version": 3,
        "brief_hash": "h",
        "plan_phase": "initial",
        "plan_method": "api",
        "input_path": "docs/spec.md" if with_lineage else None,
        "changes": [
            {"name": "foundation", "scope": "s", "complexity": "M", "phase": 1,
             "requirements": ["REQ-1", "REQ-2"]},
            {"name": "catalog", "scope": "s", "complexity": "M", "phase": 2,
             "requirements": [{"id": "REQ-3"}, {"id": "REQ-4"}]},
        ],
    }
    if not with_lineage:
        plan.pop("input_path", None)
    with open(plan_path, "w") as fh:
        json.dump(plan, fh)
    # Write state to BOTH the local "proj/state.json" (engine archive path uses
    # `dirname(state_file)`) AND the SetRuntime canonical location (helpers
    # that read SetRuntime see the lineage too).
    rt = SetRuntime(str(proj))
    rt.ensure_dirs()
    init_state(plan_path, rt.state_file,
               spec_path="docs/spec.md" if with_lineage else None,
               project_path=str(proj))
    # Mirror to a project-local state.json for engine helpers that compute
    # archive paths from `dirname(state_file)`.
    local_state = str(proj / "state.json")
    import shutil
    shutil.copy(rt.state_file, local_state)
    return proj, plan_path, local_state


# ---------------------------------------------------------------------------
# Section 2 — session_summary
# ---------------------------------------------------------------------------


def _write_session_files(claude_dir, *, n_calls=3):
    """Synthesise a Claude session JSONL with `n_calls` assistant entries."""
    claude_dir.mkdir(parents=True, exist_ok=True)
    sess = claude_dir / "abc-session.jsonl"
    with open(sess, "w") as fh:
        for i in range(n_calls):
            fh.write(json.dumps({
                "type": "user",
                "timestamp": f"2026-01-01T10:{i:02d}:00Z",
            }) + "\n")
            fh.write(json.dumps({
                "type": "assistant",
                "timestamp": f"2026-01-01T10:{i:02d}:30Z",
                "message": {"usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cache_read_input_tokens": 200,
                    "cache_creation_input_tokens": 25,
                }},
            }) + "\n")


def test_session_summary_aggregates_calls_and_tokens(tmp_path):
    wt = tmp_path / "wt-foundation"
    wt.mkdir()
    mangled = _claude_mangle_path(str(wt))
    claude_dir = Path(os.path.expanduser("~/.claude/projects/-")) / Path(f"-{mangled}")
    # Reroute to tmp_path so we don't touch the real ~/.claude dir.
    claude_dir = tmp_path / "claude" / f"-{mangled}"
    # Patch HOME so engine resolves the same place.
    os.environ["HOME"] = str(tmp_path)
    sessions_dir = Path(os.path.expanduser("~/.claude/projects/-") + mangled)
    _write_session_files(sessions_dir, n_calls=4)

    summary = _compute_session_summary(str(wt))
    assert summary["call_count"] == 4
    assert summary["input_tokens"] == 400
    assert summary["output_tokens"] == 200
    assert summary["cache_read_tokens"] == 800
    assert summary["cache_create_tokens"] == 100
    assert summary["first_call_ts"] == "2026-01-01T10:00:30Z"
    assert summary["last_call_ts"] == "2026-01-01T10:03:30Z"
    assert summary["total_duration_ms"] == 3 * 60 * 1000  # 3 minutes


def test_session_summary_missing_dir_returns_zero_block(tmp_path):
    os.environ["HOME"] = str(tmp_path)
    summary = _compute_session_summary("/tmp/nonexistent-worktree-12345")
    assert summary["call_count"] == 0
    assert summary["input_tokens"] == 0
    assert summary["first_call_ts"] is None
    assert summary["last_call_ts"] is None
    assert summary["total_duration_ms"] == 0


def test_session_summary_handles_no_worktree_path(tmp_path):
    summary = _compute_session_summary(None)
    assert summary["call_count"] == 0
    summary2 = _compute_session_summary("")
    assert summary2["call_count"] == 0


def test_archive_writer_includes_session_summary(tmp_path):
    proj, _, state_path = _setup_project_with_state(tmp_path)
    state = load_state(state_path)
    state.changes[0].status = "merged"
    state.changes[0].worktree_path = str(tmp_path / "wt-foundation")
    save_state(state, state_path)

    # No Claude session dir — summary should be all zeros, archive still works.
    os.environ["HOME"] = str(tmp_path)
    _archive_completed_to_jsonl(state_path)

    archive_path = tp.state_archive(proj)
    line = json.loads(archive_path.read_text().splitlines()[0])
    assert "session_summary" in line
    assert line["session_summary"]["call_count"] == 0
    assert line["session_summary"]["first_call_ts"] is None


# ---------------------------------------------------------------------------
# Section 5 — worktree history
# ---------------------------------------------------------------------------


def test_worktree_history_append_writes_line(tmp_path):
    proj, _, _ = _setup_project_with_state(tmp_path)
    _append_worktree_history(
        str(proj),
        change_name="foundation",
        original_path="/projects/foo-wt-foundation",
        removed_path="/projects/foo-wt-foundation.removed.1700000000",
    )
    history = (proj / "set" / "orchestration" / "worktrees-history.json").read_text()
    rec = json.loads(history.strip().splitlines()[0])
    assert rec["change_name"] == "foundation"
    assert rec["purged"] is False
    assert rec["spec_lineage_id"] == "docs/spec.md"
    assert rec["sentinel_session_id"] is not None
    assert "removed_path" in rec


def test_mark_worktree_purged_flips_flag(tmp_path):
    proj, _, _ = _setup_project_with_state(tmp_path)
    removed = "/projects/foo-wt-foundation.removed.1700000000"
    _append_worktree_history(
        str(proj),
        change_name="foundation",
        original_path="/projects/foo-wt-foundation",
        removed_path=removed,
    )
    ok = _mark_worktree_purged(str(proj), removed)
    assert ok is True
    history = (proj / "set" / "orchestration" / "worktrees-history.json").read_text()
    rec = json.loads(history.strip().splitlines()[0])
    assert rec["purged"] is True
    assert "purged_at" in rec


def test_mark_worktree_purged_no_match_returns_false(tmp_path):
    proj, _, _ = _setup_project_with_state(tmp_path)
    _append_worktree_history(
        str(proj), change_name="x", original_path="/a", removed_path="/a.removed.1",
    )
    assert _mark_worktree_purged(str(proj), "/wrong-path") is False


def test_mark_worktree_purged_only_flips_most_recent(tmp_path):
    proj, _, _ = _setup_project_with_state(tmp_path)
    removed = "/projects/foo.removed.1"
    _append_worktree_history(
        str(proj), change_name="x", original_path="/a", removed_path=removed,
    )
    _append_worktree_history(
        str(proj), change_name="x", original_path="/a", removed_path=removed,
    )
    assert _mark_worktree_purged(str(proj), removed) is True
    history = (proj / "set" / "orchestration" / "worktrees-history.json").read_text()
    recs = [json.loads(l) for l in history.strip().splitlines() if l.strip()]
    # Only one of the two entries gets flipped (the most recent one).
    purged_count = sum(1 for r in recs if r.get("purged"))
    assert purged_count == 1


# ---------------------------------------------------------------------------
# Section 11 — coverage history
# ---------------------------------------------------------------------------


def test_coverage_history_append_writes_expected_shape(tmp_path):
    proj, _, state_path = _setup_project_with_state(tmp_path)
    _append_coverage_history_for_merge(state_path, "foundation")
    history_path = proj / "set" / "orchestration" / "spec-coverage-history.jsonl"
    rec = json.loads(history_path.read_text().splitlines()[0])
    assert rec["change"] == "foundation"
    assert rec["plan_version"] == 3
    assert rec["session_id"] is not None
    assert rec["spec_lineage_id"] == "docs/spec.md"
    assert rec["reqs"] == ["REQ-1", "REQ-2"]
    assert "ts" in rec
    assert "merged_at" in rec


def test_coverage_history_extracts_reqs_from_dict_form(tmp_path):
    proj, _, state_path = _setup_project_with_state(tmp_path)
    _append_coverage_history_for_merge(state_path, "catalog")
    history_path = proj / "set" / "orchestration" / "spec-coverage-history.jsonl"
    rec = json.loads(history_path.read_text().splitlines()[0])
    # Plan stored requirements as [{"id": "REQ-3"}, ...] — appender extracts ids.
    assert rec["reqs"] == ["REQ-3", "REQ-4"]


def test_coverage_history_handles_unknown_change(tmp_path):
    proj, _, state_path = _setup_project_with_state(tmp_path)
    # Unknown change → empty reqs list, but still writes an attribution line.
    _append_coverage_history_for_merge(state_path, "ghost-change")
    history_path = proj / "set" / "orchestration" / "spec-coverage-history.jsonl"
    rec = json.loads(history_path.read_text().splitlines()[0])
    assert rec["change"] == "ghost-change"
    assert rec["reqs"] == []


# ---------------------------------------------------------------------------
# Section 12 — e2e manifest history
# ---------------------------------------------------------------------------


def test_e2e_manifest_history_append(tmp_path):
    proj, _, state_path = _setup_project_with_state(tmp_path)
    wt = tmp_path / "wt-foundation"
    wt.mkdir()
    manifest = {
        "tests": [{"name": "homepage", "passed": True, "duration_ms": 120}],
        "summary": {"total": 1, "passed": 1, "failed": 0},
    }
    (wt / "e2e-manifest.json").write_text(json.dumps(manifest))

    _append_e2e_manifest_history_for_merge(state_path, "foundation", str(wt))
    history_path = proj / "set" / "orchestration" / "e2e-manifest-history.jsonl"
    rec = json.loads(history_path.read_text().splitlines()[0])
    assert rec["change"] == "foundation"
    assert rec["spec_lineage_id"] == "docs/spec.md"
    assert rec["manifest"] == manifest


def test_e2e_manifest_skips_when_no_manifest(tmp_path):
    proj, _, state_path = _setup_project_with_state(tmp_path)
    wt = tmp_path / "wt-no-manifest"
    wt.mkdir()
    _append_e2e_manifest_history_for_merge(state_path, "foundation", str(wt))
    history_path = proj / "set" / "orchestration" / "e2e-manifest-history.jsonl"
    assert not history_path.exists()


def test_e2e_manifest_skips_when_no_worktree(tmp_path):
    proj, _, state_path = _setup_project_with_state(tmp_path)
    _append_e2e_manifest_history_for_merge(state_path, "foundation", "")
    history_path = proj / "set" / "orchestration" / "e2e-manifest-history.jsonl"
    assert not history_path.exists()


def test_e2e_manifest_handles_corrupt_manifest(tmp_path):
    proj, _, state_path = _setup_project_with_state(tmp_path)
    wt = tmp_path / "wt-bad"
    wt.mkdir()
    (wt / "e2e-manifest.json").write_text("{ this is not json")
    # Should not raise; should not append.
    _append_e2e_manifest_history_for_merge(state_path, "foundation", str(wt))
    history_path = proj / "set" / "orchestration" / "e2e-manifest-history.jsonl"
    assert not history_path.exists()
