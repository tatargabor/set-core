"""Activity timeline API — time-based activity breakdown from orchestration events.

Reconstructs typed activity spans from event sources (orchestration-events JSONL,
sentinel events, loop-state files) and returns a structured timeline with breakdown.
"""

from __future__ import annotations

import glob as _glob
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

from .helpers import _resolve_project, _state_path, _sentinel_dir

logger = logging.getLogger(__name__)
router = APIRouter()

# ─── Activity categories ────────────────────────────────────────────

CATEGORY_ORDER = [
    "planning", "implementing", "fixing",
    "llm:review", "llm:spec_verify", "llm:replan", "llm:classify",
    "gate:build", "gate:test", "gate:review", "gate:verify",
    "gate:e2e", "gate:e2e-smoke", "gate:smoke",
    "gate:scope-check", "gate:rules", "gate:dep-install",
    "merge", "idle", "stall-recovery", "dep-wait", "manual-wait",
    "sentinel",
    "sentinel:llm:review", "sentinel:llm:spec_verify",
    "sentinel:llm:replan", "sentinel:llm:classify",
]


# ─── Event loading ──────────────────────────────────────────────────


def _cycle_sort_key(path: str) -> tuple:
    """Sort `*-cycleN.jsonl` rotated files by their integer cycle id.

    Matches the resolver in lib/set_orch/paths.py so callers see the same
    ordering across activity and llm-calls readers.
    """
    import re as _re
    base = path.rsplit("/", 1)[-1]
    m = _re.search(r"-cycle(\d+)\.jsonl$", base)
    if not m:
        return (0, base)
    return (1, int(m.group(1)))


def _load_events(project_path: Path, from_ts: str | None, to_ts: str | None) -> list[dict]:
    """Load and merge events from orchestration and sentinel JSONL files.

    Section 4.1 of run-history-and-phase-continuity: rotated cycle files
    (`orchestration-events-cycle*.jsonl`, `orchestration-state-events-cycle*.jsonl`)
    are read in cycle-ascending order BEFORE the live file so the timeline
    contains the full project history, not just the current cycle.
    CYCLE_HEADER lines are skipped — they are metadata, not events.
    """
    events: list[dict] = []

    # 1. Orchestration events — cycle files first (by numeric cycle), then live
    for base_dir in [project_path, project_path / "set" / "orchestration"]:
        for name in ["orchestration-events.jsonl", "orchestration-state-events.jsonl"]:
            stem = name.replace(".jsonl", "")
            cycle_pattern = str(base_dir / f"{stem}-cycle*.jsonl")
            for archive in sorted(_glob.glob(cycle_pattern), key=_cycle_sort_key):
                _read_jsonl(Path(archive), events, from_ts, to_ts)
            # Other archive variants (legacy non-cycle suffixes) — keep
            # alphanumeric order so behaviour for old projects is unchanged.
            other_pattern = str(base_dir / f"{stem}-*.jsonl")
            for archive in sorted(_glob.glob(other_pattern)):
                if "-cycle" in archive:
                    continue  # already handled above
                _read_jsonl(Path(archive), events, from_ts, to_ts)
            live = base_dir / name
            if live.exists():
                _read_jsonl(live, events, from_ts, to_ts)

    # 2. Sentinel events
    sentinel_dir = _sentinel_dir(project_path)
    sentinel_events_file = sentinel_dir / "events.jsonl"
    if sentinel_events_file.exists():
        _read_jsonl(sentinel_events_file, events, from_ts, to_ts, source="sentinel")

    # Sort by timestamp; CYCLE_HEADER entries are filtered in _read_jsonl.
    events.sort(key=lambda e: e.get("ts", ""))
    return events


def _read_jsonl(
    path: Path,
    out: list[dict],
    from_ts: str | None,
    to_ts: str | None,
    source: str = "orchestration",
) -> None:
    """Read a JSONL file, filtering by time range, appending to out."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # CYCLE_HEADER lines are metadata about the rotation point,
                # not events that should appear on the timeline.
                if ev.get("type") == "CYCLE_HEADER":
                    continue
                ts = ev.get("ts", "")
                if from_ts and ts < from_ts:
                    continue
                if to_ts and ts > to_ts:
                    continue
                ev["_source"] = source
                out.append(ev)
    except OSError:
        pass


# ─── Span reconstruction ───────────────────────────────────────────


def _build_spans(
    events: list[dict],
    from_ts: str | None,
    to_ts: str | None,
    active_changes: set[str] | None = None,
) -> list[dict]:
    """Reconstruct activity spans from an ordered event stream."""
    spans: list[dict] = []

    # Tracking open spans
    # gate spans: key = (change, gate_name)
    open_gates: dict[tuple[str, str], dict] = {}
    # step spans: key = change
    open_steps: dict[str, dict] = {}
    # merge spans: key = change
    open_merges: dict[str, dict] = {}
    # idle span
    open_idle: dict | None = None
    # manual-wait: key = change
    open_manual: dict[str, dict] = {}
    # dep-wait: key = change
    open_dep: dict[str, dict] = {}
    # stall-recovery: key = change
    open_stall: dict[str, dict] = {}
    # DISPATCH-based implementing fallback: key = change
    open_implementing: dict[str, dict] = {}
    # Changes that had STEP_TRANSITION — DISPATCH fallback spans are filtered
    # out for these after the walk (STEP_TRANSITION takes precedence).
    step_transition_seen: set[str] = set()
    # Last observed event timestamp per change (used to tight-flush open
    # implementing spans when a change is abandoned/failed without emitting
    # a terminal STATE_CHANGE event).
    last_event_ts_per_change: dict[str, str] = {}
    # Pre-orchestration planning phase: DIGEST_STARTED → first DISPATCH.
    # Captures digest + decomposer + planner as a single "planning" span.
    planning_start_ts: str | None = None
    planning_emitted = False

    def _close_implementing(ch: str, end_ts_val: str) -> None:
        """Close an open DISPATCH-fallback implementing span for `ch` at `end_ts_val`."""
        if ch in open_implementing:
            impl = open_implementing.pop(ch)
            spans.append({
                "category": "implementing",
                "change": ch,
                "start": impl["start"],
                "end": end_ts_val,
                "duration_ms": _ts_diff_ms(impl["start"], end_ts_val),
                "detail": {"source": "dispatch-fallback"},
            })

    for ev in events:
        etype = ev.get("type", "")
        change = ev.get("change", "")
        ts = ev.get("ts", "")
        data = ev.get("data", {})
        source = ev.get("_source", "orchestration")

        # Track last event timestamp per change (orchestration events only,
        # excluding heartbeats which carry no activity signal).
        if (
            change
            and ts
            and source == "orchestration"
            and etype not in ("WATCHDOG_HEARTBEAT", "MONITOR_HEARTBEAT")
        ):
            last_event_ts_per_change[change] = ts

        # ── LLM call spans ──
        # LLM_CALL events are emitted AFTER the subprocess returns, so `ts`
        # is the END of the call. Start is reconstructed as ts - duration_ms.
        # Orchestrator-source → "llm:<purpose>", sentinel-source → "sentinel:llm:<purpose>".
        if etype == "LLM_CALL":
            purpose = str(data.get("purpose", "unknown")).strip() or "unknown"
            raw_duration = data.get("duration_ms", 0)
            try:
                duration_ms_val = int(raw_duration) if raw_duration is not None else 0
            except (TypeError, ValueError):
                duration_ms_val = 0
            cat_prefix = "sentinel:llm" if source == "sentinel" else "llm"
            cat = f"{cat_prefix}:{purpose}"
            detail: dict = {
                "model": data.get("model"),
                "cost_usd": data.get("cost_usd"),
                "input_tokens": data.get("input_tokens"),
                "output_tokens": data.get("output_tokens"),
                "cache_read_tokens": data.get("cache_read_tokens"),
                "cache_create_tokens": data.get("cache_create_tokens"),
            }
            # Strip None-valued detail keys
            detail = {k: v for k, v in detail.items() if v is not None}
            if duration_ms_val > 0:
                start_ts = _ts_shift_ms(ts, -duration_ms_val)
                spans.append({
                    "category": cat,
                    "change": change,
                    "start": start_ts,
                    "end": ts,
                    "duration_ms": duration_ms_val,
                    "detail": detail,
                })
            else:
                # Missing/zero duration — emit a zero-length marker span, log warning.
                logger.warning(
                    "LLM_CALL with missing/zero duration_ms: purpose=%s change=%s ts=%s data=%r",
                    purpose, change, ts, data,
                )
                spans.append({
                    "category": cat,
                    "change": change,
                    "start": ts,
                    "end": ts,
                    "duration_ms": 0,
                    "detail": detail,
                })
            continue

        # ── Gate spans ──
        if etype == "GATE_START":
            gate = data.get("gate", "unknown").replace("_", "-")
            key = (change, gate)
            open_gates[key] = {"start": ts, "change": change, "gate": gate}

        elif etype == "GATE_PASS":
            gate = data.get("gate", "unknown").replace("_", "-")
            key = (change, gate)
            if key in open_gates:
                start_ev = open_gates.pop(key)
                cat = f"gate:{gate}"
                spans.append({
                    "category": cat,
                    "change": change,
                    "start": start_ev["start"],
                    "end": ts,
                    "duration_ms": data.get("elapsed_ms", _ts_diff_ms(start_ev["start"], ts)),
                    "result": "pass",
                })

        elif etype == "VERIFY_GATE":
            # VERIFY_GATE from verifier.py uses "stop_gate" not "gate"
            gate = (data.get("gate") or data.get("stop_gate", "unknown")).replace("_", "-")
            result = data.get("result", "unknown")
            key = (change, gate)
            if key in open_gates:
                start_ev = open_gates.pop(key)
                cat = f"gate:{gate}"
                retry = sum(1 for s in spans if s["category"] == cat and s["change"] == change)
                spans.append({
                    "category": cat,
                    "change": change,
                    "start": start_ev["start"],
                    "end": ts,
                    "duration_ms": _ts_diff_ms(start_ev["start"], ts),
                    "result": "fail" if result in ("fail", "failed", "critical") else result,
                    "retry": retry,
                })
            else:
                # No matching GATE_START (verifier.py doesn't emit them) —
                # create a span only if we have actual timing data
                gate_ms_key = f"gate_{gate}_ms"
                duration = data.get(gate_ms_key, 0) or data.get("elapsed_ms", 0)
                if gate != "unknown" and duration:
                    cat = f"gate:{gate}"
                    retry = sum(1 for s in spans if s["category"] == cat and s["change"] == change)
                    spans.append({
                        "category": cat,
                        "change": change,
                        "start": ts,
                        "end": ts,
                        "duration_ms": int(duration),
                        "result": "fail" if result in ("fail", "failed", "critical") else result,
                        "retry": retry,
                    })

        # ── Step spans (implementing, planning, fixing) ──
        elif etype == "STEP_TRANSITION":
            # Mark that this change has STEP_TRANSITION events — the DISPATCH
            # fallback implementing spans for this change will be filtered out
            # after the walk, because STEP_TRANSITION gives finer granularity.
            if change:
                step_transition_seen.add(change)
            new_step = data.get("to", "")
            # Close previous step span for this change
            if change in open_steps:
                prev = open_steps.pop(change)
                spans.append({
                    "category": prev["step"],
                    "change": change,
                    "start": prev["start"],
                    "end": ts,
                    "duration_ms": _ts_diff_ms(prev["start"], ts),
                })
            # Open new step span if it's a tracked category
            if new_step in ("implementing", "planning", "fixing"):
                open_steps[change] = {"start": ts, "step": new_step}

        # ── Pre-dispatch planning phase ──
        # DIGEST_STARTED marks the start of the digest/decomposition pipeline.
        # The phase ends at the first DISPATCH event (handled below).
        elif etype == "DIGEST_STARTED":
            if planning_start_ts is None:
                planning_start_ts = ts

        # ── DISPATCH-based implementing fallback ──
        # The agent runs as a separate `claude -p` process in its worktree and
        # does NOT emit LLM_CALL events. Fallback: treat DISPATCH → {next DISPATCH
        # | MERGE_START | state failed/pending | end-of-stream} as an
        # implementing span. We deliberately do NOT close on CHANGE_DONE,
        # because a single dispatch can produce multiple CHANGE_DONE events as
        # the verifier loops (review → redispatch agent → review again).
        # STEP_TRANSITION takes precedence when present (filtered at end).
        # CHANGE_REDISPATCH is treated identically to DISPATCH — the agent
        # is being woken up to retry after a failure.
        elif etype in ("DISPATCH", "CHANGE_REDISPATCH"):
            # Emit the planning span on the very first DISPATCH (only once).
            if not planning_emitted and planning_start_ts is not None:
                spans.append({
                    "category": "planning",
                    "change": "",
                    "start": planning_start_ts,
                    "end": ts,
                    "duration_ms": _ts_diff_ms(planning_start_ts, ts),
                    "detail": {"source": "digest-to-dispatch"},
                })
                planning_emitted = True
            if change:
                # Close any already-open implementing span for this change
                # (redispatch case — the previous session ended when this one started).
                if change in open_implementing:
                    _close_implementing(change, ts)
                open_implementing[change] = {"start": ts}

        # ── Merge spans ──
        elif etype == "MERGE_START":
            open_merges[change] = {"start": ts}
            # Agent work is considered done once the merge pipeline starts.
            if change:
                _close_implementing(change, ts)

        elif etype == "MERGE_COMPLETE":
            if change in open_merges:
                start_ev = open_merges.pop(change)
                spans.append({
                    "category": "merge",
                    "change": change,
                    "start": start_ev["start"],
                    "end": ts,
                    "duration_ms": _ts_diff_ms(start_ev["start"], ts),
                    "result": data.get("result", "success"),
                })

        # ── Idle spans ──
        elif etype == "IDLE_START":
            if not open_idle:
                open_idle = {"start": ts, "watched": data.get("watched_changes", [])}

        elif etype == "IDLE_END":
            if open_idle:
                spans.append({
                    "category": "idle",
                    "change": "",
                    "start": open_idle["start"],
                    "end": ts,
                    "duration_ms": _ts_diff_ms(open_idle["start"], ts),
                })
                open_idle = None

        # ── Manual stop/resume spans ──
        elif etype == "MANUAL_STOP":
            open_manual[change] = {"start": ts}

        elif etype == "MANUAL_RESUME":
            if change in open_manual:
                start_ev = open_manual.pop(change)
                spans.append({
                    "category": "manual-wait",
                    "change": change,
                    "start": start_ev["start"],
                    "end": ts,
                    "duration_ms": _ts_diff_ms(start_ev["start"], ts),
                })

        # ── Dep-blocked spans ──
        elif etype == "STATE_CHANGE":
            new_status = data.get("to", "")
            old_status = data.get("from", "")
            if new_status == "dep-blocked":
                open_dep[change] = {"start": ts}
            elif old_status == "dep-blocked" and change in open_dep:
                start_ev = open_dep.pop(change)
                spans.append({
                    "category": "dep-wait",
                    "change": change,
                    "start": start_ev["start"],
                    "end": ts,
                    "duration_ms": _ts_diff_ms(start_ev["start"], ts),
                })
            # Failure / abort transitions close any open implementing span.
            if new_status in ("failed", "pending") and change:
                _close_implementing(change, ts)

        # ── Watchdog escalation / stall-recovery ──
        elif etype == "WATCHDOG_ESCALATION":
            action = data.get("action", "")
            if action in ("restart", "redispatch", "fail"):
                open_stall[change] = {"start": ts, "action": action}

        elif etype == "CHANGE_RECOVERED" or (etype == "STATE_CHANGE" and data.get("to") == "running"):
            if change in open_stall:
                start_ev = open_stall.pop(change)
                spans.append({
                    "category": "stall-recovery",
                    "change": change,
                    "start": start_ev["start"],
                    "end": ts,
                    "duration_ms": _ts_diff_ms(start_ev["start"], ts),
                    "detail": {"action": start_ev.get("action", "")},
                })

        # ── Sentinel events (crash → restart) ──
        elif source == "sentinel":
            sentinel_type = data.get("type") or etype
            if sentinel_type == "crash":
                open_stall.setdefault("__sentinel__", {"start": ts, "action": "crash"})
            elif sentinel_type == "restart":
                if "__sentinel__" in open_stall:
                    start_ev = open_stall.pop("__sentinel__")
                    spans.append({
                        "category": "stall-recovery",
                        "change": "",
                        "start": start_ev["start"],
                        "end": ts,
                        "duration_ms": _ts_diff_ms(start_ev["start"], ts),
                        "detail": {"action": "sentinel-restart"},
                    })

        # ── Conflict resolution ──
        elif etype == "CONFLICT_RESOLUTION_START":
            open_stall[f"conflict:{change}"] = {"start": ts, "action": "conflict"}

        elif etype == "CONFLICT_RESOLUTION_END":
            ckey = f"conflict:{change}"
            if ckey in open_stall:
                start_ev = open_stall.pop(ckey)
                spans.append({
                    "category": "merge",
                    "change": change,
                    "start": start_ev["start"],
                    "end": ts,
                    "duration_ms": data.get("duration_ms", _ts_diff_ms(start_ev["start"], ts)),
                    "detail": {"sub": "conflict-resolution", "result": data.get("result", "")},
                })

    # Close any open spans at end of time range or last event
    end_ts = to_ts or (events[-1].get("ts", "") if events else "")
    if end_ts:
        for change, step_data in open_steps.items():
            spans.append({
                "category": step_data["step"],
                "change": change,
                "start": step_data["start"],
                "end": end_ts,
                "duration_ms": _ts_diff_ms(step_data["start"], end_ts),
                "open": True,
            })
        if open_idle:
            spans.append({
                "category": "idle",
                "change": "",
                "start": open_idle["start"],
                "end": end_ts,
                "duration_ms": _ts_diff_ms(open_idle["start"], end_ts),
                "open": True,
            })
        for change, start_ev in open_manual.items():
            spans.append({
                "category": "manual-wait",
                "change": change,
                "start": start_ev["start"],
                "end": end_ts,
                "duration_ms": _ts_diff_ms(start_ev["start"], end_ts),
                "open": True,
            })
        for change, start_ev in open_dep.items():
            spans.append({
                "category": "dep-wait",
                "change": change,
                "start": start_ev["start"],
                "end": end_ts,
                "duration_ms": _ts_diff_ms(start_ev["start"], end_ts),
                "open": True,
            })
        # Drop unclosed gate spans — a GATE_START without GATE_PASS is an
        # instrumentation gap (missing GATE_PASS), not a gate that's actually
        # still running. Flushing them to end_ts creates artificially huge spans.
        # (Future runs will have proper GATE_PASS events.)
        # Flush unclosed merge spans
        for change, start_ev in open_merges.items():
            spans.append({
                "category": "merge",
                "change": change,
                "start": start_ev["start"],
                "end": end_ts,
                "duration_ms": _ts_diff_ms(start_ev["start"], end_ts),
                "open": True,
            })
        # Flush unclosed stall-recovery spans
        for key, start_ev in open_stall.items():
            change = key if not key.startswith("conflict:") and key != "__sentinel__" else ""
            spans.append({
                "category": "stall-recovery",
                "change": change,
                "start": start_ev["start"],
                "end": end_ts,
                "duration_ms": _ts_diff_ms(start_ev["start"], end_ts),
                "open": True,
            })
        # Flush unclosed DISPATCH-based implementing spans.
        #
        # Close-at logic:
        #   1. If the change is CURRENTLY ACTIVE (running/integrating/verifying/
        #      dispatched/implementing) in the live state file, close at end_ts
        #      (~now). The change is still doing work but the agent doesn't emit
        #      LLM_CALL events to the orchestrator event bus, so we have no
        #      newer event to anchor on — the span should extend to the present.
        #   2. Otherwise, close at the last event observed for that change.
        #      Failed/abandoned changes often have no terminal STATE_CHANGE
        #      event (the state file is updated without emitting), so flushing
        #      to end-of-stream would produce wildly inflated spans for those.
        active_change_set = active_changes or set()
        for ch_name, impl in list(open_implementing.items()):
            if ch_name in active_change_set:
                # Live change → extend to ~now (end_ts is the latest event or
                # the user's `to` query param). This matches the user's
                # intuition that an actively-running change should have its
                # implementing bar growing on the timeline.
                close_ts = end_ts
            else:
                close_ts = last_event_ts_per_change.get(ch_name, end_ts)
                # Guard: if last event is earlier than the span's start
                # (shouldn't happen, but defensive), fall back to end_ts.
                if _ts_diff_ms(impl["start"], close_ts) <= 0:
                    close_ts = end_ts
            spans.append({
                "category": "implementing",
                "change": ch_name,
                "start": impl["start"],
                "end": close_ts,
                "duration_ms": _ts_diff_ms(impl["start"], close_ts),
                "detail": {"source": "dispatch-fallback"},
                "open": True,
            })
        open_implementing.clear()

    # STEP_TRANSITION precedence: drop dispatch-fallback implementing spans
    # for any change where a STEP_TRANSITION was observed — the regular
    # open_steps code path already produced higher-granularity spans for them.
    if step_transition_seen:
        spans = [
            s for s in spans
            if not (
                s.get("category") == "implementing"
                and s.get("change") in step_transition_seen
                and isinstance(s.get("detail"), dict)
                and s["detail"].get("source") == "dispatch-fallback"
            )
        ]

    # Detect idle gaps from event gaps (>60s with no events for any change)
    _detect_idle_gaps(events, spans, from_ts, to_ts)

    # Clip spans to time range
    if from_ts or to_ts:
        spans = _clip_spans(spans, from_ts, to_ts)

    # Sort by start time
    spans.sort(key=lambda s: s.get("start", ""))
    return spans


def _detect_idle_gaps(
    events: list[dict],
    spans: list[dict],
    from_ts: str | None,
    to_ts: str | None,
) -> None:
    """Detect idle periods as time intervals not covered by ANY non-idle span.

    Algorithm:
        1. Take the orchestration event time range as the walk bounds
           (sentinel/heartbeat events excluded, they don't imply activity).
        2. Build the union of all non-idle spans' intervals (merge overlapping).
        3. Walk complementary gaps between merged intervals, clamped to the
           walk bounds; emit `idle` span for any complementary interval > 60s.

    This is correct under partial overlap, where the old strict-containment
    check produced false-idle spans.
    """
    idle_threshold_ms = 60 * 1000

    activity_events = [
        e for e in events
        if e.get("type", "") not in ("WATCHDOG_HEARTBEAT", "MONITOR_HEARTBEAT", "IDLE_START", "IDLE_END")
        and e.get("_source") != "sentinel"
    ]
    if len(activity_events) < 2:
        return

    range_start_ms = _ts_to_ms(activity_events[0].get("ts", ""))
    range_end_ms = _ts_to_ms(activity_events[-1].get("ts", ""))
    if range_end_ms <= range_start_ms:
        return

    # 1. Build list of non-idle span intervals, clamped to the walk range.
    intervals: list[tuple[int, int]] = []
    for s in spans:
        if s.get("category") == "idle":
            continue
        start = s.get("start")
        end = s.get("end")
        if not start or not end:
            continue
        s_start = _ts_to_ms(start)
        s_end = _ts_to_ms(end)
        if s_end <= s_start:
            continue
        # Clamp to walk range
        s_start = max(s_start, range_start_ms)
        s_end = min(s_end, range_end_ms)
        if s_end > s_start:
            intervals.append((s_start, s_end))

    # 2. Sort and merge overlapping/adjacent intervals.
    intervals.sort()
    merged: list[list[int]] = []
    for s_start, s_end in intervals:
        if merged and s_start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], s_end)
        else:
            merged.append([s_start, s_end])

    # 3. Walk complementary gaps.
    emitted_count = 0
    emitted_total_ms = 0
    cursor = range_start_ms
    for seg_start, seg_end in merged:
        if seg_start > cursor:
            gap = seg_start - cursor
            if gap > idle_threshold_ms:
                spans.append({
                    "category": "idle",
                    "change": "",
                    "start": _ts_shift_ms(activity_events[0].get("ts", ""), cursor - range_start_ms),
                    "end": _ts_shift_ms(activity_events[0].get("ts", ""), seg_start - range_start_ms),
                    "duration_ms": gap,
                    "detail": {"source": "gap-detection"},
                })
                emitted_count += 1
                emitted_total_ms += gap
        if seg_end > cursor:
            cursor = seg_end
        if cursor >= range_end_ms:
            break

    # Trailing gap from last segment to range_end_ms
    if cursor < range_end_ms:
        gap = range_end_ms - cursor
        if gap > idle_threshold_ms:
            spans.append({
                "category": "idle",
                "change": "",
                "start": _ts_shift_ms(activity_events[0].get("ts", ""), cursor - range_start_ms),
                "end": activity_events[-1].get("ts", ""),
                "duration_ms": gap,
                "detail": {"source": "gap-detection"},
            })
            emitted_count += 1
            emitted_total_ms += gap

    logger.debug(
        "idle gap detection: %d non-idle intervals → %d merged → %d idle gaps emitted (%d ms total)",
        len(intervals), len(merged), emitted_count, emitted_total_ms,
    )


def _clip_spans(spans: list[dict], from_ts: str | None, to_ts: str | None) -> list[dict]:
    """Clip spans to the requested time range."""
    result = []
    for s in spans:
        start = s.get("start", "")
        end = s.get("end", "")
        if to_ts and start > to_ts:
            continue
        if from_ts and end < from_ts:
            continue
        clipped = dict(s)
        if from_ts and start < from_ts:
            clipped["start"] = from_ts
            clipped["duration_ms"] = _ts_diff_ms(from_ts, end)
        if to_ts and end > to_ts:
            clipped["end"] = to_ts
            clipped["duration_ms"] = _ts_diff_ms(clipped["start"], to_ts)
        result.append(clipped)
    return result


# ─── Breakdown computation ──────────────────────────────────────────


def _compute_breakdown(spans: list[dict]) -> tuple[int, int, float, list[dict]]:
    """Compute per-category breakdown from spans.

    Returns (wall_time_ms, activity_time_ms, parallel_efficiency, breakdown_list).
    """
    if not spans:
        return 0, 0, 0.0, []

    # Wall time = first start to last end
    starts = [s["start"] for s in spans if s.get("start")]
    ends = [s["end"] for s in spans if s.get("end")]
    if not starts or not ends:
        return 0, 0, 0.0, []

    wall_time_ms = _ts_diff_ms(min(starts), max(ends))

    # Activity time = sum of all span durations
    activity_time_ms = sum(s.get("duration_ms", 0) for s in spans)

    # Parallel efficiency
    parallel_efficiency = round(activity_time_ms / wall_time_ms, 2) if wall_time_ms > 0 else 0.0

    # Per-category aggregation
    cat_totals: dict[str, int] = {}
    for s in spans:
        cat = s.get("category", "unknown")
        cat_totals[cat] = cat_totals.get(cat, 0) + s.get("duration_ms", 0)

    # Sort by total time descending
    breakdown = []
    for cat in sorted(cat_totals, key=lambda c: cat_totals[c], reverse=True):
        total_ms = cat_totals[cat]
        pct = round(total_ms / activity_time_ms * 100, 1) if activity_time_ms > 0 else 0
        breakdown.append({
            "category": cat,
            "total_ms": total_ms,
            "pct": pct,
        })

    return wall_time_ms, activity_time_ms, parallel_efficiency, breakdown


# ─── Timestamp helpers ──────────────────────────────────────────────


def _ts_diff_ms(ts1: str, ts2: str) -> int:
    """Compute millisecond difference between two ISO 8601 timestamps."""
    try:
        dt1 = datetime.fromisoformat(ts1.replace("Z", "+00:00"))
        dt2 = datetime.fromisoformat(ts2.replace("Z", "+00:00"))
        return max(0, int((dt2 - dt1).total_seconds() * 1000))
    except (ValueError, AttributeError):
        return 0


def _ts_shift_ms(ts: str, delta_ms: int) -> str:
    """Return a new ISO 8601 timestamp shifted by `delta_ms` (can be negative)."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        shifted = dt + timedelta(milliseconds=delta_ms)
        # Preserve the Z-suffix convention if input had it; otherwise emit offset form.
        iso = shifted.isoformat()
        return iso
    except (ValueError, AttributeError):
        return ts


def _ts_to_ms(ts: str) -> int:
    """Convert an ISO 8601 timestamp to epoch milliseconds; 0 on failure."""
    try:
        return int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)
    except (ValueError, AttributeError):
        return 0


# ─── API endpoint ───────────────────────────────────────────────────


@router.get("/api/{project}/activity-timeline")
def get_activity_timeline(
    project: str,
    from_ts: Optional[str] = Query(None, alias="from"),
    to_ts: Optional[str] = Query(None, alias="to"),
):
    """Get activity timeline with spans and breakdown for a project."""
    project_path = _resolve_project(project)

    # Load events from all sources
    events = _load_events(project_path, from_ts, to_ts)
    if not events:
        return {
            "wall_time_ms": 0,
            "activity_time_ms": 0,
            "parallel_efficiency": 0,
            "spans": [],
            "breakdown": [],
        }

    # Load current state to identify live-active changes. Open implementing
    # spans for these changes extend to ~now instead of the last observed
    # event (which can be stale by many minutes while the agent is actively
    # working but not emitting orchestration events).
    active_changes: set[str] = set()
    try:
        from ..state import load_state
        state_path = _state_path(project_path)
        if state_path.exists():
            state = load_state(str(state_path))
            _ACTIVE_STATUSES = {
                "running", "implementing", "verifying",
                "integrating", "dispatched", "planning", "fixing",
            }
            for c in state.changes:
                if c.status in _ACTIVE_STATUSES:
                    active_changes.add(c.name)
    except Exception:  # noqa: BLE001
        logger.debug("active_changes load failed (non-fatal)", exc_info=True)

    # Build spans from events
    spans = _build_spans(events, from_ts, to_ts, active_changes=active_changes)

    # Enrich implementing spans with per-span aggregates (llm calls, tool calls,
    # subagent count) from the drilldown sub-span data. Without this the
    # frontend renders a plain "implementing" bar for currently-running changes,
    # making it look like nothing is happening even when the agent is actively
    # calling tools. With this enrichment, each implementing span carries
    # detail.llm_calls / detail.tool_calls / detail.subagent_count that the
    # frontend can display inline (e.g., "implementing · 37 LLM · 24 tools").
    #
    # Perf: _build_sub_spans_for_change is cached per-change, so the sub-spans
    # are loaded at most once per change regardless of how many implementing
    # spans that change has. The in-memory filter + aggregate on each span is
    # O(sub_spans).
    try:
        from .activity_detail import (
            _build_sub_spans_for_change,
            _clip_and_filter,
            _compute_aggregates,
        )

        sub_span_cache: dict[str, list[dict]] = {}
        for span in spans:
            if span.get("category") != "implementing":
                continue
            change_name = span.get("change", "")
            if not change_name:
                continue
            if change_name not in sub_span_cache:
                try:
                    loaded, _hit = _build_sub_spans_for_change(project_path, change_name)
                    sub_span_cache[change_name] = loaded
                except Exception:  # noqa: BLE001
                    logger.debug(
                        "sub-span enrichment failed for %s",
                        change_name,
                        exc_info=True,
                    )
                    sub_span_cache[change_name] = []
            sub_spans = sub_span_cache[change_name]
            if not sub_spans:
                continue
            window = _clip_and_filter(
                sub_spans, span.get("start"), span.get("end")
            )
            if not window:
                continue
            agg = _compute_aggregates(window)
            detail = span.get("detail") or {}
            if not isinstance(detail, dict):
                detail = {}
            detail["llm_calls"] = agg["total_llm_calls"]
            detail["tool_calls"] = agg["total_tool_calls"]
            detail["subagent_count"] = agg["subagent_count"]
            span["detail"] = detail
    except Exception:  # noqa: BLE001
        logger.debug("implementing-span enrichment pass failed", exc_info=True)

    # Compute breakdown
    wall_time_ms, activity_time_ms, parallel_efficiency, breakdown = _compute_breakdown(spans)

    # Clean internal fields from span output
    clean_spans = []
    for s in spans:
        cs = {k: v for k, v in s.items() if not k.startswith("_")}
        cs.pop("open", None)
        clean_spans.append(cs)

    return {
        "wall_time_ms": wall_time_ms,
        "activity_time_ms": activity_time_ms,
        "parallel_efficiency": parallel_efficiency,
        "spans": clean_spans,
        "breakdown": breakdown,
    }
