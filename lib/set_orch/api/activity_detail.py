"""Activity detail — heuristic sub-span reconstruction from Claude session JSONL.

Drilldown for the `implementing` spans produced by `activity.py`. Reads
`~/.claude/projects/-<mangled-worktree>/<uuid>.jsonl` files and classifies
time gaps into typed sub-spans:

- agent:llm-wait        — gap from user → assistant (Claude API roundtrip)
- agent:tool:<name>     — gap from tool_use → matching tool_result
- agent:subagent:<purp> — Task tool linked to a sibling sub-session
- agent:review-wait     — gap while orchestrator review gate runs (ralph resume)
- agent:verify-wait     — gap while orchestrator verify/e2e gate runs
- agent:loop-restart    — gap between ralph loop iterations
- agent:gap             — unaccounted gap (fallback)

Pure heuristic — no LLM calls. Verifier sessions (prefix `[PURPOSE:<type>:...]`)
are excluded because their time is already shown on the main timeline as
`llm:<type>` spans. Cached per-change at
`<project>/set/orchestration/activity-detail-<change>.jsonl` with mtime-based
invalidation.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from .helpers import _resolve_project, _state_path, _claude_mangle
from ..state import load_state

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Tool name normalization ────────────────────────────────────────

KNOWN_TOOLS = {
    "bash", "edit", "read", "write", "glob", "grep",
    "webfetch", "websearch", "task", "agent", "skill",
    "notebookedit", "multiedit", "todowrite", "toolsearch",
    "exitplanmode", "enterplanmode",
}

# Tool names that represent a sub-agent dispatch — these are candidates for
# linking to a sibling sub-session via _link_subagents().
SUBAGENT_TOOL_NAMES = {"task", "agent"}

# Verifier sessions launched by `run_claude_logged()` (verifier.py, engine.py)
# start with a user message prefixed `[PURPOSE:<purpose>:<change>]`. These
# sessions are already represented on the main activity timeline as
# `llm:<purpose>` spans from LLM_CALL events — we exclude them from the
# drilldown to avoid double-counting.
VERIFIER_PURPOSE_RE = re.compile(r'^\s*\[PURPOSE:([a-z_]+):([a-zA-Z0-9_-]+)\]')

# Gap categorization — identifies the cause of a time gap inside a session
# by pattern-matching the first user/queue content that appears after the gap.
# Applied in declaration order; the first matching pattern wins.
GAP_CATEGORY_PATTERNS: list[tuple[str, str]] = [
    ("agent:review-wait",  r"critical code review failure"),
    ("agent:review-wait",  r"review findings"),
    ("agent:review-wait",  r"you must fix the review"),
    ("agent:verify-wait",  r"failing tests"),
    ("agent:verify-wait",  r"e2e failed"),
    ("agent:verify-wait",  r"smoke tests? (also )?failed"),
    ("agent:verify-wait",  r"tests? also failed"),
    ("agent:verify-wait",  r"gate.*failed"),
    ("agent:loop-restart", r"^\s*#\s*task\s"),
    ("agent:loop-restart", r"iteration \d+ of \d+"),
]
GAP_CATEGORY_REGEXES = [(cat, re.compile(pat, re.IGNORECASE)) for cat, pat in GAP_CATEGORY_PATTERNS]

# Minimum gap threshold — gaps below this are considered normal inter-turn
# latency, not meaningful overhead.
GAP_THRESHOLD_MS = 30_000


def _normalize_tool_name(raw: str) -> str:
    """Map a tool_use.name to a stable category suffix."""
    lower = (raw or "").lower().replace("_", "")
    if lower in KNOWN_TOOLS:
        return lower
    return "other"


# ─── Session file discovery ─────────────────────────────────────────


def _find_session_files(project_path: Path, change_name: str) -> list[Path]:
    """Find session JSONL files for a change's worktree directory only.

    Drilldown intentionally excludes the project-dir sessions — those contain
    orchestrator-side verifier sessions launched by `run_claude_logged()`, which
    are already represented in the main timeline as `llm:review`/`llm:spec_verify`
    spans from `LLM_CALL` events. Including them here would double-count and
    mix orchestrator work into the per-change agent breakdown.

    Returns absolute paths sorted by mtime ascending.
    """
    state = load_state(_state_path(project_path))
    files: list[Path] = []
    for change in state.changes:
        if change.name != change_name:
            continue
        if change.worktree_path:
            wt_dir = Path.home() / ".claude" / "projects" / f"-{_claude_mangle(change.worktree_path)}"
            if wt_dir.is_dir():
                for f in wt_dir.iterdir():
                    if f.is_file() and f.suffix == ".jsonl":
                        files.append(f)
        break
    files.sort(key=lambda p: p.stat().st_mtime)
    return files


def _find_sibling_session_files(parent_session: Path) -> list[Path]:
    """Return all sibling .jsonl files in the same Claude projects dir as `parent_session`."""
    parent_dir = parent_session.parent
    if not parent_dir.is_dir():
        return []
    return sorted(
        [f for f in parent_dir.iterdir() if f.is_file() and f.suffix == ".jsonl" and f != parent_session],
        key=lambda p: p.stat().st_mtime,
    )


# ─── Session file parsing ───────────────────────────────────────────


def _parse_session_file(path: Path) -> list[dict]:
    """Parse a Claude session JSONL into normalized entries.

    Each returned entry dict has:
        type:        "user" | "assistant" | "attachment" | "queue-operation" | other
        ts:          ISO 8601 timestamp string (or "" if missing)
        ts_ms:       int epoch milliseconds (0 if unparseable)
        uuid:        entry uuid (str)
        parent_uuid: parent uuid (str)
        request_id:  request id (str, may be empty)
        tool_uses:   list[(id, name)] for assistant entries
        tool_results: list[id] for user entries
        text_first200: first 200 chars of any user text content (for sub-agent matching)
        usage:       dict (model, tokens) for assistant entries
        raw:         original entry dict (for top-N preview rendering)
    """
    entries: list[dict] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug("session %s: skipping malformed line", path.name)
                    continue
                ts = raw.get("timestamp", "")
                ts_ms = _ts_to_ms(ts)
                norm: dict[str, Any] = {
                    "type": raw.get("type", ""),
                    "ts": ts,
                    "ts_ms": ts_ms,
                    "uuid": raw.get("uuid", ""),
                    "parent_uuid": raw.get("parentUuid", ""),
                    "request_id": raw.get("requestId", ""),
                    "tool_uses": [],
                    "tool_results": [],
                    "text_first200": "",
                    "usage": {},
                    "raw": raw,
                }
                msg = raw.get("message") or {}
                content = msg.get("content") if isinstance(msg, dict) else None
                if isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        btype = block.get("type", "")
                        if btype == "tool_use":
                            tid = block.get("id", "")
                            tname = block.get("name", "")
                            norm["tool_uses"].append((tid, tname, block.get("input", {})))
                        elif btype == "tool_result":
                            norm["tool_results"].append(block.get("tool_use_id", ""))
                        elif btype == "text" and norm["type"] == "user" and not norm["text_first200"]:
                            norm["text_first200"] = (block.get("text", "") or "")[:200]
                elif isinstance(content, str) and norm["type"] == "user" and not norm["text_first200"]:
                    norm["text_first200"] = content[:200]
                # `queue-operation` entries carry their payload in a top-level
                # `content` string field. Capture it into `text_first200` so
                # gap categorization can pattern-match against it without
                # needing to re-parse the raw dict.
                if raw.get("type") == "queue-operation":
                    qc = raw.get("content", "")
                    if isinstance(qc, str) and qc:
                        norm["text_first200"] = qc[:200]
                if isinstance(msg, dict):
                    usage = msg.get("usage") or {}
                    if isinstance(usage, dict):
                        norm["usage"] = {
                            "model": msg.get("model"),
                            "input_tokens": usage.get("input_tokens"),
                            "output_tokens": usage.get("output_tokens"),
                            "cache_read_tokens": usage.get("cache_read_input_tokens"),
                            "cache_create_tokens": usage.get("cache_creation_input_tokens"),
                        }
                entries.append(norm)
    except OSError as e:
        logger.warning("activity_detail: cannot read session %s: %s", path, e)
        return []
    # Drop entries without a parseable timestamp (e.g., `last-prompt` markers).
    # They have no temporal meaning and would distort wall-time computation.
    entries = [e for e in entries if e["ts_ms"] > 0]
    entries.sort(key=lambda e: e["ts_ms"])
    return entries


# ─── Sub-span builders ──────────────────────────────────────────────


def _build_llm_wait_spans(entries: list[dict], session_id: str) -> list[dict]:
    """Emit agent:llm-wait spans for time the LLM is producing output.

    Includes:
        user → assistant       (initial response after a user message)
        attachment → assistant (response after a file attachment)
        assistant → assistant  (multi-message streaming continuation, same requestId)
    """
    spans: list[dict] = []
    prev = None
    for e in entries:
        if e["type"] == "assistant" and prev is not None and prev["type"] in ("user", "assistant", "attachment"):
            start_ms = prev["ts_ms"]
            end_ms = e["ts_ms"]
            if 0 < end_ms - start_ms < 30 * 60 * 1000:  # cap 30min outliers
                spans.append({
                    "category": "agent:llm-wait",
                    "start": prev["ts"],
                    "end": e["ts"],
                    "duration_ms": end_ms - start_ms,
                    "detail": {
                        "session": session_id,
                        "kind": "stream" if prev["type"] == "assistant" else "response",
                        **{k: v for k, v in e.get("usage", {}).items() if v is not None},
                    },
                })
        prev = e
    return spans


def _build_tool_spans(entries: list[dict], session_id: str) -> list[dict]:
    """Emit agent:tool:<name> spans for each tool_use → matching tool_result pair.

    Special case: `Agent` / `Task` tool calls (sub-agent dispatches) become
    `agent:subagent:<slugified-purpose>` instead of `agent:tool:agent`. Current
    Claude Code runs sub-agents in-process; their internal turns are NOT logged
    to a separate session jsonl, so linking via filesystem matching is rarely
    possible. The description field of the tool input is used as the purpose label.
    """
    spans: list[dict] = []
    pending: dict[str, tuple[str, dict, dict]] = {}  # tool_use_id → (raw_name, entry, input)
    for e in entries:
        if e["type"] == "assistant":
            for tid, tname, tinput in e["tool_uses"]:
                if tid:
                    pending[tid] = (tname, e, tinput)
        elif e["type"] == "user":
            for tid in e["tool_results"]:
                if tid in pending:
                    raw_name, start_entry, tinput = pending.pop(tid)
                    norm_name = _normalize_tool_name(raw_name)
                    start_ms = start_entry["ts_ms"]
                    end_ms = e["ts_ms"]
                    if not (0 <= end_ms - start_ms < 60 * 60 * 1000):  # cap 1h outliers
                        continue
                    detail: dict = {
                        "session": session_id,
                        "tool": raw_name,
                    }
                    if isinstance(tinput, dict):
                        for k in ("command", "file_path", "pattern", "url", "query", "path", "description"):
                            if isinstance(tinput.get(k), str):
                                detail["preview"] = tinput[k][:60]
                                break
                    # Sub-agent dispatch → distinct top-level category
                    if norm_name in SUBAGENT_TOOL_NAMES:
                        purpose = ""
                        if isinstance(tinput, dict):
                            purpose = (tinput.get("description") or tinput.get("subagent_type") or tinput.get("prompt") or "")[:200]
                        slug = _slugify_purpose(purpose) or "agent"
                        category = f"agent:subagent:{slug}"
                        if purpose:
                            detail["purpose"] = purpose[:200]
                    else:
                        category = f"agent:tool:{norm_name}"
                    spans.append({
                        "category": category,
                        "start": start_entry["ts"],
                        "end": e["ts"],
                        "duration_ms": end_ms - start_ms,
                        "detail": detail,
                    })
    return spans


# ─── Sub-agent linking ──────────────────────────────────────────────


def _link_subagents(
    parent_session: Path,
    parent_entries: list[dict],
    parent_session_id: str,
    tool_spans: list[dict],
) -> list[dict]:
    """Replace agent:tool:task spans with agent:subagent:* spans where matchable.

    Walks Task tool_use blocks in the parent and looks for sibling sessions
    whose first user content matches the prompt prefix and whose first entry
    timestamp is within 5 seconds of the tool_use timestamp.

    Returns a NEW list of spans with the substitutions applied.
    """
    siblings = _find_sibling_session_files(parent_session)
    if not siblings:
        return list(tool_spans)

    # Pre-parse sibling first entries (cheap — only first ~5 lines per file)
    sibling_first: list[tuple[Path, int, str]] = []
    for sf in siblings:
        try:
            with open(sf, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if raw.get("type") != "user":
                        continue
                    msg = raw.get("message") or {}
                    content = msg.get("content") if isinstance(msg, dict) else None
                    text = ""
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text = block.get("text", "")
                                break
                    elif isinstance(content, str):
                        text = content
                    if text:
                        sibling_first.append((sf, _ts_to_ms(raw.get("timestamp", "")), text[:200]))
                        break
        except OSError:
            continue

    # Build a quick lookup from parent's Agent/Task tool_uses → tool_use_id
    task_by_id: dict[str, tuple[int, str]] = {}  # tool_use_id → (start_ms, prompt_prefix)
    for e in parent_entries:
        if e["type"] != "assistant":
            continue
        for tid, tname, tinput in e["tool_uses"]:
            if (tname or "").lower() in SUBAGENT_TOOL_NAMES and tid:
                prompt = ""
                if isinstance(tinput, dict):
                    prompt = (tinput.get("prompt") or tinput.get("description") or "")[:200]
                task_by_id[tid] = (e["ts_ms"], prompt)

    if not task_by_id:
        return list(tool_spans)

    # For each subagent span (already categorized as agent:subagent:* by
    # _build_tool_spans, or legacy agent:tool:task/agent), try to match a sibling
    # session and enhance with the subagent_session_id link.
    legacy_subagent_categories = {f"agent:tool:{n}" for n in SUBAGENT_TOOL_NAMES}
    result: list[dict] = []
    used_siblings: set[Path] = set()
    matched_count = 0
    unmatched_count = 0
    for span in tool_spans:
        is_subagent = (
            span["category"].startswith("agent:subagent:")
            or span["category"] in legacy_subagent_categories
        )
        if not is_subagent:
            result.append(span)
            continue
        # Find the matching task by start timestamp (closest <= 100ms diff)
        span_start_ms = _ts_to_ms(span["start"])
        best_tid = None
        best_diff = 1_000_000
        for tid, (start_ms, _prompt) in task_by_id.items():
            diff = abs(start_ms - span_start_ms)
            if diff < best_diff:
                best_diff = diff
                best_tid = tid
        if best_tid is None or best_diff > 1000:
            result.append(span)
            unmatched_count += 1
            continue
        _, prompt_prefix = task_by_id[best_tid]
        # Search siblings for a match
        match: Optional[tuple[Path, int]] = None
        for sf, sf_first_ms, sf_first_text in sibling_first:
            if sf in used_siblings:
                continue
            if abs(sf_first_ms - span_start_ms) > 5000:
                continue
            if not prompt_prefix:
                continue
            # Substring match in either direction (sub-agent prompt may be wrapped)
            if prompt_prefix[:80] in sf_first_text or sf_first_text[:80] in prompt_prefix:
                match = (sf, sf_first_ms)
                break
        if match is None:
            logger.warning(
                "activity_detail: unmatched Task in session %s — prompt prefix: %r",
                parent_session_id, prompt_prefix[:60],
            )
            result.append(span)
            unmatched_count += 1
            continue
        # Build the subagent span using the sub-session's wall window
        sf, _sf_start_ms = match
        used_siblings.add(sf)
        sub_entries = _parse_session_file(sf)
        if not sub_entries:
            result.append(span)
            continue
        sub_start_ts = sub_entries[0]["ts"]
        sub_end_ts = sub_entries[-1]["ts"]
        sub_dur_ms = sub_entries[-1]["ts_ms"] - sub_entries[0]["ts_ms"]
        # Derive a purpose label from the prompt prefix (first 30 chars, slugified)
        purpose = _slugify_purpose(prompt_prefix)
        result.append({
            "category": f"agent:subagent:{purpose}",
            "start": sub_start_ts,
            "end": sub_end_ts,
            "duration_ms": max(sub_dur_ms, span["duration_ms"]),
            "detail": {
                "session": parent_session_id,
                "subagent_session_id": sf.stem,
                "subagent_session_path": str(sf),
                "prompt_preview": prompt_prefix[:60],
            },
        })
        matched_count += 1

    if matched_count or unmatched_count:
        logger.info(
            "activity_detail: subagent linking — matched=%d unmatched=%d session=%s",
            matched_count, unmatched_count, parent_session_id,
        )
    return result


def _slugify_purpose(text: str) -> str:
    """Slugify the first words of a prompt into a purpose label."""
    if not text:
        return "task"
    words = []
    for word in text.split()[:3]:
        cleaned = "".join(c for c in word.lower() if c.isalnum())
        if cleaned:
            words.append(cleaned)
        if len(words) >= 3:
            break
    return "-".join(words) or "task"


# ─── Per-session sub-span build ─────────────────────────────────────


def _is_verifier_session(entries: list[dict]) -> bool:
    """Detect whether a session jsonl is a verifier session (should be skipped).

    Verifier sessions are launched by `run_claude_logged()` from the orchestrator
    (verifier.py / engine.py / profile_types.py) with a prompt prefixed
    `[PURPOSE:<type>:<change>]`. Their time is already shown on the main
    timeline as `llm:<type>` spans from LLM_CALL events; including them in the
    drilldown would double-count the same wall time.
    """
    for e in entries:
        if e.get("type") != "user":
            continue
        text = e.get("text_first200", "") or ""
        return bool(VERIFIER_PURPOSE_RE.match(text))
    return False


def _categorize_gap(next_prompt: str) -> str:
    """Classify a time gap by pattern-matching the user/queue prompt that follows it."""
    if not next_prompt:
        return "agent:gap"
    for category, regex in GAP_CATEGORY_REGEXES:
        if regex.search(next_prompt):
            return category
    return "agent:gap"


def _build_gap_spans(entries: list[dict], existing_spans: list[dict], session_id: str) -> list[dict]:
    """Emit one sub-span per non-trivial time gap not covered by an existing span.

    Walks consecutive entry pairs. For each gap > GAP_THRESHOLD_MS not fully
    contained inside an existing llm-wait/tool/subagent span, emits a span
    categorized by the prompt content that appears after the gap.

    This replaces the old single `agent:overhead` span that covered the
    entire session wall — with per-gap spans we keep exact start/end
    timestamps AND a semantic label for each gap, so the timeline shows
    WHERE and WHY time was spent, not just HOW MUCH.
    """
    if len(entries) < 2:
        return []

    # Build a sorted list of covered intervals from existing spans so we can
    # check containment in O(log n) — but the number of spans is usually small
    # enough that a linear scan is fine.
    covered: list[tuple[int, int]] = []
    for s in existing_spans:
        s_start = _ts_to_ms(s.get("start", ""))
        s_end = _ts_to_ms(s.get("end", ""))
        if s_end > s_start:
            covered.append((s_start, s_end))
    covered.sort()

    def _is_covered(gap_start: int, gap_end: int) -> bool:
        """True if an existing span fully encloses [gap_start, gap_end]."""
        for cs, ce in covered:
            if cs <= gap_start and ce >= gap_end:
                return True
            if cs > gap_start:
                break  # sorted → no later span can start earlier
        return False

    result: list[dict] = []
    for i in range(len(entries) - 1):
        a = entries[i]
        b = entries[i + 1]
        a_ms = a["ts_ms"]
        b_ms = b["ts_ms"]
        gap_ms = b_ms - a_ms
        if gap_ms < GAP_THRESHOLD_MS:
            continue
        if _is_covered(a_ms, b_ms):
            continue

        # Look at the first user/queue-operation entry in the next few to get the
        # prompt content that caused the gap to end. queue-operation entries
        # carry the enqueued prompt directly; user entries carry text_first200.
        next_prompt = ""
        for j in range(i + 1, min(i + 6, len(entries))):
            nt = entries[j].get("type", "")
            if nt in ("user", "queue-operation"):
                text = entries[j].get("text_first200", "") or ""
                if text:
                    next_prompt = text
                    break
        category = _categorize_gap(next_prompt)
        result.append({
            "category": category,
            "start": a["ts"],
            "end": b["ts"],
            "duration_ms": gap_ms,
            "detail": {
                "session": session_id,
                "next_prompt": next_prompt[:160],
            },
        })
    return result


def _build_sub_spans_for_session(session_path: Path) -> list[dict]:
    """Build all sub-spans for a single session jsonl file.

    Verifier sessions (prefix `[PURPOSE:*]`) are skipped to avoid double-counting
    time that's already visible on the main timeline as `llm:*` spans.

    For agent sessions, the residual time between spans is broken down into
    per-gap spans with a semantic category (review-wait, verify-wait,
    loop-restart, gap) based on the prompt that follows each gap. This replaces
    the old single `agent:overhead` span which hid the gap timing and cause.
    """
    entries = _parse_session_file(session_path)
    if len(entries) < 2:
        return []
    session_id = session_path.stem

    # Skip verifier sessions outright — their wall time is the same wall time
    # shown on the main timeline as llm:review/llm:spec_verify/llm:replan.
    if _is_verifier_session(entries):
        logger.debug("activity_detail: skipping verifier session %s", session_id)
        return []

    llm_spans = _build_llm_wait_spans(entries, session_id)
    tool_spans = _build_tool_spans(entries, session_id)
    tool_spans = _link_subagents(session_path, entries, session_id, tool_spans)

    sub_spans = list(llm_spans) + list(tool_spans)
    gap_spans = _build_gap_spans(entries, sub_spans, session_id)
    sub_spans.extend(gap_spans)

    return sub_spans


def _union_duration_ms(spans: list[dict]) -> int:
    """Compute the union duration (in ms) of a list of spans, handling overlap."""
    intervals = []
    for s in spans:
        start_ms = _ts_to_ms(s.get("start", ""))
        end_ms = _ts_to_ms(s.get("end", ""))
        if end_ms > start_ms:
            intervals.append((start_ms, end_ms))
    if not intervals:
        return 0
    intervals.sort()
    merged = [list(intervals[0])]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return sum(end - start for start, end in merged)


# ─── Cache file ─────────────────────────────────────────────────────


def _cache_path(project_path: Path) -> Path:
    return project_path / "set" / "orchestration" / "activity-detail.jsonl"


def _is_cache_valid(cache_path: Path, session_files: list[Path]) -> bool:
    if not cache_path.is_file():
        return False
    cache_mtime = cache_path.stat().st_mtime
    for sf in session_files:
        try:
            if sf.stat().st_mtime > cache_mtime:
                return False
        except OSError:
            return False
    return True


def _load_cache(cache_path: Path) -> Optional[list[dict]]:
    """Load cache file. Returns None on parse error (caller should rebuild)."""
    if not cache_path.is_file():
        return None
    spans: list[dict] = []
    try:
        with open(cache_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                spans.append(json.loads(line))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("activity_detail: corrupted cache at %s — deleting and rebuilding (%s)", cache_path, e)
        try:
            cache_path.unlink()
        except OSError:
            pass
        return None
    return spans


def _write_cache(cache_path: Path, sub_spans: list[dict]) -> None:
    """Atomically write the cache file as JSONL."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            for span in sub_spans:
                f.write(json.dumps(span) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, cache_path)
    except OSError as e:
        logger.warning("activity_detail: failed to write cache at %s: %s", cache_path, e)
        try:
            tmp.unlink()
        except OSError:
            pass


def _build_sub_spans_for_change(
    project_path: Path,
    change_name: str,
) -> tuple[list[dict], bool]:
    """Build (or load from cache) all sub-spans for a change. Returns (spans, cache_hit)."""
    session_files = _find_session_files(project_path, change_name)
    if not session_files:
        return [], False
    cache = _cache_path(project_path)
    # Per-change cache key — partition cache by change name
    # Cache filename carries a format version suffix so old caches written
    # with a different schema (e.g., the pre-gap-categorization `agent:overhead`
    # format) are naturally ignored after a code upgrade.
    cache_for_change = cache.with_name(f"activity-detail-v2-{change_name}.jsonl")
    if _is_cache_valid(cache_for_change, session_files):
        cached = _load_cache(cache_for_change)
        if cached is not None:
            return cached, True
    # Full rebuild for this change
    all_spans: list[dict] = []
    for sf in session_files:
        all_spans.extend(_build_sub_spans_for_session(sf))
    all_spans.sort(key=lambda s: s.get("start", ""))
    _write_cache(cache_for_change, all_spans)
    return all_spans, False


# ─── Time helpers ───────────────────────────────────────────────────


def _ts_to_ms(ts: str) -> int:
    if not ts:
        return 0
    try:
        return int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)
    except (ValueError, AttributeError):
        return 0


def _clip_and_filter(
    sub_spans: list[dict],
    from_ts: Optional[str],
    to_ts: Optional[str],
) -> list[dict]:
    """Filter sub-spans to the requested time window, clipping partial overlaps."""
    if not from_ts and not to_ts:
        return sub_spans
    from_ms = _ts_to_ms(from_ts) if from_ts else 0
    to_ms = _ts_to_ms(to_ts) if to_ts else 2**63 - 1
    result = []
    for s in sub_spans:
        s_start = _ts_to_ms(s.get("start", ""))
        s_end = _ts_to_ms(s.get("end", ""))
        if s_end < from_ms or s_start > to_ms:
            continue
        clipped = dict(s)
        if s_start < from_ms:
            clipped["start"] = from_ts
            clipped["duration_ms"] = max(0, s_end - from_ms)
        if s_end > to_ms:
            clipped["end"] = to_ts
            clipped["duration_ms"] = max(0, _ts_to_ms(clipped["end"]) - _ts_to_ms(clipped["start"]))
        result.append(clipped)
    return result


# ─── Aggregates for the response ────────────────────────────────────


def _compute_aggregates(sub_spans: list[dict]) -> dict:
    """Compute headline counts + top operations for the response."""
    total_llm = sum(1 for s in sub_spans if s["category"] == "agent:llm-wait")
    total_tools = sum(1 for s in sub_spans if s["category"].startswith("agent:tool:"))
    subagent_count = sum(1 for s in sub_spans if s["category"].startswith("agent:subagent:"))

    # Top 5 longest individual operations (excluding llm-wait and overhead)
    candidates = [s for s in sub_spans if not s["category"].startswith("agent:llm-wait") and s["category"] != "agent:overhead"]
    candidates.sort(key=lambda s: s.get("duration_ms", 0), reverse=True)
    top = []
    for s in candidates[:5]:
        top.append({
            "category": s["category"],
            "duration_ms": s.get("duration_ms", 0),
            "preview": (s.get("detail") or {}).get("preview", "") or (s.get("detail") or {}).get("prompt_preview", ""),
            "tool": (s.get("detail") or {}).get("tool", ""),
        })

    return {
        "total_llm_calls": total_llm,
        "total_tool_calls": total_tools,
        "subagent_count": subagent_count,
        "top_operations": top,
    }


# ─── API endpoint ───────────────────────────────────────────────────


@router.get("/api/{project}/activity-timeline/session-detail")
def get_session_detail(
    project: str,
    change: str = Query(...),
    from_ts: Optional[str] = Query(None, alias="from"),
    to_ts: Optional[str] = Query(None, alias="to"),
):
    """Drilldown: typed sub-spans inside an implementing window for one change."""
    if not change:
        raise HTTPException(status_code=400, detail="change query param required")
    project_path = _resolve_project(project)
    sub_spans, cache_hit = _build_sub_spans_for_change(project_path, change)
    if not sub_spans:
        logger.warning("activity_detail: no session jsonls for change=%s in project=%s", change, project)
        return {
            "sub_spans": [],
            "total_llm_calls": 0,
            "total_tool_calls": 0,
            "top_operations": [],
            "subagent_count": 0,
            "cache_hit": cache_hit,
        }
    clipped = _clip_and_filter(sub_spans, from_ts, to_ts)
    agg = _compute_aggregates(clipped)
    return {
        "sub_spans": clipped,
        "cache_hit": cache_hit,
        **agg,
    }
