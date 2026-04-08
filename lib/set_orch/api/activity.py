"""Activity timeline API — time-based activity breakdown from orchestration events.

Reconstructs typed activity spans from event sources (orchestration-events JSONL,
sentinel events, loop-state files) and returns a structured timeline with breakdown.
"""

from __future__ import annotations

import glob as _glob
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

from .helpers import _resolve_project, _state_path, _sentinel_dir

logger = logging.getLogger(__name__)
router = APIRouter()

# ─── Activity categories ────────────────────────────────────────────

CATEGORY_ORDER = [
    "planning", "implementing", "fixing",
    "gate:build", "gate:test", "gate:review", "gate:verify",
    "gate:e2e", "gate:e2e-smoke", "gate:smoke",
    "gate:scope-check", "gate:rules", "gate:dep-install",
    "merge", "idle", "stall-recovery", "dep-wait", "manual-wait", "sentinel",
]


# ─── Event loading ──────────────────────────────────────────────────


def _load_events(project_path: Path, from_ts: str | None, to_ts: str | None) -> list[dict]:
    """Load and merge events from orchestration and sentinel JSONL files."""
    events: list[dict] = []

    # 1. Orchestration events
    for base_dir in [project_path, project_path / "set" / "orchestration"]:
        for name in ["orchestration-events.jsonl", "orchestration-state-events.jsonl"]:
            candidate = base_dir / name
            if candidate.exists():
                _read_jsonl(candidate, events, from_ts, to_ts)
                stem = name.replace(".jsonl", "")
                for archive in sorted(_glob.glob(str(base_dir / f"{stem}-*.jsonl"))):
                    _read_jsonl(Path(archive), events, from_ts, to_ts)

    # 2. Sentinel events
    sentinel_dir = _sentinel_dir(project_path)
    sentinel_events_file = sentinel_dir / "events.jsonl"
    if sentinel_events_file.exists():
        _read_jsonl(sentinel_events_file, events, from_ts, to_ts, source="sentinel")

    # Sort by timestamp
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


def _build_spans(events: list[dict], from_ts: str | None, to_ts: str | None) -> list[dict]:
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

    for ev in events:
        etype = ev.get("type", "")
        change = ev.get("change", "")
        ts = ev.get("ts", "")
        data = ev.get("data", {})
        source = ev.get("_source", "orchestration")

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
                # create a point span from per-gate timing if available
                gate_ms_key = f"gate_{gate}_ms"
                duration = data.get(gate_ms_key, 0) or data.get("elapsed_ms", 0)
                if gate != "unknown":
                    cat = f"gate:{gate}"
                    retry = sum(1 for s in spans if s["category"] == cat and s["change"] == change)
                    spans.append({
                        "category": cat,
                        "change": change,
                        "start": ts,
                        "end": ts,
                        "duration_ms": int(duration) if duration else 0,
                        "result": "fail" if result in ("fail", "failed", "critical") else result,
                        "retry": retry,
                    })

        # ── Step spans (implementing, planning, fixing) ──
        elif etype == "STEP_TRANSITION":
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

        # ── Merge spans ──
        elif etype == "MERGE_START":
            open_merges[change] = {"start": ts}

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
        # Flush unclosed gate spans
        for (change, gate), start_ev in open_gates.items():
            spans.append({
                "category": f"gate:{gate}",
                "change": change,
                "start": start_ev["start"],
                "end": end_ts,
                "duration_ms": _ts_diff_ms(start_ev["start"], end_ts),
                "open": True,
            })
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
    """Detect idle periods from gaps between events where no spans exist."""
    # Build a set of seconds that are covered by existing spans
    # Use simple approach: check for gaps > 60s in the event stream
    idle_threshold = 60  # seconds

    activity_events = [
        e for e in events
        if e.get("type", "") not in ("WATCHDOG_HEARTBEAT", "MONITOR_HEARTBEAT", "IDLE_START", "IDLE_END")
        and e.get("_source") != "sentinel"
    ]

    if len(activity_events) < 2:
        return

    # Build a list of covered time ranges from existing spans to avoid double-counting
    existing_ranges: list[tuple[int, int]] = []
    for s in spans:
        if s.get("start") and s.get("end"):
            try:
                s_start = int(datetime.fromisoformat(s["start"].replace("Z", "+00:00")).timestamp() * 1000)
                s_end = int(datetime.fromisoformat(s["end"].replace("Z", "+00:00")).timestamp() * 1000)
                existing_ranges.append((s_start, s_end))
            except (ValueError, AttributeError):
                pass

    def _is_covered(gap_start_ms: int, gap_end_ms: int) -> bool:
        """Check if a gap is already covered by existing spans."""
        for rs, re in existing_ranges:
            if rs <= gap_start_ms and re >= gap_end_ms:
                return True
        return False

    for i in range(len(activity_events) - 1):
        ts1 = activity_events[i].get("ts", "")
        ts2 = activity_events[i + 1].get("ts", "")
        gap_ms = _ts_diff_ms(ts1, ts2)
        if gap_ms > idle_threshold * 1000:
            try:
                g_start = int(datetime.fromisoformat(ts1.replace("Z", "+00:00")).timestamp() * 1000)
                g_end = int(datetime.fromisoformat(ts2.replace("Z", "+00:00")).timestamp() * 1000)
            except (ValueError, AttributeError):
                continue
            if not _is_covered(g_start, g_end):
                spans.append({
                    "category": "idle",
                    "change": "",
                    "start": ts1,
                    "end": ts2,
                    "duration_ms": gap_ms,
                    "detail": {"source": "gap-detection"},
                })


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

    # Build spans from events
    spans = _build_spans(events, from_ts, to_ts)

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
