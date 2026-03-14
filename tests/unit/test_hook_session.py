"""Tests for wt_hooks.session — dedup cycle, cache round-trip, turn counter."""

import json
import os
import sys
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from wt_hooks.session import (
    dedup_clear,
    dedup_check,
    dedup_add,
    make_dedup_key,
    content_hash,
    gen_context_id,
    increment_turn,
    get_turn_count,
    get_last_checkpoint_turn,
    set_last_checkpoint_turn,
)
from wt_hooks.util import read_cache, write_cache


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def cache_file(tmp_dir):
    return os.path.join(tmp_dir, "session-cache.json")


# ─── dedup cycle ──────────────────────────────────────────────


class TestDedupCycle:
    def test_add_and_check(self, cache_file):
        assert dedup_check(cache_file, "key1") is False
        dedup_add(cache_file, "key1")
        assert dedup_check(cache_file, "key1") is True

    def test_clear_removes_dedup_keys(self, cache_file):
        dedup_add(cache_file, "key1")
        dedup_add(cache_file, "key2")
        dedup_clear(cache_file)
        assert dedup_check(cache_file, "key1") is False
        assert dedup_check(cache_file, "key2") is False

    def test_clear_preserves_turn_count(self, cache_file):
        write_cache(cache_file, {"turn_count": 5, "key1": 1})
        dedup_clear(cache_file)
        cache = read_cache(cache_file)
        assert cache.get("turn_count") == 5
        assert "key1" not in cache

    def test_clear_preserves_metrics(self, cache_file):
        write_cache(cache_file, {"_metrics": [{"ts": "now"}], "key1": 1})
        dedup_clear(cache_file)
        cache = read_cache(cache_file)
        assert len(cache.get("_metrics", [])) == 1

    def test_clear_preserves_frustration_history(self, cache_file):
        write_cache(
            cache_file,
            {"frustration_history": {"count": 3}, "dedup_key": 1},
        )
        dedup_clear(cache_file)
        cache = read_cache(cache_file)
        assert cache.get("frustration_history", {}).get("count") == 3

    def test_check_nonexistent_cache(self, cache_file):
        assert dedup_check(cache_file, "anything") is False

    def test_clear_nonexistent_cache(self, cache_file):
        dedup_clear(cache_file)  # Should not raise


# ─── make_dedup_key ───────────────────────────────────────────


class TestMakeDedupKey:
    def test_consistent(self):
        k1 = make_dedup_key("PostToolUse", "Read", "/foo/bar")
        k2 = make_dedup_key("PostToolUse", "Read", "/foo/bar")
        assert k1 == k2

    def test_different_inputs(self):
        k1 = make_dedup_key("PostToolUse", "Read", "/foo")
        k2 = make_dedup_key("PostToolUse", "Bash", "/foo")
        assert k1 != k2

    def test_length(self):
        k = make_dedup_key("a", "b", "c")
        assert len(k) == 16


# ─── content_hash ─────────────────────────────────────────────


class TestContentHash:
    def test_consistent(self):
        assert content_hash("hello") == content_hash("hello")

    def test_different(self):
        assert content_hash("hello") != content_hash("world")


# ─── gen_context_id ───────────────────────────────────────────


class TestGenContextId:
    def test_returns_4_hex(self, cache_file):
        cid = gen_context_id(cache_file)
        assert len(cid) == 4
        int(cid, 16)  # Should not raise

    def test_unique_ids(self, cache_file):
        ids = set()
        for _ in range(10):
            ids.add(gen_context_id(cache_file))
        assert len(ids) == 10  # All unique

    def test_stored_in_cache(self, cache_file):
        gen_context_id(cache_file)
        gen_context_id(cache_file)
        cache = read_cache(cache_file)
        assert len(cache.get("_used_context_ids", [])) == 2


# ─── turn counter ─────────────────────────────────────────────


class TestTurnCounter:
    def test_increment(self, cache_file):
        assert increment_turn(cache_file) == 1
        assert increment_turn(cache_file) == 2
        assert increment_turn(cache_file) == 3

    def test_get_count(self, cache_file):
        assert get_turn_count(cache_file) == 0
        increment_turn(cache_file)
        assert get_turn_count(cache_file) == 1

    def test_checkpoint_turn(self, cache_file):
        assert get_last_checkpoint_turn(cache_file) == 0
        set_last_checkpoint_turn(cache_file, 10)
        assert get_last_checkpoint_turn(cache_file) == 10

    def test_increment_preserves_checkpoint(self, cache_file):
        set_last_checkpoint_turn(cache_file, 5)
        increment_turn(cache_file)
        assert get_last_checkpoint_turn(cache_file) == 5


# ─── cache round-trip ─────────────────────────────────────────


class TestCacheRoundTrip:
    def test_write_and_read(self, cache_file):
        data = {"key": "value", "num": 42, "list": [1, 2, 3]}
        write_cache(cache_file, data)
        loaded = read_cache(cache_file)
        assert loaded == data

    def test_read_nonexistent(self, cache_file):
        assert read_cache(cache_file) == {}

    def test_overwrite(self, cache_file):
        write_cache(cache_file, {"a": 1})
        write_cache(cache_file, {"b": 2})
        loaded = read_cache(cache_file)
        assert loaded == {"b": 2}
