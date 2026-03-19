#!/usr/bin/env python3
"""
set-core MCP Server

Exposes set-core functionality to Claude Code and other MCP clients.
Enables agents to see worktree status, Ralph loop status, and team activity.
"""

import subprocess
import json
import os
import re
import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# FastMCP for simple MCP server creation
from fastmcp import FastMCP

# Logging to stderr (stdout is reserved for JSON-RPC protocol)
import logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

mcp = FastMCP(name="set-core")

# Project root - where set-core is installed
SET_TOOLS_ROOT = Path(__file__).parent.parent
SCRIPT_DIR = SET_TOOLS_ROOT / "bin"
CONFIG_DIR = Path.home() / ".config" / "set-core"
PROJECTS_FILE = CONFIG_DIR / "projects.json"


def run_command(cmd: list[str], cwd: str = None) -> str:
    """Run a shell command and return output"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=cwd or str(SET_TOOLS_ROOT)
        )
        if result.returncode == 0:
            return result.stdout.strip() if result.stdout else "(no output)"
        else:
            return f"Error (exit {result.returncode}): {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out"
    except Exception as e:
        return f"Error: {str(e)}"


def get_projects() -> dict:
    """Load projects from set-core config"""
    if not PROJECTS_FILE.exists():
        return {}
    try:
        data = json.loads(PROJECTS_FILE.read_text())
        return data.get("projects", {})
    except Exception as e:
        logger.error(f"Error reading projects: {e}")
        return {}


def get_worktrees_for_project(project_path: str) -> list[dict]:
    """Get all worktrees for a project using git"""
    worktrees = []
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=project_path
        )
        if result.returncode != 0:
            return []

        current_wt = {}
        for line in result.stdout.strip().split("\n"):
            if line.startswith("worktree "):
                if current_wt:
                    worktrees.append(current_wt)
                current_wt = {"path": line[9:]}
            elif line.startswith("branch "):
                current_wt["branch"] = line[7:]
            elif line.startswith("HEAD "):
                current_wt["head"] = line[5:]

        if current_wt:
            worktrees.append(current_wt)

    except Exception as e:
        logger.error(f"Error getting worktrees for {project_path}: {e}")

    return worktrees


def get_ralph_state(wt_path: str) -> Optional[dict]:
    """Read Ralph loop state from a worktree"""
    state_file = Path(wt_path) / ".set" / "loop-state.json"
    if not state_file.exists():
        return None

    try:
        return json.loads(state_file.read_text())
    except Exception as e:
        logger.error(f"Error reading Ralph state from {state_file}: {e}")
        return None


def get_activity_state(wt_path: str) -> Optional[dict]:
    """Read activity state from a worktree"""
    activity_file = Path(wt_path) / ".set" / "activity.json"
    if not activity_file.exists():
        return None

    try:
        return json.loads(activity_file.read_text())
    except Exception as e:
        logger.error(f"Error reading activity from {activity_file}: {e}")
        return None


def is_activity_stale(activity: dict, stale_minutes: int = 5) -> bool:
    """Check if activity data is stale (older than stale_minutes)"""
    updated_at = activity.get("updated_at", "")
    if not updated_at:
        return True
    try:
        updated = updated_at.replace("+", "Z").split("Z")[0]
        updated_dt = datetime.fromisoformat(updated)
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        elapsed = now_utc - updated_dt
        return elapsed.total_seconds() > stale_minutes * 60
    except Exception:
        return True


def format_duration(started_at: str) -> str:
    """Format duration from ISO timestamp to human readable"""
    try:
        # Parse ISO format with timezone
        started = started_at.replace("+", "Z").split("Z")[0]
        start_dt = datetime.fromisoformat(started)
        elapsed = datetime.now() - start_dt

        hours = int(elapsed.total_seconds() // 3600)
        mins = int((elapsed.total_seconds() % 3600) // 60)

        if hours > 0:
            return f"{hours}h {mins}m"
        return f"{mins}m"
    except Exception:
        return "?"


# ============================================================================
# TOOLS - Actions that agents can perform
# ============================================================================

@mcp.tool
def list_worktrees() -> str:
    """List all git worktrees across all projects.

    Shows worktree path, branch, and status for each active worktree.
    """
    projects = get_projects()
    if not projects:
        return "No projects configured in set-core"

    lines = ["Git Worktrees:", ""]

    for name, info in projects.items():
        project_path = info.get("path", "")
        if not project_path or not Path(project_path).exists():
            continue

        worktrees = get_worktrees_for_project(project_path)
        if len(worktrees) <= 1:  # Only main worktree
            continue

        lines.append(f"  {name}:")
        for wt in worktrees:
            wt_path = wt.get("path", "")
            branch = wt.get("branch", "").replace("refs/heads/", "")

            # Skip main worktree
            if wt_path == project_path:
                continue

            # Check for Ralph loop
            ralph_state = get_ralph_state(wt_path)
            ralph_indicator = ""
            if ralph_state:
                status = ralph_state.get("status", "")
                if status == "running":
                    ralph_indicator = " [Ralph running]"
                elif status == "done":
                    ralph_indicator = " [Ralph done]"
                elif status == "stuck":
                    ralph_indicator = " [Ralph stuck]"

            # Extract change-id from path
            wt_name = Path(wt_path).name
            lines.append(f"    - {wt_name}: {branch}{ralph_indicator}")

    return "\n".join(lines) if len(lines) > 2 else "No active worktrees"


@mcp.tool
def get_ralph_status(change_id: str = None) -> str:
    """Get Ralph loop status for a worktree.

    Args:
        change_id: Optional change ID to check. If not provided, shows all active loops.

    Returns status including: running/stopped, iteration count, last activity.
    """
    projects = get_projects()
    if not projects:
        return "No projects configured"

    all_loops = []

    for name, info in projects.items():
        project_path = info.get("path", "")
        if not project_path or not Path(project_path).exists():
            continue

        worktrees = get_worktrees_for_project(project_path)

        for wt in worktrees:
            wt_path = wt.get("path", "")
            if wt_path == project_path:
                continue

            ralph_state = get_ralph_state(wt_path)
            if not ralph_state:
                continue

            loop_change_id = ralph_state.get("change_id", "")

            # Filter by change_id if specified
            if change_id and loop_change_id != change_id:
                continue

            status = ralph_state.get("status", "unknown")
            iteration = ralph_state.get("current_iteration", 0)
            max_iter = ralph_state.get("max_iterations", 0)
            task = ralph_state.get("task", "")[:60]
            started = ralph_state.get("started_at", "")

            # Status emoji
            status_icon = {
                "running": "🔄",
                "done": "✅",
                "stuck": "⚠️",
                "stopped": "⏹️",
                "starting": "🚀"
            }.get(status, "❓")

            duration = format_duration(started) if started else "?"

            loop_info = {
                "project": name,
                "change_id": loop_change_id,
                "status": status,
                "status_icon": status_icon,
                "iteration": iteration,
                "max_iterations": max_iter,
                "task": task,
                "duration": duration,
                "wt_path": wt_path
            }
            all_loops.append(loop_info)

    if not all_loops:
        if change_id:
            return f"No Ralph loop found for: {change_id}"
        return "No active Ralph loops"

    # Format output
    lines = ["Ralph Loop Status:", ""]

    for loop in all_loops:
        lines.append(f"  {loop['status_icon']} {loop['change_id']} ({loop['project']})")
        lines.append(f"     Status: {loop['status']}")
        lines.append(f"     Iteration: {loop['iteration']}/{loop['max_iterations']}")
        lines.append(f"     Running for: {loop['duration']}")
        lines.append(f"     Task: {loop['task']}...")
        lines.append("")

    return "\n".join(lines)


@mcp.tool
def get_worktree_tasks(worktree_path: str) -> str:
    """Get tasks for a worktree.

    Args:
        worktree_path: Path to the worktree directory.

    Returns the tasks.md content showing implementation progress.
    """
    wt_path = Path(worktree_path)

    # Prefer worktree root
    root_tasks = wt_path / "tasks.md"
    if root_tasks.exists():
        return root_tasks.read_text()

    # Fallback: search subdirectories (maxdepth 3), excluding archive/node_modules
    for tasks_file in sorted(wt_path.rglob("tasks.md"), key=lambda p: len(p.parts)):
        rel = tasks_file.relative_to(wt_path)
        if len(rel.parts) > 3:
            continue
        if any(part in ("archive", "node_modules") for part in rel.parts):
            continue
        return tasks_file.read_text()

    return "No tasks file found in this worktree"


@mcp.tool
def get_team_status() -> str:
    """Get team member activity from set-control.

    Shows which team members are active, what they're working on,
    and their current agent status (idle/working).
    """
    # Read from the GUI's team data cache if available
    team_cache = Path.home() / ".cache" / "set-core" / "team_status.json"
    if team_cache.exists():
        try:
            data = json.loads(team_cache.read_text())
            lines = ["Team Status:", ""]
            for member in data.get("members", []):
                status = member.get("agent_status", "idle")
                change = member.get("change_id", "none")
                name = member.get("member_full", member.get("member", "?"))
                broadcast = member.get("broadcast")
                line = f"  {name}: {status} - working on: {change}"
                if broadcast:
                    line += f" | broadcast: {broadcast}"
                lines.append(line)
            return "\n".join(lines) if len(lines) > 2 else "No team members found"
        except Exception as e:
            return f"Error reading team status: {e}"

    return "Team status not available (GUI not running or no team sync)"


@mcp.tool
def get_activity(change_id: str = None) -> str:
    """Get agent activity from all local worktrees.

    Reads .set/activity.json from each worktree to show what agents
    are currently doing. This is the fast path for same-machine coordination.

    Args:
        change_id: Optional change ID to filter by. If not provided, shows all.

    Returns activity including: skill, skill_args, broadcast, staleness.
    """
    projects = get_projects()
    if not projects:
        return "No projects configured"

    all_activity = []

    for name, info in projects.items():
        project_path = info.get("path", "")
        if not project_path or not Path(project_path).exists():
            continue

        worktrees = get_worktrees_for_project(project_path)

        for wt in worktrees:
            wt_path = wt.get("path", "")
            branch = wt.get("branch", "").replace("refs/heads/", "")

            activity = get_activity_state(wt_path)
            if not activity:
                continue

            # Derive change_id from branch or worktree name
            wt_change_id = Path(wt_path).name if wt_path != project_path else branch

            # Filter by change_id if specified
            if change_id and wt_change_id != change_id:
                continue

            stale = is_activity_stale(activity)

            entry = {
                "project": name,
                "worktree": wt_path,
                "change_id": wt_change_id,
                "skill": activity.get("skill"),
                "skill_args": activity.get("skill_args"),
                "broadcast": activity.get("broadcast"),
                "updated_at": activity.get("updated_at"),
                "stale": stale,
            }
            all_activity.append(entry)

    if not all_activity:
        if change_id:
            return f"No agent activity found for: {change_id}"
        return "No agent activity found"

    # Sort by updated_at (most recent first)
    all_activity.sort(
        key=lambda x: x.get("updated_at") or "",
        reverse=True,
    )

    # Format output
    lines = ["Agent Activity:", ""]

    for act in all_activity:
        stale_tag = " (stale)" if act["stale"] else ""
        skill_str = act["skill"] or "unknown"
        if act["skill_args"]:
            skill_str += f" {act['skill_args']}"

        lines.append(f"  {act['change_id']} ({act['project']}){stale_tag}")
        lines.append(f"     Skill: {skill_str}")
        if act["broadcast"]:
            lines.append(f"     Broadcast: {act['broadcast']}")
        lines.append(f"     Updated: {act['updated_at'] or '?'}")
        lines.append(f"     Path: {act['worktree']}")
        lines.append("")

    return "\n".join(lines)


def _get_member_name() -> str:
    """Get the current member name (user@hostname) matching set-control-sync format"""
    try:
        result = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True)
        user_name = result.stdout.strip() if result.returncode == 0 else os.environ.get("USER", "unknown")
    except Exception:
        user_name = os.environ.get("USER", "unknown")
    try:
        result = subprocess.run(["hostname", "-s"], capture_output=True, text=True)
        hostname = result.stdout.strip()
    except Exception:
        import socket
        hostname = socket.gethostname().split(".")[0]
    user_clean = user_name.lower().replace(" ", "-")
    user_clean = re.sub(r"[^a-z0-9-]", "", user_clean)
    return f"{user_clean}@{hostname.lower()}"


def _find_control_worktree() -> Optional[Path]:
    """Find the first project's .set-control worktree"""
    projects = get_projects()
    for name, info in projects.items():
        project_path = info.get("path", "")
        if project_path:
            control = Path(project_path) / ".set-control"
            if control.exists():
                return control
    return None


def _find_control_worktree_for_project(project_name: str) -> Optional[Path]:
    """Find .set-control for a specific project"""
    projects = get_projects()
    info = projects.get(project_name, {})
    project_path = info.get("path", "")
    if project_path:
        control = Path(project_path) / ".set-control"
        if control.exists():
            return control
    return None


def _resolve_project_name() -> Optional[str]:
    """Resolve the project name for messaging (first available project)"""
    projects = get_projects()
    for name, info in projects.items():
        project_path = info.get("path", "")
        if project_path:
            control = Path(project_path) / ".set-control"
            if control.exists():
                return name
    return None


@mcp.tool
def send_message(recipient: str, message: str) -> str:
    """Send a directed message to another agent or team member.

    Appends the message to the local outbox file. The message is delivered
    on the next sync cycle (~15 seconds). Zero additional git operations.

    Args:
        recipient: Target member name (e.g., "tg@linux" or "tg@linux/change-id").
        message: Message text (supports multiline).

    Returns confirmation or error message.
    """
    project_name = _resolve_project_name()
    if not project_name:
        return "Error: No project with set-control found"

    control = _find_control_worktree()
    if not control:
        return "Error: No .set-control worktree found"

    # Use set-control-chat with --no-push
    try:
        cmd = [
            str(SCRIPT_DIR / "set-control-chat"),
            "--path", str(control.parent),
            "--no-push",
            "send", recipient, message
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            msg_id = str(uuid.uuid4())[:8]
            return json.dumps({
                "status": "queued",
                "id": msg_id,
                "delivery": "next sync cycle (~15s)"
            })
        else:
            error = result.stderr.strip() or result.stdout.strip()
            return f"Error: {error}"
    except Exception as e:
        return f"Error sending message: {e}"


@mcp.tool
def get_inbox(since: str = None) -> str:
    """Get directed messages for the current agent.

    Reads local outbox files (no git operations). Messages are filtered
    to those addressed to the current member.

    Args:
        since: Optional ISO timestamp to filter messages (e.g., "2026-02-08T08:00:00Z").

    Returns formatted inbox messages or "No messages".
    """
    project_name = _resolve_project_name()
    if not project_name:
        return "Error: No project with set-control found"

    control = _find_control_worktree()
    if not control:
        return "Error: No .set-control worktree found"

    # Use set-control-chat to read messages
    try:
        cmd = [
            str(SCRIPT_DIR / "set-control-chat"),
            "--path", str(control.parent),
            "--json",
            "read"
        ]
        if since:
            cmd.extend(["--since", since])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            messages = json.loads(result.stdout)
            if not messages:
                return "No messages"

            # Format as readable text
            lines = []
            for msg in messages:
                ts = msg.get("ts", "")[:19].replace("T", " ")
                sender = msg.get("from", "?")
                text = msg.get("text", "[encrypted]")
                lines.append(f"[{ts}] {sender}: {text}")
            return "\n".join(lines)
        else:
            error = result.stderr.strip() or result.stdout.strip()
            return f"Error: {error}"
    except Exception as e:
        return f"Error reading inbox: {e}"


# ============================================================================
# RESOURCES - Data that agents can read
# ============================================================================

@mcp.resource("set://worktrees")
def worktrees_resource() -> str:
    """Current worktree list as a resource"""
    return list_worktrees()


@mcp.resource("set://ralph/status")
def ralph_status_resource() -> str:
    """Current Ralph loop status as a resource"""
    return get_ralph_status()


@mcp.resource("set://team")
def team_resource() -> str:
    """Team member status as a resource"""
    return get_team_status()


# ============================================================================
# MEMORY TOOLS - Uses daemon client with CLI fallback
# ============================================================================

# Project dir for memory tools — set at registration time by set-project init
MEMORY_PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR")

# Lazy daemon client (one per process lifetime)
_memory_client = None


def _get_memory_client():
    """Get or create daemon client. Returns None if unavailable."""
    global _memory_client
    if _memory_client is not None:
        return _memory_client
    try:
        # Add set-core lib to path if needed
        lib_path = str(SET_TOOLS_ROOT / "lib")
        if lib_path not in sys.path:
            sys.path.insert(0, lib_path)
        from set_memoryd.client import MemoryClient
        _memory_client = MemoryClient.for_project(project_dir=MEMORY_PROJECT_DIR)
        return _memory_client
    except Exception:
        return None


def _run_memory_via_daemon(method: str, **params) -> str | None:
    """Try daemon first, return JSON string or None if unavailable."""
    client = _get_memory_client()
    if client is None:
        return None
    try:
        result = client.request(method, params)
        return json.dumps(result, indent=2) if result is not None else "(no output)"
    except Exception:
        return None


def _run_memory(args: list[str], input_text: str | None = None, timeout: int = 30) -> str:
    """Run a set-memory CLI command with project-scoped CWD (fallback path)."""
    try:
        result = subprocess.run(
            ["set-memory"] + args,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=MEMORY_PROJECT_DIR,
        )
        output = result.stdout.strip()
        if result.returncode != 0 and result.stderr:
            return f"Error: {result.stderr.strip()}"
        return output or "(no output)"
    except FileNotFoundError:
        return "Error: set-memory not found in PATH"
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"


def _run_memory_json(args: list[str], input_text: str | None = None) -> str:
    """Run a set-memory CLI command and return parsed JSON or raw output."""
    raw = _run_memory(args, input_text)
    try:
        parsed = json.loads(raw)
        return json.dumps(parsed, indent=2)
    except (json.JSONDecodeError, TypeError):
        return raw


# --- Core memory tools ---

@mcp.tool
def remember(content: str, type: str = "Learning", tags: str = "") -> str:
    """Save a memory. Types: Decision, Learning, Context. Tags: comma-separated."""
    result = _run_memory_via_daemon("remember", content=content, type=type, tags=tags)
    if result is not None:
        return result
    args = ["remember", "--type", type]
    if tags:
        args.extend(["--tags", tags])
    return _run_memory(args, input_text=content)


@mcp.tool
def recall(query: str, limit: int = 5, mode: str = "hybrid", tags: str = "") -> str:
    """Semantic search for memories. Modes: semantic, temporal, hybrid, causal, associative."""
    result = _run_memory_via_daemon("recall", query=query, limit=limit, mode=mode, tags=tags)
    if result is not None:
        return result
    args = ["recall", query, "--limit", str(limit), "--mode", mode]
    if tags:
        args.extend(["--tags", tags])
    return _run_memory_json(args)


@mcp.tool
def proactive_context(context: str, limit: int = 5) -> str:
    """Context-aware retrieval with relevance scores. Richer than recall."""
    result = _run_memory_via_daemon("proactive_context", context=context, limit=limit)
    if result is not None:
        return result
    return _run_memory_json(["proactive", context, "--limit", str(limit)])


@mcp.tool
def forget(id: str) -> str:
    """Delete a single memory by ID."""
    result = _run_memory_via_daemon("forget", id=id)
    if result is not None:
        return result
    return _run_memory(["forget", id])


@mcp.tool
def forget_by_tags(tags: str) -> str:
    """Delete all memories matching the given tags (comma-separated)."""
    result = _run_memory_via_daemon("forget_by_tags", tags=tags)
    if result is not None:
        return result
    return _run_memory(["forget", "--tags", tags])


@mcp.tool
def list_memories(type: str = "", limit: int = 20) -> str:
    """List memories. Optionally filter by type (Decision, Learning, Context)."""
    result = _run_memory_via_daemon("list", type=type, limit=limit)
    if result is not None:
        return result
    args = ["list", "--limit", str(limit)]
    if type:
        args.extend(["--type", type])
    return _run_memory_json(args)


@mcp.tool
def get_memory(id: str) -> str:
    """Get a single memory by ID (full details)."""
    result = _run_memory_via_daemon("get", id=id)
    if result is not None:
        return result
    return _run_memory_json(["get", id])


@mcp.tool
def context_summary(topic: str = "") -> str:
    """Condensed memory summary by category. Optionally filter by topic."""
    result = _run_memory_via_daemon("context_summary", topic=topic)
    if result is not None:
        return result
    args = ["context"]
    if topic:
        args.append(topic)
    return _run_memory(args)


@mcp.tool
def brain() -> str:
    """3-tier memory visualization (core/active/peripheral)."""
    result = _run_memory_via_daemon("brain")
    if result is not None:
        return result
    return _run_memory(["brain"])


@mcp.tool
def memory_stats() -> str:
    """Memory quality diagnostics: types, tags, importance distribution."""
    result = _run_memory_via_daemon("stats")
    if result is not None:
        return result
    return _run_memory_json(["stats", "--json"])


# --- Maintenance tools ---

@mcp.tool
def memory_health() -> str:
    """Check if shodh-memory is available and healthy."""
    result = _run_memory_via_daemon("health")
    if result is not None:
        return result
    return _run_memory(["health"])


@mcp.tool
def audit(threshold: float = 0.75) -> str:
    """Duplicate detection report. Lower threshold = stricter matching."""
    return _run_memory_json(["audit", "--threshold", str(threshold), "--json"])


@mcp.tool
def cleanup(threshold: float = 0.2, dry_run: bool = True) -> str:
    """Remove low-value memories. Set dry_run=False to actually delete."""
    args = ["cleanup", "--threshold", str(threshold)]
    if dry_run:
        args.append("--dry-run")
    return _run_memory(args)


@mcp.tool
def dedup(threshold: float = 0.75, dry_run: bool = True) -> str:
    """Remove duplicate memories. Set dry_run=False to actually delete."""
    args = ["dedup", "--threshold", str(threshold)]
    if dry_run:
        args.append("--dry-run")
    return _run_memory(args)


# --- Sync tools ---

@mcp.tool
def sync() -> str:
    """Push + pull memory sync in one step (git-based)."""
    return _run_memory(["sync"], timeout=60)


@mcp.tool
def sync_push() -> str:
    """Export and push memories to git remote."""
    return _run_memory(["sync", "push"], timeout=60)


@mcp.tool
def sync_pull(from_source: str = "") -> str:
    """Pull and import memories from git remote."""
    args = ["sync", "pull"]
    if from_source:
        args.extend(["--from", from_source])
    return _run_memory(args, timeout=60)


@mcp.tool
def sync_status() -> str:
    """Show memory sync state and remote sources."""
    return _run_memory(["sync", "status"])


# --- Export/Import tools ---

@mcp.tool
def export_memories() -> str:
    """Export all memories to JSON."""
    return _run_memory_json(["export"])


@mcp.tool
def import_memories(file_path: str, dry_run: bool = True) -> str:
    """Import memories from a JSON file. Set dry_run=False to actually import."""
    args = ["import", file_path]
    if dry_run:
        args.append("--dry-run")
    return _run_memory(args, timeout=60)


# --- Todo tools ---

@mcp.tool
def add_todo(content: str, tags: str = "") -> str:
    """Save a todo/idea for later. Fire-and-forget capture."""
    args = ["todo", "add"]
    if tags:
        args.extend(["--tags", tags])
    return _run_memory(args, input_text=content)


@mcp.tool
def list_todos() -> str:
    """List all open todos."""
    return _run_memory_json(["todo", "list", "--json"])


@mcp.tool
def complete_todo(id: str) -> str:
    """Mark a todo as done (deletes it). Supports ID prefix matching."""
    return _run_memory(["todo", "done", id])


# --- API parity tools ---

@mcp.tool
def verify_index() -> str:
    """Verify index integrity — find orphaned memories not in vector index."""
    result = _run_memory_via_daemon("verify_index")
    if result is not None:
        return result
    return _run_memory_json(["verify"])


@mcp.tool
def consolidation_report(since: str = "") -> str:
    """Memory consolidation report — strengthening/decay events."""
    result = _run_memory_via_daemon("consolidation_report", since=since)
    if result is not None:
        return result
    args = ["consolidation"]
    if since:
        args.extend(["--since", since])
    return _run_memory_json(args)


@mcp.tool
def graph_stats() -> str:
    """Knowledge graph statistics (node count, edge count, etc.)."""
    result = _run_memory_via_daemon("graph_stats")
    if result is not None:
        return result
    return _run_memory_json(["graph-stats"])


@mcp.tool
def recall_by_date(since: str = "", until: str = "", limit: int = 20) -> str:
    """Recall memories within a date range. ISO 8601 dates."""
    result = _run_memory_via_daemon("recall_by_date", since=since, until=until, limit=limit)
    if result is not None:
        return result
    args = ["recall", "--limit", str(limit)]
    if since:
        args.extend(["--since", since])
    if until:
        args.extend(["--until", until])
    return _run_memory_json(args)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    logger.info("Starting set-core MCP server...")
    mcp.run(transport="stdio")
