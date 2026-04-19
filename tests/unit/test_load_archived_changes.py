"""Tests for api.helpers._load_archived_changes."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.api.helpers import _load_archived_changes


def _write_archive(root: Path, entries: list[dict]) -> None:
    archive = root / "state-archive.jsonl"
    with open(archive, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


class TestLoadArchivedChanges:
    def test_missing_archive_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            assert _load_archived_changes(Path(tmp)) == []

    def test_wrong_nested_path_is_not_consulted(self):
        # Reader must look at <root>/state-archive.jsonl, not the old
        # <root>/set/orchestration/state-archive.jsonl location.
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "set" / "orchestration"
            nested.mkdir(parents=True)
            (nested / "state-archive.jsonl").write_text(
                json.dumps({"name": "ghost", "status": "merged"}) + "\n"
            )
            assert _load_archived_changes(Path(tmp)) == []

    def test_parses_flat_per_change_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_archive(
                Path(tmp),
                [
                    {"name": "foundation-setup", "status": "merged", "phase": 1},
                    {"name": "auth-and-accounts", "status": "merged", "phase": 1},
                ],
            )
            result = _load_archived_changes(Path(tmp))
            names = sorted(r["name"] for r in result)
            assert names == ["auth-and-accounts", "foundation-setup"]
            assert all(r["_archived"] is True for r in result)
            assert all(r["phase"] == 1 for r in result)

    def test_later_entry_for_same_name_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_archive(
                Path(tmp),
                [
                    {"name": "cart", "status": "skipped"},
                    {"name": "cart", "status": "merged"},
                ],
            )
            result = _load_archived_changes(Path(tmp))
            assert len(result) == 1
            assert result[0]["status"] == "merged"

    def test_missing_phase_returned_as_is_post_migration(self):
        # Section 3.4 of run-history-and-phase-continuity dropped the
        # synthetic `phase = 0` fallback in `_load_archived_changes`.
        # The reader now returns entries verbatim; the backfill migration
        # owns phase recovery from state-events JSONLs.
        with tempfile.TemporaryDirectory() as tmp:
            _write_archive(
                Path(tmp),
                [{"name": "legacy", "status": "merged"}],
            )
            result = _load_archived_changes(Path(tmp))
            assert "phase" not in result[0]
            assert result[0]["_archived"] is True

    def test_skips_malformed_and_nameless_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "state-archive.jsonl"
            archive.write_text(
                "\n"
                "not-json\n"
                + json.dumps({"status": "merged"}) + "\n"  # missing name
                + json.dumps({"name": "ok", "status": "merged"}) + "\n"
            )
            result = _load_archived_changes(Path(tmp))
            assert [r["name"] for r in result] == ["ok"]
