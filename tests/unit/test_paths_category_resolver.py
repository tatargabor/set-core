"""Tests for category-resolver path constants and the JSONL append helper.

These properties are consumed by:
- ``lib/set_orch/category_resolver.py`` (audit log + cache lookup)
- ``lib/set_orch/insights.py`` (aggregator input + output)
- The dispatcher (read both before each dispatch)
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import pytest

from set_orch.paths import LineagePaths, append_jsonl


@pytest.fixture
def lineage(tmp_path: Path) -> LineagePaths:
    return LineagePaths(str(tmp_path))


def test_category_classifications_path_is_under_state(lineage, tmp_path):
    """Audit log lives at ``<project>/.set/state/category-classifications.jsonl``."""
    assert lineage.category_classifications == str(
        tmp_path / ".set" / "state" / "category-classifications.jsonl"
    )


def test_project_insights_path_is_under_state(lineage, tmp_path):
    """Insights aggregate lives at ``<project>/.set/state/project-insights.json``."""
    assert lineage.project_insights == str(
        tmp_path / ".set" / "state" / "project-insights.json"
    )


def test_category_paths_consistent_with_other_state_files(lineage, tmp_path):
    """Both new paths share the ``.set/state/`` parent — same write
    domain so a single ``mkdir(parents=True)`` covers both."""
    cat_parent = os.path.dirname(lineage.category_classifications)
    insights_parent = os.path.dirname(lineage.project_insights)
    assert cat_parent == insights_parent
    assert cat_parent == str(tmp_path / ".set" / "state")


# ─── append_jsonl ────────────────────────────────────────────────────────


def test_append_jsonl_creates_parent_dir(tmp_path):
    """Caller doesn't need to mkdir; helper handles it."""
    path = str(tmp_path / "deeply" / "nested" / "log.jsonl")
    append_jsonl(path, {"k": "v"})
    assert os.path.isfile(path)


def test_append_jsonl_writes_one_line_per_call(tmp_path):
    path = str(tmp_path / "log.jsonl")
    append_jsonl(path, {"a": 1})
    append_jsonl(path, {"a": 2})
    append_jsonl(path, {"a": 3})
    lines = open(path).read().strip().split("\n")
    assert len(lines) == 3
    assert [json.loads(line)["a"] for line in lines] == [1, 2, 3]


def test_append_jsonl_handles_non_serializable_via_default_str(tmp_path):
    """``default=str`` lets us pass Path/datetime/etc. without manual coercion."""
    path = str(tmp_path / "log.jsonl")
    append_jsonl(path, {"path": Path("/tmp/x"), "n": 1})
    record = json.loads(open(path).read().strip())
    assert record["path"] == "/tmp/x"
    assert record["n"] == 1


def test_append_jsonl_concurrent_writes_no_corruption(tmp_path):
    """Concurrent appenders MUST interleave at line boundaries.

    POSIX guarantees atomic writes < PIPE_BUF (4096 bytes) when the
    file is opened with O_APPEND. Each record here is well under that.
    """
    path = str(tmp_path / "log.jsonl")
    n_threads = 8
    n_per_thread = 50

    def writer(thread_id: int):
        for i in range(n_per_thread):
            append_jsonl(path, {"thread": thread_id, "i": i})

    threads = [threading.Thread(target=writer, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = open(path).read().strip().split("\n")
    assert len(lines) == n_threads * n_per_thread
    # Every line must be valid JSON (no torn writes).
    for line in lines:
        record = json.loads(line)
        assert "thread" in record and "i" in record
