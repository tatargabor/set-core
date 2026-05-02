"""Tests for the sub-phase classifier in set_orch.api.activity_detail.

Covers Section 4 (tasks 4.1-4.12) and the AC-1..AC-13 acceptance criteria
from the activity-implementing-sub-phases change. Validates:

- _classify_sub_span: drilldown category + detail.preview/file_path → bucket
- _merge_consecutive_sub_phases: 30-second gap-tolerant collapse
- _classify_sub_phases: end-to-end pipeline behaviour

The classifier is pure (no I/O), so these tests run in milliseconds.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.api.activity_detail import (
    SUB_PHASE_BUILD_RE,
    SUB_PHASE_EXCLUDED_CATEGORIES,
    SUB_PHASE_TEST_RE,
    _classify_sub_phases,
    _classify_sub_span,
    _merge_consecutive_sub_phases,
)


# ─── Helpers ─────────────────────────────────────────────────────────


def _iso(seconds: int) -> str:
    """Build an ISO 8601 timestamp at `seconds` from a fixed epoch base."""
    base = datetime(2026, 5, 2, 11, 0, 0, tzinfo=timezone.utc)
    return (base + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def _span(category: str, **detail: object) -> dict:
    """Build a minimal drilldown sub-span dict suitable for _classify_sub_span."""
    return {
        "category": category,
        "start": _iso(0),
        "end": _iso(1),
        "duration_ms": 1000,
        "detail": dict(detail),
    }


# ─── 4.1 — Edit/Write/MultiEdit path classification ─────────────────


def test_edit_to_openspec_changes_classifies_as_spec():
    """AC-1: relative path under openspec/changes/ → spec."""
    span = _span("agent:tool:edit", preview="openspec/changes/foo/proposal.md", tool="Edit")
    assert _classify_sub_span(span) == "spec"


def test_edit_to_openspec_specs_classifies_as_spec():
    """AC-1: relative path under openspec/specs/ → spec."""
    span = _span("agent:tool:write", preview="openspec/specs/bar/spec.md", tool="Write")
    assert _classify_sub_span(span) == "spec"


def test_edit_to_absolute_openspec_path_classifies_as_spec():
    """AC-1 (absolute path): full file_path takes precedence over truncated preview."""
    span = _span(
        "agent:tool:edit",
        # Preview truncated at 60 chars — `openspec/` not visible.
        preview="/Users/foo/.local/share/set-core/e2e-runs/big-project/op",
        # Full path on detail.file_path stashed by _build_tool_spans.
        file_path="/Users/foo/.local/share/set-core/e2e-runs/big-project/openspec/changes/x/proposal.md",
        tool="Edit",
    )
    assert _classify_sub_span(span) == "spec"


def test_edit_to_non_openspec_path_classifies_as_code():
    """AC-2: edits anywhere else are `code`."""
    span = _span("agent:tool:edit", preview="lib/foo.py", file_path="lib/foo.py", tool="Edit")
    assert _classify_sub_span(span) == "code"


def test_multiedit_to_non_openspec_path_classifies_as_code():
    """AC-2: MultiEdit is treated like Edit/Write."""
    span = _span("agent:tool:multiedit", preview="src/x.ts", tool="MultiEdit")
    assert _classify_sub_span(span) == "code"


def test_edit_with_missing_preview_classifies_as_code():
    """AC-9: missing preview falls back to `code` (safe default)."""
    span = _span("agent:tool:edit", tool="Edit")  # no preview/file_path
    assert _classify_sub_span(span) == "code"


def test_edit_with_empty_preview_classifies_as_code():
    """AC-9: empty preview also falls back to `code`."""
    span = _span("agent:tool:edit", preview="", tool="Edit")
    assert _classify_sub_span(span) == "code"


# ─── 4.2 — Bash command classification ──────────────────────────────


def test_bash_pytest_classifies_as_test():
    """AC-3: `pytest` matches the test regex."""
    assert _classify_sub_span(_span("agent:tool:bash", preview="pytest tests/unit", tool="Bash")) == "test"


def test_bash_pnpm_test_classifies_as_test():
    """AC-3: `pnpm test:e2e` matches via `pnpm\\s+(run\\s+)?test`."""
    assert _classify_sub_span(_span("agent:tool:bash", preview="pnpm test:e2e", tool="Bash")) == "test"


def test_bash_npm_test_classifies_as_test():
    """AC-3: `npm test` matches."""
    assert _classify_sub_span(_span("agent:tool:bash", preview="npm test --watch=false", tool="Bash")) == "test"


def test_bash_go_test_classifies_as_test():
    """AC-3: `go test ./...` matches."""
    assert _classify_sub_span(_span("agent:tool:bash", preview="go test ./...", tool="Bash")) == "test"


def test_bash_next_build_classifies_as_build():
    """AC-4: `next build` matches the build regex."""
    assert _classify_sub_span(_span("agent:tool:bash", preview="next build", tool="Bash")) == "build"


def test_bash_tsc_classifies_as_build():
    """AC-4: `tsc --noEmit` matches via `tsc`."""
    assert _classify_sub_span(_span("agent:tool:bash", preview="tsc --noEmit", tool="Bash")) == "build"


def test_bash_make_build_classifies_as_build():
    """AC-4: `make build` matches via `make\\s+(build|all)`."""
    assert _classify_sub_span(_span("agent:tool:bash", preview="make build", tool="Bash")) == "build"


def test_bash_git_status_classifies_as_other():
    """AC-5: arbitrary bash falls into `other`."""
    assert _classify_sub_span(_span("agent:tool:bash", preview="git status", tool="Bash")) == "other"


def test_bash_cat_classifies_as_other():
    """AC-5: `cat foo.txt` → other."""
    assert _classify_sub_span(_span("agent:tool:bash", preview="cat foo.txt", tool="Bash")) == "other"


def test_bash_test_pattern_is_case_insensitive():
    """Regex is case-insensitive per design D2."""
    assert _classify_sub_span(_span("agent:tool:bash", preview="PYTEST tests/", tool="Bash")) == "test"
    assert _classify_sub_span(_span("agent:tool:bash", preview="Next Build", tool="Bash")) == "build"


# ─── 4.3 — Subagent classification ──────────────────────────────────


def test_subagent_dispatch_classifies_as_subagent():
    """AC-6: agent:subagent:<purpose> → subagent regardless of slug."""
    assert _classify_sub_span(_span("agent:subagent:explore-code")) == "subagent"
    assert _classify_sub_span(_span("agent:subagent:review")) == "subagent"
    assert _classify_sub_span(_span("agent:subagent:")) == "subagent"  # empty slug edge


# ─── 4.4 — Other tool types ─────────────────────────────────────────


def test_read_classifies_as_other():
    """AC-7: agent:tool:read → other."""
    assert _classify_sub_span(_span("agent:tool:read")) == "other"


def test_grep_classifies_as_other():
    assert _classify_sub_span(_span("agent:tool:grep")) == "other"


def test_glob_classifies_as_other():
    assert _classify_sub_span(_span("agent:tool:glob")) == "other"


def test_webfetch_classifies_as_other():
    assert _classify_sub_span(_span("agent:tool:webfetch")) == "other"


def test_websearch_classifies_as_other():
    assert _classify_sub_span(_span("agent:tool:websearch")) == "other"


def test_unknown_tool_classifies_as_other():
    """AC-7: any agent:tool:<unknown> → other (catch-all)."""
    assert _classify_sub_span(_span("agent:tool:foo")) == "other"


def test_non_tool_non_subagent_category_classifies_as_other():
    """A category that does not fit our buckets at all → other."""
    assert _classify_sub_span(_span("agent:something-else")) == "other"


# ─── 4.5 — Excluded categories ──────────────────────────────────────


def test_llm_wait_is_excluded():
    """AC-8: agent:llm-wait dropped (think time, not deliberate work)."""
    assert _classify_sub_span(_span("agent:llm-wait")) is None


def test_gap_is_excluded():
    assert _classify_sub_span(_span("agent:gap")) is None


def test_hook_overhead_is_excluded():
    assert _classify_sub_span(_span("agent:hook-overhead")) is None


def test_loop_restart_is_excluded():
    assert _classify_sub_span(_span("agent:loop-restart")) is None


def test_review_wait_is_excluded():
    assert _classify_sub_span(_span("agent:review-wait")) is None


def test_verify_wait_is_excluded():
    assert _classify_sub_span(_span("agent:verify-wait")) is None


def test_excluded_set_membership():
    """SUB_PHASE_EXCLUDED_CATEGORIES contains exactly the documented six."""
    expected = {
        "agent:llm-wait",
        "agent:gap",
        "agent:hook-overhead",
        "agent:loop-restart",
        "agent:review-wait",
        "agent:verify-wait",
    }
    assert SUB_PHASE_EXCLUDED_CATEGORIES == expected


# ─── 4.6 — Defensive parsing ────────────────────────────────────────


def test_missing_detail_dict():
    """Spans without `detail` should not crash; classify per category alone."""
    assert _classify_sub_span({"category": "agent:llm-wait"}) is None
    assert _classify_sub_span({"category": "agent:tool:read"}) == "other"


def test_non_dict_detail():
    """A non-dict `detail` field should not crash."""
    assert _classify_sub_span({"category": "agent:tool:edit", "detail": "garbage"}) == "code"


def test_non_string_preview():
    """A non-string preview should be ignored, not raise."""
    span = {"category": "agent:tool:edit", "detail": {"preview": 123}}
    assert _classify_sub_span(span) == "code"  # falls into safe default


# ─── 4.7-4.10 — Consecutive merge ───────────────────────────────────


def _classified(category: str, start_s: int, end_s: int, trigger_detail: str = "") -> dict:
    return {
        "category": category,
        "start": _iso(start_s),
        "end": _iso(end_s),
        "duration_ms": (end_s - start_s) * 1000,
        "trigger_tool": "Edit",
        "trigger_detail": trigger_detail,
    }


def test_adjacent_same_category_within_30s_merges():
    """AC-10: same category, 5s gap → merged with first's trigger."""
    items = [
        _classified("code", 0, 5, "a.py"),
        _classified("code", 10, 20, "b.py"),  # 5s gap
    ]
    merged = _merge_consecutive_sub_phases(items)
    assert len(merged) == 1
    assert merged[0]["start"] == _iso(0)
    assert merged[0]["end"] == _iso(20)
    assert merged[0]["trigger_detail"] == "a.py"  # first wins


def test_adjacent_same_category_more_than_30s_apart_do_not_merge():
    """AC-11: same category, 60s gap > 30s → separate entries."""
    items = [
        _classified("code", 0, 5, "a.py"),
        _classified("code", 65, 70, "b.py"),  # 60s gap
    ]
    merged = _merge_consecutive_sub_phases(items)
    assert len(merged) == 2


def test_different_categories_never_merge():
    """AC-12: code → test (no gap) stays as two entries."""
    items = [
        _classified("code", 0, 5),
        _classified("test", 5, 20),
    ]
    merged = _merge_consecutive_sub_phases(items)
    assert len(merged) == 2
    assert merged[0]["category"] == "code"
    assert merged[1]["category"] == "test"


def test_long_run_of_micro_spans_collapses_to_one_range():
    """AC-13: 200 micro-spans with sub-second gaps → 1 merged range."""
    items = []
    for i in range(200):
        # Each span 1s long, 0.1s gap between them — well under 30s threshold
        items.append(_classified("code", i * 2, i * 2 + 1, f"file{i}.py"))
    # First start is 0, last end is 199*2+1 = 399
    merged = _merge_consecutive_sub_phases(items)
    assert len(merged) == 1
    assert merged[0]["start"] == _iso(0)
    assert merged[0]["end"] == _iso(399)
    assert merged[0]["trigger_detail"] == "file0.py"  # first wins


def test_merge_threshold_is_inclusive_at_30s():
    """Boundary check — exactly 30s gap merges; 30.001s does not."""
    items_at_30 = [
        _classified("code", 0, 5),
        _classified("code", 35, 40),  # exactly 30s gap
    ]
    merged_at_30 = _merge_consecutive_sub_phases(items_at_30)
    assert len(merged_at_30) == 1, "30s gap should merge (≤ 30_000ms)"

    items_past_30 = [
        _classified("code", 0, 5),
        _classified("code", 36, 40),  # 31s gap
    ]
    merged_past_30 = _merge_consecutive_sub_phases(items_past_30)
    assert len(merged_past_30) == 2, "31s gap should NOT merge"


def test_merge_empty_input():
    """Empty list returns empty list (no crash on edge)."""
    assert _merge_consecutive_sub_phases([]) == []


def test_merge_single_entry():
    """Single entry returns a copy of itself."""
    items = [_classified("code", 0, 5)]
    merged = _merge_consecutive_sub_phases(items)
    assert len(merged) == 1
    # Identity-independent (returns a copy, not the same dict reference)
    assert merged[0] is not items[0]


# ─── 4.11 — Pipeline integration ────────────────────────────────────


def test_pipeline_excludes_waits_and_merges():
    """End-to-end: drilldown sub-spans → categorized merged ranges."""
    windowed = [
        # Two edits separated only by an excluded llm-wait → merge
        {
            "category": "agent:tool:edit",
            "start": _iso(0),
            "end": _iso(5),
            "duration_ms": 5000,
            "detail": {"tool": "Edit", "preview": "lib/x.py"},
        },
        {
            "category": "agent:llm-wait",
            "start": _iso(5),
            "end": _iso(20),
            "duration_ms": 15000,
            "detail": {},
        },
        {
            "category": "agent:tool:edit",
            "start": _iso(25),
            "end": _iso(30),
            "duration_ms": 5000,
            "detail": {"tool": "Edit", "preview": "lib/y.py"},
        },
        # Test bash separated from the code by 30s exactly
        {
            "category": "agent:tool:bash",
            "start": _iso(60),
            "end": _iso(120),
            "duration_ms": 60000,
            "detail": {"tool": "Bash", "preview": "pnpm test"},
        },
    ]
    result = _classify_sub_phases(windowed)
    # Two edits (with llm-wait dropped) merge into one code; bash is a separate test span.
    assert len(result) == 2
    assert result[0]["category"] == "code"
    assert result[0]["start"] == _iso(0)
    assert result[0]["end"] == _iso(30)
    assert result[0]["trigger_tool"] == "Edit"
    assert result[0]["trigger_detail"] == "lib/x.py"
    assert result[1]["category"] == "test"
    assert result[1]["trigger_detail"] == "pnpm test"


def test_pipeline_missing_trigger_metadata_yields_none_fields():
    """AC-30: drilldown sub-span without detail.tool/preview → null fields, not omitted."""
    windowed = [
        {
            "category": "agent:tool:read",
            "start": _iso(0),
            "end": _iso(5),
            "duration_ms": 5000,
            "detail": {},  # neither tool nor preview
        },
    ]
    result = _classify_sub_phases(windowed)
    assert len(result) == 1
    assert result[0]["category"] == "other"
    assert result[0]["trigger_tool"] is None
    assert result[0]["trigger_detail"] is None


# ─── 4.12 — No classifiable work ────────────────────────────────────


def test_pipeline_only_excluded_categories_returns_empty():
    """AC-15: window of only waits/gaps → []."""
    windowed = [
        {
            "category": "agent:llm-wait",
            "start": _iso(0),
            "end": _iso(100),
            "duration_ms": 100000,
            "detail": {},
        },
        {
            "category": "agent:gap",
            "start": _iso(100),
            "end": _iso(200),
            "duration_ms": 100000,
            "detail": {},
        },
        {
            "category": "agent:hook-overhead",
            "start": _iso(200),
            "end": _iso(220),
            "duration_ms": 20000,
            "detail": {},
        },
    ]
    assert _classify_sub_phases(windowed) == []


def test_pipeline_empty_input_returns_empty():
    """No drilldown sub-spans → []."""
    assert _classify_sub_phases([]) == []


# ─── Regex sanity ───────────────────────────────────────────────────


def test_test_regex_word_boundary():
    """Word-boundary anchored — `pytestify` should NOT match (no boundary)."""
    # `pytest` matches inside `pytestify` because `pytest` itself is followed
    # by `i` which is a word char — \b only fires at word-non-word boundary.
    # Verify our intent: a true plausible false-positive
    assert SUB_PHASE_TEST_RE.search("pytestify foo") is None
    assert SUB_PHASE_TEST_RE.search("pytest foo") is not None


def test_build_regex_does_not_match_substring():
    """`tscompile` should NOT match `tsc` due to word boundary."""
    assert SUB_PHASE_BUILD_RE.search("tscompile") is None
    assert SUB_PHASE_BUILD_RE.search("tsc --noEmit") is not None
