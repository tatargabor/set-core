"""Hook event handlers: SessionStart, UserPrompt, PostTool, Stop routing.

1:1 migration of lib/hooks/events.sh.
"""

import json
import os
import re
import subprocess
import sys
from typing import Optional

from .util import (
    _log,
    _dbg,
    read_cache,
    write_cache,
    metrics_timer_start,
    metrics_timer_elapsed,
    metrics_append,
    extract_scores,
    METRICS_ENABLED,
    CHECKPOINT_INTERVAL,
)
from .session import (
    dedup_clear,
    dedup_check,
    dedup_add,
    make_dedup_key,
    increment_turn,
    get_last_checkpoint_turn,
)
from .memory_ops import (
    recall_memories,
    proactive_context,
    load_matching_rules,
    extract_query,
    output_hook_context,
    get_last_context_ids,
)
from .stop import (
    flush_metrics,
    extract_insights,
    save_commit_memories,
    save_checkpoint,
)


def handle_event(event: str, input_data: dict, cache_file: str, **kwargs) -> Optional[str]:
    """Route by event type. Returns JSON output string or None."""
    handlers = {
        "SessionStart": handle_session_start,
        "UserPromptSubmit": handle_user_prompt,
        "PreToolUse": handle_pre_tool,
        "PostToolUse": handle_post_tool,
        "PostToolUseFailure": handle_post_tool_failure,
        "SubagentStart": handle_subagent_start,
        "SubagentStop": handle_subagent_stop,
        "Stop": handle_stop,
    }

    handler = handlers.get(event)
    if handler is None:
        _dbg(event, f"unknown event: {event}")
        return None

    return handler(input_data, cache_file, **kwargs)


def handle_session_start(
    input_data: dict, cache_file: str, **kwargs
) -> Optional[str]:
    """SessionStart: dedup clear, cheat sheet recall, project context recall."""
    metrics_timer_start()
    source = input_data.get("source", "")
    _dbg("SessionStart", f"source={source}")

    if source in ("startup", "clear"):
        dedup_clear(cache_file)

    # Cheat sheet recall
    cheat_sheet = _recall_cheat_sheet()

    # Proactive project context
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    project_name = os.path.basename(project_dir)
    recent_files = _get_recent_files(project_dir)

    proactive_query = f"Project: {project_name}. Changed files: {recent_files}"
    project_ctx = proactive_context(proactive_query, cache_file, limit=5)

    # Build output
    output_parts = []
    if cheat_sheet:
        output_parts.append(f"=== OPERATIONAL CHEAT SHEET ===\n{cheat_sheet}")
    if project_ctx:
        output_parts.append(f"=== PROJECT CONTEXT ===\n{project_ctx}")

    if not output_parts:
        dur = metrics_timer_elapsed()
        metrics_append(cache_file, "L1", "SessionStart", proactive_query, 0, 0, [], dur, 0, 0)
        return None

    output_text = "\n\n".join(output_parts)
    tok_est = len(output_text) // 4
    dur = metrics_timer_elapsed()
    context_ids = get_last_context_ids()
    metrics_append(
        cache_file, "L1", "SessionStart", proactive_query,
        len(context_ids), len(context_ids), [], dur, tok_est, 0, context_ids,
    )

    return output_hook_context("SessionStart", output_text)


def handle_user_prompt(
    input_data: dict, cache_file: str, **kwargs
) -> Optional[str]:
    """UserPromptSubmit: topic recall, rules matching, frustration detection."""
    metrics_timer_start()
    prompt = input_data.get("prompt", "")
    _dbg("UserPromptSubmit", f"prompt='{prompt[:120]}'")
    if not prompt:
        return None

    # Turn counter
    turn_count = increment_turn(cache_file)
    last_checkpoint = get_last_checkpoint_turn(cache_file)

    # Checkpoint trigger
    if turn_count - last_checkpoint >= CHECKPOINT_INTERVAL:
        save_checkpoint(cache_file, turn_count, last_checkpoint)

    # Frustration detection
    emotion_result = _detect_frustration(input_data, cache_file, kwargs.get("set_tools_root", ""))
    emotion_inject = False
    emotion_warning = ""
    if emotion_result:
        level = emotion_result.get("level", "none")
        triggers = ", ".join(emotion_result.get("triggers", []))
        emotion_inject = emotion_result.get("inject", False)
        should_save = emotion_result.get("save", False)

        if should_save:
            _save_frustration_memory(level, prompt, triggers)

        if emotion_inject:
            if level == "high":
                emotion_warning = f"\u26a0 EMOTION DETECTED: The user appears strongly frustrated (triggers: {triggers}). Acknowledge their concern directly. Be extra careful and avoid repeating previous mistakes."
            elif level == "moderate":
                emotion_warning = f"\u26a0 EMOTION DETECTED: The user appears frustrated (triggers: {triggers}). Acknowledge their concern. Be extra careful with this task."
            else:
                emotion_warning = f"Note: The user may be slightly frustrated (triggers: {triggers}). Pay attention to their concern."

    # Extract change name from skill invocation
    change_name = _extract_change_name(prompt)

    query = f"{change_name} {prompt[:200]}" if change_name else prompt[:200]

    # Proactive recall
    formatted = proactive_context(query, cache_file, limit=5)

    # Load mandatory rules
    rules_block = load_matching_rules(prompt)

    # Build output
    parts = []
    if rules_block:
        parts.append(rules_block)
    if emotion_warning:
        parts.append(emotion_warning)
    if formatted:
        memory_section = "=== PROJECT MEMORY — If any memory below directly answers the user's question, cite it in your response ==="
        if change_name:
            memory_section += f"\nChange: {change_name}"
        memory_section += f"\nRelevant past experience:\n{formatted}\n=== END ==="
        parts.append(memory_section)

    if not parts:
        dur = metrics_timer_elapsed()
        metrics_append(cache_file, "L2", "UserPromptSubmit", query[:200], 0, 0, [], dur, 0, 0)
        return None

    context_text = "\n".join(parts)
    tok_est = len(context_text) // 4
    dur = metrics_timer_elapsed()
    context_ids = get_last_context_ids()
    metrics_append(
        cache_file, "L2", "UserPromptSubmit", query[:200],
        len(context_ids), len(context_ids), [], dur, tok_est, 0, context_ids,
    )

    return output_hook_context("UserPromptSubmit", context_text)


def handle_pre_tool(input_data: dict, cache_file: str, **kwargs) -> Optional[str]:
    """PreToolUse — disabled (memory recall removed)."""
    _dbg("PreToolUse", "disabled, skipping")
    return None


def handle_post_tool(
    input_data: dict, cache_file: str, **kwargs
) -> Optional[str]:
    """PostToolUse: file/command context recall, commit save."""
    metrics_timer_start()
    tool_name = input_data.get("tool_name", "")
    _dbg("PostToolUse", f"tool={tool_name}")

    if tool_name not in ("Read", "Bash"):
        return None

    # Bash → check for git commit
    if tool_name == "Bash":
        cmd = input_data.get("tool_input", {}).get("command", "")[:300]
        if "git commit" in cmd:
            _commit_save(input_data, cache_file)

    query = extract_query(input_data)
    if not query:
        return None

    # Dedup check
    key = make_dedup_key("PostToolUse", tool_name, query)
    if dedup_check(cache_file, key):
        dur = metrics_timer_elapsed()
        metrics_append(cache_file, "L3", "PostToolUse", query[:200], 0, 0, [], dur, 0, 1)
        return None

    formatted = recall_memories(query, cache_file, limit=2, mode="hybrid")
    if not formatted:
        dur = metrics_timer_elapsed()
        metrics_append(cache_file, "L3", "PostToolUse", query[:200], 0, 0, [], dur, 0, 0)
        return None

    dedup_add(cache_file, key)
    output_text = f"=== MEMORY: Context for this file/command ===\n{formatted}"
    tok_est = len(output_text) // 4
    dur = metrics_timer_elapsed()
    context_ids = get_last_context_ids()
    metrics_append(
        cache_file, "L3", "PostToolUse", query[:200],
        len(context_ids), len(context_ids), [], dur, tok_est, 0, context_ids,
    )

    return output_hook_context("PostToolUse", output_text)


def handle_post_tool_failure(
    input_data: dict, cache_file: str, **kwargs
) -> Optional[str]:
    """PostToolUseFailure: error fix surfacing."""
    metrics_timer_start()
    is_interrupt = input_data.get("is_interrupt", False)
    error_text = input_data.get("error", "")[:300]

    if is_interrupt or len(error_text) < 10:
        return None

    formatted = recall_memories(error_text, cache_file, limit=3, mode="hybrid")
    if not formatted:
        dur = metrics_timer_elapsed()
        metrics_append(cache_file, "L4", "PostToolUseFailure", error_text[:200], 0, 0, [], dur, 0, 0)
        return None

    output_text = f"=== MEMORY: Past fix for this error ===\n{formatted}"
    tok_est = len(output_text) // 4
    dur = metrics_timer_elapsed()
    context_ids = get_last_context_ids()
    metrics_append(
        cache_file, "L4", "PostToolUseFailure", error_text[:200],
        len(context_ids), len(context_ids), [], dur, tok_est, 0, context_ids,
    )

    return output_hook_context("PostToolUseFailure", output_text)


def handle_subagent_start(
    input_data: dict, cache_file: str, **kwargs
) -> Optional[str]:
    """SubagentStart: proactive recall based on task description."""
    ti = input_data.get("tool_input", {})
    task_desc = ti.get("prompt", "") or ti.get("description", "") or ""
    task_desc = task_desc[:300]

    if not task_desc:
        return None

    formatted = proactive_context(task_desc, cache_file, limit=3)
    if not formatted:
        return None

    return output_hook_context(
        "SubagentStart", f"=== MEMORY: Context for subagent ===\n{formatted}"
    )


def handle_subagent_stop(
    input_data: dict, cache_file: str, **kwargs
) -> Optional[str]:
    """SubagentStop: proactive recall from agent transcript summary."""
    agent_path = input_data.get("agent_transcript_path", "")
    if not agent_path:
        return None

    agent_path = os.path.expanduser(agent_path)
    if not os.path.isfile(agent_path):
        return None

    summary = _extract_agent_summary(agent_path)
    if not summary:
        return None

    formatted = proactive_context(summary, cache_file, limit=2)
    if not formatted:
        return None

    return output_hook_context(
        "SubagentStop", f"=== MEMORY: Context from subagent ===\n{formatted}"
    )


def handle_stop(
    input_data: dict, cache_file: str, **kwargs
) -> Optional[str]:
    """Stop: transcript extraction + commit-based extraction."""
    stop_active = input_data.get("stop_hook_active", False)
    if stop_active:
        _dbg("Stop", "already active, skipping")
        return None

    # Check for no-op marker
    noop_marker = ".claude/loop-iteration-noop"
    if os.path.isfile(noop_marker):
        try:
            import time
            with open(noop_marker, "r") as f:
                marker_ts = f.read().strip()
            from set_orch.loop_state import parse_date_to_epoch
            marker_epoch = parse_date_to_epoch(marker_ts)
            now_epoch = int(time.time())
            age = now_epoch - marker_epoch
            if marker_epoch > 0 and age < 3600:
                _log("Stop", f"Skipping memory save — no-op iteration (age: {age}s)")
                os.remove(noop_marker)
                flush_metrics(
                    cache_file,
                    input_data.get("session_id", "unknown"),
                    kwargs.get("transcript_path", ""),
                    kwargs.get("set_tools_root", ""),
                )
                dedup_clear(cache_file)
                return None
            os.remove(noop_marker)
        except Exception:
            pass

    session_id = input_data.get("session_id", "unknown")
    transcript_path = input_data.get("transcript_path", "")
    if transcript_path:
        transcript_path = os.path.expanduser(transcript_path)

    # Flush metrics
    flush_metrics(
        cache_file,
        session_id,
        transcript_path,
        kwargs.get("set_tools_root", ""),
    )

    # Clear metrics from cache
    cache = read_cache(cache_file)
    cache.pop("_metrics", None)
    write_cache(cache_file, cache)

    # Clean dedup
    dedup_clear(cache_file)

    # Background transcript extraction
    if transcript_path and os.path.isfile(transcript_path):
        change_name = _extract_change_from_transcript(transcript_path)
        extract_insights(transcript_path, change_name)

    # Commit extraction
    save_commit_memories()

    return None


# ─── Internal helpers ─────────────────────────────────────────


def _recall_cheat_sheet() -> str:
    """Recall cheat sheet memories."""
    try:
        result = subprocess.run(
            [
                "wt-memory",
                "recall",
                "cheat-sheet operational",
                "--tags",
                "cheat-sheet",
                "--limit",
                "5",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return ""
        memories = json.loads(result.stdout)
    except Exception:
        return ""

    if not memories:
        return ""

    seen = set()
    lines = []
    for m in memories:
        c = m.get("content", "").replace("\n", " ").strip()
        if len(c) < 20:
            continue
        key = c[:50]
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"  - {c}")

    return "\n".join(lines)


def _get_recent_files(project_dir: str) -> str:
    """Get recently changed files from git."""
    try:
        result = subprocess.run(
            ["git", "-C", project_dir, "diff", "--name-only", "HEAD~5", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            files = result.stdout.strip().splitlines()[:10]
            return ", ".join(files)

        # Fallback: unstaged changes
        result = subprocess.run(
            ["git", "-C", project_dir, "diff", "--name-only"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            files = result.stdout.strip().splitlines()[:10]
            return ", ".join(files)
    except Exception:
        pass
    return ""


def _detect_frustration(input_data: dict, cache_file: str, set_tools_root: str) -> Optional[dict]:
    """Run frustration detection on prompt."""
    if not set_tools_root:
        return None

    prompt = input_data.get("prompt", "")
    if not prompt:
        return None

    try:
        if set_tools_root not in sys.path:
            sys.path.insert(0, set_tools_root)
        from lib.frustration import detect

        cache = read_cache(cache_file)
        history = cache.get("frustration_history", {"count": 0, "last_level": "none"})

        result = detect(prompt, session_history=history)

        cache["frustration_history"] = history
        write_cache(cache_file, cache)

        return result
    except Exception:
        return None


def _save_frustration_memory(level: str, prompt: str, triggers: str) -> None:
    """Save frustration memory."""
    if level == "high":
        tags = "frustration,high-priority,source:emotion-detect"
        prefix = "\U0001f534 User frustrated (high)"
    else:
        tags = "frustration,recurring,source:emotion-detect"
        prefix = "\u26a0\ufe0f User frustrated (moderate)"

    content = f"{prefix}: {prompt[:500]}"
    try:
        subprocess.run(
            ["wt-memory", "remember", "--type", "Learning", "--tags", tags],
            input=content,
            text=True,
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass


def _extract_change_name(prompt: str) -> str:
    """Extract change name from opsx/openspec skill invocation."""
    pattern = r"(?:opsx:(?:apply|continue|verify|archive|sync|ff|new)|openspec-(?:apply|continue|verify|archive|sync|ff|new)[\w-]*)\s+(\S+)"
    m = re.search(pattern, prompt)
    return m.group(1) if m else ""


def _commit_save(input_data: dict, cache_file: str) -> None:
    """Save git commit message as memory."""
    cmd = input_data.get("tool_input", {}).get("command", "")
    desc = input_data.get("tool_input", {}).get("description", "")

    save_content = ""

    # Heredoc pattern
    heredoc_m = re.search(r"cat\s*<<\s*['\"]?(\w+)['\"]?", cmd)
    if heredoc_m:
        marker = heredoc_m.group(1)
        lines = cmd.split("\n")
        in_heredoc = False
        msg_lines = []
        for line in lines:
            if in_heredoc:
                stripped = line.strip()
                if stripped == marker or stripped in (
                    f"{marker})",
                    f"'{marker}'",
                    f'{marker}"',
                ):
                    break
                if stripped and stripped not in (")", ')"', ")'"):
                    msg_lines.append(stripped)
            elif re.search(r"cat\s*<<", line):
                in_heredoc = True
        if msg_lines:
            save_content = f"Committed: {msg_lines[0][:200]}"

    # Simple -m "message"
    if not save_content:
        m = re.search(r'git commit.*?-m\s+["\']([^"\']+)["\']', cmd)
        if m:
            save_content = f"Committed: {m.group(1)[:200]}"

    # Fallback to description
    if not save_content and desc:
        save_content = f"Committed: {desc[:200]}"

    if not save_content:
        return

    key = make_dedup_key("WriteSave", "commit", save_content)
    if dedup_check(cache_file, key):
        return

    try:
        subprocess.run(
            [
                "wt-memory",
                "remember",
                "--type",
                "Learning",
                "--tags",
                "phase:commit-save,source:hook",
            ],
            input=save_content,
            text=True,
            capture_output=True,
            timeout=5,
        )
        dedup_add(cache_file, key)
        _log("PostToolUse", f"commit_save: {save_content[:80]}")
    except Exception:
        pass


def _extract_agent_summary(agent_path: str) -> str:
    """Extract last few assistant text entries from agent transcript."""
    entries = []
    try:
        with open(agent_path, "r", errors="replace") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    if obj.get("type") == "assistant":
                        for block in obj.get("message", {}).get("content", []) or []:
                            if isinstance(block, dict) and block.get("type") == "text":
                                entries.append(block.get("text", "")[:200])
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    return " ".join(entries[-3:])[:500]


def _extract_change_from_transcript(transcript_path: str) -> str:
    """Extract change names from transcript."""
    names = set()
    try:
        with open(transcript_path, "r", errors="replace") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    if obj.get("type") != "assistant":
                        continue
                    for block in obj.get("message", {}).get("content", []) or []:
                        if not isinstance(block, dict):
                            continue
                        if (
                            block.get("type") == "tool_use"
                            and block.get("name") == "Skill"
                        ):
                            inp = block.get("input", {})
                            skill = inp.get("skill", "")
                            if "opsx:" in skill or "openspec-" in skill:
                                args = inp.get("args", "").strip()
                                if args:
                                    names.add(args.split()[0])
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass

    if names:
        return sorted(names)[0]
    return "unknown"
