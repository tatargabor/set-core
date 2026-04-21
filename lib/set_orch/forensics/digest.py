"""Aggregate error/anomaly signals across every jsonl in a resolved run."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

from .jsonl_reader import (
    CLEAN_STOP_REASONS,
    extract_bash_exit_code,
    extract_stop_reason,
    extract_text_content,
    get_record_type,
    get_session_id,
    get_timestamp,
    is_error_result,
    is_permission_denial,
    is_user_interrupt,
    iter_records,
    iter_tool_results,
    iter_tool_uses,
)
from .resolver import ResolvedRun

logger = logging.getLogger(__name__)

SIGNAL_TOOL_ERROR = "tool_error"
SIGNAL_BASH_EXIT = "bash_nonzero_exit"
SIGNAL_STOP_ANOMALY = "stop_reason_anomaly"
SIGNAL_USER_INTERRUPT = "user_interrupt"
SIGNAL_PERMISSION_DENIAL = "permission_denial"
SIGNAL_CRASH_SUSPECT = "crash_suspect"


@dataclass
class SignalGroup:
    change: str
    session_uuid: str
    signal_type: str
    tool_name: Optional[str]
    count: int = 0
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    snippet: str = ""

    def key(self) -> tuple[str, str, str, Optional[str]]:
        return (self.change, self.session_uuid, self.signal_type, self.tool_name)


@dataclass
class DigestResult:
    run_id: str
    sessions_scanned: int = 0
    groups: list[SignalGroup] = field(default_factory=list)
    crash_suspect_sessions: list[dict[str, str]] = field(default_factory=list)

    def total_signals(self) -> int:
        return sum(g.count for g in self.groups)

    def groups_by_change(self) -> dict[str, list[SignalGroup]]:
        out: dict[str, list[SignalGroup]] = {}
        for g in self.groups:
            out.setdefault(g.change, []).append(g)
        return out


def _truncate(text: str, limit: int = 200) -> str:
    text = text.replace("\r", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _session_uuid_from_path(path: Path) -> str:
    return path.stem


class _Aggregator:
    def __init__(self, run_id: str) -> None:
        self.result = DigestResult(run_id=run_id)
        self._groups: dict[tuple[str, str, str, Optional[str]], SignalGroup] = {}

    def record(
        self,
        *,
        change: str,
        session_uuid: str,
        signal_type: str,
        tool_name: Optional[str],
        timestamp: Optional[str],
        text: str,
    ) -> None:
        key = (change, session_uuid, signal_type, tool_name)
        grp = self._groups.get(key)
        if grp is None:
            grp = SignalGroup(
                change=change,
                session_uuid=session_uuid,
                signal_type=signal_type,
                tool_name=tool_name,
            )
            self._groups[key] = grp
            self.result.groups.append(grp)
        grp.count += 1
        if timestamp is not None:
            if grp.first_seen is None or timestamp < grp.first_seen:
                grp.first_seen = timestamp
            if grp.last_seen is None or timestamp > grp.last_seen:
                grp.last_seen = timestamp
                grp.snippet = _truncate(text)
        elif not grp.snippet:
            grp.snippet = _truncate(text)


def _scan_session_file(agg: _Aggregator, change: str, path: Path) -> None:
    session_uuid = _session_uuid_from_path(path)
    last_assistant_stop: Optional[str] = None
    last_assistant_timestamp: Optional[str] = None
    has_assistant_record = False
    prior_tool_uses: dict[str, dict[str, Any]] = {}

    for record in iter_records(path):
        rec_type = get_record_type(record)
        ts = get_timestamp(record)

        # Track tool_use to map result → tool name via tool_use_id.
        for tu in iter_tool_uses(record):
            tu_id = tu.get("id")
            if isinstance(tu_id, str):
                prior_tool_uses[tu_id] = tu

        # Tool results: errors + bash exits.
        for tr in iter_tool_results(record):
            tu_id = tr.get("tool_use_id")
            tool_use = prior_tool_uses.get(tu_id) if isinstance(tu_id, str) else None
            tool_name = None
            if isinstance(tool_use, dict):
                tn = tool_use.get("name")
                if isinstance(tn, str):
                    tool_name = tn

            if is_error_result(tr):
                agg.record(
                    change=change,
                    session_uuid=session_uuid,
                    signal_type=SIGNAL_TOOL_ERROR,
                    tool_name=tool_name,
                    timestamp=ts,
                    text=extract_text_content(tr),
                )
            exit_code = extract_bash_exit_code(tr)
            if exit_code is not None and exit_code != 0:
                agg.record(
                    change=change,
                    session_uuid=session_uuid,
                    signal_type=SIGNAL_BASH_EXIT,
                    tool_name=tool_name or "Bash",
                    timestamp=ts,
                    text=extract_text_content(tr),
                )

        # Permission denials (may appear in tool_results or system text).
        if is_permission_denial(record):
            agg.record(
                change=change,
                session_uuid=session_uuid,
                signal_type=SIGNAL_PERMISSION_DENIAL,
                tool_name=None,
                timestamp=ts,
                text=extract_text_content(record),
            )

        # User interrupts.
        if is_user_interrupt(record):
            agg.record(
                change=change,
                session_uuid=session_uuid,
                signal_type=SIGNAL_USER_INTERRUPT,
                tool_name=None,
                timestamp=ts,
                text=extract_text_content(record),
            )

        # Track assistant stop_reason (last one wins for crash-suspect check).
        if rec_type == "assistant":
            has_assistant_record = True
            sr = extract_stop_reason(record)
            if sr is not None:
                last_assistant_stop = sr
                last_assistant_timestamp = ts
                if sr not in CLEAN_STOP_REASONS:
                    agg.record(
                        change=change,
                        session_uuid=session_uuid,
                        signal_type=SIGNAL_STOP_ANOMALY,
                        tool_name=None,
                        timestamp=ts,
                        text=f"stop_reason={sr}",
                    )

    # Crash-suspect: session ended without any clean stop_reason on the last assistant message.
    if has_assistant_record and (
        last_assistant_stop is None or last_assistant_stop not in CLEAN_STOP_REASONS
    ):
        agg.result.crash_suspect_sessions.append(
            {
                "change": change,
                "session_uuid": session_uuid,
                "reason": last_assistant_stop or "no-stop-reason",
                "last_assistant_timestamp": last_assistant_timestamp or "",
            }
        )


def digest_run(resolved: ResolvedRun) -> DigestResult:
    agg = _Aggregator(run_id=resolved.run_id)
    for change, session_dir in resolved.iter_all_session_dirs():
        for jsonl in sorted(session_dir.glob("*.jsonl")):
            agg.result.sessions_scanned += 1
            _scan_session_file(agg, change, jsonl)
    # Stable ordering: by change, then count desc, then signal type.
    agg.result.groups.sort(key=lambda g: (g.change, -g.count, g.signal_type, g.session_uuid))
    return agg.result


def to_markdown(result: DigestResult) -> str:
    by_change = result.groups_by_change()
    lines: list[str] = []
    lines.append(f"# Digest: {result.run_id}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Sessions scanned: **{result.sessions_scanned}**")
    lines.append(f"- Total error signals: **{result.total_signals()}**")
    per_change_totals = {c: sum(g.count for g in gs) for c, gs in by_change.items()}
    if per_change_totals:
        lines.append("- Per change:")
        for c in sorted(per_change_totals):
            lines.append(f"  - `{c}`: {per_change_totals[c]}")
    else:
        lines.append("- No error signals recorded.")
    lines.append("")

    lines.append("## Errors by change")
    if not by_change:
        lines.append("_None._")
    else:
        for change in sorted(by_change):
            lines.append(f"### {change}")
            by_session: dict[str, list[SignalGroup]] = {}
            for g in by_change[change]:
                by_session.setdefault(g.session_uuid, []).append(g)
            for session in sorted(by_session):
                short = session[:8] if len(session) >= 8 else session
                lines.append(f"- **session `{short}`**")
                for g in by_session[session]:
                    tool_part = f" [{g.tool_name}]" if g.tool_name else ""
                    snippet_part = f" — {g.snippet}" if g.snippet else ""
                    lines.append(
                        f"  - `{g.signal_type}`{tool_part} × {g.count}"
                        f" ({g.first_seen or '?'} → {g.last_seen or '?'}){snippet_part}"
                    )
            lines.append("")

    lines.append("## Crash suspects")
    if not result.crash_suspect_sessions:
        lines.append("_None._")
    else:
        for entry in result.crash_suspect_sessions:
            short = entry["session_uuid"][:8]
            lines.append(
                f"- `{entry['change']}/{short}` — reason: `{entry['reason']}`"
                + (f" — last @ {entry['last_assistant_timestamp']}" if entry["last_assistant_timestamp"] else "")
            )
    lines.append("")
    return "\n".join(lines)


def to_json(result: DigestResult) -> dict[str, Any]:
    return {
        "run_id": result.run_id,
        "sessions_scanned": result.sessions_scanned,
        "total_signals": result.total_signals(),
        "groups": [asdict(g) for g in result.groups],
        "crash_suspects": result.crash_suspect_sessions,
    }
