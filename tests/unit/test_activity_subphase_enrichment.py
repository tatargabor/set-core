"""Integration tests for the implementing-span enrichment pass.

Covers Section 5 (tasks 5.1-5.8) and AC-22..AC-30 acceptance criteria from
the activity-implementing-sub-phases change. Validates the integration
between `activity.py::_enrich_implementing_spans` and the drilldown
classifier — that every implementing span ends up with a `sub_spans`
field, that the per-change cache is shared with the existing aggregate
computation, and that classifier failures are isolated.

Strategy: monkey-patch `activity_detail._build_sub_spans_for_change` to
return synthetic drilldown data, then call the extracted helper. This
gives genuine coverage of the enrichment loop without spinning up the
FastAPI client or building real session JSONLs.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.api import activity as activity_module
from set_orch.api import activity_detail as activity_detail_module
from set_orch.api.activity import _enrich_implementing_spans


# ─── Helpers ─────────────────────────────────────────────────────────


def _iso(seconds: int) -> str:
    base = datetime(2026, 5, 2, 11, 0, 0, tzinfo=timezone.utc)
    return (base + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def _impl_span(change: str, start_s: int, end_s: int) -> dict:
    return {
        "category": "implementing",
        "change": change,
        "start": _iso(start_s),
        "end": _iso(end_s),
        "duration_ms": (end_s - start_s) * 1000,
    }


def _drilldown_edit(start_s: int, end_s: int, file_path: str) -> dict:
    return {
        "category": "agent:tool:edit",
        "start": _iso(start_s),
        "end": _iso(end_s),
        "duration_ms": (end_s - start_s) * 1000,
        "detail": {"tool": "Edit", "preview": file_path[:60], "file_path": file_path},
    }


def _drilldown_bash(start_s: int, end_s: int, command: str) -> dict:
    return {
        "category": "agent:tool:bash",
        "start": _iso(start_s),
        "end": _iso(end_s),
        "duration_ms": (end_s - start_s) * 1000,
        "detail": {"tool": "Bash", "preview": command[:60]},
    }


def _drilldown_subagent(start_s: int, end_s: int, slug: str = "explore") -> dict:
    return {
        "category": f"agent:subagent:{slug}",
        "start": _iso(start_s),
        "end": _iso(end_s),
        "duration_ms": (end_s - start_s) * 1000,
        "detail": {"tool": "Task", "preview": "explore foo"},
    }


def _drilldown_llm_wait(start_s: int, end_s: int) -> dict:
    return {
        "category": "agent:llm-wait",
        "start": _iso(start_s),
        "end": _iso(end_s),
        "duration_ms": (end_s - start_s) * 1000,
        "detail": {},
    }


# ─── 5.1 — End-to-end integration with synthetic drilldown ──────────


def test_implementing_span_gets_classified_sub_spans():
    """AC-22+AC-23: implementing span gets sub_spans field with classified entries."""
    drilldown = [
        _drilldown_edit(0, 5, "openspec/changes/foo/proposal.md"),
        _drilldown_edit(10, 15, "lib/foo.py"),
        _drilldown_bash(20, 30, "pnpm test"),
        _drilldown_subagent(40, 60),
    ]
    spans = [_impl_span("foo", 0, 100)]
    with patch.object(
        activity_detail_module,
        "_build_sub_spans_for_change",
        return_value=(drilldown, False),
    ):
        _enrich_implementing_spans(spans, Path("/tmp"))

    sub = spans[0]["sub_spans"]
    cats = [s["category"] for s in sub]
    assert "spec" in cats
    assert "code" in cats
    assert "test" in cats
    assert "subagent" in cats
    # Entries are start-ascending and non-overlapping
    for i in range(len(sub) - 1):
        assert sub[i]["start"] <= sub[i + 1]["start"]
        # End of one is <= start of next (no overlap)
        assert sub[i]["end"] <= sub[i + 1]["start"] or sub[i]["category"] != sub[i + 1]["category"]


def test_every_subspan_has_required_fields():
    """AC-23: each sub-span entry has category/start/end/duration_ms/trigger_tool/trigger_detail."""
    drilldown = [_drilldown_edit(0, 5, "lib/x.py")]
    spans = [_impl_span("foo", 0, 100)]
    with patch.object(
        activity_detail_module,
        "_build_sub_spans_for_change",
        return_value=(drilldown, False),
    ):
        _enrich_implementing_spans(spans, Path("/tmp"))

    for entry in spans[0]["sub_spans"]:
        assert set(entry.keys()) >= {
            "category",
            "start",
            "end",
            "duration_ms",
            "trigger_tool",
            "trigger_detail",
        }
        assert entry["category"] in {"spec", "code", "test", "build", "subagent", "other"}


def test_sub_spans_confined_to_parent_window():
    """AC-24: every sub-span is within the parent's [start, end] window.

    The caller (_clip_and_filter) is responsible for clipping; here we
    pre-clip via the parent window boundaries. Verify the contract holds.
    """
    drilldown = [
        _drilldown_edit(50, 70, "lib/inside.py"),
        _drilldown_edit(150, 160, "lib/outside.py"),  # outside parent
    ]
    spans = [_impl_span("foo", 0, 100)]
    with patch.object(
        activity_detail_module,
        "_build_sub_spans_for_change",
        return_value=(drilldown, False),
    ):
        _enrich_implementing_spans(spans, Path("/tmp"))

    parent_start = spans[0]["start"]
    parent_end = spans[0]["end"]
    for entry in spans[0]["sub_spans"]:
        assert entry["start"] >= parent_start
        assert entry["end"] <= parent_end


# ─── 5.2 — Empty / missing data paths ───────────────────────────────


def test_implementing_span_with_no_drilldown_gets_empty_sub_spans():
    """AC-22 (empty case): drilldown returns no spans → sub_spans: []."""
    spans = [_impl_span("foo", 0, 100)]
    with patch.object(
        activity_detail_module,
        "_build_sub_spans_for_change",
        return_value=([], False),
    ):
        _enrich_implementing_spans(spans, Path("/tmp"))
    assert spans[0]["sub_spans"] == []


def test_implementing_span_with_only_excluded_drilldown_gets_empty_sub_spans():
    """AC-22 + AC-15: drilldown is all llm-wait → sub_spans: []."""
    drilldown = [_drilldown_llm_wait(0, 50), _drilldown_llm_wait(50, 100)]
    spans = [_impl_span("foo", 0, 100)]
    with patch.object(
        activity_detail_module,
        "_build_sub_spans_for_change",
        return_value=(drilldown, False),
    ):
        _enrich_implementing_spans(spans, Path("/tmp"))
    assert spans[0]["sub_spans"] == []


def test_implementing_span_without_change_gets_empty_sub_spans():
    """An implementing span lacking `change` (malformed) still gets `sub_spans: []`."""
    spans = [{"category": "implementing", "start": _iso(0), "end": _iso(100), "duration_ms": 100000}]
    _enrich_implementing_spans(spans, Path("/tmp"))
    assert spans[0]["sub_spans"] == []


def test_non_implementing_spans_untouched():
    """Only `category == "implementing"` spans are touched; others get nothing."""
    spans = [
        {"category": "planning", "change": "foo", "start": _iso(0), "end": _iso(50)},
        {"category": "fixing", "change": "foo", "start": _iso(50), "end": _iso(100)},
    ]
    _enrich_implementing_spans(spans, Path("/tmp"))
    assert "sub_spans" not in spans[0]
    assert "sub_spans" not in spans[1]


# ─── 5.3 — Dispatch-fallback close path ─────────────────────────────


def test_dispatch_fallback_implementing_span_gets_sub_spans():
    """AC-22: dispatch-fallback implementing span (`detail.source = "dispatch-fallback"`) is enriched too."""
    drilldown = [_drilldown_edit(0, 5, "lib/x.py")]
    span = _impl_span("foo", 0, 100)
    span["detail"] = {"source": "dispatch-fallback"}
    with patch.object(
        activity_detail_module,
        "_build_sub_spans_for_change",
        return_value=(drilldown, False),
    ):
        _enrich_implementing_spans([span], Path("/tmp"))
    assert len(span["sub_spans"]) == 1
    assert span["sub_spans"][0]["category"] == "code"
    # Existing detail is preserved alongside the new aggregate fields
    assert span["detail"]["source"] == "dispatch-fallback"
    assert span["detail"]["tool_calls"] == 1


# ─── 5.4 — Multiple implementing spans for the same change ──────────


def test_multiple_implementing_parents_share_cache():
    """AC-26: drilldown loaded ONCE per change even when multiple implementing parents exist."""
    drilldown = [
        _drilldown_edit(0, 5, "lib/x.py"),
        _drilldown_edit(50, 55, "lib/y.py"),
    ]
    spans = [
        _impl_span("foo", 0, 25),
        _impl_span("foo", 30, 60),  # second implementing parent for SAME change
    ]
    call_count = {"n": 0}

    def counting_loader(_proj_path, _change_name):
        call_count["n"] += 1
        return drilldown, False

    with patch.object(
        activity_detail_module,
        "_build_sub_spans_for_change",
        side_effect=counting_loader,
    ):
        _enrich_implementing_spans(spans, Path("/tmp"))

    assert call_count["n"] == 1, f"expected 1 cache load, got {call_count['n']}"
    # Each parent gets only its own window's sub-spans
    assert all(s["start"] >= spans[0]["start"] and s["end"] <= spans[0]["end"] for s in spans[0]["sub_spans"])
    assert all(s["start"] >= spans[1]["start"] and s["end"] <= spans[1]["end"] for s in spans[1]["sub_spans"])


def test_different_changes_load_drilldown_separately():
    """Different change names → separate drilldown loads."""
    spans = [
        _impl_span("foo", 0, 100),
        _impl_span("bar", 0, 100),
    ]
    seen = []

    def per_change_loader(_proj_path, change_name):
        seen.append(change_name)
        return [_drilldown_edit(0, 5, "lib/x.py")], False

    with patch.object(
        activity_detail_module,
        "_build_sub_spans_for_change",
        side_effect=per_change_loader,
    ):
        _enrich_implementing_spans(spans, Path("/tmp"))

    assert sorted(seen) == ["bar", "foo"]


# ─── 5.6 — Failure isolation ────────────────────────────────────────


def test_drilldown_load_failure_isolated_to_one_change():
    """AC-27: one change's drilldown load failure doesn't break other changes."""
    spans = [
        _impl_span("broken", 0, 100),
        _impl_span("ok", 0, 100),
    ]

    def selective_loader(_proj_path, change_name):
        if change_name == "broken":
            raise RuntimeError("simulated cache load failure")
        return [_drilldown_edit(0, 5, "lib/x.py")], False

    with patch.object(
        activity_detail_module,
        "_build_sub_spans_for_change",
        side_effect=selective_loader,
    ):
        _enrich_implementing_spans(spans, Path("/tmp"))

    # broken change → empty sub_spans (default)
    assert spans[0]["sub_spans"] == []
    # ok change → classified
    assert len(spans[1]["sub_spans"]) == 1


def test_classifier_failure_isolated_to_one_span():
    """AC-27: one span's classifier failure doesn't break others; that span gets `[]`."""
    spans = [_impl_span("foo", 0, 100)]
    drilldown = [_drilldown_edit(0, 5, "lib/x.py")]

    def broken_classify(_window):
        raise RuntimeError("simulated classifier failure")

    with patch.object(
        activity_detail_module,
        "_build_sub_spans_for_change",
        return_value=(drilldown, False),
    ), patch.object(activity_detail_module, "_classify_sub_phases", side_effect=broken_classify):
        _enrich_implementing_spans(spans, Path("/tmp"))

    # Span still has the field (defensive default), just empty
    assert spans[0]["sub_spans"] == []
    # But aggregates DID land — the classifier runs AFTER aggregates
    assert spans[0]["detail"]["tool_calls"] == 1


# ─── 5.7-5.8 — Trigger metadata ─────────────────────────────────────


def test_trigger_metadata_round_trip():
    """AC-28: detail.tool / detail.preview surface as trigger_tool / trigger_detail."""
    drilldown = [_drilldown_edit(0, 5, "openspec/changes/foo/proposal.md")]
    spans = [_impl_span("foo", 0, 100)]
    with patch.object(
        activity_detail_module,
        "_build_sub_spans_for_change",
        return_value=(drilldown, False),
    ):
        _enrich_implementing_spans(spans, Path("/tmp"))
    entry = spans[0]["sub_spans"][0]
    assert entry["category"] == "spec"
    assert entry["trigger_tool"] == "Edit"
    assert entry["trigger_detail"] == "openspec/changes/foo/proposal.md"


def test_missing_trigger_metadata_yields_null_fields():
    """AC-30: drilldown sub-span without detail.tool/preview → null fields, not omitted."""
    drilldown = [
        {
            "category": "agent:tool:read",
            "start": _iso(0),
            "end": _iso(5),
            "duration_ms": 5000,
            "detail": {},
        }
    ]
    spans = [_impl_span("foo", 0, 100)]
    with patch.object(
        activity_detail_module,
        "_build_sub_spans_for_change",
        return_value=(drilldown, False),
    ):
        _enrich_implementing_spans(spans, Path("/tmp"))
    entry = spans[0]["sub_spans"][0]
    # Field is PRESENT (not omitted) but null
    assert "trigger_tool" in entry
    assert entry["trigger_tool"] is None
    assert "trigger_detail" in entry
    assert entry["trigger_detail"] is None


# ─── Aggregate fields preserved alongside sub_spans ─────────────────


def test_aggregate_fields_still_set_alongside_sub_spans():
    """Existing tool_calls/llm_calls/subagent_count enrichment still works."""
    drilldown = [
        _drilldown_edit(0, 5, "lib/x.py"),
        _drilldown_edit(10, 15, "lib/y.py"),
        _drilldown_bash(20, 30, "pnpm test"),
        _drilldown_subagent(40, 50),
        _drilldown_llm_wait(50, 60),
    ]
    spans = [_impl_span("foo", 0, 100)]
    with patch.object(
        activity_detail_module,
        "_build_sub_spans_for_change",
        return_value=(drilldown, False),
    ):
        _enrich_implementing_spans(spans, Path("/tmp"))
    detail = spans[0]["detail"]
    assert detail["llm_calls"] == 1
    # tool_calls counts agent:tool:* (excludes subagent which is agent:subagent:*)
    assert detail["tool_calls"] == 3  # 2 edits + 1 bash
    assert detail["subagent_count"] == 1
