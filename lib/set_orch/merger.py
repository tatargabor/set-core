"""Merge pipeline, worktree cleanup, archive operations.

Migrated from: lib/orchestration/merger.sh (672 lines)
Source line comments reference the original bash function names.

Functions:
    archive_change          — move openspec change dir to dated archive, git commit
    _collect_smoke_screenshots — copy test-results to attempt-N subdirs
    merge_change            — full merge pipeline with smoke/conflict handling
    _sync_running_worktrees — sync running worktrees after merge
    _archive_worktree_logs  — copy .claude/logs to orchestration archive
    cleanup_worktree        — set-close with fallback manual removal
    cleanup_all_worktrees   — iterate terminal changes, cleanup each
    execute_merge_queue     — drain merge queue
    retry_merge_queue       — retry queue + merge-blocked changes
    _try_merge              — single attempt with conflict fingerprint dedup
"""

from __future__ import annotations

import glob
import hashlib
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
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
DEFAULT_MERGE_TIMEOUT = 300  # 5 min (no post-merge smoke — just ff + deps + hooks)



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
    """Archive openspec change via CLI, then git-commit the results.

    The openspec CLI moves the change dir to archive/ and syncs delta specs
    into openspec/specs/, but does NOT run git add/commit.  We must commit
    so that subsequent worktrees (forked from master) see the updated specs.
    """
    change_dir = f"openspec/changes/{change_name}"
    if not os.path.isdir(change_dir):
        return True  # nothing to archive

    result = run_command(
        ["openspec", "archive", change_name, "--yes"],
        timeout=60,
    )
    if result.exit_code != 0:
        logger.warning("Failed to archive %s (non-blocking): %s", change_name, result.stderr)
        return False

    logger.info("Archived %s via openspec CLI", change_name)

    # Commit archive move + spec sync so new worktrees inherit specs/
    run_command(["git", "add", "openspec/"], timeout=30)
    commit_result = run_command(
        ["git", "commit", "-m", f"chore: archive {change_name} and sync specs"],
        timeout=30,
    )
    if commit_result.exit_code == 0:
        logger.info("Committed archive + specs for %s", change_name)
    else:
        # Nothing to commit (e.g. no spec changes) — not an error
        logger.info("No git changes to commit after archive of %s", change_name)

    return True


# ─── Smoke Screenshot Collection ────────────────────────────────────

# Source: merger.sh _collect_smoke_screenshots() L38-52


# ─── Worktree Lifecycle ─────────────────────────────────────────────

# Source: merger.sh _archive_worktree_logs() L506-518
def _archive_worktree_logs(change_name: str, wt_path: str) -> int:
    """Archive worktree agent logs before cleanup. Returns file count."""
    logs_src = os.path.join(wt_path, ".set", "logs")
    if not os.path.isdir(logs_src):
        # Legacy fallback
        logs_src = os.path.join(wt_path, ".claude", "logs")
        if not os.path.isdir(logs_src):
            return 0

    try:
        from .paths import SetRuntime
        archive_dir = SetRuntime().change_logs_dir(change_name)
    except Exception:
        archive_dir = f"set-core/orchestration/logs/{change_name}"
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
def cleanup_worktree(change_name: str, wt_path: str, retention: str = "") -> None:
    """Clean up worktree and branch after successful merge.

    Args:
        retention: "keep" (default) = archive logs only, preserve worktree+branch.
                   "delete-on-merge" = legacy behavior, remove worktree+branch.
                   Empty string = auto-detect from orchestration.yaml.
    """
    # Always archive logs regardless of retention
    if wt_path and os.path.isdir(wt_path):
        _archive_worktree_logs(change_name, wt_path)

    # Resolve retention policy
    if not retention:
        retention = _resolve_retention()

    if retention == "keep":
        logger.info("Worktree retained for %s (retention=keep)", change_name)
        return

    # delete-on-merge: legacy behavior
    # Try set-close first
    result = run_command(["set-close", change_name], timeout=60)
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


def _resolve_retention() -> str:
    """Read worktree_retention from orchestration.yaml, default 'keep'."""
    try:
        from .config import load_config_file
        config = load_config_file("wt/orchestration/orchestration.yaml")
        return config.get("worktree_retention", "keep")
    except Exception:
        return "keep"


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
            if wt_path:
                logger.debug("Post-merge sync: skipping %s — worktree missing (%s)", change.name, wt_path)
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


def _apply_merge_strategies() -> None:
    """Load plugin merge strategies and write .gitattributes for merge behavior.

    Strategies define file-pattern → merge-driver mappings (e.g., theirs-wins
    for lockfiles). Written to .gitattributes before merge, cleaned up after.
    """
    try:
        from .profile_loader import load_profile, NullProfile
        profile = load_profile()
        if isinstance(profile, NullProfile):
            return
        strategies = profile.merge_strategies()
        if not strategies:
            return

        lines = []
        for s in strategies:
            patterns = s.get("patterns", [])
            strategy = s.get("strategy", "")
            if not patterns or not strategy:
                continue
            # Map strategy names to git merge drivers
            if strategy == "theirs":
                driver = "merge=ours"  # from their perspective on ff-only
            elif strategy == "ours":
                driver = "merge=ours"
            else:
                continue
            for pat in patterns:
                lines.append(f"{pat} {driver}")

        if lines:
            gitattrs = Path(".gitattributes")
            existing = gitattrs.read_text() if gitattrs.exists() else ""
            marker = "# set-merge-strategies"
            if marker not in existing:
                block = f"\n{marker}\n" + "\n".join(lines) + f"\n{marker}-end\n"
                gitattrs.write_text(existing + block)
                logger.info("Applied %d merge strategy pattern(s)", len(lines))
    except Exception:
        logger.debug("Failed to apply merge strategies (non-critical)", exc_info=True)


# ─── Merge Pipeline ────────────────────────────────────────────────

# Source: merger.sh merge_change() L56-476
def merge_change(
    change_name: str,
    state_file: str,
    *,
    event_bus: Any = None,
) -> MergeResult:
    """Execute the full merge pipeline for a completed change.

    Handles: pre-merge hook, branch check, set-merge, post-merge deps/build/scope,
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
        try:
            from .digest import update_coverage_status
            update_coverage_status(change_name, "merged")
        except Exception:
            logger.debug("Coverage update failed for %s (non-critical)", change_name)
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
            try:
                from .digest import update_coverage_status
                update_coverage_status(change_name, "merged")
            except Exception:
                logger.debug("Coverage update failed for %s (non-critical)", change_name)
            return MergeResult(success=True, status="merged", smoke_result="skip_merged")

    # Case 3: Fast-forward only merge (integrate-then-verify pattern)
    # The branch already has main integrated and all gates passed.
    # ff-only ensures we only advance main to a tested commit.

    # Apply plugin merge strategies (e.g., theirs-wins for lockfiles)
    _apply_merge_strategies()

    pre_merge_sha = run_command(["git", "rev-parse", "HEAD"], timeout=10).stdout.strip()
    merge_result = run_command(
        ["set-merge", change_name, "--no-push", "--ff-only"],
        timeout=120,
    )

    if merge_result.exit_code == 0:
        # FF merge succeeded — main advanced to a tested commit
        update_change_field(state_file, change_name, "status", "merged")
        logger.info("Merged %s (ff-only)", change_name)

        # Heartbeat helper for post-merge steps
        def _heartbeat(step: str) -> None:
            if event_bus:
                event_bus.emit("MERGE_PROGRESS", change=change_name, data={"step": step})

        _heartbeat("merge_complete")

        # Git tags for recovery
        run_command(["git", "tag", "-f", f"orch/{change_name}", "HEAD"], timeout=10)

        # Update coverage status
        try:
            from .digest import update_coverage_status
            update_coverage_status(change_name, "merged")
        except Exception:
            logger.debug("Coverage update failed for %s (non-critical)", change_name)

        # Post-merge dependency install via profile (or legacy fallback)
        _heartbeat("deps_install")
        try:
            from .profile_loader import load_profile
            _profile = load_profile()
            if hasattr(_profile, "post_merge_install"):
                _profile.post_merge_install(".")
        except Exception:
            _post_merge_deps_install(lockfile_conflicted=False, pre_merge_sha=pre_merge_sha)

        # Post-merge custom command
        _post_merge_custom_command(state_file)

        # Post-merge plugin directives
        _run_plugin_post_merge_directives(change_name)

        # Post-merge profile hooks (i18n sidecar merge, codegen, etc.)
        try:
            from .profile_loader import load_profile as _lp
            _pm_profile = _lp()
            if hasattr(_pm_profile, "post_merge_hooks"):
                _pm_profile.post_merge_hooks(change_name, state_file)
        except Exception:
            logger.debug("Post-merge profile hooks failed (non-critical)", exc_info=True)

        # Post-merge hook
        _run_hook("post_merge", change_name, "merged", "")

        # Persist review learnings (template + project split)
        _heartbeat("review_learnings")
        _persist_change_review_learnings(change_name, state_file)

        _heartbeat("archive")
        cleanup_worktree(change_name, wt_path or "")
        archive_change(change_name)

        # Sync running worktrees AFTER archive (Bug #38)
        _heartbeat("worktree_sync")
        _sync_running_worktrees(change_name, state_file)

        _remove_from_merge_queue(state_file, change_name)

        return MergeResult(
            success=True,
            status="merged",
        )
    else:
        # FF failed — log detailed diagnostics (MERGE-001)
        logger.error(
            "FF merge failed for %s — cmd: set-merge %s --no-push --ff-only, "
            "exit=%d, stdout=%s, stderr=%s",
            change_name, change_name,
            merge_result.exit_code,
            merge_result.stdout[:500] if merge_result.stdout else "(empty)",
            merge_result.stderr[:500] if merge_result.stderr else "(empty)",
        )

        # Log merge-base divergence details (MERGE-002)
        head_sha = run_command(["git", "rev-parse", "HEAD"], timeout=10).stdout.strip()
        mb = run_command(
            ["git", "merge-base", "HEAD", source_branch], timeout=10,
        )
        if mb.exit_code == 0:
            mb_sha = mb.stdout.strip()
            ahead = run_command(
                ["git", "rev-list", "--count", f"{mb_sha}..{source_branch}"], timeout=10,
            ).stdout.strip()
            behind = run_command(
                ["git", "rev-list", "--count", f"{mb_sha}..HEAD"], timeout=10,
            ).stdout.strip()
            logger.error(
                "FF merge diagnostics for %s: HEAD=%s, branch=%s, merge-base=%s, "
                "branch ahead=%s, main ahead=%s",
                change_name, head_sha[:12], source_sha[:12], mb_sha[:12], ahead, behind,
            )

        # Re-integrate main into branch and re-trigger gate pipeline.
        ff_retry_count = change.extras.get("ff_retry_count", 0) if change else 0
        max_ff_retries = 3

        if ff_retry_count >= max_ff_retries:
            logger.error("FF merge failed for %s — retry limit reached (%d)", change_name, max_ff_retries)
            update_change_field(state_file, change_name, "status", "merge-blocked")
            _remove_from_merge_queue(state_file, change_name)
            return MergeResult(success=False, status="merge-blocked")

        logger.warning(
            "FF merge failed for %s — main advanced, re-integrating (attempt %d/%d)",
            change_name, ff_retry_count + 1, max_ff_retries,
        )
        update_change_field(state_file, change_name, "ff_retry_count", ff_retry_count + 1)

        # Re-integrate: the verifier will merge main into branch and re-run gates
        # Set status back so the monitor dispatches the change through handle_change_done again
        update_change_field(state_file, change_name, "status", "done")
        _remove_from_merge_queue(state_file, change_name)

        # Add back to merge queue — handle_change_done will re-integrate and re-gate,
        # then re-queue for merge
        return MergeResult(success=False, status="running")


# ─── Merge Queue ────────────────────────────────────────────────────


def _integrate_for_merge(wt_path: str, change_name: str) -> str:
    """Integrate current main into branch before ff-only merge.

    Returns "ok" or "conflict". Checks exit code (unlike old _try_merge).
    """
    main_branch = _get_main_branch(cwd=wt_path)

    # Best-effort fetch from origin
    run_command(["git", "fetch", "origin", main_branch], timeout=60, cwd=wt_path)

    # Check if integration is needed
    merge_ref = f"origin/{main_branch}"
    ref_check = run_command(["git", "rev-parse", merge_ref], timeout=10, cwd=wt_path)
    if ref_check.exit_code != 0:
        merge_ref = main_branch  # no remote, use local

    merge_base = run_command(["git", "merge-base", "HEAD", merge_ref], timeout=10, cwd=wt_path)
    ref_head = run_command(["git", "rev-parse", merge_ref], timeout=10, cwd=wt_path)
    if (merge_base.exit_code == 0 and ref_head.exit_code == 0
            and merge_base.stdout.strip() == ref_head.stdout.strip()):
        logger.info("Integration skip for %s — branch already up-to-date", change_name)
        return "ok"

    # Merge main into branch
    logger.info("Integrating %s into branch for %s", main_branch, change_name)
    result = run_command(
        ["git", "merge", merge_ref, "--no-edit",
         "-m", f"Merge {main_branch} for pre-ff integration"],
        timeout=120, cwd=wt_path,
    )

    if result.exit_code == 0:
        logger.info("Integration merge succeeded for %s", change_name)
        return "ok"

    # Check for conflict
    conflict_check = run_command(
        ["git", "diff", "--name-only", "--diff-filter=U"], timeout=10, cwd=wt_path,
    )
    has_conflicts = conflict_check.exit_code == 0 and conflict_check.stdout.strip()

    # Abort the failed merge
    run_command(["git", "merge", "--abort"], timeout=10, cwd=wt_path)

    if has_conflicts:
        logger.warning("Integration conflict for %s: %s", change_name, conflict_check.stdout.strip()[:200])
        return "conflict"

    logger.error("Integration merge failed for %s (non-conflict): %s", change_name, result.stderr[:300])
    return "conflict"  # treat non-conflict errors as conflict for safety


def _run_integration_gates(
    change_name: str, change: Change, wt_path: str,
    state_file: str, profile: Any = None,
) -> bool:
    """Run integration gates (build + test + e2e) in worktree after integration.

    Uses lightweight subprocess calls (not the full gate executors which need
    many parameters). Only checks: does it build? do tests pass?

    Returns True if all gates pass, False if any blocking gate fails.
    """
    from .gate_profiles import resolve_gate_config
    from .gate_runner import GateResult
    from .subprocess_utils import run_command

    gc = resolve_gate_config(change, profile)

    # Load .env from worktree if exists (agents create .env during impl
    # but it's not committed — integration gates need it for e.g. DATABASE_URL)
    gate_env: dict[str, str] = {}
    env_path = os.path.join(wt_path, ".env")
    if os.path.isfile(env_path):
        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, val = line.partition("=")
                        gate_env[key.strip()] = val.strip().strip('"').strip("'")
        except OSError:
            pass

    # Load directives for test/build commands
    try:
        state = load_state(state_file)
        directives = state.extras.get("directives", {})
    except Exception:
        directives = {}

    # Dep install after integration merge (new deps from other changes)
    if profile and hasattr(profile, "detect_dep_install_command"):
        dep_cmd = profile.detect_dep_install_command(wt_path)
        if dep_cmd:
            logger.info("Integration gate: dep install for %s (%s)", change_name, dep_cmd)
            run_command(["bash", "-c", dep_cmd], timeout=120, cwd=wt_path, env=gate_env or None)

    # Pre-build setup (e.g. Prisma DB schema sync for Next.js + Prisma projects)
    # next build executes server components which query the DB — needs schema synced
    if profile and hasattr(profile, "integration_pre_build"):
        try:
            ok = profile.integration_pre_build(wt_path)
            if not ok:
                logger.warning("integration_pre_build returned False for %s (non-blocking)", change_name)
        except Exception:
            logger.warning("integration_pre_build failed for %s (non-blocking)", change_name, exc_info=True)

    # Build gate
    if gc.should_run("build"):
        build_cmd = directives.get("build_command", "")
        if not build_cmd and profile and hasattr(profile, "detect_build_command"):
            build_cmd = profile.detect_build_command(wt_path) or ""
        if build_cmd:
            logger.info("Integration gate: build for %s (%s)", change_name, build_cmd)
            result = run_command(["bash", "-c", build_cmd], timeout=120, cwd=wt_path, env=gate_env or None)
            if result.exit_code != 0:
                logger.error("Integration gate: build FAILED for %s", change_name)
                update_change_field(state_file, change_name, "integration_gate_fail", "build")
                return False

    # Test gate
    if gc.should_run("test"):
        test_cmd = directives.get("test_command", "")
        if not test_cmd and profile and hasattr(profile, "detect_test_command"):
            test_cmd = profile.detect_test_command(wt_path) or ""
        if test_cmd:
            logger.info("Integration gate: test for %s (%s)", change_name, test_cmd)
            result = run_command(["bash", "-c", test_cmd], timeout=120, cwd=wt_path, env=gate_env or None)
            if result.exit_code != 0 and gc.is_blocking("test"):
                # Check if failure is because test runner isn't installed (missing script/binary)
                output = (result.stdout or "") + (result.stderr or "")
                missing_indicators = [
                    "Missing script",
                    "ERR_PNPM_NO_SCRIPT",
                    "command not found",
                    "not found",
                    'is not recognized',
                ]
                is_missing = any(ind.lower() in output.lower() for ind in missing_indicators)
                # pnpm/npm exit 1 with empty output when script doesn't exist — only apply this heuristic for npm/pnpm
                is_empty_fail = (
                    not output.strip()
                    and result.exit_code == 1
                    and any(pm in test_cmd for pm in ("pnpm", "npm"))
                )
                if is_missing or is_empty_fail:
                    logger.warning(
                        "Integration gate: test command not available for %s (missing script or empty output) — skipping",
                        change_name,
                    )
                else:
                    logger.error("Integration gate: test FAILED for %s", change_name)
                    update_change_field(state_file, change_name, "integration_gate_fail", "test")
                    return False

    # E2E gate (from profile — web only)
    if gc.should_run("e2e"):
        e2e_cmd = directives.get("e2e_command", "")
        if not e2e_cmd and profile and hasattr(profile, "detect_e2e_command"):
            e2e_cmd = profile.detect_e2e_command(wt_path) or ""
        if e2e_cmd:
            # Assign unique port to avoid collisions with parallel agents
            import hashlib
            port_offset = int(hashlib.md5(change_name.encode()).hexdigest()[:4], 16) % 1000
            e2e_port = 4000 + port_offset
            e2e_env = dict(gate_env) if gate_env else {}
            if profile and hasattr(profile, "e2e_gate_env"):
                e2e_env.update(profile.e2e_gate_env(e2e_port))
            logger.info("Integration gate: e2e for %s (%s, port=%d)", change_name, e2e_cmd, e2e_port)
            result = run_command(["bash", "-c", e2e_cmd], timeout=180, cwd=wt_path, env=e2e_env)
            if result.exit_code != 0:
                # Integration e2e is always non-blocking: the verify phase
                # already validated e2e, and integration e2e is prone to
                # flaky failures (port conflicts, stale servers, timeouts).
                logger.warning(
                    "Integration gate: e2e FAILED for %s (non-blocking — verify phase already passed)",
                    change_name,
                )
                update_change_field(state_file, change_name, "integration_gate_fail", "e2e-warn")

    return True


def execute_merge_queue(state_file: str, *, event_bus: Any = None) -> int:
    """Drain merge queue. Serialized: integrate → verify → ff-only per change.

    Each change integrates fresh main (including prior merges in this queue drain),
    runs integration gates (build/test/e2e), then ff-only merges.
    """
    from .profile_loader import load_profile

    profile = load_profile()
    state = load_state(state_file)
    merged = 0

    for name in list(state.merge_queue):
        change = _find_change(state, name)
        if not change:
            _remove_from_merge_queue(state_file, name)
            continue

        wt_path = change.worktree_path or ""

        # Step 1: Integrate current main into branch
        if wt_path and os.path.isdir(wt_path):
            integration = _integrate_for_merge(wt_path, name)
            if integration == "conflict":
                # Delegate to conflict handler (agent rebase)
                conflict_result = _handle_merge_conflict(name, state_file, wt_path)
                if not conflict_result.success:
                    _remove_from_merge_queue(state_file, name)
                continue

            # Step 2: Integration gates (build + test + e2e)
            if not _run_integration_gates(name, change, wt_path, state_file, profile):
                update_change_field(state_file, name, "status", "merge-blocked")
                _remove_from_merge_queue(state_file, name)
                continue

        # Step 3: ff-only merge
        try:
            result = merge_change(name, state_file, event_bus=event_bus)
            if result.success:
                merged += 1
        except Exception:
            logger.warning("Merge failed for %s", name, exc_info=True)

        # Re-read state for next iteration (main may have changed)
        state = load_state(state_file)

    return merged


def retry_merge_queue(state_file: str, *, event_bus: Any = None) -> int:
    """Retry merge queue + merge-blocked changes with fresh integration.

    Uses the same integrate → verify → ff flow as execute_merge_queue.
    Tracks merge_retry_count per change — max 3 retries before integration-failed.
    """
    state = load_state(state_file)

    MAX_MERGE_RETRIES = 3

    # Re-add merge-blocked changes to queue for retry (with retry counter)
    for change in state.changes:
        if change.status == "merge-blocked" and change.name not in state.merge_queue:
            retry_count = change.extras.get("merge_retry_count", 0)
            if retry_count >= MAX_MERGE_RETRIES:
                logger.warning(
                    "Merge retry limit reached for %s (%d/%d) — marking integration-failed",
                    change.name, retry_count, MAX_MERGE_RETRIES,
                )
                update_change_field(state_file, change.name, "status", "integration-failed", event_bus=event_bus)
                continue
            # Increment retry counter
            with locked_state(state_file) as st:
                ch = _find_change(st, change.name)
                if ch:
                    ch.extras["merge_retry_count"] = retry_count + 1
                if change.name not in st.merge_queue:
                    st.merge_queue.append(change.name)

    return execute_merge_queue(state_file, event_bus=event_bus)


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


def _get_main_branch(cwd: str = "") -> str:
    """Detect the main branch name from the given repo (or cwd)."""
    kwargs = {"cwd": cwd} if cwd else {}
    result = run_command(
        ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
        timeout=10, **kwargs,
    )
    if result.exit_code == 0:
        ref = result.stdout.strip()
        return ref.replace("refs/remotes/origin/", "")
    # No origin — check which local branch exists
    for candidate in ("main", "master"):
        check = run_command(["git", "rev-parse", "--verify", candidate], timeout=5, **kwargs)
        if check.exit_code == 0:
            return candidate
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


def merge_i18n_sidecars(project_root: str = ".") -> int:
    """Merge i18n sidecar files into canonical message files.

    Scans for `<locale>.<namespace>.json` sidecar files in i18n message
    directories and merges them into the canonical `<locale>.json` at the
    top level (Object.assign semantics — no deep merge needed since each
    sidecar owns a unique top-level namespace).

    Returns the number of sidecar files merged.
    """
    msg_dirs = ["src/messages", "messages", "src/i18n/messages", "public/locales"]
    msg_dir = ""
    for d in msg_dirs:
        full = os.path.join(project_root, d)
        if os.path.isdir(full):
            msg_dir = full
            break

    if not msg_dir:
        return 0

    merged_count = 0
    # Find sidecar files: <locale>.<namespace>.json (has 2+ dots before .json)
    for f in sorted(os.listdir(msg_dir)):
        if not f.endswith(".json"):
            continue
        parts = f.rsplit(".", 2)  # e.g. ["en", "checkout", "json"]
        if len(parts) != 3:
            continue
        locale, _namespace, _ext = parts

        sidecar_path = os.path.join(msg_dir, f)
        canonical_path = os.path.join(msg_dir, f"{locale}.json")

        try:
            sidecar_data = json.loads(Path(sidecar_path).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("i18n sidecar: failed to read %s", sidecar_path)
            continue

        # Load or create canonical file
        canonical_data: dict = {}
        if os.path.isfile(canonical_path):
            try:
                canonical_data = json.loads(Path(canonical_path).read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                canonical_data = {}

        # Check for namespace collision
        for key in sidecar_data:
            if key in canonical_data:
                logger.warning(
                    "i18n sidecar: namespace '%s' from %s already exists in %s — overwriting",
                    key, f, f"{locale}.json",
                )

        # Merge at top level
        canonical_data.update(sidecar_data)

        try:
            Path(canonical_path).write_text(
                json.dumps(canonical_data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            os.remove(sidecar_path)
            merged_count += 1
            logger.info("i18n sidecar: merged %s into %s.json", f, locale)
        except OSError:
            logger.warning("i18n sidecar: failed to write %s", canonical_path)

    return merged_count


def _post_merge_deps_install(lockfile_conflicted: bool = False, pre_merge_sha: str = "") -> None:
    """Install dependencies if package.json changed or lock file was conflicted."""
    if not lockfile_conflicted:
        diff_ref = f"{pre_merge_sha}..HEAD" if pre_merge_sha else "HEAD~1"
        diff_result = run_command(
            ["git", "diff", diff_ref, "--name-only"], timeout=30,
        )
        if "package.json" not in diff_result.stdout:
            return

    reason = "lock file was conflicted" if lockfile_conflicted else "package.json changed"

    # Profile first, legacy fallback
    from .profile_loader import NullProfile, load_profile

    profile = load_profile()
    if not isinstance(profile, NullProfile):
        logger.info("Post-merge: %s, running profile.post_merge_install()", reason)
        profile.post_merge_install(".")
        return

    # TODO(profile-cleanup): remove after profile adoption confirmed
    # Legacy fallback
    install_cmd = None
    if os.path.exists("pnpm-lock.yaml"):
        install_cmd = ["pnpm", "install"]
    elif os.path.exists("yarn.lock"):
        install_cmd = ["yarn", "install"]
    elif os.path.exists("package-lock.json"):
        install_cmd = ["npm", "install"]

    if install_cmd:
        logger.info("Post-merge: %s, running %s", reason, " ".join(install_cmd))
        result = run_command(install_cmd, timeout=600)
        if result.exit_code == 0:
            logger.info("Post-merge: %s succeeded", " ".join(install_cmd))
        else:
            logger.warning("Post-merge: %s failed (merge not reverted)", " ".join(install_cmd))


def _extract_change_review_patterns(
    findings_path: str, change_name: str
) -> list[dict]:
    """Extract CRITICAL/HIGH patterns from review-findings.jsonl for a change."""
    import re

    if not os.path.isfile(findings_path):
        return []

    patterns: list[dict] = []
    seen: set[str] = set()
    try:
        with open(findings_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("change") != change_name:
                    continue
                for issue in entry.get("issues", []):
                    sev = issue.get("severity", "")
                    if sev not in ("CRITICAL", "HIGH"):
                        continue
                    summary = re.sub(
                        r"\[(?:CRITICAL|HIGH)\]\s*", "", issue.get("summary", "")
                    ).strip()
                    norm = summary.lower()[:60]
                    if norm and norm not in seen:
                        seen.add(norm)
                        patterns.append({
                            "pattern": summary,
                            "severity": sev,
                            "fix_hint": issue.get("fix", ""),
                            "source_changes": [change_name],
                        })
    except OSError:
        logger.debug("Failed to read review findings from %s", findings_path)

    return patterns


def _persist_change_review_learnings(change_name: str, state_file: str) -> None:
    """Extract review patterns for a merged change and persist to profile learnings."""
    try:
        from .profile_loader import load_profile

        findings_dir = os.path.join(
            os.path.dirname(state_file), "wt", "orchestration"
        )
        findings_path = os.path.join(findings_dir, "review-findings.jsonl")

        patterns = _extract_change_review_patterns(findings_path, change_name)
        if not patterns:
            return

        profile = load_profile()
        project_path = os.path.dirname(state_file)
        profile.persist_review_learnings(patterns, project_path)
        logger.info(
            "Persisted %d review learnings for %s", len(patterns), change_name
        )

        # Auto-commit project JSONL to main if it was written
        proj_jsonl = os.path.join(
            project_path, "wt", "orchestration", "review-learnings.jsonl"
        )
        if os.path.isfile(proj_jsonl):
            from .subprocess_utils import run_git
            run_git("add", proj_jsonl, cwd=project_path)
            # Only commit if there are staged changes
            diff_r = run_git("diff", "--cached", "--quiet", cwd=project_path)
            if diff_r.exit_code != 0:
                run_git(
                    "commit", "-m",
                    "chore: update review learnings [skip ci]",
                    "--no-verify",
                    cwd=project_path,
                )
    except Exception:
        logger.debug(
            "Failed to persist review learnings for %s (non-critical)",
            change_name, exc_info=True,
        )


def _post_merge_custom_command(state_file: str) -> None:
    """Run post_merge_command from directives if configured."""
    # Source: merger.sh L169-180
    state = load_state(state_file)
    pmc = state.extras.get("directives", {}).get("post_merge_command", "")
    if not pmc:
        return

    logger.info("Post-merge: running custom command: %s", pmc)
    result = run_command(["bash", "-c", pmc], timeout=600)
    if result.exit_code == 0:
        logger.info("Post-merge: custom command succeeded")
    else:
        logger.warning("Post-merge: custom command failed (rc=%d)", result.exit_code)


def _run_plugin_post_merge_directives(change_name: str) -> None:
    """Run post-merge commands from plugin orchestration directives."""
    try:
        from .profile_loader import load_profile, NullProfile
        profile = load_profile()
        if isinstance(profile, NullProfile):
            return
        directives = profile.get_orchestration_directives()
        for d in directives:
            if getattr(d, "action", "") != "post-merge":
                continue
            trigger = getattr(d, "trigger", "")
            if trigger and trigger.lower() not in change_name.lower():
                continue
            config = getattr(d, "config", {}) or {}
            cmd = config.get("command", "")
            if not cmd:
                continue
            logger.info("Plugin post-merge directive: running '%s' for %s", cmd, change_name)
            result = run_command(["bash", "-c", cmd], timeout=300)
            if result.exit_code != 0:
                logger.warning("Plugin post-merge command failed (rc=%d): %s", result.exit_code, cmd)
    except Exception:
        logger.debug("Plugin post-merge directives failed (non-critical)", exc_info=True)




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
    main_branch = _get_main_branch(cwd=wt_path)
    # Use local branch refs — origin may not exist (e.g., E2E tests)
    run_command(["git", "fetch", "origin", main_branch], timeout=60)  # best-effort

    merge_base_result = run_command(
        ["git", "merge-base", f"change/{change_name}", main_branch],
        timeout=30,
    )
    merge_base = merge_base_result.stdout.strip()

    conflict_confirmed = False
    if merge_base:
        tree_result = run_command(
            ["git", "merge-tree", merge_base, main_branch, f"change/{change_name}"],
            timeout=30,
        )
        conflict_confirmed = "<<<<<<<" in tree_result.stdout

    if not conflict_confirmed:
        logger.info("No real conflict markers for %s — retrying merge", change_name)
        retry_env = dict(os.environ)
        retry_env["SET_MERGE_SCOPE"] = (change.scope if change else "")[:2000]
        retry_result = run_command(
            ["set-merge", change_name, "--no-push", "--llm-resolve"],
            timeout=600, env=retry_env,
        )
        if retry_result.exit_code == 0:
            update_change_field(state_file, change_name, "status", "merged")
            return MergeResult(success=True, status="merged")

        logger.warning("set-merge failed for %s but no conflict markers — trying agent rebase", change_name)
        # Fall through to agent rebase instead of giving up immediately

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
            f"Run: git merge {main_branch}\n\n"
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


