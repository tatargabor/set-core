"""Tests for the per-change journal append hook in state.py."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch import state as state_module
from set_orch.state import (
    Change,
    OrchestratorState,
    _JOURNAL_SEQ_CACHE,
    _JOURNALED_FIELDS,
    _journal_path,
    save_state,
    update_change_field,
)


@pytest.fixture
def clean_seq_cache():
    _JOURNAL_SEQ_CACHE.clear()
    yield
    _JOURNAL_SEQ_CACHE.clear()


def _make_state(tmpdir: str) -> str:
    state_file = os.path.join(tmpdir, "state.json")
    s = OrchestratorState(
        changes=[
            Change(name="foo", status="ready"),
            Change(name="bar", status="ready"),
        ]
    )
    save_state(s, state_file)
    return state_file


def _read_journal(state_file: str, change_name: str) -> list[dict]:
    path = _journal_path(state_file, change_name)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


class TestJournaledFieldsFrozenset:
    def test_contains_core_gate_fields(self):
        for f in ("build_result", "test_result", "e2e_result", "review_result"):
            assert f in _JOURNALED_FIELDS

    def test_contains_status_and_current_step(self):
        assert "status" in _JOURNALED_FIELDS
        assert "current_step" in _JOURNALED_FIELDS

    def test_contains_retry_context(self):
        assert "retry_context" in _JOURNALED_FIELDS


class TestJournalAppend:
    def test_overwrite_produces_entry(self, clean_seq_cache):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = _make_state(tmp)
            update_change_field(state_file, "foo", "status", "running")
            entries = _read_journal(state_file, "foo")
            assert len(entries) == 1
            assert entries[0]["field"] == "status"
            assert entries[0]["old"] == "ready"
            assert entries[0]["new"] == "running"
            assert entries[0]["seq"] == 1
            assert "ts" in entries[0]

    def test_no_op_write_produces_none(self, clean_seq_cache):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = _make_state(tmp)
            update_change_field(state_file, "foo", "status", "ready")
            entries = _read_journal(state_file, "foo")
            assert entries == []

    def test_non_journaled_field_produces_none(self, clean_seq_cache):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = _make_state(tmp)
            update_change_field(state_file, "foo", "worktree_path", "/tmp/wt")
            entries = _read_journal(state_file, "foo")
            assert entries == []

    def test_first_write_with_null_old_value(self, clean_seq_cache):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = _make_state(tmp)
            update_change_field(state_file, "foo", "build_result", "pass")
            entries = _read_journal(state_file, "foo")
            assert len(entries) == 1
            assert entries[0]["old"] is None
            assert entries[0]["new"] == "pass"

    def test_unwritable_journal_dir_logs_warning_but_state_commits(
        self, clean_seq_cache, caplog
    ):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = _make_state(tmp)

            with mock.patch(
                "set_orch.state._append_journal",
                side_effect=PermissionError("denied"),
            ):
                with caplog.at_level("WARNING"):
                    update_change_field(state_file, "foo", "status", "running")

            from set_orch.state import load_state

            s = load_state(state_file)
            assert s.changes[0].status == "running"
            assert any(
                "_append_journal failed" in rec.message for rec in caplog.records
            )

    def test_append_journal_direct_with_path_fallback(self, clean_seq_cache):
        """_append_journal must survive non-JSON-native types via default=str."""
        with tempfile.TemporaryDirectory() as tmp:
            state_file = os.path.join(tmp, "state.json")
            state_module._append_journal(
                state_file, "foo", "build_output", None, Path("/tmp/x")
            )
            entries = _read_journal(state_file, "foo")
            assert len(entries) == 1
            assert entries[0]["new"] == "/tmp/x"

    def test_append_journal_bytes_fallback(self, clean_seq_cache):
        """_append_journal must survive bytes values via repr fallback."""
        with tempfile.TemporaryDirectory() as tmp:
            state_file = os.path.join(tmp, "state.json")
            state_module._append_journal(
                state_file, "foo", "build_output", None, b"\xff\xfe"
            )
            entries = _read_journal(state_file, "foo")
            assert len(entries) == 1
            assert "xff" in entries[0]["new"] or entries[0]["new"] == "b'\\xff\\xfe'"


class TestJournalSeqCache:
    def test_seq_monotonic_within_single_test(self, clean_seq_cache):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = _make_state(tmp)
            update_change_field(state_file, "foo", "status", "running")
            update_change_field(state_file, "foo", "status", "done")
            update_change_field(state_file, "foo", "current_step", "verify")
            entries = _read_journal(state_file, "foo")
            seqs = [e["seq"] for e in entries]
            assert seqs == [1, 2, 3]

    def test_seq_independent_per_change(self, clean_seq_cache):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = _make_state(tmp)
            update_change_field(state_file, "foo", "status", "running")
            update_change_field(state_file, "bar", "status", "running")
            foo = _read_journal(state_file, "foo")
            bar = _read_journal(state_file, "bar")
            assert foo[0]["seq"] == 1
            assert bar[0]["seq"] == 1


class TestJournalThreadSafety:
    def test_concurrent_writes_both_preserved(self, clean_seq_cache):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = _make_state(tmp)

            errors: list[BaseException] = []

            def worker(new_status: str) -> None:
                try:
                    update_change_field(state_file, "foo", "current_step", new_status)
                except BaseException as exc:
                    errors.append(exc)

            t1 = threading.Thread(target=worker, args=("step_a",))
            t2 = threading.Thread(target=worker, args=("step_b",))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            assert errors == []
            entries = _read_journal(state_file, "foo")
            assert len(entries) == 2
            values = {e["new"] for e in entries}
            assert values == {"step_a", "step_b"}
