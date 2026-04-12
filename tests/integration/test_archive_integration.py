"""Integration tests for archive_and_write at sentinel findings/status call sites.

These tests validate that the migrated `_write()` methods accumulate snapshots
in the sentinel archive directory.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.sentinel.findings import SentinelFindings
from set_orch.sentinel.status import SentinelStatus


@pytest.fixture
def isolated_runtime(monkeypatch, tmp_path):
    """Redirect SetRuntime into a temp directory so sentinel state is scoped."""
    from set_orch import paths as paths_mod

    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    monkeypatch.setattr(paths_mod, "SET_TOOLS_DATA_DIR", str(runtime_root))
    yield tmp_path


class TestFindingsArchiveAccumulation:
    def test_three_finding_writes_accumulate_archives(self, isolated_runtime):
        project = isolated_runtime / "proj"
        project.mkdir()

        sf = SentinelFindings(str(project))
        sf.add("critical", "change-a", "summary 1")
        sf.add("high", "change-a", "summary 2")
        sf.add("medium", "change-b", "summary 3")

        archive_dir = Path(sf.sentinel_dir) / "archive" / "findings"
        assert archive_dir.exists(), f"archive dir missing: {archive_dir}"
        snapshots = [
            f
            for f in archive_dir.iterdir()
            if f.suffix == ".json" and not f.name.endswith(".meta.json")
        ]
        # First call archives no prior content. Next 2 writes each archive
        # the previous file → 2 snapshots total.
        assert len(snapshots) == 2


class TestStatusRollingRetention:
    def test_25_heartbeats_keep_20_snapshots(self, isolated_runtime):
        project = isolated_runtime / "proj"
        project.mkdir()

        ss = SentinelStatus(str(project))
        ss.register("sentinel-a", orchestrator_pid=12345)

        for _ in range(25):
            ss.heartbeat()

        archive_dir = Path(ss.sentinel_dir) / "archive" / "status"
        assert archive_dir.exists(), f"archive dir missing: {archive_dir}"
        snapshots = [
            f
            for f in archive_dir.iterdir()
            if f.suffix == ".json" and not f.name.endswith(".meta.json")
        ]
        assert len(snapshots) == 20
