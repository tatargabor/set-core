"""Content-only regex search across jsonl bodies (emit message.content text, never jsonl lines)."""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterator, Optional

from .jsonl_reader import (
    extract_text_content,
    get_record_type,
    get_timestamp,
    iter_records,
    iter_tool_results,
    iter_tool_uses,
)
from .resolver import ResolvedRun

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 50


@dataclass
class GrepMatch:
    change: str
    session_uuid: str
    session_short: str
    timestamp: str
    record_type: str
    tool_name: Optional[str]
    snippet: str


@dataclass
class GrepOutcome:
    matches: list[GrepMatch]
    total_matches: int  # matches found before limit was applied
    limit: int


def _iter_searchable_texts(
    record: dict[str, Any],
    tool_filter: Optional[str],
    tool_use_ids_to_names: dict[str, str],
) -> Iterator[tuple[str, Optional[str]]]:
    """Yield (text, tool_name) tuples extracted from a record's content blocks.

    When `tool_filter` is set, only yield tool_use / tool_result blocks for matching tools.
    `tool_use_ids_to_names` accumulates across records in the same session so that
    tool_result blocks (emitted in later records) can be resolved to their tool name.
    """
    rec_type = get_record_type(record)

    for tu in iter_tool_uses(record):
        tu_id = tu.get("id")
        name = tu.get("name") if isinstance(tu.get("name"), str) else None
        if isinstance(tu_id, str) and name:
            tool_use_ids_to_names[tu_id] = name
        if tool_filter is not None and (name is None or name.lower() != tool_filter.lower()):
            continue
        text = extract_text_content(tu)
        if text:
            yield text, name

    for tr in iter_tool_results(record):
        tu_id = tr.get("tool_use_id")
        tool_name = tool_use_ids_to_names.get(tu_id) if isinstance(tu_id, str) else None
        if tool_filter is not None and (
            tool_name is None or tool_name.lower() != tool_filter.lower()
        ):
            continue
        text = extract_text_content(tr)
        if text:
            yield text, tool_name

    if tool_filter is None and rec_type in {"user", "assistant", "system"}:
        # Emit plain-text blocks for role-based matching.
        msg = record.get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            yield content, None
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") in {"text", "thinking"}:
                    text = extract_text_content(block)
                    if text:
                        yield text, None


def _extract_context(text: str, match: re.Match[str], context_lines: int = 2) -> str:
    """Return the matching region plus up to `context_lines` lines before and after."""
    lines = text.splitlines()
    if not lines:
        return text.strip()
    # Find which line the match starts on.
    start = match.start()
    cumulative = 0
    match_line = 0
    for i, line in enumerate(lines):
        if cumulative + len(line) + 1 > start:
            match_line = i
            break
        cumulative += len(line) + 1
    lo = max(0, match_line - context_lines)
    hi = min(len(lines), match_line + context_lines + 1)
    return "\n".join(lines[lo:hi]).strip()


def grep_content(
    resolved: ResolvedRun,
    pattern: str,
    *,
    tool: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
    case_insensitive: bool = False,
) -> GrepOutcome:
    flags = re.MULTILINE
    if case_insensitive:
        flags |= re.IGNORECASE
    try:
        compiled = re.compile(pattern, flags)
    except re.error as exc:
        raise ValueError(f"invalid regex {pattern!r}: {exc}") from exc

    matches: list[GrepMatch] = []
    total = 0

    for change, session_dir in resolved.iter_all_session_dirs():
        for jsonl in sorted(session_dir.glob("*.jsonl")):
            session_uuid = jsonl.stem
            short = session_uuid[:8]
            tool_use_ids_to_names: dict[str, str] = {}
            for record in iter_records(jsonl):
                ts = get_timestamp(record) or ""
                rec_type = get_record_type(record)
                for text, tool_name in _iter_searchable_texts(
                    record, tool, tool_use_ids_to_names
                ):
                    for m in compiled.finditer(text):
                        total += 1
                        if len(matches) < limit:
                            snippet = _extract_context(text, m)
                            matches.append(
                                GrepMatch(
                                    change=change,
                                    session_uuid=session_uuid,
                                    session_short=short,
                                    timestamp=ts,
                                    record_type=rec_type,
                                    tool_name=tool_name,
                                    snippet=snippet,
                                )
                            )
    return GrepOutcome(matches=matches, total_matches=total, limit=limit)


def to_markdown(outcome: GrepOutcome) -> str:
    lines: list[str] = []
    for m in outcome.matches:
        tool_part = f" [{m.tool_name}]" if m.tool_name else ""
        lines.append(f"### {m.change}/{m.session_short} @ {m.timestamp}{tool_part}:")
        lines.append("```")
        lines.append(m.snippet)
        lines.append("```")
        lines.append("")
    suppressed = outcome.total_matches - len(outcome.matches)
    if suppressed > 0:
        lines.append(
            f"_({suppressed} more matches suppressed; use --limit to raise)_"
        )
    elif not outcome.matches:
        lines.append("_(no matches)_")
    return "\n".join(lines)


def to_json(outcome: GrepOutcome) -> dict[str, Any]:
    return {
        "total_matches": outcome.total_matches,
        "limit": outcome.limit,
        "suppressed": max(0, outcome.total_matches - len(outcome.matches)),
        "matches": [asdict(m) for m in outcome.matches],
    }
