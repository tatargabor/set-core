"""Action routes: approve, stop, start, shutdown, pause, resume, skip, process management."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..state import load_state, save_state, StateCorruptionError
from ..process import check_pid, safe_kill
from .helpers import _resolve_project, _state_path, _sentinel_dir, _with_state_lock

router = APIRouter()

@router.post("/api/{project}/approve")
async def approve_checkpoint(project: str):
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
            checkpoints[-1]["approved_at"] = datetime.now(timezone.utc).astimezone().isoformat()

        save_state(state, str(sp))
        return {"ok": True}

    return await _with_state_lock(sp, do_approve)


@router.post("/api/{project}/stop")
async def stop_orchestration(project: str):
    """Stop the orchestration process.

    `safe_kill` blocks up to 10s waiting for SIGTERM to take effect; running it
    inline in this async handler would freeze the uvicorn event loop and make
    every other endpoint look dead while the kill is in flight. Offload to a
    threadpool so the worker stays responsive.
    """
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

    orch_pid = state.extras.get("orchestrator_pid") or state.extras.get("pid")
    if orch_pid:
        result = await asyncio.to_thread(safe_kill, int(orch_pid), "set-orchestrate")
        kill_result = result.outcome
    else:
        kill_result = "no_pid"

    def do_stop():
        s = load_state(str(sp))
        s.status = "stopped"
        save_state(s, str(sp))

    await _with_state_lock(sp, do_stop)
    return {"ok": True, "kill_result": kill_result}


@router.post("/api/{project}/start")
def start_orchestration(project: str):
    """Start or resume orchestration by spawning a detached set-orchestrate process."""
    import shutil
    import subprocess as _sp

    project_path = _resolve_project(project)

    # Check for corrupt state
    sp = _state_path(project_path)
    if sp.exists():
        try:
            load_state(str(sp))
        except StateCorruptionError as e:
            raise HTTPException(500, f"Corrupt state file: {e.detail}")

    # Check if orchestrator is already running
    if sp.exists():
        try:
            state = load_state(str(sp))
            orch_pid = state.extras.get("orchestrator_pid") or state.extras.get("pid")
            if orch_pid and check_pid(int(orch_pid)):
                raise HTTPException(409, "Orchestrator already running")
        except (HTTPException,):
            raise
        except Exception:
            pass

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
        raise HTTPException(400, "Cannot determine spec path — set 'spec' in the orchestration config (LineagePaths.config_yaml)")

    # Resolve set-orchestrate binary
    orch_bin = shutil.which("set-orchestrate")
    if not orch_bin:
        raise HTTPException(500, "set-orchestrate not found in PATH")

    # Spawn detached orchestrator
    proc = _sp.Popen(
        [orch_bin, "start", "--spec", spec_path],
        cwd=str(project_path),
        start_new_session=True,
        stdout=open(os.devnull, "w"),
        stderr=open(os.devnull, "w"),
    )

    return {"ok": True, "pid": proc.pid, "spec": spec_path}


@router.post("/api/{project}/shutdown")
def shutdown_orchestration(project: str):
    """Graceful shutdown: signals orchestrator to stop agents cleanly and preserve state."""
    project_path = _resolve_project(project)
    sp = _state_path(Path(project_path))
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")

    try:
        state = load_state(str(sp))
    except StateCorruptionError as e:
        raise HTTPException(500, f"Corrupt state: {e.detail}")

    orch_pid = state.extras.get("orchestrator_pid") or state.extras.get("pid")
    if not orch_pid:
        raise HTTPException(409, "No orchestrator PID found in state")

    pid = int(orch_pid)
    if not check_pid(pid):
        raise HTTPException(409, "Orchestrator not running (stale PID)")

    result = safe_kill(pid, "set-orchestrate")
    return {"ok": True, "message": "Shutdown initiated", "orchestrator_pid": pid, "result": result.outcome}


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
async def stop_change(project: str, name: str):
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
        result = await asyncio.to_thread(safe_kill, target.ralph_pid, "set-loop")
        kill_result = result.outcome

    def do_stop_change():
        s = load_state(str(sp))
        for c in s.changes:
            if c.name == name:
                c.status = "stopped"
                break
        save_state(s, str(sp))

    await _with_state_lock(sp, do_stop_change)
    return {"ok": True, "kill_result": kill_result}


@router.post("/api/{project}/changes/{name}/skip")
async def skip_change(project: str, name: str):
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

    return await _with_state_lock(sp, do_skip)


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
    """Build full process tree for a project from PID files + worktree scan.

    Process discovery is two-phase:
      1. Tracked roots — sentinel.pid file and state.extras.orchestrator_pid.
         These build full child-process trees via ps --ppid.
      2. Orphan scan — any process whose cmdline references the project path
         or one of its worktree paths but isn't already in a tracked tree.
         These typically arise when an old sentinel was killed without
         tearing down its set-loop / claude / playwright children, leaving
         them re-parented to PID 1 (init). Without this scan, the
         "Stop All" button can't reach them and the user has to hunt by
         hand. Marked role=orphan so the UI surfaces them visibly.
    """
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
    worktree_paths: list[str] = []
    if sp.exists():
        try:
            state = load_state(str(sp))
            orch_pid = state.extras.get("orchestrator_pid") or state.extras.get("pid")
            if orch_pid:
                pid = int(orch_pid)
                already_in_tree = any(_find_pid_in_tree(t, pid) for t in trees)
                if not already_in_tree:
                    node = _build_process_tree_node(pid)
                    if node:
                        node["role"] = "orchestrator"
                        trees.append(node)
            # Collect worktree paths so the orphan scan finds set-loop /
            # claude / playwright / next-server processes started in a
            # worktree even when the supervisor that spawned them is gone.
            for ch in state.changes:
                wt = getattr(ch, "worktree_path", "") or ""
                if wt:
                    worktree_paths.append(wt)
        except Exception:
            pass

    # ── Orphan scan ─────────────────────────────────────────────────
    # Search match-paths: project root + all known worktree paths. We use
    # str(project_path) because runs typically live in <runs_dir>/<run-name>
    # and worktrees in <runs_dir>/<run-name>-wt-<change>; matching the run
    # root would also catch in-run processes if the run dir is the cwd.
    match_paths = {str(project_path)} | set(worktree_paths)
    tracked_pids: set[int] = set()
    for t in trees:
        for p in _collect_all_pids(t):
            tracked_pids.add(p)

    orphan_pids: list[int] = []
    try:
        # ps -eo pid,args — full cmdline across all processes. cwd info is
        # also useful but cmdline+args is enough for set-loop/claude/playwright
        # which always include the worktree path explicitly.
        psr = subprocess.run(
            ["ps", "-eo", "pid,args", "--no-headers"],
            capture_output=True, text=True, timeout=5,
        )
        if psr.returncode == 0:
            for line in psr.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    pid_str, args = line.split(None, 1)
                    pid = int(pid_str)
                except ValueError:
                    continue
                if pid in tracked_pids:
                    continue
                # Match if any known path appears in the cmdline. Strict
                # substring match; project paths are absolute so false
                # positives are rare in practice.
                if any(p in args for p in match_paths):
                    orphan_pids.append(pid)
    except Exception:
        pass

    # Build a tree node per orphan, but skip orphans that are descendants
    # of another orphan (their parent will pull them in via _get_process_children).
    if orphan_pids:
        orphan_set = set(orphan_pids)
        roots: list[int] = []
        for pid in orphan_pids:
            try:
                ppid_r = subprocess.run(
                    ["ps", "-p", str(pid), "-o", "ppid=", "--no-headers"],
                    capture_output=True, text=True, timeout=2,
                )
                ppid = int(ppid_r.stdout.strip()) if ppid_r.returncode == 0 else 1
            except Exception:
                ppid = 1
            if ppid not in orphan_set:
                roots.append(pid)
        for pid in roots:
            node = _build_process_tree_node(pid)
            if node:
                node["role"] = "orphan"
                trees.append(node)

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
async def stop_all_processes(project: str):
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
        await asyncio.sleep(3)
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
            await _with_state_lock(sp, do_stop)
        except Exception:
            pass

    return {"ok": True, "killed": killed, "total": len(killed)}


