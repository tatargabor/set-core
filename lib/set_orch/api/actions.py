"""Action routes: approve, stop, start, shutdown, pause, resume, skip, process management."""

from __future__ import annotations

import json
import os
import signal
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..state import load_state, save_state, StateCorruptionError
from ..process import check_pid, safe_kill
from .helpers import _resolve_project, _state_path, _sentinel_dir, _with_state_lock

router = APIRouter()

@router.post("/api/{project}/approve")
def approve_checkpoint(project: str):
    """Approve the latest checkpoint."""
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")

    def do_approve():
        state = load_state(str(sp))
        if state.status != "checkpoint":
            raise HTTPException(409, "Not at checkpoint")

        checkpoints = state.extras.get("checkpoints", [])
        if not checkpoints:
            # Try from dataclass field
            checkpoints = state.checkpoints
        if checkpoints:
            checkpoints[-1]["approved"] = True
            checkpoints[-1]["approved_at"] = datetime.now(timezone.utc).isoformat()

        save_state(state, str(sp))
        return {"ok": True}

    return _with_state_lock(sp, do_approve)


@router.post("/api/{project}/stop")
def stop_orchestration(project: str):
    """Stop the orchestration process."""
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")

    try:
        state = load_state(str(sp))
    except StateCorruptionError as e:
        raise HTTPException(500, f"Corrupt state: {e.detail}")

    if state.status not in ("running", "checkpoint"):
        raise HTTPException(409, f"Not running (status: {state.status})")

    # Find orchestrator PID from state extras
    orch_pid = state.extras.get("orchestrator_pid") or state.extras.get("pid")
    if orch_pid:
        result = safe_kill(int(orch_pid), "set-orchestrate")
        kill_result = result.outcome
    else:
        kill_result = "no_pid"

    def do_stop():
        s = load_state(str(sp))
        s.status = "stopped"
        save_state(s, str(sp))

    _with_state_lock(sp, do_stop)
    return {"ok": True, "kill_result": kill_result}


@router.post("/api/{project}/start")
def start_orchestration(project: str):
    """Start or resume orchestration by spawning a detached set-sentinel process."""
    import shutil
    import subprocess as _sp

    project_path = _resolve_project(project)

    # Check if sentinel is already running
    pid_file = _sentinel_dir(project_path) / "sentinel.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            raise HTTPException(409, "Sentinel already running")
        except (ValueError, ProcessLookupError, PermissionError):
            pass  # Stale PID, safe to start

    # Check for corrupt state
    sp = _state_path(project_path)
    if sp.exists():
        try:
            load_state(str(sp))
        except StateCorruptionError as e:
            raise HTTPException(500, f"Corrupt state file: {e.detail}")

    # Resolve spec path: state extras → config.yaml → fallback patterns
    spec_path = None
    if sp.exists():
        try:
            state = load_state(str(sp))
            spec_path = (state.extras or {}).get("spec_path")
        except Exception:
            pass
    if not spec_path:
        config_yaml = project_path / "set" / "orchestration" / "config.yaml"
        if config_yaml.exists():
            try:
                import yaml
                with open(config_yaml) as f:
                    cfg = yaml.safe_load(f) or {}
                spec_path = cfg.get("spec") or cfg.get("spec_path")
            except Exception:
                pass
    if not spec_path:
        for candidate in ["docs/spec.md", "docs/v1-*.md", "project-brief.md"]:
            import glob as _glob
            matches = _glob.glob(str(project_path / candidate))
            if matches:
                spec_path = str(Path(matches[0]).relative_to(project_path))
                break
    if not spec_path:
        raise HTTPException(400, "Cannot determine spec path — set 'spec' in set/orchestration/config.yaml")

    # Resolve set-sentinel binary
    sentinel_bin = shutil.which("set-sentinel")
    if not sentinel_bin:
        raise HTTPException(500, "set-sentinel not found in PATH")

    # Spawn detached sentinel
    proc = _sp.Popen(
        [sentinel_bin, "--spec", spec_path],
        cwd=str(project_path),
        start_new_session=True,
        stdout=open(os.devnull, "w"),
        stderr=open(os.devnull, "w"),
    )

    return {"ok": True, "pid": proc.pid, "spec": spec_path}


@router.post("/api/{project}/shutdown")
def shutdown_orchestration(project: str):
    """Graceful shutdown: signals sentinel to stop agents cleanly and preserve state."""
    project_path = _resolve_project(project)
    pid_file = _sentinel_dir(Path(project_path)) / "sentinel.pid"
    if not pid_file.exists():
        raise HTTPException(409, "No sentinel running")

    sentinel_pid = pid_file.read_text().strip()
    if not sentinel_pid:
        raise HTTPException(409, "No sentinel running")

    try:
        pid = int(sentinel_pid)
        import os
        os.kill(pid, 0)  # check if alive
    except (ValueError, ProcessLookupError, PermissionError):
        raise HTTPException(409, "No sentinel running (stale PID file)")

    import signal
    try:
        import os
        os.kill(pid, signal.SIGUSR1)
    except ProcessLookupError:
        raise HTTPException(409, "Sentinel died before shutdown signal")

    return {"ok": True, "message": "Shutdown initiated", "sentinel_pid": pid}


@router.post("/api/{project}/changes/{name}/pause")
def pause_change(project: str, name: str):
    """Pause a running change: SIGTERM its Ralph process and set status to paused."""
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")

    try:
        state = load_state(str(sp))
    except StateCorruptionError as e:
        raise HTTPException(500, f"Corrupt state: {e.detail}")

    target = None
    for c in state.changes:
        if c.name == name:
            target = c
            break
    if target is None:
        raise HTTPException(404, f"Change not found: {name}")

    # Idempotent: already paused
    if target.status == "paused":
        return {"ok": True, "message": "Already paused", "status": "paused"}

    # Only running changes can be paused
    if target.status not in ("running", "dispatched", "verifying"):
        raise HTTPException(409, f"Change is not in a pausable state (status: {target.status})")

    # Send SIGTERM to Ralph for graceful iteration stop
    if target.ralph_pid:
        import signal as sig
        try:
            os.kill(target.ralph_pid, sig.SIGTERM)
        except (OSError, ProcessLookupError):
            pass

    from .state import update_change_field
    update_change_field(str(sp), name, "status", "paused")

    return {"ok": True, "message": f"Change '{name}' paused", "status": "paused"}


@router.post("/api/{project}/changes/{name}/resume")
def resume_change(project: str, name: str):
    """Resume a paused change: set status to dispatched so the monitor re-dispatches Ralph."""
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")

    try:
        state = load_state(str(sp))
    except StateCorruptionError as e:
        raise HTTPException(500, f"Corrupt state: {e.detail}")

    target = None
    for c in state.changes:
        if c.name == name:
            target = c
            break
    if target is None:
        raise HTTPException(404, f"Change not found: {name}")

    # Idempotent: already running
    if target.status in ("running", "dispatched"):
        return {"ok": True, "message": "Already running", "status": target.status}

    if target.status != "paused":
        raise HTTPException(409, f"Change is not paused (status: {target.status})")

    # Check max_parallel
    running_count = sum(1 for c in state.changes if c.status in ("running", "dispatched", "verifying"))
    # Read max_parallel from directives in extras
    max_parallel = (state.extras or {}).get("directives", {}).get("max_parallel", 3)
    if running_count >= max_parallel:
        raise HTTPException(429, f"Max parallel changes reached ({max_parallel}), try again later")

    from .state import update_change_field
    update_change_field(str(sp), name, "status", "dispatched")

    return {"ok": True, "message": f"Change '{name}' resumed (will be dispatched)", "status": "dispatched"}


@router.post("/api/{project}/changes/{name}/stop")
def stop_change(project: str, name: str):
    """Stop a specific change's Ralph process."""
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")

    try:
        state = load_state(str(sp))
    except StateCorruptionError as e:
        raise HTTPException(500, f"Corrupt state: {e.detail}")

    target = None
    for c in state.changes:
        if c.name == name:
            target = c
            break
    if target is None:
        raise HTTPException(404, f"Change not found: {name}")
    if target.status != "running":
        raise HTTPException(409, f"Change not running (status: {target.status})")

    kill_result = "no_pid"
    if target.ralph_pid:
        result = safe_kill(target.ralph_pid, "set-loop")
        kill_result = result.outcome

    def do_stop_change():
        s = load_state(str(sp))
        for c in s.changes:
            if c.name == name:
                c.status = "stopped"
                break
        save_state(s, str(sp))

    _with_state_lock(sp, do_stop_change)
    return {"ok": True, "kill_result": kill_result}


@router.post("/api/{project}/changes/{name}/skip")
def skip_change(project: str, name: str):
    """Mark a change as skipped."""
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")

    def do_skip():
        state = load_state(str(sp))
        for c in state.changes:
            if c.name == name:
                if c.status not in ("pending", "failed", "verify-failed", "stalled"):
                    raise HTTPException(409, f"Cannot skip change with status: {c.status}")
                c.status = "skipped"
                save_state(state, str(sp))
                return {"ok": True}
        raise HTTPException(404, f"Change not found: {name}")

    return _with_state_lock(sp, do_skip)


# ─── Process Management ──────────────────────────────────────────────


def _process_info(pid: int) -> dict | None:
    """Get process info (pid, command, uptime, cpu, mem) via ps. Returns None if dead."""
    try:
        os.kill(pid, 0)  # check alive
    except (ProcessLookupError, PermissionError):
        return None
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "pid,etime,%cpu,rss,args", "--no-headers"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        parts = result.stdout.strip().split(None, 4)
        if len(parts) < 5:
            return None
        etime = parts[1]  # e.g. "1:23:45" or "02:15" or "45"
        # Parse etime to seconds
        segs = etime.replace("-", ":").split(":")
        segs = [int(s) for s in segs]
        if len(segs) == 1:
            uptime = segs[0]
        elif len(segs) == 2:
            uptime = segs[0] * 60 + segs[1]
        elif len(segs) == 3:
            uptime = segs[0] * 3600 + segs[1] * 60 + segs[2]
        elif len(segs) == 4:
            uptime = segs[0] * 86400 + segs[1] * 3600 + segs[2] * 60 + segs[3]
        else:
            uptime = 0
        return {
            "pid": pid,
            "command": parts[4][:120],
            "uptime_seconds": uptime,
            "cpu_percent": float(parts[2]),
            "memory_mb": round(int(parts[3]) / 1024, 1),
            "children": [],
        }
    except Exception:
        return None


def _get_process_children(pid: int) -> list[int]:
    """Get direct child PIDs using ps --ppid."""
    try:
        result = subprocess.run(
            ["ps", "--ppid", str(pid), "-o", "pid", "--no-headers"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return []
        return [int(p.strip()) for p in result.stdout.strip().split("\n") if p.strip()]
    except Exception:
        return []


def _build_process_tree_node(pid: int) -> dict | None:
    """Recursively build process tree from a root PID."""
    info = _process_info(pid)
    if not info:
        return None
    children_pids = _get_process_children(pid)
    for cpid in children_pids:
        child = _build_process_tree_node(cpid)
        if child:
            info["children"].append(child)
    return info


def _build_project_process_tree(project_path: Path) -> list[dict]:
    """Build full process tree for a project from PID files."""
    trees: list[dict] = []
    # Sentinel PID
    sentinel_pid_file = _sentinel_dir(project_path) / "sentinel.pid"
    if sentinel_pid_file.exists():
        try:
            pid = int(sentinel_pid_file.read_text().strip())
            node = _build_process_tree_node(pid)
            if node:
                node["role"] = "sentinel"
                trees.append(node)
        except (ValueError, OSError):
            pass

    # Orchestrator PID from state
    sp = _state_path(project_path)
    if sp.exists():
        try:
            state = load_state(str(sp))
            orch_pid = state.extras.get("orchestrator_pid") or state.extras.get("pid")
            if orch_pid:
                pid = int(orch_pid)
                # Skip if already in sentinel tree
                already_in_tree = any(_find_pid_in_tree(t, pid) for t in trees)
                if not already_in_tree:
                    node = _build_process_tree_node(pid)
                    if node:
                        node["role"] = "orchestrator"
                        trees.append(node)
        except Exception:
            pass

    return trees


def _find_pid_in_tree(node: dict, pid: int) -> bool:
    """Check if a PID exists anywhere in a process tree."""
    if node.get("pid") == pid:
        return True
    return any(_find_pid_in_tree(c, pid) for c in node.get("children", []))


def _collect_all_pids(node: dict) -> list[int]:
    """Collect all PIDs from a tree, leaves first (bottom-up)."""
    pids: list[int] = []
    for child in node.get("children", []):
        pids.extend(_collect_all_pids(child))
    pids.append(node["pid"])
    return pids


@router.get("/api/{project}/processes")
def get_processes(project: str):
    """Get process tree for a project."""
    project_path = _resolve_project(project)
    trees = _build_project_process_tree(Path(project_path))
    return {"processes": trees}


@router.post("/api/{project}/processes/{pid}/stop")
def stop_process(project: str, pid: int):
    """Stop a specific process by PID."""
    _resolve_project(project)  # validate project exists
    try:
        os.kill(pid, 0)  # check alive
    except ProcessLookupError:
        return {"ok": True, "result": "already_dead"}
    except PermissionError:
        raise HTTPException(403, "Permission denied")

    import signal
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return {"ok": True, "result": "died_before_signal"}
    return {"ok": True, "result": "sigterm_sent", "pid": pid}


@router.post("/api/{project}/processes/stop-all")
def stop_all_processes(project: str):
    """Stop all processes bottom-up: agents → orchestrator → sentinel."""
    project_path = _resolve_project(project)
    trees = _build_project_process_tree(Path(project_path))

    # Collect all PIDs bottom-up
    all_pids: list[int] = []
    for tree in trees:
        all_pids.extend(_collect_all_pids(tree))

    import signal
    killed: list[int] = []
    for pid in all_pids:
        try:
            os.kill(pid, signal.SIGTERM)
            killed.append(pid)
        except (ProcessLookupError, PermissionError):
            pass

    # Wait up to 3s for graceful shutdown, then SIGKILL survivors
    if killed:
        time.sleep(3)
        for pid in killed:
            try:
                os.kill(pid, 0)  # still alive?
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

    # Set orchestration state to stopped
    sp = _state_path(Path(project_path))
    if sp.exists():
        try:
            def do_stop():
                s = load_state(str(sp))
                s.status = "stopped"
                save_state(s, str(sp))
            _with_state_lock(sp, do_stop)
        except Exception:
            pass

    return {"ok": True, "killed": killed, "total": len(killed)}


