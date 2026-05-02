"""Activity timeline API — time-based activity breakdown from orchestration events.

Reconstructs typed activity spans from event sources (orchestration-events JSONL,
sentinel events, loop-state files) and returns a structured timeline with breakdown.
"""

from __future__ import annotations

import glob as _glob
import json
import logging
import os
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
    # Per-iteration Claude session markers (zero-width spans) — show where a
    # new agent process was launched and whether it `--resume`d the prior
    # session ("agent:session-resume", warm cache) or started fresh
    # ("agent:session-fresh", new context window).
    "agent:session-fresh", "agent:session-resume",
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


def _collect_session_boundaries(project_path: Path) -> list[dict]:
    """Section 8.1: return one boundary record per sentinel session transition.

    Reads CYCLE_HEADER lines from rotated event files in cycle order and
    emits a record whenever `sentinel_session_id` differs from the
    previous header's id.  Returns at most `(N_sessions - 1)` markers per
    AC-19; the very first session boundary (project start) is omitted.
    """
    boundaries: list[dict] = []
    last_session: Optional[str] = None
    for base_dir in [project_path, project_path / "set" / "orchestration"]:
        for stem in ("orchestration-events", "orchestration-state-events"):
            cycle_pattern = str(base_dir / f"{stem}-cycle*.jsonl")
            for path in sorted(_glob.glob(cycle_pattern), key=_cycle_sort_key):
                try:
                    with open(path, encoding="utf-8") as fh:
                        first = fh.readline().strip()
                except OSError:
                    continue
                if not first:
                    continue
                try:
                    header = json.loads(first)
                except json.JSONDecodeError:
                    continue
                if header.get("type") != "CYCLE_HEADER":
                    continue
                sid = header.get("sentinel_session_id")
                if sid is None or sid == last_session:
                    continue
                if last_session is not None:
                    boundaries.append({
                        "ts": header.get("ts", ""),
                        "session_id": sid,
                        "session_started_at": header.get("ts", ""),
                        "spec_lineage_id": header.get("spec_lineage_id"),
                    })
                last_session = sid
    return boundaries


def _load_events(project_path: Path, from_ts: str | None, to_ts: str | None) -> list[dict]:
    """Load and merge events from orchestration and sentinel JSONL files.

    Section 4.1 of run-history-and-phase-continuity: rotated cycle files
    (`orchestration-events-cycle*.jsonl`, `orchestration-state-events-cycle*.jsonl`)
    are read in cycle-ascending order BEFORE the live file so the timeline
    contains the full project history, not just the current cycle.
    CYCLE_HEADER lines are skipped — they are metadata, not events.
    """
    events: list[dict] = []

    # 1. Orchestration events — cycle files first (by numeric cycle), then live.
    # Source of truth is LineagePaths.  We enumerate both the live events and
    # the state events streams plus every rotated cycle sibling.  Legacy
    # project-local layouts are still read for backward compat during
    # Section 15b migration — each literal is derived from a resolver
    # basename so the audit passes.
    from ..paths import LineagePaths as _LP_evt
    _lp_evt = _LP_evt(str(project_path))
    _live_events_base = os.path.basename(_lp_evt.events_file)
    _live_state_events_base = os.path.basename(_lp_evt.state_events_file)

    # Resolver-canonical location
    for live_file, rotated_list in [
        (_lp_evt.events_file, _lp_evt.rotated_event_files),
        (_lp_evt.state_events_file, _lp_evt.rotated_state_event_files),
    ]:
        for archive in rotated_list:
            _read_jsonl(Path(archive), events, from_ts, to_ts)
        live = Path(live_file)
        if live.exists():
            _read_jsonl(live, events, from_ts, to_ts)

    # Legacy project-local fallback (project root + project/set/orchestration/).
    for base_dir in [project_path, project_path / "set" / "orchestration"]:
        for name in [_live_events_base, _live_state_events_base]:
            stem = name.rsplit(".", 1)[0]
            cycle_pattern = str(base_dir / f"{stem}-cycle*.jsonl")
            for archive in sorted(_glob.glob(cycle_pattern), key=_cycle_sort_key):
                _read_jsonl(Path(archive), events, from_ts, to_ts)
            other_pattern = str(base_dir / f"{stem}-*.jsonl")
            for archive in sorted(_glob.glob(other_pattern)):
                if "-cycle" in archive:
                    continue
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
    # Gates already closed via an explicit GATE_PASS — used to suppress
    # duplicate spans from a subsequent VERIFY_GATE event covering the same
    # gate run.  key = (change, gate_name).
    finalized_gates: set[tuple[str, str]] = set()
    # Iteration markers already emitted this walk — `_poll_iteration_events`
    # may re-emit ITERATION_END after orchestrator crash-restart (the
    # `last_emitted_iter` field is persisted only AFTER all events for the
    # tick are written, so a crash in between leaves it unupdated).
    # Dedup on `(change, iteration)`. Key uses int iteration; `None` from a
    # malformed event maps to a single sentinel so we still suppress
    # repeated unscoped emissions.
    seen_iterations: set[tuple[str, int]] = set()
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

        # SUPERVISOR_START marks the boundary between sentinel sessions —
        # every new `set-supervisor` spawn appends one to the shared events
        # stream.  Reset the planning span state so the next session's
        # DIGEST_STARTED → DISPATCH pair emits its own planning span
        # instead of being swallowed by the first session's `planning_emitted`.
        if etype == "SUPERVISOR_START":
            planning_start_ts = None
            planning_emitted = False

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
                finalized_gates.add(key)

        elif etype == "VERIFY_GATE":
            # The verifier emits a single VERIFY_GATE event per pipeline run
            # carrying:
            #   • per-gate timings in `gate_ms` (insertion-ordered by
            #     execution order — Python 3.7+ dict semantics)
            #   • per-gate verdicts as top-level fields, e.g.
            #     `"build": "pass", "test": "pass", "e2e": "fail"`
            #   • the gate that stopped the pipeline as `stop_gate`
            # We reconstruct one span per gate, laid out back-to-back so they
            # end at the VERIFY_GATE timestamp. Gates already opened by an
            # explicit `GATE_START` are skipped (closed below).
            stop_gate_raw = str(data.get("stop_gate") or data.get("gate") or "")
            stop_gate = stop_gate_raw.replace("_", "-") if stop_gate_raw else ""
            overall_result = data.get("result", "unknown")
            gate_ms_map = data.get("gate_ms") or {}

            def _norm_verdict(raw: object, fallback: str = "unknown") -> str:
                v = str(raw) if raw is not None else fallback
                return "fail" if v in ("fail", "failed", "critical") else v

            # (gate_name, duration_ms, verdict) tuples in execution order.
            timings: list[tuple[str, int, str]] = []
            seen: set[str] = set()
            for raw_name, dur in gate_ms_map.items():
                try:
                    dur_int = int(dur) if dur else 0
                except (TypeError, ValueError):
                    dur_int = 0
                norm = str(raw_name).replace("_", "-")
                verdict_raw = (
                    data.get(raw_name)
                    if data.get(raw_name) is not None
                    else data.get(norm)
                )
                timings.append((norm, dur_int, _norm_verdict(verdict_raw)))
                seen.add(norm)

            # The stop_gate often has no entry in `gate_ms` (e.g. the
            # verifier filters out zero-duration results, or the gate was
            # cached and short-circuited). Synthesize a small span so the
            # failing gate is visible on the timeline.
            if stop_gate and stop_gate not in seen:
                verdict_raw = (
                    data.get(stop_gate_raw)
                    if data.get(stop_gate_raw) is not None
                    else data.get(stop_gate)
                )
                timings.append((stop_gate, 1000, _norm_verdict(verdict_raw, overall_result)))

            # Lay out back-to-back ending at `ts`.
            total_ms = sum(d for _, d, _ in timings)
            cursor_start_ts = _ts_shift_ms(ts, -total_ms) if total_ms > 0 else ts
            for gname, dur_int, verdict in timings:
                cat = f"gate:{gname}"
                # If a GATE_START for this gate is still open, defer to the
                # explicit-pair handling below — emit nothing here.
                if (change, gname) in open_gates:
                    cursor_start_ts = _ts_shift_ms(cursor_start_ts, dur_int)
                    continue
                # If a GATE_PASS already closed this gate (same pipeline
                # run), suppress the duplicate from VERIFY_GATE.
                if (change, gname) in finalized_gates:
                    cursor_start_ts = _ts_shift_ms(cursor_start_ts, dur_int)
                    continue
                if dur_int <= 0:
                    cursor_start_ts = _ts_shift_ms(cursor_start_ts, dur_int)
                    continue
                end_ts_g = _ts_shift_ms(cursor_start_ts, dur_int)
                retry = sum(
                    1 for s in spans
                    if s.get("category") == cat and s.get("change") == change
                )
                spans.append({
                    "category": cat,
                    "change": change,
                    "start": cursor_start_ts,
                    "end": end_ts_g,
                    "duration_ms": dur_int,
                    "result": verdict,
                    "retry": retry,
                })
                cursor_start_ts = end_ts_g

            # Close any explicit GATE_START that pairs with the stop_gate.
            if stop_gate and (change, stop_gate) in open_gates:
                start_ev = open_gates.pop((change, stop_gate))
                cat = f"gate:{stop_gate}"
                verdict_raw = (
                    data.get(stop_gate_raw)
                    if data.get(stop_gate_raw) is not None
                    else data.get(stop_gate)
                )
                retry = sum(
                    1 for s in spans
                    if s.get("category") == cat and s.get("change") == change
                )
                spans.append({
                    "category": cat,
                    "change": change,
                    "start": start_ev["start"],
                    "end": ts,
                    "duration_ms": _ts_diff_ms(start_ev["start"], ts),
                    "result": _norm_verdict(verdict_raw, overall_result),
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

        # ── Agent session markers ──
        # AGENT_SESSION_DECISION is emitted by the orchestrator when it
        # decides whether to `claude --resume <sid>` or start fresh for a
        # change. We render it as a zero-width marker on the timeline so
        # the operator can see WHERE the agent was relaunched and WHY a
        # fresh session was forced (resume_skip_reason). This is the
        # orchestrator's *intent*; the bash loop's actual session_id may
        # still differ if context_too_large triggers fresh mid-loop.
        elif etype == "AGENT_SESSION_DECISION":
            # Skip events that didn't carry a change name — the marker would
            # land on an unscoped lane and confuse the timeline.
            if not change:
                continue
            mode = str(data.get("session_mode") or "").strip()
            if mode in ("fresh", "resume"):
                cat = f"agent:session-{mode}"
                detail = {
                    "source": "orchestrator-decision",
                    "resume_skip_reason": data.get("resume_skip_reason"),
                    "prior_session_id": data.get("prior_session_id"),
                    "session_age_min": data.get("session_age_min"),
                    "is_merge_retry": data.get("is_merge_retry"),
                    "is_poisoned_stall_recovery": data.get(
                        "is_poisoned_stall_recovery"
                    ),
                }
                # Strip absent values and empty strings only. `False` and
                # `0` survive (Python: `False != ""` is True) so boolean
                # flags like `is_merge_retry=False` remain visible in the
                # tooltip.
                detail = {k: v for k, v in detail.items() if v is not None and v != ""}
                spans.append({
                    "category": cat,
                    "change": change,
                    "start": ts,
                    "end": ts,
                    "duration_ms": 0,
                    "detail": detail,
                })

        # ITERATION_END is emitted by `_poll_iteration_events` when the
        # bash ralph loop appends a new entry to `loop-state.json`. This
        # is the *ground truth* session marker — `entry.resumed` reflects
        # what `claude` actually did (--resume vs fresh) regardless of
        # what the orchestrator decided. We render the iteration as a
        # zero-width marker at its `started` timestamp so multiple iters
        # of the same dispatch each get their own decoration.
        elif etype == "ITERATION_END":
            # Per-iteration markers must be scoped to a change. An iteration
            # event without a `change` field is malformed and would land on
            # an unscoped lane; drop it and log at debug for diagnosis.
            if not change:
                logger.debug(
                    "ITERATION_END dropped: missing change name (data=%r)", data,
                )
                continue
            iter_n = data.get("iteration")
            # Dedup: a crash between event emit and the persistence of
            # `last_emitted_iter` re-emits the same ITERATION_END on the
            # next orchestrator startup. Suppress duplicates here so the
            # timeline shows one marker per actual iteration.
            try:
                _iter_key = (change, int(iter_n) if iter_n is not None else -1)
            except (TypeError, ValueError):
                _iter_key = (change, -1)
            if _iter_key in seen_iterations:
                continue
            seen_iterations.add(_iter_key)
            resumed = bool(data.get("resumed", False))
            cat = "agent:session-resume" if resumed else "agent:session-fresh"
            # Anchor at `started`; if absent, prefer `ended` over the event
            # ts (the orchestrator poll timestamp). Both `started`/`ended`
            # come from the bash loop's clock; the event ts is the
            # orchestrator-side poll time which can be 0–15 s after the
            # iteration actually finished.
            started = data.get("started", "") or data.get("ended", "") or ts
            session_id = str(data.get("session_id") or "")
            detail = {
                "source": "ralph-iteration",
                "iteration": iter_n,
                "session_id": session_id[:8] if session_id else "",
                "session_id_full": session_id,
                "resumed": resumed,
                "duration_ms": data.get("duration_ms"),
                "tokens_used": data.get("tokens_used"),
                "no_op": data.get("no_op"),
                "ff_exhausted": data.get("ff_exhausted"),
            }
            # Keep `False`/`0` values — they're meaningful.
            detail = {k: v for k, v in detail.items() if v is not None and v != ""}
            spans.append({
                "category": cat,
                "change": change,
                "start": started,
                "end": started,
                "duration_ms": 0,
                "detail": detail,
            })

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


# ─── Implementing-span enrichment ───────────────────────────────────


def _enrich_implementing_spans(spans: list[dict], project_path: Path) -> None:
    """Mutate `spans` in place: add aggregates + sub_spans to implementing entries.

    Behaviour contract:
    - Every span with `category == "implementing"` gets a `sub_spans` key
      (empty list when no classifiable drilldown data — set early so the
      no-data and failure paths still satisfy the API contract).
    - The drilldown cache is loaded at most once per change_name via
      `sub_span_cache`, then reused for both aggregates and classification.
    - The classifier is wrapped in a per-span try/except so one change's
      failure does not block classification of other changes.

    Extracted from the inline enrichment block originally at activity.py:1152
    so the integration tests can exercise this loop without spinning up the
    FastAPI client.
    """
    from .activity_detail import (
        _build_sub_spans_for_change,
        _classify_sub_phases,
        _clip_and_filter,
        _compute_aggregates,
    )

    sub_span_cache: dict[str, list[dict]] = {}
    for span in spans:
        if span.get("category") != "implementing":
            continue
        # Default: every implementing span gets a `sub_spans` field.
        span["sub_spans"] = []
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
        window = _clip_and_filter(sub_spans, span.get("start"), span.get("end"))
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
        # Sub-phase classification — reuses `window` (no re-clip).
        # Per-span try/except so one change's failure does not block
        # classification of other changes' spans in the same response.
        try:
            span["sub_spans"] = _classify_sub_phases(window)
        except Exception:  # noqa: BLE001
            logger.debug(
                "sub-phase classification failed for %s",
                change_name,
                exc_info=True,
            )
            span["sub_spans"] = []


# ─── API endpoint ───────────────────────────────────────────────────


@router.get("/api/{project}/activity-timeline")
def get_activity_timeline(
    project: str,
    from_ts: Optional[str] = Query(None, alias="from"),
    to_ts: Optional[str] = Query(None, alias="to"),
    lineage: Optional[str] = None,
):
    """Get activity timeline with spans and breakdown for a project.

    Section 13.4: when `?lineage=` is provided, only spans attributable
    to that lineage are returned.  Spans without a `change` field
    (project-wide events) pass through unfiltered.
    """
    project_path = _resolve_project(project)

    # Resolve the effective lineage early so we can filter the spans below.
    from .lineages import resolve_lineage_default
    effective_lineage = lineage or resolve_lineage_default(project_path)

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

    # Section 8.1: insert zero-width `sentinel:session_boundary` spans at
    # every detected session_id transition.  CYCLE_HEADERs carry the
    # session_id at rotation time; we walk them in order and emit a
    # marker whenever the id changes.
    try:
        boundaries = _collect_session_boundaries(project_path)
        for b in boundaries:
            spans.append({
                "category": "sentinel:session_boundary",
                "start": b["ts"],
                "end": b["ts"],
                "duration_ms": 0,
                "change": "",
                "detail": {
                    "session_id": b.get("session_id"),
                    "session_started_at": b.get("session_started_at"),
                    "spec_lineage_id": b.get("spec_lineage_id"),
                },
            })
        spans.sort(key=lambda s: s.get("start", ""))
    except Exception:
        logger.debug("session_boundary extraction failed", exc_info=True)

    # Enrich implementing spans with per-span aggregates + sub-phase rollup.
    # See `_enrich_implementing_spans` (above) for the full contract.
    try:
        _enrich_implementing_spans(spans, project_path)
    except Exception:  # noqa: BLE001
        logger.debug("implementing-span enrichment pass failed", exc_info=True)

    # Section 13.4 — apply lineage filter to spans before breakdown.
    if effective_lineage and effective_lineage != "__all__":
        try:
            from ..state import load_state
            change_lineage: dict[str, str] = {}
            sp = _state_path(project_path)
            if sp.exists():
                _st = load_state(str(sp))
                for c in _st.changes:
                    lid = c.spec_lineage_id or _st.spec_lineage_id
                    if lid:
                        change_lineage[c.name] = lid
            from .helpers import _load_archived_changes
            for entry in _load_archived_changes(project_path):
                lid = entry.get("spec_lineage_id")
                if lid and entry.get("name") not in change_lineage:
                    change_lineage[entry["name"]] = lid

            # Compute the lineage's active time window from change-attributed
            # spans.  Project-wide spans (no `change` field) — typically idle
            # gaps, planner ticks, cross-lineage daemon events — are only
            # kept when they fall INSIDE the lineage's own activity window.
            # Without this filter, a v2-only view inherits v1's idle periods
            # and the timeline's wall-time stretches to cover both lineages.
            lineage_span_starts: list[str] = []
            lineage_span_ends: list[str] = []
            for s in spans:
                ch = s.get("change")
                if not ch:
                    continue
                if change_lineage.get(ch, "__legacy__") != effective_lineage:
                    continue
                st = s.get("start")
                en = s.get("end")
                if st:
                    lineage_span_starts.append(st)
                if en:
                    lineage_span_ends.append(en)
            window_start = min(lineage_span_starts) if lineage_span_starts else None
            window_end = max(lineage_span_ends) if lineage_span_ends else None

            def _in_window(span: dict) -> bool:
                if window_start is None or window_end is None:
                    return False
                st = span.get("start") or ""
                en = span.get("end") or st
                # Keep the span when it overlaps the window on either side.
                return not (en < window_start or st > window_end)

            filtered: list[dict] = []
            for s in spans:
                ch = s.get("change")
                if not ch:
                    # session_boundary markers carry their own lineage tag
                    # — respect it first, otherwise fall back to the
                    # activity-window overlap check so we do not drag in
                    # cross-lineage idle / planner spans.
                    detail_l = (s.get("detail") or {}).get("spec_lineage_id")
                    if detail_l:
                        if detail_l == effective_lineage:
                            filtered.append(s)
                        continue
                    if _in_window(s):
                        filtered.append(s)
                    continue
                if change_lineage.get(ch, "__legacy__") == effective_lineage:
                    filtered.append(s)
            spans = filtered
        except Exception:
            logger.debug("activity lineage filter failed", exc_info=True)

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
        "effective_lineage": effective_lineage,
    }
