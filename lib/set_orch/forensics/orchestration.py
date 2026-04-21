"""Summarise orchestration-level logs (engine events + state transitions)."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from .resolver import ResolvedRun

logger = logging.getLogger(__name__)


class OrchestrationDirMissing(RuntimeError):
    """Raised when the orchestration dir is absent for the resolved run."""


@dataclass
class DispatchRow:
    change: str
    first_dispatch_at: Optional[str] = None
    last_gate_status: Optional[str] = None
    terminal_status: Optional[str] = None
    num_dispatches: int = 0


@dataclass
class StateTransition:
    timestamp: str
    change: str
    field: str
    old: Any
    new: Any


@dataclass
class OrchestrationSummary:
    run_id: str
    dispatch_rows: list[DispatchRow] = field(default_factory=list)
    gate_outcomes: dict[str, dict[str, int]] = field(default_factory=dict)
    state_transitions: list[StateTransition] = field(default_factory=list)
    terminal_status_at: Optional[str] = None


def _stream_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("%s:%d malformed jsonl skipped: %s", path, lineno, exc)
                continue
            if isinstance(rec, dict):
                records.append(rec)
    return records


def _event_type(rec: dict[str, Any]) -> str:
    for key in ("event", "type", "event_type", "kind"):
        val = rec.get(key)
        if isinstance(val, str):
            return val
    return ""


def _event_change(rec: dict[str, Any]) -> Optional[str]:
    for key in ("change", "change_name", "changeName"):
        val = rec.get(key)
        if isinstance(val, str):
            return val
    data = rec.get("data") or rec.get("payload")
    if isinstance(data, dict):
        for key in ("change", "change_name", "changeName"):
            val = data.get(key)
            if isinstance(val, str):
                return val
    return None


def _event_timestamp(rec: dict[str, Any]) -> str:
    for key in ("timestamp", "ts", "time", "at"):
        val = rec.get(key)
        if isinstance(val, str):
            return val
    return ""


def _extract_nested(rec: dict[str, Any], *keys: str) -> Any:
    data = rec
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def orchestration_summary(resolved: ResolvedRun) -> OrchestrationSummary:
    if resolved.orchestration_dir is None:
        raise OrchestrationDirMissing(
            f"orchestration dir not found for run {resolved.run_id!r}"
        )

    events_path = resolved.orchestration_dir / "orchestration-events.jsonl"
    state_path = resolved.orchestration_dir / "orchestration-state-events.jsonl"

    events = _stream_jsonl(events_path)
    state_events = _stream_jsonl(state_path)

    summary = OrchestrationSummary(run_id=resolved.run_id)

    # Known gate-verdict tokens that appear as keys inside VERIFY_GATE.data.
    _verdict_tokens = {"pass", "fail", "skipped", "cached", "retry", "warn", "warn-fail"}

    dispatches: dict[str, DispatchRow] = {}
    for rec in events:
        et_raw = _event_type(rec)
        et = et_raw.lower()
        change = _event_change(rec)
        ts = _event_timestamp(rec)

        # Dispatch counting (DISPATCH, CHANGE_REDISPATCH).
        if et in {"dispatch", "change_redispatch"} or "dispatch" in et:
            if change:
                row = dispatches.setdefault(change, DispatchRow(change=change))
                row.num_dispatches += 1
                if row.first_dispatch_at is None or (ts and ts < row.first_dispatch_at):
                    row.first_dispatch_at = ts

        # VERIFY_GATE: support both shapes:
        #  (a) top-level `gate` + `verdict` (legacy / test fixtures)
        #  (b) data.<gate_name> = <verdict> (engine emits per-gate verdicts inline)
        if et_raw == "VERIFY_GATE" or "verify_gate" in et:
            top_gate = rec.get("gate") or rec.get("gate_name")
            top_verdict = rec.get("verdict") or rec.get("status")
            if isinstance(top_gate, str) and isinstance(top_verdict, str):
                bucket = summary.gate_outcomes.setdefault(top_gate, {})
                bucket[top_verdict] = bucket.get(top_verdict, 0) + 1
                if change:
                    row = dispatches.setdefault(change, DispatchRow(change=change))
                    row.last_gate_status = f"{top_gate}={top_verdict}"

            data = rec.get("data") or {}
            if isinstance(data, dict):
                stop_gate = data.get("stop_gate") if isinstance(data.get("stop_gate"), str) else None
                # Keys inside data that are NOT gate names even if their value matches a verdict token.
                _non_gate_keys = {"result", "stop_gate", "fingerprint", "uncommitted_check"}
                last_gate_token = None
                for k, v in data.items():
                    if k in _non_gate_keys:
                        continue
                    if isinstance(v, str) and v in _verdict_tokens:
                        bucket = summary.gate_outcomes.setdefault(k, {})
                        bucket[v] = bucket.get(v, 0) + 1
                        last_gate_token = f"{k}={v}"
                if change:
                    row = dispatches.setdefault(change, DispatchRow(change=change))
                    if stop_gate is not None:
                        result = data.get("result")
                        row.last_gate_status = f"{stop_gate}={result}" if isinstance(result, str) else stop_gate
                    elif last_gate_token and not row.last_gate_status:
                        row.last_gate_status = last_gate_token

        # Per-gate event types: GATE_PASS, GATE_FAIL, GATE_CACHED, GATE_SKIPPED.
        if et_raw in {"GATE_PASS", "GATE_FAIL", "GATE_CACHED", "GATE_SKIPPED"}:
            data = rec.get("data") or {}
            gate_name = data.get("gate") if isinstance(data, dict) else None
            verdict_map = {
                "GATE_PASS": "pass",
                "GATE_FAIL": "fail",
                "GATE_CACHED": "cached",
                "GATE_SKIPPED": "skipped",
            }
            verdict = verdict_map[et_raw]
            if isinstance(gate_name, str):
                bucket = summary.gate_outcomes.setdefault(gate_name, {})
                bucket[verdict] = bucket.get(verdict, 0) + 1
                if change:
                    row = dispatches.setdefault(change, DispatchRow(change=change))
                    row.last_gate_status = f"{gate_name}={verdict}"

        # Per-change terminal markers: CHANGE_DONE, MERGE_SUCCESS, FIX_ISS_ESCALATED, STUCK_LOOP_ESCALATED.
        if et_raw in {"CHANGE_DONE", "MERGE_SUCCESS", "FIX_ISS_ESCALATED", "STUCK_LOOP_ESCALATED"}:
            if change:
                row = dispatches.setdefault(change, DispatchRow(change=change))
                row.terminal_status = et_raw

        # Run-level terminal: ALL_DONE / SUPERVISOR_STOP.
        if et in {"all_done", "run_complete", "done", "supervisor_stop"} or "terminal" in et:
            summary.terminal_status_at = ts or summary.terminal_status_at

    for rec in state_events:
        ts = _event_timestamp(rec)
        change = _event_change(rec) or ""
        field_name = (
            rec.get("field")
            or rec.get("key")
            or _extract_nested(rec, "data", "field")
            or ""
        )
        old_val = (
            rec.get("old")
            or rec.get("from")
            or _extract_nested(rec, "data", "old")
        )
        new_val = (
            rec.get("new")
            or rec.get("to")
            or _extract_nested(rec, "data", "new")
        )
        if not field_name and not new_val:
            # Not a transition record we can summarise.
            continue
        summary.state_transitions.append(
            StateTransition(
                timestamp=ts,
                change=change,
                field=str(field_name),
                old=old_val,
                new=new_val,
            )
        )

    summary.dispatch_rows = sorted(dispatches.values(), key=lambda r: r.change)
    summary.state_transitions.sort(key=lambda t: t.timestamp)
    return summary


def to_markdown(summary: OrchestrationSummary) -> str:
    lines: list[str] = [f"# Orchestration summary: {summary.run_id}", ""]

    lines.append("## Dispatches")
    if not summary.dispatch_rows:
        lines.append("_No dispatch events found._")
    else:
        lines.append("| change | first_dispatch_at | last_gate_status | terminal_status | num_dispatches |")
        lines.append("| --- | --- | --- | --- | --- |")
        for row in summary.dispatch_rows:
            lines.append(
                f"| `{row.change}` | {row.first_dispatch_at or ''} |"
                f" {row.last_gate_status or ''} | {row.terminal_status or ''} |"
                f" {row.num_dispatches} |"
            )
    lines.append("")

    lines.append("## Gate outcomes")
    if not summary.gate_outcomes:
        lines.append("_No verify-gate events found._")
    else:
        for gate in sorted(summary.gate_outcomes):
            parts = ", ".join(
                f"{v}={c}" for v, c in sorted(summary.gate_outcomes[gate].items())
            )
            lines.append(f"- `{gate}`: {parts}")
    lines.append("")

    lines.append("## State transitions")
    if not summary.state_transitions:
        lines.append("_None._")
    else:
        for t in summary.state_transitions[:200]:
            lines.append(
                f"- {t.timestamp} `{t.change or '(global)'}` `{t.field}`:"
                f" `{t.old!r}` → `{t.new!r}`"
            )
        if len(summary.state_transitions) > 200:
            lines.append(
                f"_({len(summary.state_transitions) - 200} more transitions; use --json for full list)_"
            )
    lines.append("")

    lines.append("## Terminal status")
    if summary.terminal_status_at:
        lines.append(f"- terminated at: {summary.terminal_status_at}")
    else:
        lines.append("_No terminal event recorded._")
    return "\n".join(lines)


def to_json(summary: OrchestrationSummary) -> dict[str, Any]:
    return {
        "run_id": summary.run_id,
        "dispatches": [asdict(r) for r in summary.dispatch_rows],
        "gate_outcomes": summary.gate_outcomes,
        "state_transitions": [asdict(t) for t in summary.state_transitions],
        "terminal_status_at": summary.terminal_status_at,
    }
