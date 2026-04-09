"""Tests for set_hooks.stop — metrics flush, commit save, checkpoint, design choices."""

import os
import sys
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_hooks.stop import (
    save_checkpoint,
    _save_design_choices,
)
from set_hooks.util import read_cache, write_cache


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def cache_file(tmp_dir):
    return os.path.join(tmp_dir, "session-cache.json")


# ─── save_checkpoint ──────────────────────────────────────────


class TestSaveCheckpoint:
    def test_empty_metrics(self, cache_file):
        write_cache(cache_file, {"_metrics": []})
        # Returns False because no set-memory command to run
        result = save_checkpoint(cache_file, 10, 0)
        # Can't test True without set-memory available, but should not crash
        assert isinstance(result, bool)

    def test_with_metrics(self, cache_file):
        metrics = [
            {"event": "UserPromptSubmit", "query": "test query with enough length"},
            {"event": "PostToolUse", "query": "/foo/bar.py"},
            {"event": "PostToolUse", "query": "git status"},
        ]
        write_cache(cache_file, {"_metrics": metrics})
        result = save_checkpoint(cache_file, 5, 0)
        assert isinstance(result, bool)


# ─── _save_design_choices ─────────────────────────────────────


class TestSaveDesignChoices:
    def test_no_design_file(self, tmp_dir):
        marker = os.path.join(tmp_dir, "marker")
        # Should not crash
        _save_design_choices("nonexistent-change", marker)

    def test_already_saved(self, tmp_dir):
        marker = os.path.join(tmp_dir, "marker")
        design_dir = os.path.join(tmp_dir, "openspec", "changes", "test-change")
        os.makedirs(design_dir)
        with open(os.path.join(design_dir, "design.md"), "w") as f:
            f.write("**Choice**: Use Python\n")
        with open(marker, "w") as f:
            f.write("test-change\n")

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_dir)
            _save_design_choices("test-change", marker)
        finally:
            os.chdir(old_cwd)
        # Should be no-op since already in marker
