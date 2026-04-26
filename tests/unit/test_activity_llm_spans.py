"""Tests for set_orch.api.activity LLM call spans, DISPATCH-based implementing
fallback, and span-coverage-aware idle gap detection.

Covers tasks 6.1-6.10 of the fix-activity-timeline-claude-coverage change.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.api.activity import _build_spans, _compute_breakdown


def _ts(seconds_from_epoch: int) -> str:
    """Build an ISO 8601 timestamp at a given offset (UTC)."""
    return datetime.fromtimestamp(seconds_from_epoch, tz=timezone.utc).isoformat()


def _ev(etype: str, ts: str, change: str = "", data: dict | None = None, source: str = "orchestration") -> dict:
    return {"ts": ts, "type": etype, "change": change, "data": data or {}, "_source": source}


# ─── LLM_CALL span tests (tasks 6.2-6.4) ────────────────────────────


class TestLlmCallSpans:
    def test_llm_call_review_produces_span_with_computed_start(self):
        """LLM_CALL with purpose=review and duration_ms=120000 at T → span [T-120s, T]."""
        end_ts = _ts(1_000_000)
        events = [
            _ev("LLM_CALL", end_ts, change="add-auth", data={
                "purpose": "review",
                "model": "opus",
                "duration_ms": 120_000,
                "input_tokens": 100,
                "output_tokens": 200,
            }),
        ]
        spans = _build_spans(events, None, None)
        # Expect 1 LLM span (no idle, since not enough events for gap detection)
        llm_spans = [s for s in spans if s["category"] == "llm:review"]
        assert len(llm_spans) == 1
        s = llm_spans[0]
        assert s["change"] == "add-auth"
        assert s["duration_ms"] == 120_000
        # start = T - 120s
        start_dt = datetime.fromisoformat(s["start"])
        end_dt = datetime.fromisoformat(s["end"])
        assert (end_dt - start_dt) == timedelta(milliseconds=120_000)
        # detail preserved
        assert s["detail"]["model"] == "opus"
        assert s["detail"]["input_tokens"] == 100
        assert s["detail"]["output_tokens"] == 200

    def test_sentinel_llm_call_uses_sentinel_prefix(self):
        """LLM_CALL from sentinel source → category sentinel:llm:<purpose>."""
        end_ts = _ts(1_000_000)
        events = [
            _ev("LLM_CALL", end_ts, change="", data={
                "purpose": "poll",
                "duration_ms": 5000,
            }, source="sentinel"),
        ]
        spans = _build_spans(events, None, None)
        sentinel_spans = [s for s in spans if s["category"].startswith("sentinel:llm")]
        assert len(sentinel_spans) == 1
        assert sentinel_spans[0]["category"] == "sentinel:llm:poll"

    def test_llm_call_zero_duration_emits_marker_span(self):
        """LLM_CALL with missing duration_ms → zero-length marker span (no crash)."""
        end_ts = _ts(1_000_000)
        events = [
            _ev("LLM_CALL", end_ts, change="x", data={
                "purpose": "classify",
                # duration_ms missing entirely
            }),
        ]
        spans = _build_spans(events, None, None)
        marker = [s for s in spans if s["category"] == "llm:classify"]
        assert len(marker) == 1
        assert marker[0]["duration_ms"] == 0
        assert marker[0]["start"] == end_ts
        assert marker[0]["end"] == end_ts


# ─── DISPATCH implementing fallback tests (tasks 6.5-6.7) ───────────


class TestDispatchImplementingFallback:
    def test_dispatch_to_merge_produces_implementing_span(self):
        """DISPATCH → MERGE_START produces an implementing span."""
        events = [
            _ev("DISPATCH", _ts(1000), change="add-auth"),
            _ev("MERGE_START", _ts(2000), change="add-auth"),
        ]
        spans = _build_spans(events, None, None)
        impl = [s for s in spans if s["category"] == "implementing"]
        assert len(impl) == 1
        assert impl[0]["change"] == "add-auth"
        assert impl[0]["duration_ms"] == 1000 * 1000  # 1000s
        assert impl[0]["detail"]["source"] == "dispatch-fallback"

    def test_redispatch_produces_two_implementing_spans(self):
        """DISPATCH → DISPATCH (same change) produces two implementing spans."""
        events = [
            _ev("DISPATCH", _ts(1000), change="add-auth"),
            _ev("DISPATCH", _ts(2000), change="add-auth"),
            _ev("MERGE_START", _ts(3000), change="add-auth"),
        ]
        spans = _build_spans(events, None, None)
        impl = sorted(
            (s for s in spans if s["category"] == "implementing"),
            key=lambda s: s["start"],
        )
        assert len(impl) == 2
        # First span: 1000 → 2000 (closed by second DISPATCH)
        assert impl[0]["duration_ms"] == 1000 * 1000
        # Second span: 2000 → 3000 (closed by MERGE_START)
        assert impl[1]["duration_ms"] == 1000 * 1000

    def test_step_transition_suppresses_dispatch_fallback(self):
        """If STEP_TRANSITION fires for a change, DISPATCH fallback is suppressed."""
        events = [
            _ev("DISPATCH", _ts(1000), change="add-auth"),
            _ev("STEP_TRANSITION", _ts(1100), change="add-auth", data={"to": "implementing"}),
            _ev("STEP_TRANSITION", _ts(1500), change="add-auth", data={"to": "fixing"}),
            _ev("MERGE_START", _ts(2000), change="add-auth"),
        ]
        spans = _build_spans(events, None, None)
        impl = [s for s in spans if s["category"] == "implementing"]
        # Only 1 implementing span — from STEP_TRANSITION (1100→1500), NOT the DISPATCH fallback.
        assert len(impl) == 1
        assert impl[0]["duration_ms"] == 400 * 1000  # 1500-1100 = 400s
        # Should not have the dispatch-fallback marker.
        assert impl[0].get("detail", {}).get("source") != "dispatch-fallback"

    def test_implementing_open_at_end_flushes_to_last_event(self):
        """An implementing span left open flushes to the last event for that change, not end-of-stream."""
        events = [
            _ev("DISPATCH", _ts(1000), change="x"),
            _ev("CHANGE_DONE", _ts(2000), change="x"),
            # Far-future event for ANOTHER change — should not extend x's implementing span.
            _ev("DISPATCH", _ts(10000), change="y"),
        ]
        spans = _build_spans(events, None, None)
        impl_x = [s for s in spans if s["category"] == "implementing" and s["change"] == "x"]
        assert len(impl_x) == 1
        # Should close at last event for x (the CHANGE_DONE at 2000), not at 10000.
        assert impl_x[0]["duration_ms"] == 1000 * 1000

    def test_implementing_overlap_with_llm_increases_activity_time(self):
        """An implementing span overlapping an LLM span makes activity_time > wall_time."""
        events = [
            _ev("DISPATCH", _ts(1000), change="x"),
            _ev("LLM_CALL", _ts(1300), change="x", data={"purpose": "review", "duration_ms": 100_000}),
            _ev("MERGE_START", _ts(2000), change="x"),
        ]
        spans = _build_spans(events, None, None)
        wall_ms, activity_ms, pe, _ = _compute_breakdown(spans)
        # implementing covers ~1000 sec, LLM is 100 sec inside it.
        # activity_time = 1000s (impl) + 100s (llm) = 1100s, wall_time ≈ 1000s
        assert activity_ms > wall_ms
        assert pe > 1.0


# ─── Span-coverage-aware idle detection (tasks 6.9-6.10) ────────────


class TestIdleGapDetection:
    def test_implementing_span_covers_event_gap(self):
        """A long implementing span covering a 90s event gap → no idle span emitted."""
        events = [
            _ev("DISPATCH", _ts(1000), change="x"),
            # No events between 1000 and 1200 — but implementing span covers it.
            _ev("MERGE_START", _ts(1200), change="x"),
        ]
        spans = _build_spans(events, None, None)
        idle = [s for s in spans if s["category"] == "idle"]
        assert idle == []

    def test_uncovered_gap_above_threshold_emits_idle(self):
        """Gap >60s with no covering span → idle emitted."""
        # Two unrelated events 5min apart with NO span coverage in between.
        events = [
            _ev("PHASE_ADVANCED", _ts(1000), data={"to": "deps"}),
            _ev("PHASE_ADVANCED", _ts(1300), data={"to": "core"}),
        ]
        spans = _build_spans(events, None, None)
        idle = [s for s in spans if s["category"] == "idle"]
        # Gap is 300s = 5min, > 60s threshold
        assert len(idle) == 1
        assert idle[0]["duration_ms"] >= 60_000

    def test_short_gap_below_threshold_not_idle(self):
        """Gap of 30s with no covering span → no idle span."""
        events = [
            _ev("PHASE_ADVANCED", _ts(1000), data={"to": "a"}),
            _ev("PHASE_ADVANCED", _ts(1030), data={"to": "b"}),
        ]
        spans = _build_spans(events, None, None)
        idle = [s for s in spans if s["category"] == "idle"]
        assert idle == []

    def test_planning_span_covers_pre_dispatch_gap(self):
        """DIGEST_STARTED → first DISPATCH should produce a planning span and suppress idle."""
        events = [
            _ev("DIGEST_STARTED", _ts(1000)),
            _ev("DIGEST_COMPLETE", _ts(1100)),
            # 25-minute gap — no events but planning span should cover it.
            _ev("DISPATCH", _ts(2600), change="x"),
            _ev("MERGE_START", _ts(2700), change="x"),
        ]
        spans = _build_spans(events, None, None)
        plan = [s for s in spans if s["category"] == "planning"]
        assert len(plan) == 1
        # Planning span covers 1000 → 2600 = 1600s
        assert plan[0]["duration_ms"] == 1600 * 1000
        # No idle, the planning span covers the entire pre-dispatch window
        idle = [s for s in spans if s["category"] == "idle"]
        assert idle == []


# ─── VERIFY_GATE per-gate span reconstruction ────────────────────────


class TestVerifyGateSpans:
    """The verifier emits a single VERIFY_GATE event with `gate_ms` carrying
    per-gate timings and per-gate verdicts as top-level fields. The activity
    timeline must produce one span per gate (build, test, e2e, ...) — not
    just the stop_gate."""

    def test_verify_gate_emits_span_per_gate_in_gate_ms(self):
        """gate_ms with build/test/i18n_check timings → 3 passing spans."""
        events = [
            _ev("VERIFY_GATE", _ts(1_000_000), change="shell", data={
                "result": "retry",
                "stop_gate": "e2e",
                "build": "pass",
                "test": "pass",
                "i18n_check": "skipped",
                "e2e": "fail",
                "gate_ms": {"build": 7355, "test": 552, "i18n_check": 1},
            }),
        ]
        spans = _build_spans(events, None, None)
        gate_spans = {s["category"]: s for s in spans if s["category"].startswith("gate:")}
        assert "gate:build" in gate_spans
        assert "gate:test" in gate_spans
        assert "gate:i18n-check" in gate_spans
        assert gate_spans["gate:build"]["duration_ms"] == 7355
        assert gate_spans["gate:build"]["result"] == "pass"
        assert gate_spans["gate:test"]["duration_ms"] == 552
        assert gate_spans["gate:test"]["result"] == "pass"
        assert gate_spans["gate:i18n-check"]["result"] == "skipped"

    def test_verify_gate_synthesizes_failing_stop_gate_when_missing_from_gate_ms(self):
        """stop_gate=e2e with no gate_ms.e2e entry → still emits a fail span."""
        events = [
            _ev("VERIFY_GATE", _ts(1_000_000), change="shell", data={
                "result": "retry",
                "stop_gate": "e2e",
                "build": "pass",
                "e2e": "fail",
                "gate_ms": {"build": 1000},
            }),
        ]
        spans = _build_spans(events, None, None)
        e2e = [s for s in spans if s["category"] == "gate:e2e"]
        assert len(e2e) == 1
        assert e2e[0]["result"] == "fail"
        assert e2e[0]["change"] == "shell"
        assert e2e[0]["duration_ms"] > 0  # synthetic non-zero so it's visible

    def test_verify_gate_lays_spans_back_to_back_ending_at_event_ts(self):
        """Spans should be sequential, ending at the VERIFY_GATE timestamp."""
        events = [
            _ev("VERIFY_GATE", _ts(1_000_000), change="c", data={
                "result": "pass",
                "build": "pass",
                "test": "pass",
                "gate_ms": {"build": 3000, "test": 1000},
            }),
        ]
        spans = _build_spans(events, None, None)
        gate_spans = sorted(
            [s for s in spans if s["category"].startswith("gate:")],
            key=lambda s: s["start"],
        )
        # Two passing gates, build first then test
        assert [s["category"] for s in gate_spans] == ["gate:build", "gate:test"]
        # The sequence ends at the VERIFY_GATE timestamp
        assert gate_spans[-1]["end"] == _ts(1_000_000)
        # build.end == test.start (back-to-back layout)
        assert gate_spans[0]["end"] == gate_spans[1]["start"]

    def test_verify_gate_underscore_normalized_to_dash(self):
        """gate_ms key 'i18n_check' → category 'gate:i18n-check' (dashes for UI)."""
        events = [
            _ev("VERIFY_GATE", _ts(1000), change="c", data={
                "result": "pass",
                "i18n_check": "pass",
                "gate_ms": {"i18n_check": 100},
            }),
        ]
        spans = _build_spans(events, None, None)
        cats = {s["category"] for s in spans if s["category"].startswith("gate:")}
        assert "gate:i18n-check" in cats
        assert "gate:i18n_check" not in cats

    def test_verify_gate_skips_when_explicit_gate_start_open(self):
        """An open GATE_START/GATE_PASS pair takes precedence — no duplicate
        span from the VERIFY_GATE gate_ms entry."""
        events = [
            _ev("GATE_START", _ts(1000), change="c", data={"gate": "build"}),
            _ev("GATE_PASS", _ts(1005), change="c", data={"gate": "build", "elapsed_ms": 5000}),
            _ev("VERIFY_GATE", _ts(1010), change="c", data={
                "result": "pass",
                "build": "pass",
                "gate_ms": {"build": 5000},
            }),
        ]
        spans = _build_spans(events, None, None)
        build_spans = [s for s in spans if s["category"] == "gate:build"]
        # Exactly one — from GATE_PASS, not duplicated by VERIFY_GATE.
        assert len(build_spans) == 1


# ─── Agent session marker spans (fresh vs resume) ────────────────────


class TestAgentSessionMarkerSpans:
    """`AGENT_SESSION_DECISION` and `ITERATION_END` events carry the
    fresh-vs-resume signal that lets the timeline show where new Claude
    sessions are started and where prior sessions are warm-resumed."""

    def test_agent_session_decision_fresh_emits_marker(self):
        """AGENT_SESSION_DECISION with mode=fresh → agent:session-fresh marker."""
        events = [
            _ev("AGENT_SESSION_DECISION", _ts(1000), change="c", data={
                "session_mode": "fresh",
                "resume_skip_reason": "session too old (84 min > 60 min)",
                "prior_session_id": "old-uuid",
                "session_age_min": 84,
                "is_merge_retry": False,
                "is_poisoned_stall_recovery": False,
            }),
        ]
        spans = _build_spans(events, None, None)
        markers = [s for s in spans if s["category"] == "agent:session-fresh"]
        assert len(markers) == 1
        assert markers[0]["change"] == "c"
        assert markers[0]["duration_ms"] == 0
        assert markers[0]["start"] == markers[0]["end"]
        assert markers[0]["detail"]["resume_skip_reason"] == "session too old (84 min > 60 min)"
        assert markers[0]["detail"]["session_age_min"] == 84

    def test_agent_session_decision_resume_emits_marker(self):
        """AGENT_SESSION_DECISION with mode=resume → agent:session-resume marker."""
        events = [
            _ev("AGENT_SESSION_DECISION", _ts(1000), change="c", data={
                "session_mode": "resume",
                "resume_skip_reason": "",
                "prior_session_id": "uuid-abc",
                "session_age_min": 12,
                "is_merge_retry": False,
                "is_poisoned_stall_recovery": False,
            }),
        ]
        spans = _build_spans(events, None, None)
        markers = [s for s in spans if s["category"] == "agent:session-resume"]
        assert len(markers) == 1
        assert markers[0]["detail"]["prior_session_id"] == "uuid-abc"

    def test_agent_session_decision_unknown_mode_skipped(self):
        """An unknown session_mode produces no marker (defensive)."""
        events = [
            _ev("AGENT_SESSION_DECISION", _ts(1000), change="c", data={
                "session_mode": "wat",
            }),
        ]
        spans = _build_spans(events, None, None)
        markers = [s for s in spans if s["category"].startswith("agent:session-")]
        assert markers == []

    def test_iteration_end_resumed_emits_resume_marker(self):
        """ITERATION_END with resumed=true → agent:session-resume marker
        anchored to the iteration's started timestamp."""
        events = [
            _ev("DISPATCH", _ts(1000), change="c"),
            _ev("ITERATION_END", _ts(1300), change="c", data={
                "iteration": 1,
                "started": _ts(1000),
                "ended": _ts(1300),
                "session_id": "uuid-abc",
                "resumed": True,
                "duration_ms": 300_000,
                "tokens_used": 1234,
            }),
        ]
        spans = _build_spans(events, None, None)
        markers = [s for s in spans if s["category"] == "agent:session-resume"]
        assert len(markers) == 1
        # Anchor to `started`, not the event ts.
        assert markers[0]["start"] == _ts(1000)
        assert markers[0]["end"] == _ts(1000)
        assert markers[0]["detail"]["iteration"] == 1
        assert markers[0]["detail"]["session_id"] == "uuid-abc"[:8]
        assert markers[0]["detail"]["resumed"] is True

    def test_iteration_end_fresh_emits_fresh_marker(self):
        """ITERATION_END with resumed=false → agent:session-fresh marker."""
        events = [
            _ev("DISPATCH", _ts(1000), change="c"),
            _ev("ITERATION_END", _ts(1300), change="c", data={
                "iteration": 5,
                "started": _ts(1000),
                "ended": _ts(1300),
                "session_id": "uuid-new",
                "resumed": False,
                "duration_ms": 300_000,
            }),
        ]
        spans = _build_spans(events, None, None)
        markers = [s for s in spans if s["category"] == "agent:session-fresh"]
        assert len(markers) == 1
        assert markers[0]["detail"]["iteration"] == 5

    def test_iteration_end_falls_back_to_ended_when_started_missing(self):
        """If `started` is empty, the marker prefers `ended` over the event
        timestamp — both come from the bash loop's clock and are closer to
        the iteration's actual end than the orchestrator poll time."""
        events = [
            _ev("ITERATION_END", _ts(1500), change="c", data={
                "iteration": 1,
                "started": "",
                "ended": _ts(1300),
                "resumed": False,
            }),
        ]
        spans = _build_spans(events, None, None)
        markers = [s for s in spans if s["category"] == "agent:session-fresh"]
        assert len(markers) == 1
        # Marker uses `ended`, not the event ts.
        assert markers[0]["start"] == _ts(1300)

    def test_iteration_end_dropped_when_change_missing(self):
        """An ITERATION_END without a change name is malformed — drop it
        rather than emit an unscoped marker."""
        events = [
            _ev("ITERATION_END", _ts(1300), change="", data={
                "iteration": 1,
                "started": _ts(1300),
                "resumed": False,
            }),
        ]
        spans = _build_spans(events, None, None)
        markers = [s for s in spans if s["category"].startswith("agent:session-")]
        assert markers == []

    def test_agent_session_decision_dropped_when_change_missing(self):
        """AGENT_SESSION_DECISION without a change name is malformed."""
        events = [
            _ev("AGENT_SESSION_DECISION", _ts(1300), change="", data={
                "session_mode": "fresh",
            }),
        ]
        spans = _build_spans(events, None, None)
        markers = [s for s in spans if s["category"].startswith("agent:session-")]
        assert markers == []

    def test_iteration_end_dedups_duplicate_iter_after_restart(self):
        """A crash between emit + baseline persist re-emits the same iter
        on restart. The build-spans walk must produce exactly one marker
        per `(change, iteration)`."""
        events = [
            _ev("ITERATION_END", _ts(1300), change="c", data={
                "iteration": 1, "started": _ts(1000), "resumed": False,
            }),
            _ev("ITERATION_END", _ts(1500), change="c", data={
                "iteration": 1, "started": _ts(1000), "resumed": False,
            }),
            _ev("ITERATION_END", _ts(1700), change="c", data={
                "iteration": 2, "started": _ts(1500), "resumed": True,
            }),
        ]
        spans = _build_spans(events, None, None)
        iters = sorted(
            (s["detail"]["iteration"] for s in spans
             if s["category"].startswith("agent:session-")),
        )
        # Iter 1 emitted twice, iter 2 once → only iter 1 + iter 2 survive.
        assert iters == [1, 2]

    def test_session_decision_detail_keeps_false_booleans(self):
        """Boolean flags like `is_merge_retry=False` survive the detail
        filter — they carry "no" information distinct from a missing
        field."""
        events = [
            _ev("AGENT_SESSION_DECISION", _ts(1000), change="c", data={
                "session_mode": "fresh",
                "is_merge_retry": False,
                "is_poisoned_stall_recovery": False,
                "session_age_min": 0,
            }),
        ]
        spans = _build_spans(events, None, None)
        m = next(s for s in spans if s["category"] == "agent:session-fresh")
        assert m["detail"]["is_merge_retry"] is False
        assert m["detail"]["is_poisoned_stall_recovery"] is False
        assert m["detail"]["session_age_min"] == 0
