"""Tests for Section 3 — backfill lineage migration + Section 4c — supervisor status."""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.migrations.backfill_lineage import (
    _MIGRATION_MARKER,
    migrate_legacy_archive,
)
from set_orch.supervisor.state import (
    SupervisorStatus,
    append_status_history,
    read_status,
    write_status,
)


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    import set_orch.paths as paths_mod
    monkeypatch.setattr(paths_mod, "SET_TOOLS_DATA_DIR",
                        str(tmp_path / "xdg" / "set-core"))
    yield


def _setup_project_with_archive(tmp_path, *, plan_input_path=None,
                                 entries=None, runtime=True):
    """Build a project with optional plan + state-archive.jsonl entries."""
    proj = tmp_path / "proj"
    proj.mkdir()

    # Plan goes either in the SetRuntime orchestration dir (preferred) or
    # in the project root, depending on `runtime`.
    if runtime:
        from set_orch.paths import SetRuntime
        rt = SetRuntime(str(proj))
        rt.ensure_dirs()
        plan_path = os.path.join(rt.orchestration_dir, "orchestration-plan.json")
        archive_path = os.path.join(rt.orchestration_dir, "state-archive.jsonl")
    else:
        plan_path = str(proj / "orchestration-plan.json")
        archive_path = str(proj / "state-archive.jsonl")

    if plan_input_path is not None:
        with open(plan_path, "w") as fh:
            json.dump({
                "plan_version": 1,
                "input_path": plan_input_path,
                "changes": [],
            }, fh)

    if entries:
        with open(archive_path, "w") as fh:
            for e in entries:
                fh.write(json.dumps(e) + "\n")

    return proj, archive_path


# ---------------------------------------------------------------------------
# AC-6 / 3.1, 3.6 — legacy entry + plan with input_path → entry attributed
# ---------------------------------------------------------------------------


def test_attributes_legacy_entries_from_plan_input_path(tmp_path):
    proj, archive = _setup_project_with_archive(
        tmp_path,
        plan_input_path="docs/spec.md",
        entries=[
            {"name": "old-1", "phase": 1, "status": "merged"},
            {"name": "old-2", "phase": 2, "status": "merged"},
        ],
    )
    stats = migrate_legacy_archive(str(proj))
    assert stats["scanned"] == 2
    assert stats["updated"] == 2
    assert stats["unknown"] == 0
    rewritten = [json.loads(l) for l in open(archive).read().splitlines() if l.strip()]
    for entry in rewritten:
        assert entry["spec_lineage_id"] == "docs/spec.md"


# ---------------------------------------------------------------------------
# AC-7 / 3.3, 3.7 — no plan file → tagged __unknown__ with WARNING
# ---------------------------------------------------------------------------


def test_unrecoverable_entries_become_unknown(tmp_path, caplog):
    import logging
    proj, archive = _setup_project_with_archive(
        tmp_path,
        plan_input_path=None,  # no plan
        entries=[{"name": "ghost", "phase": 1, "status": "merged"}],
    )
    with caplog.at_level(logging.WARNING, logger="set_orch.migrations.backfill_lineage"):
        stats = migrate_legacy_archive(str(proj))
    assert stats["unknown"] == 1
    assert any("__unknown__" in rec.message for rec in caplog.records)
    rewritten = [json.loads(l) for l in open(archive).read().splitlines() if l.strip()]
    assert rewritten[0]["spec_lineage_id"] == "__unknown__"


# ---------------------------------------------------------------------------
# AC-7a / 3.8 — idempotent: re-running on already-migrated archive is no-op
# ---------------------------------------------------------------------------


def test_migration_is_idempotent(tmp_path):
    proj, archive = _setup_project_with_archive(
        tmp_path,
        plan_input_path="docs/spec.md",
        entries=[{"name": "old-1", "phase": 1, "status": "merged"}],
    )
    migrate_legacy_archive(str(proj))
    before = open(archive).read()
    # Marker prevents re-run.
    stats = migrate_legacy_archive(str(proj))
    assert stats.get("skipped_marker") is True
    after = open(archive).read()
    assert before == after


def test_force_rerun_is_no_op_when_already_tagged(tmp_path):
    proj, archive = _setup_project_with_archive(
        tmp_path,
        plan_input_path="docs/spec.md",
        entries=[
            {"name": "old-1", "phase": 1, "status": "merged",
             "spec_lineage_id": "docs/spec.md"},
        ],
    )
    stats = migrate_legacy_archive(str(proj), force=True)
    assert stats["skipped_already_tagged"] == 1
    assert stats["updated"] == 0


# ---------------------------------------------------------------------------
# 3.9 — modern entry with spec_lineage_id is left untouched
# ---------------------------------------------------------------------------


def test_modern_entries_untouched(tmp_path):
    proj, archive = _setup_project_with_archive(
        tmp_path,
        plan_input_path="docs/spec.md",
        entries=[
            {"name": "modern", "phase": 3, "status": "merged",
             "spec_lineage_id": "docs/spec-v9.md", "sentinel_session_id": "abc"},
        ],
    )
    stats = migrate_legacy_archive(str(proj))
    rewritten = [json.loads(l) for l in open(archive).read().splitlines() if l.strip()]
    # spec_lineage_id NOT changed even though plan would suggest a different one.
    assert rewritten[0]["spec_lineage_id"] == "docs/spec-v9.md"
    assert stats["skipped_already_tagged"] == 1
    assert stats["updated"] == 0


# ---------------------------------------------------------------------------
# 3.4 — _load_archived_changes does NOT synthesize phase = 0
# ---------------------------------------------------------------------------


def test_loader_no_longer_synthesizes_phase_zero(tmp_path):
    from pathlib import Path
    from set_orch.api.helpers import _load_archived_changes
    proj = tmp_path / "proj"
    proj.mkdir()
    archive = proj / "state-archive.jsonl"
    archive.write_text(
        json.dumps({"name": "x", "status": "merged"}) + "\n"
    )
    entries = _load_archived_changes(Path(proj))
    assert "phase" not in entries[0]


# ---------------------------------------------------------------------------
# Section 4c.1 — supervisor status carries spec_lineage_id
# ---------------------------------------------------------------------------


def test_write_status_derives_lineage_from_spec(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    write_status(proj, SupervisorStatus(spec="docs/spec-v1.md"))
    s = read_status(proj)
    assert s.spec == "docs/spec-v1.md"
    assert s.spec_lineage_id == "docs/spec-v1.md"


def test_write_status_keeps_existing_lineage(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    write_status(proj, SupervisorStatus(
        spec="docs/spec.md",
        spec_lineage_id="explicit/override.md",
    ))
    s = read_status(proj)
    assert s.spec_lineage_id == "explicit/override.md"


# ---------------------------------------------------------------------------
# Section 4c.2 — append_status_history writes a JSON line on stop
# ---------------------------------------------------------------------------


def test_append_status_history_writes_record_with_rotated_at(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    status = SupervisorStatus(
        daemon_pid=12345, spec="docs/spec-v1.md",
        spec_lineage_id="docs/spec-v1.md",
        status="stopping",
    )
    append_status_history(proj, status)
    history = (proj / ".set" / "supervisor" / "status-history.jsonl").read_text()
    rec = json.loads(history.strip())
    assert rec["daemon_pid"] == 12345
    assert rec["spec_lineage_id"] == "docs/spec-v1.md"
    assert "rotated_at" in rec


def test_append_status_history_derives_lineage_when_missing(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    status = SupervisorStatus(daemon_pid=42, spec="docs/spec-v2.md")
    append_status_history(proj, status)
    history = (proj / ".set" / "supervisor" / "status-history.jsonl").read_text()
    rec = json.loads(history.strip())
    assert rec["spec_lineage_id"] == "docs/spec-v2.md"
