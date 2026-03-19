"""Hook memory operations: recall, proactive context, rules matching, output formatting.

1:1 migration of lib/hooks/memory-ops.sh.
Uses set-memoryd daemon client for fast recall (bypass CLI subprocess overhead).
Falls back to CLI subprocess if daemon is unavailable.
"""

import json
import os
import subprocess
from typing import Optional

from .util import (
    _log, _dbg, read_cache, write_cache, METRICS_ENABLED,
    get_daemon_client, daemon_is_running, HEURISTIC_RE,
)
from .session import gen_context_id, store_injected_content

# Minimum relevance score threshold
MIN_RELEVANCE = 0.3
MIN_CONTENT_LEN = 20


def recall_memories(
    query: str,
    cache_file: str,
    limit: int = 3,
    mode: str = "hybrid",
) -> Optional[str]:
    """Recall memories via daemon (fast) or CLI fallback. Returns formatted string or None."""
    _log("recall", f"query='{query[:80]}' mode={mode} limit={limit}")

    memories = None

    # Try daemon first
    client = get_daemon_client()
    if client is not None:
        try:
            memories = client.recall(query, limit=limit, mode=mode)
            _dbg("recall", "via daemon")
        except Exception as e:
            _dbg("recall", f"daemon error: {e}")

    # Fallback to CLI subprocess — but only if daemon is NOT running
    # (if daemon holds the RocksDB lock, CLI would fail with lock conflict)
    if memories is None and not daemon_is_running():
        try:
            result = subprocess.run(
                ["set-memory", "recall", query, "--limit", str(limit), "--mode", mode],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                _log("recall", "FAILED")
                return None
            memories = json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
            _log("recall", f"error: {e}")
            return None

    if not memories:
        return None

    return _format_memories(memories, cache_file, "recall")


def proactive_context(
    query: str,
    cache_file: str,
    limit: int = 5,
) -> Optional[str]:
    """Proactive context via daemon (fast) or CLI fallback. Returns formatted string or None."""
    _log("proactive", f"query='{query[:80]}' limit={limit}")

    memories = None

    # Try daemon first
    client = get_daemon_client()
    if client is not None:
        try:
            result = client.proactive_context(query, limit=limit)
            # Daemon returns {"memories": [...], ...} dict, extract the list
            if isinstance(result, dict):
                memories = result.get("memories", [])
            else:
                memories = result
            _dbg("proactive", "via daemon")
        except Exception as e:
            _dbg("proactive", f"daemon error: {e}")

    # Fallback to CLI — only if daemon is NOT running (RocksDB lock conflict)
    if memories is None and not daemon_is_running():
        try:
            result = subprocess.run(
                ["set-memory", "proactive", query, "--limit", str(limit)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                _log("proactive", "FAILED")
                return None
            raw = json.loads(result.stdout)
            if isinstance(raw, dict):
                memories = raw.get("memories", [])
            else:
                memories = raw
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
            _log("proactive", f"error: {e}")
            return None

    if not memories:
        return None

    return _format_memories(memories, cache_file, "proactive")


def load_matching_rules(prompt_text: str, project_root: str = "") -> str:
    """Read .claude/rules.yaml, match against prompt patterns. Returns rules block or empty."""
    if not project_root:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            project_root = result.stdout.strip() if result.returncode == 0 else os.getcwd()
        except (subprocess.TimeoutExpired, OSError):
            project_root = os.getcwd()

    rules_file = os.path.join(project_root, ".claude", "rules.yaml")
    if not os.path.isfile(rules_file):
        _dbg("rules", "no file")
        return ""

    try:
        import yaml
    except ImportError:
        _dbg("rules", "yaml not available")
        return ""

    try:
        with open(rules_file, "r") as f:
            data = yaml.safe_load(f)
    except Exception:
        return ""

    if not isinstance(data, dict):
        return ""
    rules = data.get("rules")
    if not isinstance(rules, list):
        return ""

    prompt_lower = prompt_text.lower()
    matched = []

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        topics = rule.get("topics") or []
        content = (rule.get("content") or "").strip()
        rid = rule.get("id") or ""
        if not topics or not content:
            continue

        hit = any(str(t).lower() in prompt_lower for t in topics)
        if hit:
            matched.append((rid, content))

    if not matched:
        _dbg("rules", "no matches")
        return ""

    lines = ["=== MANDATORY RULES ==="]
    for rid, content in matched:
        lines.append(f"[{rid}] {content}")
    lines.append("===========================")

    _log("rules", f"injecting {len(matched)} matching rule(s)")
    return "\n".join(lines)


def format_memory_output(header: str, formatted: str) -> str:
    """Format memory output with standard header."""
    return f"=== {header} ===\n{formatted}"


def extract_query(input_data: dict) -> str:
    """Extract a context-appropriate query from tool input data."""
    tool = input_data.get("tool_name", "")
    ti = input_data.get("tool_input", {})

    if tool in ("Read", "Edit", "Write"):
        fp = ti.get("file_path", "")
        parts = fp.rsplit("/", 2)
        return "/".join(parts[-2:]) if len(parts) >= 2 else fp
    elif tool == "Bash":
        return ti.get("command", "")[:200]
    elif tool == "Task":
        return ti.get("prompt", "")[:200]
    elif tool == "Grep":
        return ti.get("pattern", "")
    else:
        return (
            ti.get("file_path", "")
            or ti.get("command", "")
            or ti.get("prompt", "")
            or ti.get("pattern", "")
            or ""
        )


def output_hook_context(event_name: str, context_text: str) -> str:
    """Format hook output as JSON for Claude Code consumption."""
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": context_text,
        }
    })


def output_top_context(context_text: str) -> str:
    """Format top-level additional context as JSON."""
    return json.dumps({"additionalContext": context_text})


# ─── Internal helpers ─────────────────────────────────────────

# Track last context IDs for metrics (module-level state, reset per call)
_last_context_ids: list = []


def get_last_context_ids() -> list:
    """Get context IDs from last format_memories call."""
    return _last_context_ids


def _format_memories(memories: list, cache_file: str, source: str) -> Optional[str]:
    """Format and filter memories with dedup and relevance filtering."""
    global _last_context_ids
    _last_context_ids = []

    seen = set()
    lines = []
    context_ids = []
    content_map = {}

    for m in memories:
        # Relevance filter (proactive has scores)
        score = m.get("relevance_score")
        if score is not None and score != "N/A":
            try:
                if float(score) < MIN_RELEVANCE:
                    continue
            except (ValueError, TypeError):
                pass

        c = m.get("content", "").replace("\n", " ").strip()
        if len(c) < MIN_CONTENT_LEN:
            continue

        # Dedup by content prefix
        key = c[:50]
        if key in seen:
            continue
        seen.add(key)

        cid = gen_context_id(cache_file)
        context_ids.append(cid)
        content_map[cid] = c[:500]

        # Format score
        score_str = "?"
        if score is not None and score != "N/A":
            try:
                score_str = f"{float(score):.2f}"
            except (ValueError, TypeError):
                pass

        heur = "\u26a0\ufe0f HEURISTIC: " if HEURISTIC_RE.search(c) else ""
        lines.append(f"  - [MEM#{cid}] {heur}{c}")

    if not lines:
        return None

    # Store injected content for passive matching
    if METRICS_ENABLED:
        for cid, content in content_map.items():
            store_injected_content(cache_file, cid, content, True)

    _last_context_ids = context_ids
    return "\n".join(lines)
