"""Tests for ``lib/set_orch/insights.py``.

Pins the contract from
``openspec/specs/project-insights-aggregator/spec.md``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from set_orch.insights import (
    _by_change_type,
    _deterministic_vs_llm,
    _read_records,
    load_insights,
    update_insights,
)


def _make_record(
    *,
    change_name: str,
    change_type: str,
    final: list[str],
    deterministic_cats: list[str] | None = None,
    llm_cats: list[str] | None = None,
    cache_hit: bool = False,
    uncovered: list[str] | None = None,
) -> dict:
    """Build an audit record matching the resolver's schema."""
    return {
        "ts": "2026-04-26T15:00:00+02:00",
        "change_name": change_name,
        "cache_key": f"hash-{change_name}",
        "cache_hit": cache_hit,
        "change_type": change_type,
        "deterministic": {
            "categories": deterministic_cats or final,
            "signals": {"change_type": [], "requirements": [], "paths": [],
                        "scope": [], "deps": [], "insights": [],
                        "project_state": []},
        },
        "llm": {
            "categories": llm_cats if llm_cats is not None else final,
            "model": "claude-sonnet-4-6",
            "duration_ms": 1200,
        },
        "final": final,
        "delta": {"added_by_llm": [], "agreed": [], "removed_by_llm": []},
        "uncovered_categories": uncovered or [],
    }


def _write_records(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


# ─── update_insights ────────────────────────────────────────────────────


def test_first_run_writes_insights(tmp_path):
    jsonl = tmp_path / "audit.jsonl"
    out = tmp_path / "insights.json"
    _write_records(jsonl, [
        _make_record(change_name="ch1", change_type="feature", final=["frontend"]),
    ])
    result = update_insights(str(jsonl), str(out))
    assert result is not None
    assert result["samples_n"] == 1
    assert "feature" in result["by_change_type"]
    assert out.is_file()


def test_subsequent_runs_recompute_from_full_log(tmp_path):
    """Aggregator MUST recompute from the entire JSONL, not incrementally."""
    jsonl = tmp_path / "audit.jsonl"
    out = tmp_path / "insights.json"
    _write_records(jsonl, [
        _make_record(change_name=f"ch{i}", change_type="feature", final=["frontend"])
        for i in range(3)
    ])
    update_insights(str(jsonl), str(out))

    # Add a 4th record
    with open(jsonl, "a") as f:
        f.write(json.dumps(_make_record(
            change_name="ch3", change_type="feature", final=["frontend", "auth"]
        )) + "\n")
    second = update_insights(str(jsonl), str(out))
    assert second["samples_n"] == 4


def test_no_records_returns_none(tmp_path):
    """Missing/empty JSONL → cold start → None (not error)."""
    out = tmp_path / "insights.json"
    assert update_insights(str(tmp_path / "missing.jsonl"), str(out)) is None
    assert not out.exists()


def test_aggregator_does_not_raise_on_corrupt_jsonl(tmp_path):
    """Malformed lines are skipped; aggregator continues with valid lines."""
    jsonl = tmp_path / "audit.jsonl"
    out = tmp_path / "insights.json"
    jsonl.parent.mkdir(parents=True, exist_ok=True)
    jsonl.write_text(
        "not json at all\n"
        + json.dumps(_make_record(change_name="ch", change_type="feature", final=["frontend"])) + "\n"
        + "{not json}\n"
    )
    result = update_insights(str(jsonl), str(out))
    assert result is not None
    assert result["samples_n"] == 1


def test_atomic_write_no_partial_file_on_failure(tmp_path):
    """update_insights writes atomically. If we cannot create the
    output file (e.g. parent is read-only), no partial file is left."""
    jsonl = tmp_path / "audit.jsonl"
    _write_records(jsonl, [
        _make_record(change_name="ch", change_type="feature", final=["frontend"]),
    ])
    # Point output to a non-writable location (parent is a regular file)
    bad_parent = tmp_path / "not-a-dir.txt"
    bad_parent.write_text("blocking")
    out = bad_parent / "insights.json"
    result = update_insights(str(jsonl), str(out))
    assert result is None  # graceful failure


# ─── _by_change_type ────────────────────────────────────────────────────


def test_by_change_type_common_threshold_at_50pct(tmp_path):
    """common = freq ≥ 0.5; rare = 0 < freq < 0.5."""
    jsonl = tmp_path / "audit.jsonl"
    _write_records(jsonl, [
        _make_record(change_name=f"ch{i}", change_type="feature", final=["frontend"])
        for i in range(4)
    ] + [
        _make_record(change_name="chx", change_type="feature", final=["frontend", "auth"])
    ])
    records = _read_records(str(jsonl))
    by_type = _by_change_type(records)
    feat = by_type["feature"]
    assert feat["category_frequency"]["frontend"] == 1.0
    assert feat["category_frequency"]["auth"] == 0.2
    assert "frontend" in feat["common_categories"]
    assert "auth" in feat["rare_categories"]
    assert "auth" not in feat["common_categories"]


def test_by_change_type_empty_bucket_omitted(tmp_path):
    """No records for `schema` → key absent (not empty entry)."""
    jsonl = tmp_path / "audit.jsonl"
    _write_records(jsonl, [
        _make_record(change_name="ch", change_type="feature", final=["frontend"]),
    ])
    records = _read_records(str(jsonl))
    by_type = _by_change_type(records)
    assert "schema" not in by_type
    assert "feature" in by_type


# ─── _deterministic_vs_llm ──────────────────────────────────────────────


def test_agreement_rate_excludes_cache_hits(tmp_path):
    """Cache-hit records don't represent fresh model output."""
    jsonl = tmp_path / "audit.jsonl"
    _write_records(jsonl, [
        # 1 disagreement (LLM added auth)
        _make_record(change_name="a", change_type="feature",
                     final=["frontend", "auth"],
                     deterministic_cats=["frontend"],
                     llm_cats=["frontend", "auth"]),
        # 1 agreement
        _make_record(change_name="b", change_type="feature",
                     final=["frontend"],
                     deterministic_cats=["frontend"],
                     llm_cats=["frontend"]),
        # cache hit — must be excluded from agreement metric
        _make_record(change_name="c", change_type="feature",
                     final=["frontend"],
                     deterministic_cats=["frontend"],
                     llm_cats=["frontend"],
                     cache_hit=True),
    ])
    records = _read_records(str(jsonl))
    metrics = _deterministic_vs_llm(records)
    assert metrics["samples"] == 2  # cache hit excluded
    assert metrics["agreement_rate"] == 0.5  # 1 of 2 agreed
    assert metrics["llm_added_categories"]["auth"] == 1


def test_agreement_rate_none_when_no_fresh_records(tmp_path):
    """All cache hits → no signal → agreement_rate = None (not divide by zero)."""
    jsonl = tmp_path / "audit.jsonl"
    _write_records(jsonl, [
        _make_record(change_name="ch", change_type="feature",
                     final=["frontend"], cache_hit=True),
    ])
    records = _read_records(str(jsonl))
    metrics = _deterministic_vs_llm(records)
    assert metrics["agreement_rate"] is None


# ─── uncovered_categories ───────────────────────────────────────────────


def test_uncovered_categories_summed_across_records(tmp_path):
    jsonl = tmp_path / "audit.jsonl"
    _write_records(jsonl, [
        _make_record(change_name="a", change_type="feature",
                     final=["frontend"], uncovered=["rate-limiting"]),
        _make_record(change_name="b", change_type="feature",
                     final=["frontend"], uncovered=["rate-limiting", "observability"]),
    ])
    out = tmp_path / "insights.json"
    result = update_insights(str(jsonl), str(out))
    assert result["uncovered_categories"]["rate-limiting"] == 2
    assert result["uncovered_categories"]["observability"] == 1


# ─── load_insights ──────────────────────────────────────────────────────


def test_load_insights_round_trip(tmp_path):
    jsonl = tmp_path / "audit.jsonl"
    out = tmp_path / "insights.json"
    _write_records(jsonl, [
        _make_record(change_name="ch", change_type="feature", final=["frontend"]),
    ])
    written = update_insights(str(jsonl), str(out))
    loaded = load_insights(str(out))
    assert loaded == written


def test_load_insights_missing_returns_none(tmp_path):
    assert load_insights(str(tmp_path / "missing.json")) is None


def test_load_insights_corrupt_returns_none(tmp_path):
    bad = tmp_path / "insights.json"
    bad.write_text("{not json}")
    assert load_insights(str(bad)) is None


# ─── by_change_name (resolver consumes for deps transitive) ──────────────


def test_by_change_name_maps_each_change_to_its_categories(tmp_path):
    """Resolver's deps layer reads this to propagate parent categories."""
    jsonl = tmp_path / "audit.jsonl"
    out = tmp_path / "insights.json"
    _write_records(jsonl, [
        _make_record(change_name="auth-foundation", change_type="foundational",
                     final=["frontend", "auth"]),
        _make_record(change_name="user-list", change_type="feature",
                     final=["frontend", "api"]),
    ])
    result = update_insights(str(jsonl), str(out))
    assert "auth" in result["by_change_name"]["auth-foundation"]
    assert "api" in result["by_change_name"]["user-list"]
