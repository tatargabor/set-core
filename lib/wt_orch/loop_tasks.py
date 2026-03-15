"""Loop task detection: find tasks, check completion, manual tasks, done criteria.

1:1 migration of lib/loop/tasks.sh.
"""

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class TaskStatus:
    """Completion status of a tasks.md file."""

    total: int = 0
    done: int = 0
    pending: int = 0
    manual: int = 0
    percent: float = 0.0


@dataclass
class ManualTask:
    """A [?] task requiring human action."""

    id: str = ""
    description: str = ""
    type: str = "confirm"  # "confirm" or "input"
    input_key: str = ""


def find_tasks_file(wt_path: str) -> Optional[str]:
    """Search worktree for tasks.md (root → subdirs).

    Returns path to tasks.md or None if not found.
    """
    # Prefer worktree root
    root_tasks = os.path.join(wt_path, "tasks.md")
    if os.path.isfile(root_tasks):
        return root_tasks

    # Fallback: search in subdirectories (maxdepth 4), excluding archive/node_modules
    for root, dirs, files in os.walk(wt_path):
        # Limit depth to 4
        depth = root[len(wt_path) :].count(os.sep)
        if depth >= 4:
            dirs.clear()
            continue
        # Exclude archive and node_modules
        dirs[:] = [
            d for d in dirs if d not in ("archive", "node_modules", ".git", ".claude")
        ]
        if "tasks.md" in files:
            return os.path.join(root, "tasks.md")

    return None


def check_completion(wt_path: str, tasks_file: Optional[str] = None) -> TaskStatus:
    """Parse checkboxes in tasks.md, return TaskStatus."""
    if tasks_file is None:
        tasks_file = find_tasks_file(wt_path)
    if not tasks_file or not os.path.isfile(tasks_file):
        return TaskStatus()

    try:
        with open(tasks_file, "r") as f:
            content = f.read()
    except OSError:
        return TaskStatus()

    lines = content.splitlines()
    done = 0
    pending = 0
    manual = 0

    for line in lines:
        stripped = line.strip()
        # Done: - [x] or - [X]
        if re.match(r"^-\s*\[[xX]\]", stripped):
            done += 1
        # Pending auto-task: - [ ]
        elif re.match(r"^-\s*\[\s*\]", stripped):
            pending += 1
        # Manual task: - [?]
        elif re.match(r"^-\s*\[\?\]", stripped):
            manual += 1

    total = done + pending + manual
    percent = (done / total * 100.0) if total > 0 else 0.0

    return TaskStatus(
        total=total,
        done=done,
        pending=pending,
        manual=manual,
        percent=round(percent, 1),
    )


def find_manual_tasks(wt_path: str, tasks_file: Optional[str] = None) -> list:
    """Extract [?] tasks with type annotations. Returns list of ManualTask."""
    if tasks_file is None:
        tasks_file = find_tasks_file(wt_path)
    if not tasks_file or not os.path.isfile(tasks_file):
        return []

    try:
        with open(tasks_file, "r") as f:
            content = f.read()
    except OSError:
        return []

    results = []
    # Match: - [?] 3.3 Description [input:KEY] or [confirm]
    pattern = re.compile(
        r"^\s*-\s*\[\?\]\s+(\d+\.\d+)\s+(.*)", re.MULTILINE
    )

    for m in pattern.finditer(content):
        task_id = m.group(1)
        rest = m.group(2)
        task_type = "confirm"
        input_key = ""
        description = rest

        # Extract type annotation
        input_match = re.search(r"\[input:([^\]]+)\]", rest)
        confirm_match = re.search(r"\[confirm\]", rest)

        if input_match:
            task_type = "input"
            input_key = input_match.group(1)
            description = rest[: input_match.start()].rstrip()
        elif confirm_match:
            task_type = "confirm"
            description = rest[: confirm_match.start()].rstrip()

        results.append(
            ManualTask(
                id=task_id,
                description=description,
                type=task_type,
                input_key=input_key,
            )
        )

    return results


def is_done(
    wt_path: str,
    done_criteria: str = "tasks",
    target_change: str = "",
) -> bool:
    """Comprehensive done check (tasks complete OR archived OR marker)."""
    # Uncommitted work pre-check: all criteria except "manual"
    if done_criteria != "manual":
        from .git_utils import git_has_uncommitted_work

        has_uncommitted, summary = git_has_uncommitted_work(wt_path)
        if has_uncommitted:
            return False

    if done_criteria == "tasks":
        status = check_completion(wt_path)
        return status.pending == 0 and status.total > 0

    elif done_criteria == "openspec":
        from .loop_prompt import detect_next_change_action

        action = detect_next_change_action(wt_path, target_change)
        return action == "done"

    elif done_criteria == "manual":
        state_file = os.path.join(wt_path, ".claude", "loop-state.json")
        try:
            with open(state_file, "r") as f:
                data = json.load(f)
            return data.get("manual_done", False) is True
        except (OSError, json.JSONDecodeError):
            return False

    elif done_criteria == "build":
        return _check_build_done(wt_path)

    elif done_criteria == "merge":
        return _check_merge_done(wt_path)

    elif done_criteria == "test":
        return _check_test_done(wt_path)

    return False


def generate_fallback_tasks(wt_path: str, change_name: str) -> bool:
    """Generate a minimal fallback tasks.md when ff exhausted.

    Returns True if tasks.md was created, False if insufficient context.
    """
    change_dir = os.path.join(wt_path, "openspec", "changes", change_name)
    proposal_file = os.path.join(change_dir, "proposal.md")

    if not os.path.isfile(proposal_file):
        return False

    tasks_file = os.path.join(change_dir, "tasks.md")
    if os.path.isfile(tasks_file):
        return True  # Don't overwrite

    context_note = "proposal.md"
    if os.path.isfile(os.path.join(change_dir, "design.md")):
        context_note = "proposal.md and design.md"

    content = (
        f"# Tasks\n\n"
        f"- [ ] Implement the change as described in {context_note}. "
        f"Read the artifacts in openspec/changes/{change_name}/ for full scope and design details.\n"
    )

    try:
        with open(tasks_file, "w") as f:
            f.write(content)
        return True
    except OSError:
        return False


def get_new_commits(wt_path: str, since: str = "") -> list:
    """Get commit hashes since a given date."""
    if not since:
        return []
    try:
        result = subprocess.run(
            ["git", "-C", wt_path, "log", f"--since={since}", "--format=%h"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return [h for h in result.stdout.strip().splitlines() if h]
        return []
    except (subprocess.TimeoutExpired, OSError):
        return []


# ─── Internal helpers ─────────────────────────────────────────


def _check_test_done(wt_path: str) -> bool:
    """Test command passes = done. Fallback chain: loop-state → auto-detect → build."""
    from .config import auto_detect_test_command

    # 1. Read test_command from loop-state.json
    test_cmd = None
    state_file = os.path.join(wt_path, ".claude", "loop-state.json")
    try:
        with open(state_file, "r") as f:
            data = json.load(f)
        test_cmd = data.get("test_command")  # None if absent or null
    except (OSError, json.JSONDecodeError):
        pass

    # 2. Fallback: auto-detect from project config
    if not test_cmd:
        test_cmd = auto_detect_test_command(wt_path)

    # 3. Last resort: fall back to build check
    if not test_cmd:
        return _check_build_done(wt_path)

    try:
        result = subprocess.run(
            test_cmd,
            shell=True,
            cwd=wt_path,
            capture_output=True,
            text=True,
            timeout=600,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _check_build_done(wt_path: str) -> bool:
    """Build command passes = done."""
    from .builder import _detect_pm, _detect_build_cmd

    build_cmd = _detect_build_cmd(wt_path)
    if not build_cmd:
        return True  # No build command = pass

    pm = _detect_pm(wt_path)
    try:
        result = subprocess.run(
            [pm, "run", build_cmd],
            cwd=wt_path,
            capture_output=True,
            timeout=600,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _check_merge_done(wt_path: str) -> bool:
    """Branch merges cleanly with main = done."""
    try:
        # Get main branch ref
        result = subprocess.run(
            ["git", "-C", wt_path, "symbolic-ref", "refs/remotes/origin/HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        main_ref = "main"
        if result.returncode == 0:
            main_ref = result.stdout.strip().replace("refs/remotes/origin/", "")

        # Fetch
        subprocess.run(
            ["git", "-C", wt_path, "fetch", "origin", main_ref],
            capture_output=True,
            timeout=30,
        )

        # Get current branch
        result = subprocess.run(
            ["git", "-C", wt_path, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False
        cur_branch = result.stdout.strip()

        # Merge base
        result = subprocess.run(
            ["git", "-C", wt_path, "merge-base", cur_branch, f"origin/{main_ref}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False
        mb = result.stdout.strip()

        # Merge tree check
        result = subprocess.run(
            ["git", "-C", wt_path, "merge-tree", mb, f"origin/{main_ref}", cur_branch],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return "<<<<<<<" not in result.stdout

    except (subprocess.TimeoutExpired, OSError):
        return False
