"""Hook stop pipeline: metrics flush, transcript extraction, commit-based memory save.

1:1 migration of lib/hooks/stop.sh.
"""

import json
import os
import re
import subprocess
from typing import Optional

from .util import _log, _dbg, read_cache, write_cache
from .session import dedup_clear


def flush_metrics(
    cache_file: str,
    session_id: str,
    transcript_path: str = "",
    wt_tools_root: str = "",
) -> None:
    """Collect session metrics, call lib.metrics.flush_session()."""
    cache = read_cache(cache_file)
    metrics = cache.get("_metrics", [])
    if not metrics:
        _dbg("stop", "metrics: no data")
        return

    injected_content = cache.get("_injected_content", {})

    # Resolve project name
    project = "unknown"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            project = os.path.basename(result.stdout.strip())
    except Exception:
        pass

    # Import lib.metrics (add wt_tools_root to path if needed)
    import sys

    if wt_tools_root and wt_tools_root not in sys.path:
        sys.path.insert(0, wt_tools_root)

    try:
        from lib.metrics import flush_session, scan_transcript_citations

        # Scan transcript for citations + passive matches
        citations = []
        mem_matches = []
        if transcript_path and os.path.exists(transcript_path):
            results = scan_transcript_citations(
                transcript_path, session_id, injected_content
            )
            for r in results:
                if r.get("context_id"):
                    mem_matches.append(r)
                else:
                    citations.append(r)

        flush_session(session_id, project, metrics, citations, mem_matches)
        _log("stop", f"metrics: flushed {len(metrics)} records")
    except ImportError:
        _dbg("stop", "metrics: lib.metrics not available")
    except Exception as e:
        _dbg("stop", f"metrics: error: {e}")


def extract_insights(transcript_path: str, change_name: str = "unknown") -> int:
    """Scan JSONL transcript, filter entries, save as memories.

    Returns number of entries saved.
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return 0

    entries = _filter_transcript(transcript_path)
    if not entries:
        return 0

    base_tags = "raw,phase:auto-extract,source:hook"
    if change_name != "unknown":
        base_tags = f"{base_tags},change:{change_name}"

    saved = 0
    total = len(entries)

    for i, entry in enumerate(entries, 1):
        role = entry["role"]
        content = entry["content"]
        prefix = f"[session:{change_name}, turn {i}/{total}] "
        full_content = prefix + content

        mem_type = "Context" if role == "user" else "Learning"
        tags = base_tags
        if _HEURISTIC_RE.search(content):
            tags = f"{tags},volatile"

        try:
            subprocess.run(
                ["wt-memory", "remember", "--type", mem_type, "--tags", tags],
                input=full_content,
                text=True,
                capture_output=True,
                timeout=5,
            )
            saved += 1
        except Exception:
            pass

    _log("stop", f"raw-filter: saved {saved}/{total} entries")
    return saved


def save_commit_memories(wt_tools_root: str = "") -> int:
    """Find git commits in session, save with source:commit tag.

    Returns number of commits saved.
    """
    marker_file = ".wt-tools/.last-memory-commit"
    design_marker = ".wt-tools/.saved-designs"
    codemap_marker = ".wt-tools/.saved-codemaps"

    last_hash = ""
    if os.path.isfile(marker_file):
        try:
            with open(marker_file, "r") as f:
                last_hash = f.read().strip()
        except OSError:
            pass

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return 0
        current_hash = result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        return 0

    if current_hash == last_hash:
        return 0

    # Get commits
    if last_hash:
        try:
            subprocess.run(
                ["git", "cat-file", "-t", last_hash],
                capture_output=True,
                timeout=5,
            )
            result = subprocess.run(
                ["git", "log", "--oneline", f"{last_hash}..HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            result = subprocess.run(
                ["git", "log", "--oneline", "-1"],
                capture_output=True,
                text=True,
                timeout=10,
            )
    else:
        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            capture_output=True,
            text=True,
            timeout=10,
        )

    if result.returncode != 0:
        return 0

    saved = 0
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split(" ", 1)
        if len(parts) < 2:
            continue
        commit_hash, msg = parts

        change_name = "general"
        if ":" in msg:
            change_name = msg.split(":")[0]

        # Save design choices if available
        _save_design_choices(change_name, design_marker)
        saved += 1

    # Update marker
    os.makedirs(os.path.dirname(marker_file), exist_ok=True)
    try:
        with open(marker_file, "w") as f:
            f.write(current_hash)
    except OSError:
        pass

    return saved


def save_checkpoint(
    cache_file: str,
    turn_count: int,
    last_checkpoint: int,
) -> bool:
    """Periodic summary of files/topics (every N turns). Returns True if saved."""
    cache = read_cache(cache_file)
    metrics = cache.get("_metrics", [])

    files_read = set()
    commands_run = 0
    topics = []
    l2_count = 0

    for m in metrics:
        if m.get("event") == "UserPromptSubmit":
            l2_count += 1
            if l2_count <= last_checkpoint:
                continue
            q = m.get("query", "")
            if q and len(q) > 10:
                words = q.split()[:6]
                topics.append(" ".join(words))
        elif m.get("event") == "PostToolUse" and l2_count > last_checkpoint:
            q = m.get("query", "")
            if "/" in q and not q.startswith("git "):
                files_read.add(q)
            elif q:
                commands_run += 1

    parts = []
    if files_read:
        flist = ", ".join(sorted(files_read)[:8])
        if len(files_read) > 8:
            flist += f" (+{len(files_read) - 8} more)"
        parts.append(f"Files: {flist}")
    if commands_run:
        parts.append(f"Commands: {commands_run}")
    if topics:
        seen = set()
        unique = []
        for t in topics:
            key = t[:30].lower()
            if key not in seen:
                seen.add(key)
                unique.append(t[:60])
        if unique:
            parts.append(f"Topics: {chr(10).join(unique[:5])}")

    if not parts:
        parts.append("(conversation-only, no tool activity)")

    summary = (
        f"[session checkpoint, turns {last_checkpoint + 1}-{turn_count}] "
        + " | ".join(parts)
    )
    summary = summary[:800]

    try:
        subprocess.run(
            [
                "wt-memory",
                "remember",
                "--type",
                "Context",
                "--tags",
                "phase:checkpoint,source:hook",
            ],
            input=summary,
            text=True,
            capture_output=True,
            timeout=5,
        )
        _log("stop", f"checkpoint: saved turns {last_checkpoint + 1}-{turn_count}")

        # Update last_checkpoint_turn
        from .session import set_last_checkpoint_turn

        set_last_checkpoint_turn(cache_file, turn_count)
        return True
    except Exception:
        return False


# ─── Internal helpers ─────────────────────────────────────────

_HEURISTIC_RE = re.compile(
    "|".join(
        re.escape(p)
        for p in [
            "false positive",
            "same pattern",
            "known pattern",
            "known issue",
            "was a false",
            "unlike previous",
            "same issue as",
            "this is not a real",
        ]
    ),
    re.IGNORECASE,
)


def _filter_transcript(transcript_path: str) -> list:
    """Parse JSONL transcript, return filtered entries."""
    entries = []
    file_read_counts = {}

    try:
        with open(transcript_path, "r", errors="replace") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                t = obj.get("type", "")

                if t == "user":
                    msg = obj.get("message", {})
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        # Strip system reminders
                        content = re.sub(
                            r"<system-reminder>.*?</system-reminder>",
                            "",
                            content,
                            flags=re.DOTALL,
                        ).strip()
                        content = re.sub(
                            r"<(?:local-command[\w-]*|command-name|command-message|command-args)>.*?</(?:local-command[\w-]*|command-name|command-message|command-args)>",
                            "",
                            content,
                            flags=re.DOTALL,
                        ).strip()
                        if len(content) >= 15:
                            entries.append(
                                {"role": "user", "content": content[:2000]}
                            )

                elif t == "assistant":
                    msg = obj.get("message", {})
                    for block in msg.get("content", []) or []:
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") == "text":
                            text = block.get("text", "").strip()
                            if len(text) >= 50:
                                entries.append(
                                    {"role": "assistant", "content": text[:2000]}
                                )
                        elif block.get("type") == "tool_use":
                            name = block.get("name", "")
                            inp = block.get("input", {})
                            if name == "Read":
                                fp = inp.get("file_path", "")
                                file_read_counts[fp] = (
                                    file_read_counts.get(fp, 0) + 1
                                )
                                if file_read_counts[fp] > 2:
                                    continue
                            if name == "Bash":
                                cmd = inp.get("command", "")[:200]
                                if cmd:
                                    entries.append(
                                        {
                                            "role": "assistant",
                                            "content": f"[Bash] {cmd}",
                                        }
                                    )

                elif t == "tool_result":
                    content = obj.get("content", "")
                    if isinstance(content, str):
                        cl = content.lower()
                        if (
                            "error" in cl
                            or "failed" in cl
                            or "traceback" in cl
                        ) and len(content) >= 15:
                            entries.append(
                                {
                                    "role": "assistant",
                                    "content": f"[Error] {content[:500]}",
                                }
                            )
    except OSError:
        pass

    return entries


def _save_design_choices(change_name: str, design_marker: str) -> None:
    """Extract and save design choices from design.md."""
    design_file = f"openspec/changes/{change_name}/design.md"
    if not os.path.isfile(design_file):
        return

    # Check marker
    if os.path.isfile(design_marker):
        try:
            with open(design_marker, "r") as f:
                if change_name in f.read():
                    return
        except OSError:
            pass

    try:
        with open(design_file, "r") as f:
            content = f.read()
    except OSError:
        return

    choices = []
    for line in content.splitlines():
        if line.startswith("**Choice**"):
            choice = line.replace("**Choice**:", "").replace("**Choice**", "").strip()
            if choice:
                choices.append(choice)

    if choices:
        text = f"{change_name}: {'. '.join(choices)}"
        if len(text) > 300:
            text = text[:297] + "..."
        try:
            subprocess.run(
                [
                    "wt-memory",
                    "remember",
                    "--type",
                    "Decision",
                    "--tags",
                    f"change:{change_name},phase:apply,source:hook,decisions",
                ],
                input=text,
                text=True,
                capture_output=True,
                timeout=5,
            )
        except Exception:
            pass

    # Update marker
    os.makedirs(os.path.dirname(design_marker) or ".", exist_ok=True)
    try:
        with open(design_marker, "a") as f:
            f.write(f"{change_name}\n")
    except OSError:
        pass
