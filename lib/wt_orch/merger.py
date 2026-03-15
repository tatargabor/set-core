"""Merge pipeline, worktree cleanup, archive operations.

Migrated from: lib/orchestration/merger.sh (672 lines)
Source line comments reference the original bash function names.

Functions:
    archive_change          — move openspec change dir to dated archive, git commit
    _collect_smoke_screenshots — copy test-results to attempt-N subdirs
    merge_change            — full merge pipeline with smoke/conflict handling
    _sync_running_worktrees — sync running worktrees after merge
    _archive_worktree_logs  — copy .claude/logs to orchestration archive
    cleanup_worktree        — wt-close with fallback manual removal
    cleanup_all_worktrees   — iterate terminal changes, cleanup each
    execute_merge_queue     — drain merge queue
    retry_merge_queue       — retry queue + merge-blocked changes
    _try_merge              — single attempt with conflict fingerprint dedup
"""

from __future__ import annotations

import glob
import hashlib
import logging
import os
import shutil
import time
from dataclasses import dataclass
from typing import Any, Optional

from .state import (
    Change,
    OrchestratorState,
    load_state,
    locked_state,
    update_change_field,
    update_state_field,
)
from .subprocess_utils import CommandResult, run_command

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────

MAX_MERGE_RETRIES = 5
DEFAULT_MERGE_TIMEOUT = 600  # 10 min


# ─── Data Structures ───────────────────────────────────────────────

@dataclass
class MergeResult:
    """Result of a merge_change() call."""

    success: bool
    status: str  # "merged", "merge-blocked", "smoke_failed", "merge_timeout", "skip_merged"
    smoke_result: str = ""  # "pass", "fail", "fixed", "blocked", "skip_merged"


# ─── Archive ────────────────────────────────────────────────────────

# Source: merger.sh archive_change() L11-31
def archive_change(change_name: str) -> bool:
    """Move openspec change directory to dated archive path and commit."""
    change_dir = f"openspec/changes/{change_name}"
    if not os.path.isdir(change_dir):
        return True  # nothing to archive

    archive_dir = "openspec/changes/archive"
    dated_name = f"{time.strftime('%Y-%m-%d')}-{change_name}"
    dest = f"{archive_dir}/{dated_name}"

    try:
        os.makedirs(archive_dir, exist_ok=True)
        shutil.move(change_dir, dest)
        run_command(["git", "add", dest], timeout=30)
        run_command(
            ["git", "commit", "-m", f"chore: archive {change_name} change", "--no-verify"],
            timeout=60,
        )
        logger.info("Archived %s → %s", change_name, dest)
        return True
    except Exception:
        logger.warning("Failed to archive %s (non-blocking)", change_name)
        return False


# ─── Smoke Screenshot Collection ────────────────────────────────────

# Source: merger.sh _collect_smoke_screenshots() L38-52
def _collect_smoke_screenshots(
    change_name: str, state_file: str
) -> int:
    """Collect Playwright test-results/ after a smoke run. Returns screenshot count."""
    state = load_state(state_file)
    change = _find_change(state, change_name)
    attempt_num = 0
    if change:
        attempt_num = change.extras.get("smoke_fix_attempts", 0)

    sc_dir = f"wt/orchestration/smoke-screenshots/{change_name}/attempt-{attempt_num + 1}"
    os.makedirs(sc_dir, exist_ok=True)

    if os.path.isdir("test-results"):
        try:
            shutil.copytree("test-results", sc_dir, dirs_exist_ok=True)
        except Exception:
            logger.warning("Failed to copy test-results for %s", change_name)

    # Count PNGs across all attempts
    base_dir = f"wt/orchestration/smoke-screenshots/{change_name}"
    sc_count = len(glob.glob(f"{base_dir}/**/*.png", recursive=True))

    update_change_field(state_file, change_name, "smoke_screenshot_dir", base_dir)
    update_change_field(state_file, change_name, "smoke_screenshot_count", sc_count)
    logger.info(
        "Smoke screenshots: collected %d images for %s (attempt %d)",
        sc_count, change_name, attempt_num + 1,
    )
    return sc_count


# ─── Worktree Lifecycle ─────────────────────────────────────────────

# Source: merger.sh _archive_worktree_logs() L506-518
def _archive_worktree_logs(change_name: str, wt_path: str) -> int:
    """Archive worktree agent logs before cleanup. Returns file count."""
    logs_src = os.path.join(wt_path, ".claude", "logs")
    if not os.path.isdir(logs_src):
        return 0

    archive_dir = f"wt/orchestration/logs/{change_name}"
    os.makedirs(archive_dir, exist_ok=True)

    count = 0
    for f in glob.glob(os.path.join(logs_src, "*.log")):
        dest = os.path.join(archive_dir, os.path.basename(f))
        if not os.path.exists(dest):
            try:
                shutil.copy2(f, dest)
                count += 1
            except Exception:
                pass
    logger.info("Archived %d log files for %s to %s", count, change_name, archive_dir)
    return count


# Source: merger.sh cleanup_worktree() L521-547
def cleanup_worktree(change_name: str, wt_path: str) -> None:
    """Clean up worktree and branch after successful merge."""
    if wt_path and os.path.isdir(wt_path):
        _archive_worktree_logs(change_name, wt_path)

    # Try wt-close first
    result = run_command(["wt-close", change_name], timeout=60)
    if result.exit_code == 0:
        logger.info("Cleaned up worktree for %s", change_name)
        return

    # Fallback: manual cleanup
    if wt_path and os.path.isdir(wt_path):
        run_command(["git", "worktree", "remove", wt_path, "--force"], timeout=30)
        logger.info("Force-removed worktree %s", wt_path)

    branch = f"change/{change_name}"
    check = run_command(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        timeout=10,
    )
    if check.exit_code == 0:
        run_command(["git", "branch", "-D", branch], timeout=10)
        logger.info("Deleted branch %s", branch)


# Source: merger.sh cleanup_all_worktrees() L549-574
def cleanup_all_worktrees(state_file: str) -> int:
    """Cleanup worktrees for all merged/done changes. Returns count cleaned."""
    logger.info("Cleaning up worktrees for merged/done changes...")
    state = load_state(state_file)
    cleaned = 0

    for change in state.changes:
        if change.status not in ("merged", "done"):
            continue
        wt_path = change.worktree_path or ""
        if not wt_path or not os.path.isdir(wt_path):
            continue
        cleanup_worktree(change.name, wt_path)
        cleaned += 1

    if cleaned > 0:
        logger.info("Cleaned up %d worktree(s)", cleaned)

    # Clean up milestone resources if available
    try:
        from .milestone import cleanup_milestone_servers, cleanup_milestone_worktrees
        cleanup_milestone_servers(state_file)
        cleanup_milestone_worktrees()
    except Exception:
        pass

    return cleaned


# ─── Post-Merge Sync ───────────────────────────────────────────────

# Source: merger.sh _sync_running_worktrees() L482-501
def _sync_running_worktrees(merged_change: str, state_file: str) -> int:
    """Sync all running worktrees with main after merge. Returns count synced."""
    from .dispatcher import sync_worktree_with_main

    state = load_state(state_file)
    synced = 0

    for change in state.changes:
        if change.status != "running":
            continue
        wt_path = change.worktree_path or ""
        if not wt_path or not os.path.isdir(wt_path):
            continue
        try:
            result = sync_worktree_with_main(wt_path, change.name)
            if result.ok:
                logger.info(
                    "Post-merge sync: %s synced with main (after %s merge)",
                    change.name, merged_change,
                )
                synced += 1
            else:
                logger.warning("Post-merge sync: %s sync failed (non-blocking)", change.name)
        except Exception:
            logger.warning("Post-merge sync: %s sync failed (non-blocking)", change.name)

    return synced


# ─── Merge Pipeline ────────────────────────────────────────────────

# Source: merger.sh merge_change() L56-476
def merge_change(
    change_name: str,
    state_file: str,
    *,
    event_bus: Any = None,
) -> MergeResult:
    """Execute the full merge pipeline for a completed change.

    Handles: pre-merge hook, branch check, wt-merge, post-merge deps/build/scope,
    smoke pipeline, agent-assisted rebase on conflict.
    """
    logger.info("Merging %s...", change_name)

    merge_start = time.time()
    state = load_state(state_file)
    merge_timeout = state.extras.get("directives", {}).get(
        "merge_timeout", DEFAULT_MERGE_TIMEOUT
    )

    def _timed_out() -> bool:
        return (time.time() - merge_start) >= merge_timeout

    change = _find_change(state, change_name)
    wt_path = change.worktree_path if change else ""

    # Pre-merge hook (via subprocess to bash hook system)
    hook_result = _run_hook("pre_merge", change_name, "done", wt_path or "")
    if not hook_result:
        logger.warning("pre_merge hook blocked %s", change_name)
        return MergeResult(success=False, status="merge-blocked")

    if event_bus:
        event_bus.emit("MERGE_ATTEMPT", change=change_name)

    source_branch = f"change/{change_name}"

    # Check branch existence
    branch_check = run_command(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{source_branch}"],
        timeout=10,
    )
    branch_exists = branch_check.exit_code == 0

    # Case 1: Branch no longer exists (already merged and deleted)
    if not branch_exists:
        logger.info("Skipping merge for %s — branch deleted (assumed merged)", change_name)
        update_change_field(state_file, change_name, "status", "merged")
        update_change_field(state_file, change_name, "smoke_result", "skip_merged")
        update_change_field(state_file, change_name, "smoke_status", "skipped")
        cleanup_worktree(change_name, wt_path or "")
        archive_change(change_name)
        _remove_from_merge_queue(state_file, change_name)
        return MergeResult(success=True, status="merged", smoke_result="skip_merged")

    # Case 2: Branch is ancestor of HEAD (already merged, branch not deleted)
    source_sha_result = run_command(
        ["git", "rev-parse", source_branch], timeout=10,
    )
    source_sha = source_sha_result.stdout.strip()
    if source_sha:
        ancestor_check = run_command(
            ["git", "merge-base", "--is-ancestor", source_sha, "HEAD"],
            timeout=10,
        )
        if ancestor_check.exit_code == 0:
            logger.info("Skipping merge for %s — already merged", change_name)
            update_change_field(state_file, change_name, "status", "merged")
            update_change_field(state_file, change_name, "smoke_result", "skip_merged")
            update_change_field(state_file, change_name, "smoke_status", "skipped")
            cleanup_worktree(change_name, wt_path or "")
            archive_change(change_name)
            _remove_from_merge_queue(state_file, change_name)
            return MergeResult(success=True, status="merged", smoke_result="skip_merged")

    # Case 3: Normal merge
    merge_result = run_command(
        ["wt-merge", change_name, "--no-push", "--llm-resolve"],
        timeout=300,
    )

    if merge_result.exit_code == 0:
        # Merge succeeded
        update_change_field(state_file, change_name, "status", "merged")
        logger.info("Merged %s", change_name)

        # Git tags for recovery
        run_command(["git", "tag", "-f", f"orch/{change_name}", "HEAD"], timeout=10)

        # Sync running worktrees
        _sync_running_worktrees(change_name, state_file)

        # Update coverage status
        try:
            from .digest import update_coverage_status
            update_coverage_status(change_name, "merged")
        except Exception:
            logger.debug("Coverage update failed for %s (non-critical)", change_name)

        # Post-merge dependency install
        _post_merge_deps_install()

        # Post-merge custom command
        _post_merge_custom_command(state_file)

        # Post-merge scope verification
        from .verifier import verify_merge_scope
        scope_result = verify_merge_scope(change_name)
        if not scope_result.has_implementation:
            logger.warning(
                "Scope verify FAILED for %s — only artifact files merged",
                change_name,
            )

        # Post-merge build verification
        _post_merge_build_check(change_name, state_file)

        # Merge timeout check before smoke
        if _timed_out():
            elapsed = int(time.time() - merge_start)
            logger.error(
                "Merge timeout: %s exceeded %ds — aborting before smoke",
                change_name, merge_timeout,
            )
            update_change_field(state_file, change_name, "status", "merge_timeout")
            _remove_from_merge_queue(state_file, change_name)
            return MergeResult(success=False, status="merge_timeout")

        # Smoke pipeline
        smoke_result = _run_smoke_pipeline(change_name, state_file, merge_start, merge_timeout)

        # Post-merge hook
        _run_hook("post_merge", change_name, "merged", "")

        cleanup_worktree(change_name, wt_path or "")
        archive_change(change_name)
        _remove_from_merge_queue(state_file, change_name)

        return MergeResult(
            success=True,
            status="merged",
            smoke_result=smoke_result,
        )
    else:
        # Merge conflict
        return _handle_merge_conflict(change_name, state_file, wt_path or "")


# ─── Merge Queue ────────────────────────────────────────────────────

# Source: merger.sh execute_merge_queue() L578-588
def execute_merge_queue(state_file: str, *, event_bus: Any = None) -> int:
    """Drain merge queue. Returns count merged."""
    state = load_state(state_file)
    merged = 0
    for name in list(state.merge_queue):
        try:
            result = merge_change(name, state_file, event_bus=event_bus)
            if result.success:
                merged += 1
        except Exception:
            logger.warning("Merge failed for %s", name, exc_info=True)
    return merged


# Source: merger.sh _try_merge() L595-649
def _try_merge(
    name: str, state_file: str, *, event_bus: Any = None
) -> bool:
    """Single merge attempt with conflict fingerprint dedup. Returns True if merged."""
    state = load_state(state_file)
    change = _find_change(state, name)
    retry_count = change.merge_retry_count if change else 0

    if retry_count >= MAX_MERGE_RETRIES:
        return False  # silently skip

    retry_count += 1
    update_change_field(state_file, name, "merge_retry_count", retry_count)
    logger.info("Merge attempt %d/%d for %s", retry_count, MAX_MERGE_RETRIES, name)

    # Update branch with latest main before retry
    wt_path = change.worktree_path if change else ""
    if wt_path and os.path.isdir(wt_path):
        main_branch = _get_main_branch()
        logger.info("Updating %s branch with latest %s before merge retry", name, main_branch)
        run_command(
            ["git", "fetch", "origin", main_branch], timeout=60, cwd=wt_path,
        )
        run_command(
            ["git", "merge", f"origin/{main_branch}", "--no-edit"],
            timeout=120, cwd=wt_path,
        )

    try:
        result = merge_change(name, state_file, event_bus=event_bus)
        if result.success:
            return True
    except Exception:
        pass

    # Conflict fingerprint dedup
    fingerprint = _compute_conflict_fingerprint(name)
    prev_fingerprint = ""
    if change:
        prev_fingerprint = change.extras.get("last_conflict_fingerprint", "")

    if fingerprint:
        update_change_field(state_file, name, "last_conflict_fingerprint", fingerprint)
        if fingerprint == prev_fingerprint:
            logger.info("Same conflict fingerprint for %s — stopping retries", name)
            update_change_field(state_file, name, "status", "merge-blocked")
            return False

    if retry_count >= MAX_MERGE_RETRIES:
        logger.error(
            "Merge failed after %d attempts for %s — giving up",
            MAX_MERGE_RETRIES, name,
        )
    return False


# Source: merger.sh retry_merge_queue() L651-672
def retry_merge_queue(state_file: str, *, event_bus: Any = None) -> int:
    """Retry merge queue items + merge-blocked changes. Returns count merged."""
    state = load_state(state_file)
    merged = 0

    # Process queue items
    queue_items = list(state.merge_queue)
    for name in queue_items:
        if _try_merge(name, state_file, event_bus=event_bus):
            merged += 1

    # Also find merge-blocked items not in queue (safety net)
    state = load_state(state_file)  # re-read after mutations
    for change in state.changes:
        if change.status != "merge-blocked":
            continue
        if change.name in queue_items:
            continue
        if _try_merge(change.name, state_file, event_bus=event_bus):
            merged += 1

    return merged


# ─── Internal Helpers ───────────────────────────────────────────────

def _find_change(state: OrchestratorState, name: str) -> Optional[Change]:
    """Find a change by name."""
    for c in state.changes:
        if c.name == name:
            return c
    return None


def _remove_from_merge_queue(state_file: str, change_name: str) -> None:
    """Remove a change from the merge queue."""
    with locked_state(state_file) as state:
        state.merge_queue = [n for n in state.merge_queue if n != change_name]


def _get_main_branch() -> str:
    """Detect the main branch name."""
    result = run_command(
        ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
        timeout=10,
    )
    if result.exit_code == 0:
        ref = result.stdout.strip()
        return ref.replace("refs/remotes/origin/", "")
    return "main"


def _run_hook(hook_name: str, change_name: str, status: str, wt_path: str) -> bool:
    """Run an orchestration hook via subprocess. Returns True if allowed (or no hook).

    Hook scripts are user-defined shell scripts configured via directives
    (hook_pre_merge, hook_post_merge, hook_on_fail).
    """
    # Check if the hook script is configured in state directives
    from .state import load_state
    import glob as glob_mod

    # Try to find the hook from STATE_FILENAME env var
    state_file = os.environ.get("STATE_FILENAME", "")
    if not state_file or not os.path.isfile(state_file):
        return True

    try:
        state = load_state(state_file)
        directives = state.extras.get("directives", {})
    except Exception:
        return True

    hook_key = f"hook_{hook_name}"
    hook_script = directives.get(hook_key, "")
    if not hook_script:
        return True

    logger.info("Running %s hook for %s: %s", hook_name, change_name, hook_script)

    env = dict(os.environ)
    env["CHANGE_NAME"] = change_name
    env["CHANGE_STATUS"] = status
    if wt_path:
        env["WORKTREE_PATH"] = wt_path

    result = run_command(
        ["bash", "-c", hook_script],
        timeout=120,
        env=env,
    )

    if result.exit_code != 0:
        logger.warning("%s hook failed for %s (exit %d)", hook_name, change_name, result.exit_code)
        return False

    logger.info("%s hook succeeded for %s", hook_name, change_name)
    return True


def _post_merge_deps_install() -> None:
    """Install dependencies if package.json changed in the last commit."""
    diff_result = run_command(
        ["git", "diff", "HEAD~1", "--name-only"], timeout=30,
    )
    if "package.json" not in diff_result.stdout:
        return

    # Profile first, legacy fallback
    from .profile_loader import NullProfile, load_profile

    profile = load_profile()
    if not isinstance(profile, NullProfile):
        logger.info("Post-merge: package.json changed, running profile.post_merge_install()")
        profile.post_merge_install(".")
        return

    # Legacy fallback
    install_cmd = None
    if os.path.exists("pnpm-lock.yaml"):
        install_cmd = ["pnpm", "install"]
    elif os.path.exists("yarn.lock"):
        install_cmd = ["yarn", "install"]
    elif os.path.exists("package-lock.json"):
        install_cmd = ["npm", "install"]

    if install_cmd:
        logger.info("Post-merge: package.json changed, running %s", " ".join(install_cmd))
        result = run_command(install_cmd, timeout=300)
        if result.exit_code == 0:
            logger.info("Post-merge: %s succeeded", " ".join(install_cmd))
        else:
            logger.warning("Post-merge: %s failed (merge not reverted)", " ".join(install_cmd))


def _post_merge_custom_command(state_file: str) -> None:
    """Run post_merge_command from directives if configured."""
    # Source: merger.sh L169-180
    state = load_state(state_file)
    pmc = state.extras.get("directives", {}).get("post_merge_command", "")
    if not pmc:
        return

    logger.info("Post-merge: running custom command: %s", pmc)
    result = run_command(["bash", "-c", pmc], timeout=300)
    if result.exit_code == 0:
        logger.info("Post-merge: custom command succeeded")
    else:
        logger.warning("Post-merge: custom command failed (rc=%d)", result.exit_code)


def _post_merge_build_check(change_name: str, state_file: str) -> bool:
    """Verify build on main after merge. Returns True if build passes."""
    from .profile_loader import load_profile

    profile = load_profile()
    pm = profile.detect_package_manager(".") or "npm"
    build_cmd = profile.detect_build_command(".")

    if not pm or pm == "npm":
        # Legacy fallback for PM
        if os.path.exists("pnpm-lock.yaml"):
            pm = "pnpm"
        elif os.path.exists("yarn.lock"):
            pm = "yarn"

    if build_cmd:
        # Profile returns full command like "pnpm run build"
        build_parts = build_cmd.split()
    else:
        build_parts = [pm, "run", "build"]

    logger.info("Post-merge: verifying build on main after merging %s", change_name)
    result = run_command(build_parts, timeout=300)

    if result.exit_code != 0:
        logger.error("Post-merge: build FAILED on main after merging %s", change_name)
        # Attempt LLM fix via dispatcher
        try:
            from .dispatcher import fix_base_build_with_llm
            if fix_base_build_with_llm("."):
                logger.info("Post-merge: build fix succeeded after merging %s", change_name)
                return True
            else:
                logger.warning("Post-merge: build fix failed for %s", change_name)
        except Exception:
            pass
        return False

    logger.info("Post-merge: build passed on main")
    return True


def _run_smoke_pipeline(
    change_name: str,
    state_file: str,
    merge_start: float,
    merge_timeout: int,
) -> str:
    """Run post-merge smoke tests. Returns smoke result string."""
    # Source: merger.sh L226-403
    state = load_state(state_file)
    directives = state.extras.get("directives", {})
    smoke_command = directives.get("smoke_command", "")
    if not smoke_command:
        return ""

    smoke_blocking = directives.get("smoke_blocking", "false") == "true"
    smoke_timeout = int(directives.get("smoke_timeout", 120))

    update_change_field(state_file, change_name, "smoke_status", "pending")

    if smoke_blocking:
        return _blocking_smoke_pipeline(
            change_name, state_file, smoke_command, smoke_timeout,
            merge_start, merge_timeout, directives,
        )
    else:
        return _nonblocking_smoke_pipeline(
            change_name, state_file, smoke_command, smoke_timeout,
        )


def _blocking_smoke_pipeline(
    change_name: str,
    state_file: str,
    smoke_command: str,
    smoke_timeout: int,
    merge_start: float,
    merge_timeout: int,
    directives: dict,
) -> str:
    """Run blocking smoke pipeline. Returns smoke result."""
    # Source: merger.sh L239-333
    from .verifier import extract_health_check_url, health_check, smoke_fix_scoped

    # Health check
    hc_url = directives.get("smoke_health_check_url", "")
    if not hc_url:
        hc_url = extract_health_check_url(smoke_command)

    hc_timeout = int(directives.get("smoke_health_check_timeout", 30))

    update_change_field(state_file, change_name, "smoke_status", "checking")
    if hc_url and not health_check(hc_url, timeout_secs=hc_timeout):
        # Try auto-starting dev server
        dev_cmd = directives.get("smoke_dev_server_command", "")
        if dev_cmd:
            logger.info("Post-merge: health check failed, auto-starting dev server")
            import subprocess
            proc = subprocess.Popen(
                ["bash", "-c", dev_cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if health_check(hc_url, timeout_secs=60):
                logger.info("Post-merge: dev server auto-started (PID %d)", proc.pid)
            else:
                logger.error("Post-merge: dev server auto-start failed")
                proc.kill()
                update_change_field(state_file, change_name, "smoke_result", "blocked")
                update_change_field(state_file, change_name, "smoke_status", "blocked")
                update_change_field(state_file, change_name, "status", "smoke_blocked")
                return "blocked"
        else:
            logger.error("Post-merge: health check FAILED — no server at %s", hc_url)
            update_change_field(state_file, change_name, "smoke_result", "blocked")
            update_change_field(state_file, change_name, "smoke_status", "blocked")
            update_change_field(state_file, change_name, "status", "smoke_blocked")
            return "blocked"

    # Recompile buffer
    time.sleep(5)

    # Run smoke tests
    update_change_field(state_file, change_name, "smoke_status", "running")
    logger.info("Post-merge: running smoke tests (blocking) for %s", change_name)

    smoke_result = run_command(
        ["bash", "-c", smoke_command], timeout=smoke_timeout,
    )
    _collect_smoke_screenshots(change_name, state_file)

    smoke_output = (smoke_result.stdout or "")[-2000:]
    update_change_field(state_file, change_name, "smoke_output", smoke_output)

    if smoke_result.exit_code == 0:
        logger.info("Post-merge: smoke tests passed for %s", change_name)
        update_change_field(state_file, change_name, "smoke_result", "pass")
        update_change_field(state_file, change_name, "smoke_status", "done")
        return "pass"

    logger.error("Post-merge: smoke tests FAILED for %s (exit %d)", change_name, smoke_result.exit_code)
    update_change_field(state_file, change_name, "smoke_result", "fail")
    update_change_field(state_file, change_name, "smoke_fix_attempts", 0)

    # Check timeout before fix
    if (time.time() - merge_start) >= merge_timeout:
        update_change_field(state_file, change_name, "status", "merge_timeout")
        update_change_field(state_file, change_name, "smoke_status", "timeout")
        return "fail"

    # Scoped fix
    max_retries = int(directives.get("smoke_fix_max_retries", 3))
    max_turns = int(directives.get("smoke_fix_max_turns", 15))
    if smoke_fix_scoped(
        change_name, smoke_command, smoke_timeout,
        smoke_result.stdout[-2000:], state_file,
        max_retries=max_retries, max_turns=max_turns,
    ):
        update_change_field(state_file, change_name, "smoke_result", "fixed")
        update_change_field(state_file, change_name, "smoke_status", "done")
        return "fixed"

    update_change_field(state_file, change_name, "smoke_status", "failed")
    update_change_field(state_file, change_name, "status", "smoke_failed")
    return "fail"


def _nonblocking_smoke_pipeline(
    change_name: str,
    state_file: str,
    smoke_command: str,
    smoke_timeout: int,
) -> str:
    """Run non-blocking smoke pipeline. Returns smoke result."""
    # Source: merger.sh L335-401
    logger.info("Post-merge: running smoke tests (non-blocking) for %s", change_name)

    smoke_result = run_command(
        ["bash", "-c", smoke_command], timeout=smoke_timeout,
    )
    _collect_smoke_screenshots(change_name, state_file)
    smoke_output = (smoke_result.stdout or "")[-2000:]
    update_change_field(state_file, change_name, "smoke_output", smoke_output)

    if smoke_result.exit_code == 0:
        logger.info("Post-merge: smoke tests passed for %s", change_name)
        update_change_field(state_file, change_name, "smoke_result", "pass")
        update_change_field(state_file, change_name, "smoke_status", "done")
        return "pass"

    logger.error("Post-merge: smoke tests FAILED for %s", change_name)
    update_change_field(state_file, change_name, "smoke_result", "fail")
    update_change_field(state_file, change_name, "smoke_status", "failed")
    return "fail"


def _handle_merge_conflict(
    change_name: str, state_file: str, wt_path: str
) -> MergeResult:
    """Handle merge conflict: agent rebase or mark blocked."""
    # Source: merger.sh L416-475
    state = load_state(state_file)
    change = _find_change(state, change_name)
    retry_count = change.merge_retry_count if change else 0

    if retry_count == 0:
        logger.warning("Merge conflict for %s", change_name)
    else:
        logger.info("Merge conflict for %s (retry %d)", change_name, retry_count)

    # Pre-validate: confirm conflict actually exists
    main_branch = _get_main_branch()
    run_command(["git", "fetch", "origin", main_branch], timeout=60)

    merge_base_result = run_command(
        ["git", "merge-base", f"change/{change_name}", f"origin/{main_branch}"],
        timeout=30,
    )
    merge_base = merge_base_result.stdout.strip()

    conflict_confirmed = False
    if merge_base:
        tree_result = run_command(
            ["git", "merge-tree", merge_base, f"origin/{main_branch}", f"change/{change_name}"],
            timeout=30,
        )
        conflict_confirmed = "<<<<<<<" in tree_result.stdout

    if not conflict_confirmed:
        logger.info("No real conflict markers for %s — retrying merge", change_name)
        retry_result = run_command(
            ["wt-merge", change_name, "--no-push", "--llm-resolve"],
            timeout=300,
        )
        if retry_result.exit_code == 0:
            update_change_field(state_file, change_name, "status", "merged")
            return MergeResult(success=True, status="merged")

        logger.warning("wt-merge failed for %s but no conflict markers — merge-blocked", change_name)
        update_change_field(state_file, change_name, "status", "merge-blocked")
        return MergeResult(success=False, status="merge-blocked")

    # Agent-assisted rebase
    agent_rebase_done = False
    if change:
        agent_rebase_done = change.extras.get("agent_rebase_done", False)

    if not agent_rebase_done and wt_path and os.path.isdir(wt_path):
        update_change_field(state_file, change_name, "agent_rebase_done", True)
        logger.info("First merge conflict for %s — triggering agent-assisted rebase", change_name)

        retry_prompt = (
            f"Merge conflict: your branch conflicts with {main_branch}. "
            f"Resolve by merging {main_branch} into your branch.\n\n"
            f"Run: git fetch origin {main_branch} && git merge origin/{main_branch}\n\n"
            f"Resolve any conflicts, keeping both sides' changes where possible. "
            f"Prefer your changes (the feature) when they contradict {main_branch}. "
            f"After resolving, commit the merge."
        )
        update_change_field(state_file, change_name, "retry_context", retry_prompt)
        update_change_field(state_file, change_name, "merge_rebase_pending", True)

        from .dispatcher import resume_change
        resume_change(state_file, change_name)
        return MergeResult(success=False, status="running")  # agent rebase started

    update_change_field(state_file, change_name, "status", "merge-blocked")
    return MergeResult(success=False, status="merge-blocked")


def _compute_conflict_fingerprint(change_name: str) -> str:
    """Compute MD5 fingerprint of conflicting files for dedup."""
    # Source: merger.sh L623-631
    main_branch = _get_main_branch()
    merge_base_result = run_command(
        ["git", "merge-base", f"change/{change_name}", f"origin/{main_branch}"],
        timeout=30,
    )
    merge_base = merge_base_result.stdout.strip()
    if not merge_base:
        return ""

    tree_result = run_command(
        ["git", "merge-tree", merge_base, f"origin/{main_branch}", f"change/{change_name}"],
        timeout=30,
    )
    # Extract "+++ b/" lines, sort, hash
    lines = sorted(
        line for line in tree_result.stdout.splitlines()
        if line.startswith("+++ b/")
    )
    if not lines:
        return ""
    return hashlib.md5("\n".join(lines).encode()).hexdigest()
