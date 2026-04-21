"""Streaming jsonl reader + record-shape helpers for Claude Code session transcripts.

Record types observed:
- `user` — user message; `message.content` is str or list of content blocks
- `assistant` — assistant message; `message.stop_reason`, `message.content` is list of blocks
- `system` — system messages
- `queue-operation` — harness-level queue events (mostly ignorable)
- `attachment` — tool/permission attachments
- `last-prompt` — summary marker
- `summary` — Claude Code session summary

Content block types inside `message.content`:
- `text` — plain text from user/assistant
- `thinking` — assistant extended thinking
- `tool_use` — `{name, id, input}` — assistant tool invocation
- `tool_result` — `{tool_use_id, content, is_error?}` — tool outcome (appears in user messages)
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)

CLEAN_STOP_REASONS = {"end_turn", "tool_use", "stop_sequence"}

_EXIT_CODE_PATTERNS = [
    re.compile(r"exit code:\s*(-?\d+)", re.IGNORECASE),
    re.compile(r"exit status\s+(-?\d+)", re.IGNORECASE),
    re.compile(r'"exitCode"\s*:\s*(-?\d+)'),
]

_PERMISSION_DENIED_MARKERS = (
    "requested permissions",
    "permission denied",
    "not allowed",
    "refused to run",
)

_INTERRUPT_MARKERS = (
    "[request interrupted by user",
    "[interrupted by user",
)


def iter_records(path: Path) -> Iterator[dict[str, Any]]:
    """Stream jsonl records one at a time.

    Malformed lines are logged at WARNING and skipped — never abort the whole scan.
    """
    try:
        fh = path.open("r", encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("cannot open %s: %s", path, exc)
        return
    with fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("%s:%d malformed jsonl line skipped: %s", path, lineno, exc)
                continue
            if isinstance(record, dict):
                yield record


def get_record_type(record: dict[str, Any]) -> str:
    return str(record.get("type", "unknown"))


def get_timestamp(record: dict[str, Any]) -> Optional[str]:
    ts = record.get("timestamp")
    if isinstance(ts, str):
        return ts
    msg = record.get("message") or {}
    if isinstance(msg, dict):
        ts = msg.get("timestamp")
        if isinstance(ts, str):
            return ts
    return None


def get_session_id(record: dict[str, Any]) -> Optional[str]:
    sid = record.get("sessionId")
    if isinstance(sid, str):
        return sid
    return None


def _iter_content_blocks(record: dict[str, Any]) -> Iterator[dict[str, Any]]:
    msg = record.get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                yield block


def iter_tool_uses(record: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for block in _iter_content_blocks(record):
        if block.get("type") == "tool_use":
            yield block


def iter_tool_results(record: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for block in _iter_content_blocks(record):
        if block.get("type") == "tool_result":
            yield block


def is_tool_result(block: dict[str, Any]) -> bool:
    return block.get("type") == "tool_result"


def is_error_result(block: dict[str, Any]) -> bool:
    return bool(block.get("type") == "tool_result" and block.get("is_error"))


def extract_text_content(block_or_record: dict[str, Any]) -> str:
    """Extract human-readable text from a content block or a whole record.

    - For a content block with `text` key → return the text.
    - For a `tool_result` block with `content` as str → return it directly.
    - For a `tool_result` block with `content` as list of `{type:'text', text:...}` → join.
    - For a `tool_use` block → return a compact repr of its input.
    - For a record (has `type` == 'user'|'assistant') → concatenate text from all blocks.
    """
    if "type" in block_or_record and block_or_record["type"] in {"text", "thinking"}:
        val = block_or_record.get("text") or block_or_record.get("thinking") or ""
        return str(val)
    if block_or_record.get("type") == "tool_result":
        content = block_or_record.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for c in content:
                if isinstance(c, dict):
                    t = c.get("text")
                    if isinstance(t, str):
                        parts.append(t)
                elif isinstance(c, str):
                    parts.append(c)
            return "\n".join(parts)
        return ""
    if block_or_record.get("type") == "tool_use":
        inp = block_or_record.get("input") or {}
        try:
            return json.dumps(inp, ensure_ascii=False)[:500]
        except (TypeError, ValueError):
            return str(inp)[:500]
    # Whole record: concatenate content blocks.
    rec_type = block_or_record.get("type")
    if rec_type in {"user", "assistant", "system"}:
        msg = block_or_record.get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for b in content:
                if isinstance(b, dict):
                    parts.append(extract_text_content(b))
                elif isinstance(b, str):
                    parts.append(b)
            return "\n".join(p for p in parts if p)
    # Fallbacks
    if isinstance(block_or_record.get("content"), str):
        return str(block_or_record["content"])
    return ""


def extract_bash_exit_code(block: dict[str, Any]) -> Optional[int]:
    """Return the nonzero-or-zero Bash exit code if the tool_result encodes one, else None."""
    if not is_tool_result(block):
        return None
    text = extract_text_content(block)
    for pat in _EXIT_CODE_PATTERNS:
        m = pat.search(text)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue
    return None


def extract_stop_reason(record: dict[str, Any]) -> Optional[str]:
    msg = record.get("message") or {}
    sr = msg.get("stop_reason")
    if isinstance(sr, str):
        return sr
    return None


def is_user_interrupt(record: dict[str, Any]) -> bool:
    if record.get("isInterrupt") is True:
        return True
    if record.get("type") == "user":
        txt = extract_text_content(record).lower()
        for marker in _INTERRUPT_MARKERS:
            if marker in txt:
                return True
    return False


def is_permission_denial(record: dict[str, Any]) -> bool:
    """Detect permission-related blocks in tool results or system/assistant text."""
    for block in _iter_content_blocks(record):
        if block.get("type") == "tool_result":
            txt = extract_text_content(block).lower()
            if any(m in txt for m in _PERMISSION_DENIED_MARKERS):
                return True
    rt = record.get("type")
    if rt in {"assistant", "system"}:
        txt = extract_text_content(record).lower()
        if any(m in txt for m in _PERMISSION_DENIED_MARKERS) and "permission" in txt:
            return True
    return False


def find_tool_use_for_result(
    records: list[dict[str, Any]], tool_use_id: str
) -> Optional[dict[str, Any]]:
    """Walk back through already-seen records and return the tool_use block with the given id."""
    for rec in reversed(records):
        for block in iter_tool_uses(rec):
            if block.get("id") == tool_use_id:
                return block
    return None
