"""Tests for lib/set_orch/worktree_harvest.py."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch import worktree_harvest
from set_orch.worktree_harvest import HARVEST_ARTIFACTS, harvest_worktree


@pytest.fixture
def isolated_runtime(monkeypatch, tmp_path):
    from set_orch import paths as paths_mod

    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    monkeypatch.setattr(paths_mod, "SET_TOOLS_DATA_DIR", str(runtime_root))
    yield tmp_path


def _make_worktree(wt: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        fp = wt / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)


class TestHarvestWorktree:
    def test_all_four_files_copied(self, isolated_runtime):
        project = isolated_runtime / "proj"
        project.mkdir()
        wt = isolated_runtime / "wt-foo"
        wt.mkdir()
        _make_worktree(
            wt,
            {
                ".set/reflection.md": "# reflection",
                ".set/loop-state.json": "{}",
                ".set/activity.json": "[]",
                ".claude/review-findings.md": "# findings",
            },
        )

        dest = harvest_worktree("foo", str(wt), str(project))
        assert dest is not None
        assert dest.exists()
        assert (dest / "reflection.md").exists()
        assert (dest / "loop-state.json").exists()
        assert (dest / "activity.json").exists()
        assert (dest / "review-findings.md").exists()

        meta = json.loads((dest / ".harvest-meta.json").read_text())
        assert meta["wt_name"] == "foo"
        assert meta["reason"] == "merge"
        assert len(meta["files"]) == 4

    def test_partial_files_only_two_copied(self, isolated_runtime):
        project = isolated_runtime / "proj"
        project.mkdir()
        wt = isolated_runtime / "wt-bar"
        wt.mkdir()
        _make_worktree(
            wt,
            {
                ".set/reflection.md": "r",
                ".claude/review-findings.md": "f",
            },
        )

        dest = harvest_worktree("bar", str(wt), str(project))
        meta = json.loads((dest / ".harvest-meta.json").read_text())
        assert len(meta["files"]) == 2
        assert ".set/reflection.md" in meta["files"]
        assert ".claude/review-findings.md" in meta["files"]
        assert (dest / "reflection.md").exists()
        assert (dest / "review-findings.md").exists()

    def test_all_files_missing_metadata_still_written(self, isolated_runtime):
        project = isolated_runtime / "proj"
        project.mkdir()
        wt = isolated_runtime / "wt-empty"
        wt.mkdir()

        dest = harvest_worktree("empty", str(wt), str(project))
        assert dest.exists()
        meta = json.loads((dest / ".harvest-meta.json").read_text())
        assert meta["files"] == []

    def test_second_harvest_with_valid_meta_is_idempotent(self, isolated_runtime):
        """Double-harvest from merge_change + cleanup_all_worktrees must no-op.

        Regression: nano-run-20260412-1941 showed add-item harvested
        twice 874ms apart because merge_change and cleanup_all_worktrees
        both invoke cleanup_worktree. With idempotency, the second call
        returns the existing destination without re-copying.
        """
        project = isolated_runtime / "proj"
        project.mkdir()
        wt = isolated_runtime / "wt-dup"
        wt.mkdir()
        _make_worktree(wt, {".set/reflection.md": "r1"})

        dest1 = harvest_worktree("dup", str(wt), str(project))
        dest2 = harvest_worktree("dup", str(wt), str(project))

        assert dest1 == dest2
        # Destination name is the plain change name, NOT timestamped
        assert dest2.name == "dup"

    def test_destination_without_meta_resumes_in_place(self, isolated_runtime, caplog):
        """If a crashed prior run left a partial harvest dir with no
        meta file, a new call resumes in-place (no sibling collision dir).

        This is the nano-run-20260412-1941 fix: the earlier behavior was
        to create a `<name>.<ts>` timestamped sibling, producing pairs
        like `add-item/` + `add-item.20260412T182459Z/` in the archive.
        Resume-in-place keeps a single canonical dir per change.
        """
        project = isolated_runtime / "proj"
        project.mkdir()
        wt = isolated_runtime / "wt-partial"
        wt.mkdir()
        _make_worktree(wt, {".set/reflection.md": "r1"})

        from set_orch.worktree_harvest import _resolve_dest_root
        dest_root = _resolve_dest_root(str(project), "partial")
        dest_root.mkdir(parents=True, exist_ok=True)
        (dest_root / "orphan.txt").write_text("x")

        with caplog.at_level("WARNING"):
            dest = harvest_worktree("partial", str(wt), str(project))
        assert dest is not None
        # Resume in-place — same dir, no timestamped sibling
        assert dest == dest_root
        assert dest.name == "partial"
        # Meta is written, orphan file preserved
        assert (dest / ".harvest-meta.json").is_file()
        assert (dest / "orphan.txt").is_file()
        # No sibling dirs with the same stem
        siblings = [p for p in dest.parent.iterdir() if p.name.startswith("partial.")]
        assert siblings == []
        assert any(
            "resuming in-place" in rec.message.lower() for rec in caplog.records
        )

    def test_meta_commit_none_when_not_a_git_repo(self, isolated_runtime):
        project = isolated_runtime / "proj"
        project.mkdir()
        wt = isolated_runtime / "wt-plain"
        wt.mkdir()
        _make_worktree(wt, {".set/reflection.md": "r"})

        dest = harvest_worktree("plain", str(wt), str(project))
        meta = json.loads((dest / ".harvest-meta.json").read_text())
        assert meta["commit"] is None


class TestNonBlockingInCleanup:
    def test_harvest_exception_swallowed_by_caller(self, isolated_runtime):
        """Simulate harvest raising — merger.cleanup_worktree should swallow it."""
        import logging

        from set_orch import merger

        project = isolated_runtime / "proj"
        project.mkdir()
        wt = isolated_runtime / "wt-error"
        wt.mkdir()
        (wt / ".set").mkdir()
        (wt / ".set" / "reflection.md").write_text("r")

        # Keep the worktree intact so _archive_worktree_logs doesn't fail.
        with mock.patch.object(
            merger, "_archive_worktree_logs", return_value=0
        ), mock.patch.object(
            merger, "_archive_test_artifacts", return_value=0
        ), mock.patch(
            "set_orch.worktree_harvest.harvest_worktree",
            side_effect=RuntimeError("boom"),
        ), mock.patch.object(
            merger, "_resolve_retention", return_value="keep"
        ):
            # Must not raise
            merger.cleanup_worktree(
                "error-change",
                str(wt),
                retention="keep",
                project_path=str(project),
            )
