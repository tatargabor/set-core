"""Tests for the digest cache (set_orch.digest) and planner.force_strategy."""

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch import digest as digest_mod
from set_orch.digest import (
    DIGEST_CACHE_MAX_ENTRIES,
    _cache_path,
    _clear_cache,
    _compute_cache_key,
    _prune_cache_lru,
    _read_cache_entry,
    _write_cache_entry,
    build_digest_prompt,
    call_digest_api,
    scan_spec_directory,
)


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    """Redirect DIGEST_CACHE_DIR to a tmp_path so tests don't touch the real cache."""
    monkeypatch.setattr(digest_mod, "DIGEST_CACHE_DIR", tmp_path / "digest-cache")
    yield tmp_path / "digest-cache"


# ─── _compute_cache_key ────────────────────────────────────────────


def test_compute_cache_key_deterministic():
    assert _compute_cache_key("hello", "opus") == _compute_cache_key("hello", "opus")


def test_compute_cache_key_changes_on_prompt_byte():
    a = _compute_cache_key("hello", "opus")
    b = _compute_cache_key("hellO", "opus")
    assert a != b


def test_compute_cache_key_changes_on_model():
    a = _compute_cache_key("hello", "opus")
    b = _compute_cache_key("hello", "sonnet")
    assert a != b


def test_compute_cache_key_matches_explicit_sha256():
    expected = hashlib.sha256(b"hello" + b"opus").hexdigest()
    assert _compute_cache_key("hello", "opus") == expected


# ─── build_digest_prompt determinism ───────────────────────────────


def test_build_digest_prompt_deterministic(tmp_path):
    """Cache-key stability requires byte-deterministic prompt assembly."""
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir()
    (spec_dir / "a.md").write_text("# A\nrequirement one\n")
    (spec_dir / "b.md").write_text("# B\nrequirement two\n")

    scan1 = scan_spec_directory(str(spec_dir))
    scan2 = scan_spec_directory(str(spec_dir))
    assert build_digest_prompt(str(spec_dir), scan1) == build_digest_prompt(str(spec_dir), scan2)


# ─── read/write round-trip ────────────────────────────────────────


def test_write_then_read_round_trip(isolated_cache):
    raw = '{"requirements": [{"id": "R1", "text": "x"}]}'
    key = _compute_cache_key("p", "opus")
    assert _write_cache_entry(key, raw, "opus") is True
    assert _read_cache_entry(key) == raw


def test_read_miss_returns_none(isolated_cache):
    assert _read_cache_entry("0" * 64) is None


def test_atomic_write_no_orphan_tempfile(isolated_cache):
    raw = '{"requirements": []}'
    key = _compute_cache_key("p", "opus")
    _write_cache_entry(key, raw, "opus")
    shard = isolated_cache / key[:2]
    leftover = [p for p in shard.iterdir() if p.name.startswith(".tmp-")]
    assert leftover == []


# ─── parse-failure path ────────────────────────────────────────────


def test_write_skipped_on_parse_failure(isolated_cache):
    bad_raw = "this is not json at all"
    key = _compute_cache_key("p", "opus")
    assert _write_cache_entry(key, bad_raw, "opus") is False
    assert _read_cache_entry(key) is None


# ─── LRU prune ────────────────────────────────────────────────────


def test_prune_evicts_oldest_when_over_cap(isolated_cache):
    raw = '{"requirements": []}'
    # Populate cap entries with monotonically increasing mtimes
    keys = []
    for i in range(DIGEST_CACHE_MAX_ENTRIES):
        k = hashlib.sha256(f"prompt-{i}".encode() + b"opus").hexdigest()
        keys.append(k)
        _write_cache_entry(k, raw, "opus")
        os.utime(_cache_path(k), (1000.0 + i, 1000.0 + i))

    # Add the (cap+1)th entry with the newest mtime
    extra = hashlib.sha256(b"prompt-extra" + b"opus").hexdigest()
    _write_cache_entry(extra, raw, "opus")
    os.utime(_cache_path(extra), (9999.0, 9999.0))

    _prune_cache_lru()

    # Count entries
    total = sum(1 for shard in isolated_cache.iterdir() if shard.is_dir() for p in shard.iterdir() if p.is_file())
    assert total == DIGEST_CACHE_MAX_ENTRIES
    # Oldest key (keys[0]) should be evicted
    assert _read_cache_entry(keys[0]) is None
    # Newest extra should remain
    assert _read_cache_entry(extra) == raw


def test_hit_refreshes_mtime(isolated_cache):
    raw = '{"requirements": []}'
    key = _compute_cache_key("p", "opus")
    _write_cache_entry(key, raw, "opus")
    path = _cache_path(key)
    # Set old mtime
    os.utime(path, (1000.0, 1000.0))
    assert path.stat().st_mtime == pytest.approx(1000.0, abs=1)
    _read_cache_entry(key)
    new_mtime = path.stat().st_mtime
    assert new_mtime > 1000.0
    assert abs(new_mtime - time.time()) < 5


# ─── bypass_cache ─────────────────────────────────────────────────


def _make_claude_result(stdout: str, exit_code: int = 0):
    class _R:
        pass
    r = _R()
    r.stdout = stdout
    r.exit_code = exit_code
    return r


def test_bypass_cache_invokes_api_and_skips_write(isolated_cache):
    raw_seed = '{"requirements": [{"id": "R0"}]}'
    raw_fresh = '{"requirements": [{"id": "RNEW"}]}'
    key = _compute_cache_key("p", "opus")
    _write_cache_entry(key, raw_seed, "opus")

    with patch("set_orch.digest.run_claude_logged", return_value=_make_claude_result(raw_fresh)) as m:
        out = call_digest_api("p", model="opus", bypass_cache=True)

    assert m.called
    assert out == raw_fresh
    # Cache entry must be unchanged (still the seed)
    assert _read_cache_entry(key) == raw_seed


def test_normal_call_uses_cache(isolated_cache):
    raw = '{"requirements": [{"id": "R1"}]}'
    key = _compute_cache_key("p", "opus")
    _write_cache_entry(key, raw, "opus")

    with patch("set_orch.digest.run_claude_logged") as m:
        out = call_digest_api("p", model="opus")

    assert not m.called
    assert out == raw


def test_miss_calls_api_and_writes(isolated_cache):
    raw = '{"requirements": [{"id": "R1"}]}'
    with patch("set_orch.digest.run_claude_logged", return_value=_make_claude_result(raw)) as m:
        out = call_digest_api("fresh-prompt", model="opus")

    assert m.called
    assert out == raw
    key = _compute_cache_key("fresh-prompt", "opus")
    assert _read_cache_entry(key) == raw


# ─── _clear_cache ─────────────────────────────────────────────────


def test_clear_cache_empties_dir(isolated_cache):
    raw = '{"requirements": []}'
    for i in range(17):
        k = hashlib.sha256(f"p-{i}".encode() + b"opus").hexdigest()
        _write_cache_entry(k, raw, "opus")

    _clear_cache()
    assert not isolated_cache.exists() or not any(isolated_cache.iterdir())


def test_clear_cache_idempotent_on_empty(isolated_cache):
    # No entries, no dir
    _clear_cache()  # should not raise
    _clear_cache()  # idempotent


# ─── force_strategy ───────────────────────────────────────────────


def _write_orchestration_yaml(dir_path: Path, force_strategy: str | None) -> None:
    claude_dir = dir_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    if force_strategy is None:
        (claude_dir / "orchestration.yaml").write_text("")
    else:
        (claude_dir / "orchestration.yaml").write_text(
            f"planner:\n  force_strategy: {force_strategy}\n"
        )


def test_force_strategy_default_auto(tmp_path):
    from set_orch.planner import _read_force_strategy
    assert _read_force_strategy(str(tmp_path)) == "auto"


def test_force_strategy_flat(tmp_path):
    from set_orch.planner import _read_force_strategy
    _write_orchestration_yaml(tmp_path, "flat")
    assert _read_force_strategy(str(tmp_path)) == "flat"


def test_force_strategy_domain_parallel(tmp_path):
    from set_orch.planner import _read_force_strategy
    _write_orchestration_yaml(tmp_path, "domain-parallel")
    assert _read_force_strategy(str(tmp_path)) == "domain-parallel"


def test_force_strategy_invalid_falls_back_to_auto(tmp_path, caplog):
    import logging
    from set_orch.planner import _read_force_strategy
    _write_orchestration_yaml(tmp_path, "aggressive")
    with caplog.at_level(logging.WARNING, logger="set_orch.planner"):
        assert _read_force_strategy(str(tmp_path)) == "auto"
    assert any("aggressive" in r.message for r in caplog.records)


def test_force_strategy_empty_falls_back_to_auto(tmp_path):
    from set_orch.planner import _read_force_strategy
    # Empty string is also invalid
    _write_orchestration_yaml(tmp_path, '""')
    # Note: yaml.safe_load("\"\"") returns ""; planner section with empty
    # force_strategy is treated as invalid → auto
    assert _read_force_strategy(str(tmp_path)) == "auto"
