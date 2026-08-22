#!/usr/bin/env python3
from __future__ import annotations
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
# MAIN
# ============================================================================

if __name__ == "__main__":
    logger.info("Starting set-core MCP server...")
    mcp.run(transport="stdio")
