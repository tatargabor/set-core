"""Tests for lib/set_orch/archive.py — archive_and_write helper."""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.archive import archive_and_write


class TestArchiveAndWrite:
    def test_write_to_new_file_skips_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "foo.json")
            archive_dir = os.path.join(tmp, "archives")
            result = archive_and_write(target, "new content", archive_dir=archive_dir)
            assert result is None
            assert Path(target).read_text() == "new content"
            assert not Path(archive_dir).exists() or not any(Path(archive_dir).iterdir())

    def test_write_to_existing_file_creates_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "foo.json")
            Path(target).write_text("old content")
            archive_dir = os.path.join(tmp, "archives")

            result = archive_and_write(target, "new content", archive_dir=archive_dir)

            assert result is not None
            assert Path(result).exists()
            assert Path(result).read_text() == "old content"
            assert Path(target).read_text() == "new content"

    def test_sidecar_written_when_reason_given(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "foo.json")
            Path(target).write_text("old")
            archive_dir = os.path.join(tmp, "archives")

            result = archive_and_write(
                target, "new", archive_dir=archive_dir, reason="unit-test"
            )
            sidecar = Path(result + ".meta.json")
            assert sidecar.exists()
            meta = json.loads(sidecar.read_text())
            assert meta["reason"] == "unit-test"
            assert "ts" in meta
            assert "commit" in meta

    def test_sidecar_not_written_when_reason_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "foo.json")
            Path(target).write_text("old")
            archive_dir = os.path.join(tmp, "archives")

            result = archive_and_write(target, "new", archive_dir=archive_dir)
            assert not Path(result + ".meta.json").exists()

    def test_max_archives_keeps_n_newest(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "foo.json")
            archive_dir = os.path.join(tmp, "archives")
            Path(target).write_text("v0")

            # 5 overwrites → 5 snapshots if unlimited
            for i in range(1, 6):
                archive_and_write(
                    target,
                    f"v{i}",
                    archive_dir=archive_dir,
                    max_archives=3,
                )

            snapshots = [
                f
                for f in Path(archive_dir).iterdir()
                if f.suffix == ".json"
            ]
            assert len(snapshots) == 3

    def test_max_archives_none_keeps_unlimited(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "foo.json")
            archive_dir = os.path.join(tmp, "archives")
            Path(target).write_text("v0")

            for i in range(1, 6):
                archive_and_write(
                    target,
                    f"v{i}",
                    archive_dir=archive_dir,
                    max_archives=None,
                )

            snapshots = [
                f
                for f in Path(archive_dir).iterdir()
                if f.suffix == ".json"
            ]
            assert len(snapshots) == 5

    def test_archiving_failure_does_not_prevent_write(self, caplog):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "foo.json")
            Path(target).write_text("old")

            # Use a path that points into the file — copy will fail
            archive_dir = os.path.join(target, "impossible")

            with caplog.at_level("WARNING"):
                archive_and_write(target, "new", archive_dir=archive_dir)

            assert Path(target).read_text() == "new"

    def test_write_failure_propagates(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "foo.json")
            Path(target).write_text("old")
            archive_dir = os.path.join(tmp, "archives")

            # Make the parent directory read-only AFTER creating the archive dir
            os.makedirs(archive_dir, exist_ok=True)
            os.chmod(tmp, 0o555)
            try:
                with pytest.raises((PermissionError, OSError)):
                    archive_and_write(
                        target, "new", archive_dir=archive_dir
                    )
            finally:
                os.chmod(tmp, 0o755)

    def test_bytes_content_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "bin.dat")
            archive_dir = os.path.join(tmp, "archives")
            archive_and_write(target, b"\x00\x01\x02", archive_dir=archive_dir)
            assert Path(target).read_bytes() == b"\x00\x01\x02"


class TestGitCommitResolver:
    def test_commit_none_outside_git_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "foo.json")
            Path(target).write_text("old")
            archive_dir = os.path.join(tmp, "archives")

            result = archive_and_write(
                target, "new", archive_dir=archive_dir, reason="test"
            )
            sidecar = json.loads(Path(result + ".meta.json").read_text())
            assert sidecar["commit"] is None
