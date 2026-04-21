"""Single-session timeline view with tool-call outcomes and stop reasons."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from .jsonl_reader import (
    CLEAN_STOP_REASONS,
    extract_bash_exit_code,
    extract_stop_reason,
    extract_text_content,
    get_record_type,
    get_timestamp,
    is_error_result,
    is_user_interrupt,
    iter_records,
    iter_tool_results,
    iter_tool_uses,
)
from .resolver import ResolvedRun

logger = logging.getLogger(__name__)

MIN_PREFIX_LEN = 6


class SessionNotFound(RuntimeError):
    """Raised when the given UUID prefix matches no session in the run."""


class AmbiguousSessionPrefix(RuntimeError):
    def __init__(self, prefix: str, candidates: list[dict[str, str]]):
        self.prefix = prefix
        self.candidates = candidates
        names = ", ".join(f"{c['change']}/{c['session_uuid']}" for c in candidates)
        super().__init__(f"prefix {prefix!r} is ambiguous across {len(candidates)} sessions: {names}")


@dataclass
class TimelineEntry:
    timestamp: str
    event_type: str  # tool_use | tool_result | stop | user_message | system_message
    tool_name: Optional[str]
    outcome: str  # ok | error | timeout | info
    summary: str


@dataclass
class Timeline:
    change: str
    session_uuid: str
    path: str
    entries: list[TimelineEntry] = field(default_factory=list)


def _find_session(resolved: ResolvedRun, uuid_or_prefix: str) -> tuple[str, Path]:
    """Return (change, jsonl_path) for the resolved session.

    Short prefixes below MIN_PREFIX_LEN are rejected unless they are a full UUID.
    """
    candidates: list[dict[str, str]] = []
    for change, session_dir in resolved.iter_all_session_dirs():
        for jsonl in session_dir.glob("*.jsonl"):
            uuid = jsonl.stem
            if uuid == uuid_or_prefix:
                return change, jsonl
            if uuid.startswith(uuid_or_prefix):
                candidates.append(
                    {"change": change, "session_uuid": uuid, "path": str(jsonl)}
                )

    if not candidates:
        raise SessionNotFound(
            f"no session matches {uuid_or_prefix!r} in run {resolved.run_id}"
        )
    if len(uuid_or_prefix) < MIN_PREFIX_LEN:
        raise AmbiguousSessionPrefix(uuid_or_prefix, candidates)
    if len(candidates) > 1:
        raise AmbiguousSessionPrefix(uuid_or_prefix, candidates)
    c = candidates[0]
    return c["change"], Path(c["path"])


def session_timeline(
    resolved: ResolvedRun,
    uuid_or_prefix: str,
    *,
    errors_only: bool = False,
    tool: Optional[str] = None,
) -> Timeline:
    change, path = _find_session(resolved, uuid_or_prefix)
    uuid = path.stem
    timeline = Timeline(change=change, session_uuid=uuid, path=str(path))

    pending_tool_uses: dict[str, dict[str, Any]] = {}

    for record in iter_records(path):
        rec_type = get_record_type(record)
        ts = get_timestamp(record) or ""

        # Tool uses (assistant side).
        for tu in iter_tool_uses(record):
            tu_id = tu.get("id")
            if isinstance(tu_id, str):
                pending_tool_uses[tu_id] = tu
            tool_name = tu.get("name") if isinstance(tu.get("name"), str) else None
            summary = _summarise_tool_use(tu)
            entry = TimelineEntry(
                timestamp=ts,
                event_type="tool_use",
                tool_name=tool_name,
                outcome="info",
                summary=summary,
            )
            if _keep(entry, errors_only=errors_only, tool=tool):
                timeline.entries.append(entry)

        # Tool results (user side).
        for tr in iter_tool_results(record):
            tu_id = tr.get("tool_use_id")
            tool_use = pending_tool_uses.get(tu_id) if isinstance(tu_id, str) else None
            tool_name = (
                tool_use.get("name")
                if isinstance(tool_use, dict) and isinstance(tool_use.get("name"), str)
                else None
            )
            outcome = "ok"
            if is_error_result(tr):
                outcome = "error"
            exit_code = extract_bash_exit_code(tr)
            if exit_code is not None and exit_code != 0:
                outcome = "error"
            summary = _truncate_one_line(extract_text_content(tr), 120)
            entry = TimelineEntry(
                timestamp=ts,
                event_type="tool_result",
                tool_name=tool_name,
                outcome=outcome,
                summary=summary,
            )
            if _keep(entry, errors_only=errors_only, tool=tool):
                timeline.entries.append(entry)

        # Stop reason (assistant message).
        if rec_type == "assistant":
            sr = extract_stop_reason(record)
            if sr is not None:
                outcome = "ok" if sr in CLEAN_STOP_REASONS else "error"
                entry = TimelineEntry(
                    timestamp=ts,
                    event_type="stop",
                    tool_name=None,
                    outcome=outcome,
                    summary=f"stop_reason={sr}",
                )
                if _keep(entry, errors_only=errors_only, tool=tool):
                    timeline.entries.append(entry)

        # User interrupt.
        if is_user_interrupt(record):
            entry = TimelineEntry(
                timestamp=ts,
                event_type="user_message",
                tool_name=None,
                outcome="error",
                summary="user interrupt",
            )
            if _keep(entry, errors_only=errors_only, tool=tool):
                timeline.entries.append(entry)
        elif rec_type == "user" and not _has_tool_results(record):
            summary = _truncate_one_line(extract_text_content(record), 120)
            entry = TimelineEntry(
                timestamp=ts,
                event_type="user_message",
                tool_name=None,
                outcome="info",
                summary=summary,
            )
            if _keep(entry, errors_only=errors_only, tool=tool):
                timeline.entries.append(entry)
        elif rec_type == "system":
            summary = _truncate_one_line(extract_text_content(record), 120)
            entry = TimelineEntry(
                timestamp=ts,
                event_type="system_message",
                tool_name=None,
                outcome="info",
                summary=summary,
            )
            if _keep(entry, errors_only=errors_only, tool=tool):
                timeline.entries.append(entry)

    timeline.entries.sort(key=lambda e: (e.timestamp, e.event_type))
    return timeline


def _has_tool_results(record: dict[str, Any]) -> bool:
    return any(True for _ in iter_tool_results(record))


def _truncate_one_line(text: str, limit: int) -> str:
    text = text.replace("\n", " ").replace("\r", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _summarise_tool_use(block: dict[str, Any]) -> str:
    name = block.get("name", "?")
    inp = block.get("input") or {}
    try:
        summary = json.dumps(inp, ensure_ascii=False)
    except (TypeError, ValueError):
        summary = str(inp)
    return _truncate_one_line(f"{name}({summary})", 120)


def _keep(entry: TimelineEntry, *, errors_only: bool, tool: Optional[str]) -> bool:
    if tool is not None:
        if entry.tool_name is None or entry.tool_name.lower() != tool.lower():
            return False
    if errors_only:
        if entry.outcome not in {"error", "timeout"} and not (
            entry.event_type == "stop" and entry.outcome != "ok"
        ):
            return False
    return True


def to_markdown(timeline: Timeline) -> str:
    lines = [
        f"# Session `{timeline.session_uuid}`",
        f"- change: `{timeline.change}`",
        f"- path: `{timeline.path}`",
        f"- entries: **{len(timeline.entries)}**",
        "",
        "| timestamp | event | tool | outcome | summary |",
        "| --- | --- | --- | --- | --- |",
    ]
    for e in timeline.entries:
        tool = e.tool_name or ""
        # Escape pipes in summary for markdown table safety.
        safe_summary = e.summary.replace("|", "\\|")
        lines.append(
            f"| {e.timestamp} | {e.event_type} | {tool} | {e.outcome} | {safe_summary} |"
        )
    return "\n".join(lines)


def to_json(timeline: Timeline) -> dict[str, Any]:
    return {
        "change": timeline.change,
        "session_uuid": timeline.session_uuid,
        "path": timeline.path,
        "entries": [asdict(e) for e in timeline.entries],
    }
