"""Milestone checkpoint: tag, worktree, dev server, email.

Migrated from: lib/orchestration/milestone.sh (242 lines)
Source line comments reference the original bash function names.

Functions:
    run_milestone_checkpoint     — full pipeline: tag, wt, deps, server, email, event
    _send_milestone_email        — HTML email with phase stats
    _enforce_max_milestone_worktrees — kill server + remove oldest
    cleanup_milestone_servers    — kill all milestone PIDs
    cleanup_milestone_worktrees  — remove all milestone worktree dirs
"""

from __future__ import annotations

import glob
import logging
import os
import signal
import subprocess
import time
from typing import Any

from .state import load_state, locked_state, update_change_field
from .subprocess_utils import run_command

logger = logging.getLogger(__name__)

MILESTONE_WORKTREE_DIR = ".claude/milestones"


# ─── Milestone Checkpoint ──────────────────────────────────────────

# Source: milestone.sh run_milestone_checkpoint() L12-110
def run_milestone_checkpoint(
    phase: int,
    base_port: int = 3100,
    max_worktrees: int = 3,
    state_file: str = "",
    *,
    milestone_dev_server: str = "",
    event_bus: Any = None,
) -> None:
    """Run milestone checkpoint for a completed phase.

    Steps: git tag → create worktree → install deps → start server →
    send email → emit event
    """
    logger.info("Milestone checkpoint: phase %d", phase)

    # 1. Git tag
    tag_name = f"milestone/phase-{phase}"
    result = run_command(["git", "tag", "-f", tag_name, "HEAD"], timeout=30)
    if result.exit_code != 0:
        logger.warning("Milestone: failed to create tag %s", tag_name)

    if state_file:
        with locked_state(state_file) as state:
            phases = state.extras.setdefault("phases", {})
            phases.setdefault(str(phase), {})["tag"] = tag_name

    logger.info("Milestone: tagged %s", tag_name)

    # 2. Create worktree (enforce limit)
    _enforce_max_milestone_worktrees(max_worktrees, state_file)
    wt_path = f"{MILESTONE_WORKTREE_DIR}/phase-{phase}"

    if os.path.isdir(wt_path):
        logger.warning("Milestone: worktree %s already exists — removing", wt_path)
        run_command(["git", "worktree", "remove", "--force", wt_path], timeout=30)

    os.makedirs(os.path.dirname(wt_path), exist_ok=True)
    wt_result = run_command(["git", "worktree", "add", wt_path, tag_name], timeout=60)
    if wt_result.exit_code == 0:
        logger.info("Milestone: worktree created at %s", wt_path)
    else:
        logger.warning("Milestone: failed to create worktree at %s", wt_path)

    # 3. Install deps + 4. Start dev server
    server_port = base_port + phase
    server_pid: int | None = None

    dev_cmd = _detect_dev_server(wt_path, milestone_dev_server, state_file)

    if dev_cmd and os.path.isdir(wt_path):
        # Install dependencies
        _install_dependencies(wt_path)

        # Start dev server
        logger.info("Milestone: starting dev server on port %d: %s", server_port, dev_cmd)
        env = os.environ.copy()
        env["PORT"] = str(server_port)
        try:
            proc = subprocess.Popen(
                ["bash", "-c", dev_cmd],
                cwd=wt_path,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            server_pid = proc.pid
        except Exception:
            logger.warning("Milestone: failed to start dev server")

        # Health check
        if server_pid:
            from .verifier import health_check as hc_fn

            state = load_state(state_file) if state_file else None
            hc_url = ""
            if state:
                hc_url = state.extras.get("directives", {}).get("smoke_health_check_url", "")
            if hc_url:
                # Adapt to milestone port
                import re
                hc_url = re.sub(r":\d+", f":{server_port}", hc_url)
                if hc_fn(hc_url, timeout_secs=30):
                    logger.info("Milestone: dev server healthy on port %d (PID %d)", server_port, server_pid)
                else:
                    logger.warning("Milestone: dev server health check failed on port %d", server_port)
            else:
                time.sleep(5)
                try:
                    os.kill(server_pid, 0)
                    logger.info("Milestone: dev server running on port %d (PID %d)", server_port, server_pid)
                except OSError:
                    logger.warning("Milestone: dev server died on port %d", server_port)
                    server_pid = None

        # Store PID and port
        if state_file:
            with locked_state(state_file) as state:
                phases = state.extras.setdefault("phases", {})
                phase_data = phases.setdefault(str(phase), {})
                phase_data["server_port"] = server_port
                if server_pid:
                    phase_data["server_pid"] = server_pid
    else:
        logger.info("Milestone: no dev server detected — skipping server start")

    # 5. Send email
    _send_milestone_email(phase, server_port, server_pid, state_file)

    # 6. Emit event
    if event_bus:
        state = load_state(state_file) if state_file else None
        change_count = 0
        if state:
            change_count = sum(1 for c in state.changes if c.phase == phase)
        event_bus.emit(
            "MILESTONE_COMPLETE",
            data={
                "phase": phase,
                "changes": change_count,
                "server_port": server_port,
                "tag": tag_name,
            },
        )

    logger.info("Milestone checkpoint complete: phase %d", phase)


# ─── Milestone Email ───────────────────────────────────────────────

# Source: milestone.sh _send_milestone_email() L113-164
def _send_milestone_email(
    phase: int, port: int, pid: int | None, state_file: str
) -> None:
    """Send milestone completion email with phase stats."""
    try:
        from .notifications import send_email
    except (ImportError, AttributeError):
        return

    project_name = os.path.basename(os.getcwd())
    state = load_state(state_file) if state_file else None

    total_changes = 0
    merged_changes = 0
    phase_tokens = 0
    changes_data: list[tuple[str, str, int]] = []

    if state:
        for c in state.changes:
            if c.phase != phase:
                continue
            total_changes += 1
            if c.status in ("merged", "done"):
                merged_changes += 1
            phase_tokens += c.tokens_used
            changes_data.append((c.name, c.status, c.tokens_used))

    subject = f"[set-core] {project_name} — Phase {phase} complete ({merged_changes}/{total_changes} changes)"

    html = f"<h2>Phase {phase} Complete: {project_name}</h2>"
    html += f"<p><strong>Date:</strong> {time.strftime('%Y-%m-%d %H:%M:%S')}</p>"
    html += "<h3>Phase Summary</h3>"
    html += "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;'>"
    html += f"<tr><td><strong>Changes</strong></td><td>{merged_changes} / {total_changes} merged</td></tr>"
    html += f"<tr><td><strong>Tokens</strong></td><td>{phase_tokens}</td></tr>"

    if pid:
        html += f"<tr><td><strong>Dev Server</strong></td><td><a href=\"http://localhost:{port}\">http://localhost:{port}</a></td></tr>"
    html += "</table>"

    # Per-change table
    html += f"<h3>Changes in Phase {phase}</h3>"
    html += "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;'>"
    html += "<tr style='background:#f0f0f0;'><th>Change</th><th>Status</th><th>Tokens</th></tr>"
    for name, cstatus, ctokens in changes_data:
        color = "#fff"
        if cstatus in ("done", "merged"):
            color = "#d4edda"
        elif cstatus == "failed":
            color = "#f8d7da"
        html += f"<tr style='background:{color};'><td>{name}</td><td>{cstatus}</td><td>{ctokens}</td></tr>"
    html += "</table>"

    html += "<p style='color:#888;'>Orchestrator continues automatically. Stop with: <code>set-orchestrate stop</code></p>"

    try:
        send_email(subject, html)
    except Exception:
        logger.warning("Milestone: failed to send email")


# ─── Worktree Limit Enforcement ────────────────────────────────────

# Source: milestone.sh _enforce_max_milestone_worktrees() L167-198
def _enforce_max_milestone_worktrees(max_wts: int, state_file: str) -> None:
    """Remove oldest milestone worktrees if limit exceeded."""
    if not os.path.isdir(MILESTONE_WORKTREE_DIR):
        return

    existing = sorted(
        d for d in os.listdir(MILESTONE_WORKTREE_DIR)
        if os.path.isdir(os.path.join(MILESTONE_WORKTREE_DIR, d))
    )

    while len(existing) >= max_wts:
        oldest = existing[0]
        oldest_path = os.path.join(MILESTONE_WORKTREE_DIR, oldest)
        oldest_phase = oldest.replace("phase-", "")

        # Kill server if running
        if state_file:
            state = load_state(state_file)
            phases = state.extras.get("phases", {})
            old_pid = phases.get(oldest_phase, {}).get("server_pid")
            if old_pid:
                try:
                    os.kill(int(old_pid), signal.SIGTERM)
                except OSError:
                    pass
                with locked_state(state_file) as st:
                    phases_dict = st.extras.setdefault("phases", {})
                    if oldest_phase in phases_dict:
                        phases_dict[oldest_phase].pop("server_pid", None)
                logger.info("Milestone: killed server for phase %s (PID %s)", oldest_phase, old_pid)

        # Remove worktree
        result = run_command(["git", "worktree", "remove", "--force", oldest_path], timeout=30)
        if result.exit_code != 0:
            try:
                import shutil
                shutil.rmtree(oldest_path)
            except Exception:
                pass
        logger.info("Milestone: removed oldest worktree %s (limit: %d)", oldest, max_wts)
        existing.pop(0)


# ─── Cleanup ───────────────────────────────────────────────────────

# Source: milestone.sh cleanup_milestone_servers() L203-223
def cleanup_milestone_servers(state_file: str) -> int:
    """Kill all milestone dev server processes. Returns count killed."""
    if not os.path.exists(state_file):
        return 0

    state = load_state(state_file)
    phases = state.extras.get("phases", {})
    if not phases:
        return 0

    killed = 0
    for phase_key, phase_data in phases.items():
        pid = phase_data.get("server_pid")
        if not pid:
            continue
        try:
            os.kill(int(pid), 0)  # check alive
            os.kill(int(pid), signal.SIGTERM)
            logger.info("Milestone cleanup: killed server PID %s", pid)
            killed += 1
        except OSError:
            pass

    # Clear all PIDs from state
    if killed > 0:
        with locked_state(state_file) as st:
            for phase_data in st.extras.get("phases", {}).values():
                phase_data.pop("server_pid", None)

    return killed


# Source: milestone.sh cleanup_milestone_worktrees() L226-242
def cleanup_milestone_worktrees() -> int:
    """Remove all milestone worktrees. Returns count removed."""
    if not os.path.isdir(MILESTONE_WORKTREE_DIR):
        return 0

    cleaned = 0
    for entry in os.listdir(MILESTONE_WORKTREE_DIR):
        wt_dir = os.path.join(MILESTONE_WORKTREE_DIR, entry)
        if not os.path.isdir(wt_dir):
            continue
        result = run_command(["git", "worktree", "remove", "--force", wt_dir], timeout=30)
        if result.exit_code != 0:
            try:
                import shutil
                shutil.rmtree(wt_dir)
            except Exception:
                pass
        cleaned += 1

    if cleaned > 0:
        logger.info("Milestone cleanup: removed %d worktree(s)", cleaned)

    # Remove empty milestone dir
    try:
        os.rmdir(MILESTONE_WORKTREE_DIR)
    except OSError:
        pass

    return cleaned


# ─── Internal Helpers ──────────────────────────────────────────────

def _detect_dev_server(wt_path: str, explicit_cmd: str, state_file: str) -> str:
    """Detect dev server — explicit > directive > profile > legacy."""
    if explicit_cmd:
        return explicit_cmd

    if state_file:
        state = load_state(state_file)
        smoke_dev = state.extras.get("directives", {}).get("smoke_dev_server_command", "")
        if smoke_dev:
            return smoke_dev

    # Profile-aware detection
    from .profile_loader import load_profile

    profile = load_profile(wt_path)
    cmd = profile.detect_dev_server(wt_path)
    if cmd:
        return cmd

    # TODO(profile-cleanup): remove after profile adoption confirmed
    # Legacy fallback — delegates PM detection to canonical function
    pkg_json = os.path.join(wt_path, "package.json")
    if os.path.exists(pkg_json):
        import json
        from .config import detect_package_manager
        try:
            with open(pkg_json) as f:
                pkg = json.load(f)
            scripts = pkg.get("scripts", {})
            if "dev" in scripts:
                pm = detect_package_manager(wt_path)
                return f"{pm} run dev"
        except Exception:
            pass
    return ""


def _install_dependencies(wt_path: str) -> bool:
    """Install dependencies — profile first, legacy fallback."""
    from .profile_loader import NullProfile, load_profile

    profile = load_profile(wt_path)
    if not isinstance(profile, NullProfile):
        return profile.post_merge_install(wt_path)

    # TODO(profile-cleanup): remove after profile adoption confirmed
    # Legacy fallback — delegates PM detection to canonical function
    from .config import detect_package_manager

    pm = detect_package_manager(wt_path)
    if pm in ("pnpm", "yarn", "npm", "bun"):
        cmd = [pm, "install"]
    else:
        return True

    result = run_command(cmd, timeout=600, cwd=wt_path)
    return result.exit_code == 0
