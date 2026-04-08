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

from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _set_completed_at_if_missing(state_file: str, change_name: str) -> None:
    """Set completed_at if not already set (verifier may have set it on 'done')."""
    state = load_state(state_file)
    change = _find_change(state, change_name)
    if change and not change.completed_at:
        update_change_field(state_file, change_name, "completed_at", datetime.now(timezone.utc).isoformat())

def _final_token_collect(state_file: str, change_name: str, wt_path: str) -> None:
    """Read loop-state.json tokens one last time before worktree cleanup."""
    if not wt_path or not os.path.isdir(wt_path):
        logger.debug("_final_token_collect: wt_path missing for %s: %s", change_name, wt_path)
        return
    loop_state_path = os.path.join(wt_path, ".set", "loop-state.json")
    if not os.path.isfile(loop_state_path):
        logger.debug("_final_token_collect: loop-state.json missing at %s", loop_state_path)
        return
    try:
        with open(loop_state_path) as f:
            ls = json.load(f)
        tokens = ls.get("total_tokens", 0) or 0
        in_tok = ls.get("total_input_tokens", 0) or 0
        out_tok = ls.get("total_output_tokens", 0) or 0
        cr_tok = ls.get("total_cache_read", 0) or 0
        cc_tok = ls.get("total_cache_create", 0) or 0
        if tokens > 0 or in_tok > 0:
            from .verifier import _accumulate_tokens
            _accumulate_tokens(state_file, change_name, {
                "total": tokens,
                "input": in_tok,
                "output": out_tok,
                "cache_read": cr_tok,
                "cache_create": cc_tok,
            })
            logger.info("Final token collect for %s: total=%d in=%d out=%d", change_name, tokens, in_tok, out_tok)
    except (json.JSONDecodeError, OSError):
        logger.debug("Failed to read loop-state for final token collect: %s", change_name)


# ─── Constants ──────────────────────────────────────────────────────

MAX_MERGE_RETRIES = 3
MAX_TOTAL_MERGE_ATTEMPTS = 10  # hard cap — never retry beyond this regardless of counter resets
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
    so that subsequent worktrees (forked from main) see the updated specs.
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


def _collect_test_artifacts(change_name: str, wt_path: str, state_file: str) -> None:
    """Collect test artifacts (screenshots, traces) from a worktree.

    Stores results in the change extras so the web dashboard can display them.
    Called after integration gates and after merge — whichever produces artifacts.
    Silently returns if worktree is missing or has no artifacts.
    """
    if not wt_path or not os.path.isdir(wt_path):
        logger.debug("Skipping artifact collection for %s: wt_path missing", change_name)
        return

    try:
        from .profile_loader import load_profile as _lp_art, NullProfile as _NP_art
        profile = _lp_art(wt_path)
        if isinstance(profile, _NP_art):
            logger.warning(
                "[ANOMALY] NullProfile for test artifact collection in %s "
                "— project-type detection failed",
                wt_path,
            )
        artifacts = profile.collect_test_artifacts(wt_path)
    except Exception:
        logger.warning("collect_test_artifacts() failed for %s", change_name, exc_info=True)
        return

    if not artifacts:
        logger.debug("No test artifacts found for %s in %s", change_name, wt_path)
        return

    images = [a for a in artifacts if a.get("type") == "image"]
    logger.info("Test artifacts: %d items (%d images) for %s", len(artifacts), len(images), change_name)

    # Save counts via update_change_field (top-level fields)
    update_change_field(state_file, change_name, "e2e_screenshot_count", len(images))
    if images:
        first_dir = os.path.dirname(os.path.dirname(images[0]["path"]))
        update_change_field(state_file, change_name, "e2e_screenshot_dir", first_dir)

    # Save full artifact list in extras via locked_state
    try:
        with locked_state(state_file) as _ast:
            _ach = next((c for c in _ast.changes if c.name == change_name), None)
            if _ach:
                _ach.extras["test_artifacts"] = artifacts
    except Exception:
        logger.warning("Failed to save test_artifacts to state for %s", change_name, exc_info=True)


# ─── Worktree Lifecycle ─────────────────────────────────────────────

# Source: merger.sh _archive_worktree_logs() L506-518
def _archive_worktree_logs(change_name: str, wt_path: str) -> int:
    """Archive worktree agent logs before cleanup. Returns file count."""
    logs_src = os.path.join(wt_path, ".set", "logs")
    if not os.path.isdir(logs_src):
        # Legacy fallback
        logs_src = os.path.join(wt_path, ".claude", "logs")
        if not os.path.isdir(logs_src):
            logger.debug("_archive_worktree_logs: no logs dir found in %s", wt_path)
            return 0
        logger.debug("_archive_worktree_logs: using legacy .claude/logs in %s", wt_path)

    try:
        from .paths import SetRuntime
        archive_dir = SetRuntime().change_logs_dir(change_name)
    except Exception as _e:
        archive_dir = f"set-core/orchestration/logs/{change_name}"
        logger.warning("Log archive: SetRuntime failed (%s), using fallback: %s", _e, archive_dir)
    os.makedirs(archive_dir, exist_ok=True)

    count = 0
    for f in glob.glob(os.path.join(logs_src, "*.log")):
        dest = os.path.join(archive_dir, os.path.basename(f))
        if not os.path.exists(dest):
            try:
                shutil.copy2(f, dest)
                count += 1
            except Exception as _e:
                logger.debug("Failed to copy log %s: %s", f, _e)
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
        path = "set/orchestration/config.yaml"
        if not os.path.isfile(path):
            path = "set/orchestration/config.yaml"  # legacy fallback
        config = load_config_file(path)
        result = config.get("worktree_retention", "keep")
        logger.debug("_resolve_retention: %s (from %s)", result, path)
        return result
    except Exception as _e:
        logger.debug("_resolve_retention: config load failed (%s), defaulting to 'keep'", _e)
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
    except Exception as _e:
        logger.debug("Milestone cleanup failed: %s", _e)

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
        profile = load_profile(os.getcwd())
        logger.debug("_apply_merge_strategies: profile=%s from cwd=%s", type(profile).__name__, os.getcwd())
        if isinstance(profile, NullProfile):
            logger.debug("_apply_merge_strategies: NullProfile — skipping")
            return
        strategies = profile.merge_strategies()
        if not strategies:
            logger.debug("_apply_merge_strategies: no strategies defined by %s", type(profile).__name__)
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
        logger.warning("Failed to apply merge strategies", exc_info=True)


def _clean_untracked_merge_conflicts(change_name: str) -> None:
    """Remove untracked files that would block ff-only merge.

    set-project init deploys files (CLAUDE.md, .gitignore, etc.) to the main
    worktree without committing them. When the branch has these files committed,
    git merge --ff-only refuses: 'untracked working tree files would be overwritten'.
    We detect and remove only the conflicting untracked files.
    """
    branch_ref = f"change/{change_name}"
    # List files the branch adds that don't exist in current HEAD
    diff_result = run_command(
        ["git", "diff", "--name-only", "--diff-filter=A", "HEAD", branch_ref],
        timeout=10,
    )
    if diff_result.exit_code != 0 or not diff_result.stdout.strip():
        logger.debug("_clean_untracked_merge_conflicts: no added files for %s (exit=%d)", change_name, diff_result.exit_code)
        return

    added_files = diff_result.stdout.strip().splitlines()

    # Check which of those are untracked in the working tree
    status_result = run_command(["git", "status", "--porcelain"], timeout=10)
    untracked = set()
    for line in status_result.stdout.splitlines():
        if line.startswith("?? "):
            untracked.add(line[3:].strip())

    removed = []
    for f in added_files:
        if f in untracked:
            try:
                Path(f).unlink()
                removed.append(f)
            except OSError as _e:
                logger.debug("Failed to remove untracked conflict file %s: %s", f, _e)

    if removed:
        logger.info(
            "Removed %d untracked file(s) conflicting with %s merge: %s",
            len(removed), change_name, ", ".join(removed),
        )


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
        _set_completed_at_if_missing(state_file, change_name)
        update_change_field(state_file, change_name, "smoke_result", "skip_merged")
        update_change_field(state_file, change_name, "smoke_status", "skipped")
        cleanup_worktree(change_name, wt_path or "")
        update_change_field(state_file, change_name, "current_step", "archiving")
        archive_change(change_name)
        update_change_field(state_file, change_name, "current_step", "done")
        _remove_from_merge_queue(state_file, change_name)
        try:
            from .digest import update_coverage_status
            update_coverage_status(change_name, "merged")
        except Exception:
            logger.warning("Coverage update failed for %s", change_name, exc_info=True)
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
            _set_completed_at_if_missing(state_file, change_name)
            update_change_field(state_file, change_name, "smoke_result", "skip_merged")
            update_change_field(state_file, change_name, "smoke_status", "skipped")
            cleanup_worktree(change_name, wt_path or "")
            archive_change(change_name)
            _remove_from_merge_queue(state_file, change_name)
            try:
                from .digest import update_coverage_status
                update_coverage_status(change_name, "merged")
            except Exception:
                logger.warning("Coverage update failed for %s", change_name, exc_info=True)
            return MergeResult(success=True, status="merged", smoke_result="skip_merged")

    # Case 3: Fast-forward only merge (integrate-then-verify pattern)
    # The branch already has main integrated and all gates passed.
    # ff-only ensures we only advance main to a tested commit.

    # Apply plugin merge strategies (e.g., theirs-wins for lockfiles)
    _apply_merge_strategies()

    # Remove untracked files that would conflict with the merge.
    # set-project init deploys files (CLAUDE.md, .gitignore, etc.) to the main
    # worktree without committing them. When the branch has these files committed,
    # git merge --ff-only refuses because it would overwrite untracked files.
    _clean_untracked_merge_conflicts(change_name)

    if event_bus:
        event_bus.emit("MERGE_START", change=change_name)
    update_change_field(state_file, change_name, "current_step", "merging")
    pre_merge_sha = run_command(["git", "rev-parse", "HEAD"], timeout=10).stdout.strip()
    merge_result = run_command(
        ["set-merge", change_name, "--no-push", "--ff-only"],
        timeout=120,
    )

    if merge_result.exit_code == 0:
        # FF merge succeeded — verify the branch is actually in main's history
        main_branch = _get_main_branch()
        branch_name = f"change/{change_name}"
        verify_r = run_command(
            ["git", "merge-base", "--is-ancestor", branch_name, main_branch],
            timeout=10,
        )
        if verify_r.exit_code != 0:
            # Git merge reported success but branch not in main — something went wrong
            logger.error(
                "Post-merge verification FAILED for %s: branch %s not ancestor of %s. "
                "Setting status to merge-failed.",
                change_name, branch_name, main_branch,
            )
            update_change_field(state_file, change_name, "status", "merge-failed")
            return MergeResult(success=False, message="post-merge verification failed")

        update_change_field(state_file, change_name, "status", "merged")
        _set_completed_at_if_missing(state_file, change_name)
        logger.info("Merged %s (ff-only, git-verified)", change_name)
        if event_bus:
            event_bus.emit("MERGE_COMPLETE", change=change_name, data={"result": "success"})

        # Heartbeat helper for post-merge steps
        def _heartbeat(step: str) -> None:
            if event_bus:
                event_bus.emit("MERGE_PROGRESS", change=change_name, data={"step": step})

        _heartbeat("merge_complete")

        # Git tags for recovery
        run_command(["git", "tag", "-f", f"orch/{change_name}", "HEAD"], timeout=10)

        # Update coverage status (only after git-verified merge)
        try:
            from .digest import update_coverage_status
            update_coverage_status(change_name, "merged")
        except Exception:
            logger.warning("Coverage update failed for %s", change_name, exc_info=True)

        # Post-merge dependency install via profile (or legacy fallback)
        _heartbeat("deps_install")
        try:
            from .profile_loader import load_profile
            logger.debug("load_profile for post-merge deps: cwd=%s", os.getcwd())
            _profile = load_profile()
            if hasattr(_profile, "post_merge_install"):
                _profile.post_merge_install(".")
        except Exception as _e:
            logger.warning("Profile post-merge install failed (%s), using legacy fallback", _e)
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

        # Parse test coverage
        _heartbeat("test_coverage")
        _parse_test_coverage_if_applicable(change_name, state_file)

        # Collect test artifacts via profile (screenshots, traces, reports)
        _heartbeat("collect_artifacts")
        _collect_test_artifacts(change_name, wt_path, state_file)

        # Regenerate START.md on main from current project state
        try:
            from .dispatcher import _write_startup_file
            _write_startup_file(".")
        except Exception:
            logger.debug("Post-merge START.md regeneration failed (non-critical)", exc_info=True)

        # Post-merge hook
        _run_hook("post_merge", change_name, "merged", "")

        # Persist review learnings (template + project split)
        _heartbeat("review_learnings")
        _persist_change_review_learnings(change_name, state_file)

        # Final token collection before worktree cleanup destroys loop-state
        _heartbeat("final_tokens")
        _final_token_collect(state_file, change_name, wt_path or "")

        _heartbeat("archive")
        update_change_field(state_file, change_name, "current_step", "archiving")
        cleanup_worktree(change_name, wt_path or "")
        archive_change(change_name)

        # Sync running worktrees AFTER archive (Bug #38)
        _heartbeat("worktree_sync")
        _sync_running_worktrees(change_name, state_file)

        update_change_field(state_file, change_name, "current_step", "done")
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
        total = int(change.extras.get("total_merge_attempts") or 0) if change else 0
        update_change_field(state_file, change_name, "total_merge_attempts", total + 1)

        # Re-integrate: the verifier will merge main into branch and re-run gates
        # Set status back so the monitor dispatches the change through handle_change_done again
        update_change_field(state_file, change_name, "status", "done")
        _remove_from_merge_queue(state_file, change_name)

        # Add back to merge queue — handle_change_done will re-integrate and re-gate,
        # then re-queue for merge
        return MergeResult(success=False, status="running")


# ─── Merge Queue ────────────────────────────────────────────────────


def _integrate_for_merge(wt_path: str, change_name: str, event_bus: Any = None) -> str:
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

    # Stash dirty files before merge — agents leave uncommitted changes
    # (playwright-report/, .claude/reflection.md, messages/*.json) that block git merge.
    stashed = False
    dirty = run_command(["git", "status", "--porcelain"], timeout=10, cwd=wt_path)
    if dirty.exit_code == 0 and dirty.stdout.strip():
        logger.info("Stashing dirty files before integration merge for %s", change_name)
        stash_r = run_command(["git", "stash", "push", "-u", "-m", "pre-integration-stash"], timeout=30, cwd=wt_path)
        stashed = stash_r.exit_code == 0 and "No local changes" not in (stash_r.stdout or "")

    # Merge main into branch
    logger.info("Integrating %s into branch for %s", main_branch, change_name)
    result = run_command(
        ["git", "merge", merge_ref, "--no-edit",
         "-m", f"Merge {main_branch} for pre-ff integration"],
        timeout=120, cwd=wt_path,
    )

    if result.exit_code == 0:
        logger.info("Integration merge succeeded for %s", change_name)
        if stashed:
            run_command(["git", "stash", "pop"], timeout=30, cwd=wt_path)
        return "ok"

    # Check for conflict
    conflict_check = run_command(
        ["git", "diff", "--name-only", "--diff-filter=U"], timeout=10, cwd=wt_path,
    )
    conflicted_files = [f.strip() for f in (conflict_check.stdout or "").strip().splitlines() if f.strip()]

    if conflicted_files:
        _cr_start = time.time()
        if event_bus:
            event_bus.emit("CONFLICT_RESOLUTION_START", change=change_name, data={
                "conflicted_files": conflicted_files,
            })

        # Auto-resolve .claude/** and other generated files — accept branch version ("ours")
        auto_resolve_prefixes = (".claude/", "set/", ".gitattributes")
        auto_resolvable = [f for f in conflicted_files if any(f.startswith(p) for p in auto_resolve_prefixes)]
        real_conflicts = [f for f in conflicted_files if f not in auto_resolvable]

        if auto_resolvable and not real_conflicts:
            # All conflicts are in auto-resolvable paths — resolve with "ours" and complete merge
            logger.info("Auto-resolving %d generated file conflict(s) for %s: %s",
                        len(auto_resolvable), change_name, ", ".join(auto_resolvable))
            for f in auto_resolvable:
                run_command(["git", "checkout", "--ours", f], timeout=10, cwd=wt_path)
                run_command(["git", "add", f], timeout=10, cwd=wt_path)
            # Complete the merge
            commit_result = run_command(
                ["git", "commit", "--no-edit"], timeout=30, cwd=wt_path,
            )
            if commit_result.exit_code == 0:
                logger.info("Integration merge completed after auto-resolve for %s", change_name)
                if event_bus:
                    event_bus.emit("CONFLICT_RESOLUTION_END", change=change_name, data={
                        "result": "resolved", "duration_ms": int((time.time() - _cr_start) * 1000),
                    })
                if stashed:
                    run_command(["git", "stash", "pop"], timeout=30, cwd=wt_path)
                return "ok"
            else:
                logger.error("Commit after auto-resolve failed for %s", change_name)
                run_command(["git", "merge", "--abort"], timeout=10, cwd=wt_path)
                if event_bus:
                    event_bus.emit("CONFLICT_RESOLUTION_END", change=change_name, data={
                        "result": "failed", "duration_ms": int((time.time() - _cr_start) * 1000),
                    })
        else:
            logger.warning("Integration conflict for %s: %s (auto-resolved: %s)",
                           change_name, ", ".join(real_conflicts), ", ".join(auto_resolvable) or "none")
            run_command(["git", "merge", "--abort"], timeout=10, cwd=wt_path)
            if event_bus:
                event_bus.emit("CONFLICT_RESOLUTION_END", change=change_name, data={
                    "result": "failed", "duration_ms": int((time.time() - _cr_start) * 1000),
                })
    else:
        logger.error("Integration merge failed for %s (non-conflict): %s", change_name, result.stderr[:300])
        run_command(["git", "merge", "--abort"], timeout=10, cwd=wt_path)

    # Restore stashed files
    if stashed:
        run_command(["git", "stash", "pop"], timeout=30, cwd=wt_path)

    return "conflict"


def _count_skeleton_todos(wt_path: str, change_name: str) -> int:
    """Count remaining // TODO: implement markers in the test skeleton file.

    Returns 0 if no skeleton file exists (change didn't get one).
    """
    spec_file = os.path.join(wt_path, "tests", "e2e", f"{change_name}.spec.ts")
    if not os.path.isfile(spec_file):
        return 0
    try:
        content = Path(spec_file).read_text(encoding="utf-8")
        return content.count("// TODO: implement")
    except OSError:
        return 0


def _detect_own_spec_files(wt_path: str) -> list[str]:
    """Detect which E2E spec files were added/modified by this change branch.

    Strategy: compare spec files on current HEAD vs what exists on main.
    Files present in the worktree but NOT on main are "own" (this change added them).
    Falls back to e2e-manifest.json if comparison fails.
    Returns relative paths (e.g., "tests/e2e/cart.spec.ts").
    """
    from .subprocess_utils import run_command as _run

    # Primary: compare worktree specs vs main branch specs
    try:
        # Get spec files on main
        main_specs_result = _run(
            ["git", "ls-tree", "-r", "--name-only", "main", "--", "tests/e2e/"],
            timeout=10, cwd=wt_path,
        )
        main_specs = set()
        if main_specs_result.exit_code == 0 and main_specs_result.stdout:
            main_specs = {
                f.strip() for f in main_specs_result.stdout.strip().split("\n")
                if f.strip().endswith((".spec.ts", ".spec.js"))
            }

        # Get spec files in worktree
        wt_specs = set()
        e2e_dir = os.path.join(wt_path, "tests", "e2e")
        if os.path.isdir(e2e_dir):
            for fn in os.listdir(e2e_dir):
                if fn.endswith((".spec.ts", ".spec.js")):
                    wt_specs.add(f"tests/e2e/{fn}")

        logger.debug(
            "Own spec detection: main_specs=%s, wt_specs=%s, diff=%s",
            sorted(main_specs), sorted(wt_specs), sorted(wt_specs - main_specs),
        )

        own = sorted(wt_specs - main_specs)
        if own:
            logger.info("Detected %d own spec files (worktree vs main): %s", len(own), own)
            return own
        elif wt_specs:
            # All specs exist on main too — try git log for modified specs
            log_result = _run(
                ["git", "log", "--no-merges", "--diff-filter=AM", "--name-only",
                 "--format=", "main..HEAD", "--", "tests/e2e/"],
                timeout=10, cwd=wt_path,
            )
            if log_result.exit_code == 0 and log_result.stdout:
                modified = sorted({
                    f.strip() for f in log_result.stdout.strip().split("\n")
                    if f.strip().endswith((".spec.ts", ".spec.js"))
                })
                if modified:
                    logger.info("Detected %d own spec files via git log: %s", len(modified), modified)
                    return modified
    except Exception as _e:
        logger.debug("Git spec detection failed: %s", _e)

    # Fallback: e2e-manifest.json (check actual file existence)
    manifest = os.path.join(wt_path, "e2e-manifest.json")
    if os.path.isfile(manifest):
        try:
            data = json.loads(Path(manifest).read_text(encoding="utf-8"))
            manifest_specs = data.get("spec_files", [])
            # Validate: only return specs that actually exist
            valid = [s for s in manifest_specs if os.path.isfile(os.path.join(wt_path, s))]
            if valid:
                logger.info("Detected %d own spec files via manifest: %s", len(valid), valid)
                return valid
            # Manifest has wrong names — try to find actual spec matching change name
            change_name = data.get("change", "")
            if change_name:
                e2e_dir = os.path.join(wt_path, "tests", "e2e")
                if os.path.isdir(e2e_dir):
                    for fn in os.listdir(e2e_dir):
                        if fn.endswith((".spec.ts", ".spec.js")) and change_name in fn:
                            logger.info("Detected own spec file via manifest name match: %s", fn)
                            return [f"tests/e2e/{fn}"]
        except (json.JSONDecodeError, OSError) as _e:
            logger.debug("Manifest parse failed for %s: %s", manifest, _e)

    logger.warning("Could not detect own spec files for %s — two-phase E2E disabled", wt_path)
    return []


def _run_integration_gates(
    change_name: str, change: Change, wt_path: str,
    state_file: str, profile: Any = None,
    event_bus: Any = None,
    e2e_retry_limit: int = 5,
) -> bool:
    """Run integration gates (build + test + e2e) in worktree after integration.

    Uses lightweight subprocess calls (not the full gate executors which need
    many parameters). Only checks: does it build? do tests pass?

    Returns True if all gates pass, False if any blocking gate fails.
    """
    from .gate_profiles import resolve_gate_config
    from .gate_runner import GateResult
    from .subprocess_utils import run_command

    def _record_gate_output_hash(output: str) -> None:
        """Store SHA256 of gate output for identical-output retry detection."""
        h = hashlib.sha256(output[:2000].encode(errors="replace")).hexdigest()[:16]
        hashes = (change.extras.get("gate_output_hashes") or []) if change else []
        if hashes and hashes[-1] != h:
            hashes = []  # Different output — reset
        hashes.append(h)
        update_change_field(state_file, change_name, "gate_output_hashes", hashes[-5:])

    gc = resolve_gate_config(change, profile)
    gates_executed = 0  # Track how many gates actually ran a subprocess

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

    import time as _time
    _pipeline_start = _time.monotonic()
    _gates_passed_count = 0

    # Dep install after integration merge (new deps from other changes)
    if profile and hasattr(profile, "detect_dep_install_command"):
        dep_cmd = profile.detect_dep_install_command(wt_path)
        if dep_cmd:
            logger.info("Integration gate: dep install for %s (%s)", change_name, dep_cmd)
            if event_bus:
                event_bus.emit("GATE_START", change=change_name, data={"gate": "dep_install", "phase": "integration"})
            _gs = _time.monotonic()
            run_command(["bash", "-c", dep_cmd], timeout=120, cwd=wt_path, env=gate_env or None)
            _ge = int((_time.monotonic() - _gs) * 1000)
            logger.info("Integration gate: dep install PASSED for %s (%dms)", change_name, _ge)

    # Pre-build setup (e.g. Prisma DB schema sync for Next.js + Prisma projects)
    # next build executes server components which query the DB — needs schema synced
    if profile and hasattr(profile, "integration_pre_build"):
        try:
            ok = profile.integration_pre_build(wt_path)
            if not ok:
                logger.error("integration_pre_build FAILED for %s — blocking gate pipeline", change_name)
                return False
        except Exception:
            logger.error("integration_pre_build threw for %s — blocking gate pipeline", change_name, exc_info=True)
            return False

    # Build gate
    if gc.should_run("build"):
        build_cmd = directives.get("build_command", "")
        if not build_cmd and profile and hasattr(profile, "detect_build_command"):
            build_cmd = profile.detect_build_command(wt_path) or ""
        if build_cmd:
            gates_executed += 1
            logger.info("Integration gate: build for %s (%s)", change_name, build_cmd)
            if event_bus:
                event_bus.emit("GATE_START", change=change_name, data={"gate": "build", "phase": "integration"})
            _gs = _time.monotonic()
            result = run_command(["bash", "-c", build_cmd], timeout=120, cwd=wt_path, env=gate_env or None)
            _ge = int((_time.monotonic() - _gs) * 1000)
            gate_pass = result.exit_code == 0
            update_change_field(state_file, change_name, "build_result", "pass" if gate_pass else "fail")
            update_change_field(state_file, change_name, "gate_build_ms", _ge)
            update_change_field(state_file, change_name, "build_output", ((result.stdout or "") + (result.stderr or ""))[-2000:])
            if gate_pass:
                _gates_passed_count += 1
                logger.info("Integration gate: build PASSED for %s (%dms)", change_name, _ge)
                if event_bus:
                    event_bus.emit("GATE_PASS", change=change_name, data={"gate": "build", "elapsed_ms": _ge, "phase": "integration"})
            else:
                logger.error("Integration gate: build FAILED for %s (%dms)", change_name, _ge)
                if event_bus:
                    event_bus.emit("VERIFY_GATE", change=change_name, data={"gate": "build", "result": "fail", "phase": "integration"})
                update_change_field(state_file, change_name, "integration_gate_fail", "build")
                _record_gate_output_hash((result.stdout or "") + (result.stderr or ""))
                return False

    # Test gate
    if gc.should_run("test"):
        test_cmd = directives.get("test_command", "")
        if not test_cmd and profile and hasattr(profile, "detect_test_command"):
            test_cmd = profile.detect_test_command(wt_path) or ""
        if test_cmd:
            gates_executed += 1
            logger.info("Integration gate: test for %s (%s)", change_name, test_cmd)
            if event_bus:
                event_bus.emit("GATE_START", change=change_name, data={"gate": "test", "phase": "integration"})
            _gs = _time.monotonic()
            result = run_command(["bash", "-c", test_cmd], timeout=120, cwd=wt_path, env=gate_env or None)
            _ge = int((_time.monotonic() - _gs) * 1000)
            update_change_field(state_file, change_name, "gate_test_ms", _ge)
            update_change_field(state_file, change_name, "test_output", ((result.stdout or "") + (result.stderr or ""))[-2000:])
            if result.exit_code == 0:
                _gates_passed_count += 1
                update_change_field(state_file, change_name, "test_result", "pass")
                logger.info("Integration gate: test PASSED for %s (%dms)", change_name, _ge)
                if event_bus:
                    event_bus.emit("GATE_PASS", change=change_name, data={"gate": "test", "elapsed_ms": _ge, "phase": "integration"})
            elif gc.is_blocking("test"):
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
                # Check if failure is because no test files exist (vitest/jest exit non-zero)
                no_tests_indicators = [
                    "no test suite found",
                    "no test files found",
                    "no tests found, exiting with code",
                    "no tests found",
                ]
                is_no_tests = any(ind in output.lower() for ind in no_tests_indicators)
                if is_missing or is_empty_fail:
                    logger.warning(
                        "Integration gate: test command not available for %s (missing script or empty output) — skipping",
                        change_name,
                    )
                    update_change_field(state_file, change_name, "test_result", "skip")
                    if event_bus:
                        event_bus.emit("VERIFY_GATE", change=change_name, data={
                            "gate": "test", "result": "skip", "phase": "integration"})
                elif is_no_tests:
                    logger.warning(
                        "Integration gate: test skipped for %s (no test files found)",
                        change_name,
                    )
                    update_change_field(state_file, change_name, "test_result", "skip")
                    if event_bus:
                        event_bus.emit("VERIFY_GATE", change=change_name, data={
                            "gate": "test", "result": "skip", "phase": "integration"})
                else:
                    logger.error("Integration gate: test FAILED for %s", change_name)
                    update_change_field(state_file, change_name, "test_result", "fail")
                    update_change_field(state_file, change_name, "integration_gate_fail", "test")
                    _record_gate_output_hash(output)
                    if event_bus:
                        event_bus.emit("VERIFY_GATE", change=change_name, data={
                            "gate": "test", "result": "fail", "phase": "integration"})
                    return False

    # TODO count warning — check if agent left unfilled test skeletons
    _todo_count = _count_skeleton_todos(wt_path, change_name)
    if _todo_count > 0:
        logger.warning(
            "E2E skeleton has %d unfilled // TODO: implement blocks in %s — "
            "agent may not have completed all test bodies",
            _todo_count, change_name,
        )

    # E2E gate (from profile — web only)
    # Two-phase: Phase 1 = smoke inherited (non-blocking), Phase 2 = own tests (blocking)
    if gc.should_run("e2e"):
        e2e_cmd = directives.get("e2e_command", "")
        if not e2e_cmd and profile and hasattr(profile, "detect_e2e_command"):
            e2e_cmd = profile.detect_e2e_command(wt_path) or ""
        if e2e_cmd:
            gates_executed += 1
            # Assign unique port to avoid collisions with parallel agents
            port_offset = int(hashlib.md5(change_name.encode()).hexdigest()[:4], 16) % 1000
            e2e_port = 4000 + port_offset
            e2e_env = dict(gate_env) if gate_env else {}
            if profile and hasattr(profile, "e2e_gate_env"):
                e2e_env.update(profile.e2e_gate_env(e2e_port))
            if event_bus:
                event_bus.emit("GATE_START", change=change_name, data={"gate": "e2e", "phase": "integration"})

            # Detect own vs inherited spec files
            own_specs = _detect_own_spec_files(wt_path)
            all_specs = sorted(
                glob.glob(os.path.join(wt_path, "tests", "e2e", "*.spec.ts"))
                + glob.glob(os.path.join(wt_path, "tests", "e2e", "*.spec.js"))
            )
            # Convert to relative paths for command construction
            own_specs_abs = [os.path.join(wt_path, s) for s in own_specs]
            inherited_specs = [s for s in all_specs if s not in own_specs_abs]

            _use_two_phase = bool(own_specs) and profile is not None
            _smoke_failed = False
            _smoke_output = ""

            # E2E two-phase summary log (task 2.4)
            if _use_two_phase:
                _n_inherited_smoke = len(inherited_specs)
                logger.info(
                    "E2E two-phase: %d own specs, %d inherited specs, smoke=%d tests",
                    len(own_specs), _n_inherited_smoke, _n_inherited_smoke,
                )
                update_change_field(state_file, change_name, "smoke_test_count", _n_inherited_smoke)
                update_change_field(state_file, change_name, "own_test_count", len(own_specs))
                update_change_field(state_file, change_name, "inherited_file_count", _n_inherited_smoke)

            # ── Phase 1: Smoke inherited tests (non-blocking) ──
            if _use_two_phase and inherited_specs:
                smoke_names = []
                for spec in inherited_specs:
                    if hasattr(profile, "extract_first_test_name"):
                        name = profile.extract_first_test_name(spec)
                        if name:
                            smoke_names.append(name)

                smoke_cmd = None
                if smoke_names and hasattr(profile, "e2e_smoke_command"):
                    smoke_cmd = profile.e2e_smoke_command(e2e_cmd, smoke_names)

                if smoke_cmd:
                    logger.info(
                        "Integration gate: e2e smoke for %s (%d inherited tests from %d files)",
                        change_name, len(smoke_names), len(inherited_specs),
                    )
                    _s1 = _time.monotonic()
                    smoke_result = run_command(
                        ["bash", "-c", smoke_cmd], timeout=120, cwd=wt_path, env=e2e_env,
                    )
                    _s1e = int((_time.monotonic() - _s1) * 1000)
                    update_change_field(state_file, change_name, "gate_e2e_smoke_ms", _s1e)
                    _smoke_output = ((smoke_result.stdout or "") + (smoke_result.stderr or ""))[-1000:]

                    if smoke_result.exit_code == 0:
                        logger.info(
                            "Integration gate: e2e smoke PASSED for %s (%dms, %d tests)",
                            change_name, _s1e, len(smoke_names),
                        )
                        update_change_field(state_file, change_name, "smoke_e2e_result", "pass")
                    else:
                        _smoke_failed = True
                        logger.warning(
                            "Integration gate: e2e smoke FAILED for %s (non-blocking, %dms) — "
                            "inherited tests failed, regression possible",
                            change_name, _s1e,
                        )
                        update_change_field(state_file, change_name, "smoke_e2e_result", "fail")
                        if event_bus:
                            event_bus.emit("VERIFY_GATE", change=change_name, data={
                                "gate": "e2e-smoke", "result": "fail", "phase": "integration",
                                "inherited_files": len(inherited_specs)})
                        # Non-blocking: continue to Phase 2
                    # Always save smoke output (pass or fail)
                    update_change_field(state_file, change_name, "smoke_e2e_output", _smoke_output)
                else:
                    logger.info("Integration gate: skipping smoke phase (profile doesn't support smoke commands)")

            # ── Phase 2: Own tests (blocking) ──
            if _use_two_phase and own_specs:
                scoped_cmd = None
                if hasattr(profile, "e2e_scoped_command"):
                    scoped_cmd = profile.e2e_scoped_command(e2e_cmd, own_specs)
                actual_cmd = scoped_cmd or e2e_cmd

                logger.info(
                    "Integration gate: e2e own for %s (%s, port=%d, %d own files)",
                    change_name, actual_cmd, e2e_port, len(own_specs),
                )
                _s2 = _time.monotonic()
                result = run_command(
                    ["bash", "-c", actual_cmd], timeout=180, cwd=wt_path, env=e2e_env,
                )
                _s2e = int((_time.monotonic() - _s2) * 1000)
            else:
                # Fallback: single-phase (no ownership detected or no profile)
                update_change_field(state_file, change_name, "own_test_count", len(all_specs))
                update_change_field(state_file, change_name, "smoke_test_count", 0)
                update_change_field(state_file, change_name, "inherited_file_count", 0)
                logger.info(
                    "Integration gate: e2e for %s (%s, port=%d) — single-phase fallback",
                    change_name, e2e_cmd, e2e_port,
                )
                _s2 = _time.monotonic()
                result = run_command(
                    ["bash", "-c", e2e_cmd], timeout=180, cwd=wt_path, env=e2e_env,
                )
                _s2e = int((_time.monotonic() - _s2) * 1000)

            update_change_field(state_file, change_name, "gate_e2e_own_ms", _s2e)
            _ge = int((_time.monotonic() - (_s2 - _s2e / 1000)) * 1000)  # approximate total
            e2e_pass = result.exit_code == 0
            update_change_field(state_file, change_name, "e2e_result", "pass" if e2e_pass else "fail")
            update_change_field(state_file, change_name, "gate_e2e_ms", _s2e)
            update_change_field(state_file, change_name, "e2e_output", ((result.stdout or "") + (result.stderr or ""))[-8000:])
            if e2e_pass:
                _gates_passed_count += 1
                logger.info("Integration gate: e2e PASSED for %s (%dms)", change_name, _s2e)
                # ANOMALY: E2E passed but 0 spec files (task 3.2)
                if not all_specs:
                    logger.warning(
                        "[ANOMALY] E2E gate passed for %s but 0 spec files found "
                        "— tests may be missing",
                        change_name,
                    )
                if event_bus:
                    event_bus.emit("GATE_PASS", change=change_name, data={"gate": "e2e", "elapsed_ms": _s2e, "phase": "integration"})
            else:
                if event_bus:
                    event_bus.emit("VERIFY_GATE", change=change_name, data={"gate": "e2e", "result": "fail", "phase": "integration"})
            if not e2e_pass:
                if gc.is_blocking("e2e"):
                    e2e_output = (result.stdout or "")[-2000:] + "\n" + (result.stderr or "")[-1000:]
                    e2e_retry = change.extras.get("integration_e2e_retry_count", 0)

                    if e2e_retry < e2e_retry_limit:
                        # Redispatch agent to fix e2e failures — scoped to own tests
                        logger.warning(
                            "Integration gate: e2e FAILED for %s — redispatching agent (attempt %d/%d)",
                            change_name, e2e_retry + 1, e2e_retry_limit,
                        )
                        update_change_field(state_file, change_name, "integration_e2e_retry_count", e2e_retry + 1)
                        update_change_field(state_file, change_name, "integration_e2e_output", e2e_output)
                        # Scoped retry context: only own test output + own file list
                        from .engine import _build_gate_retry_context
                        retry_ctx = _build_gate_retry_context(change, wt_path, e2e_output)
                        if own_specs:
                            retry_ctx = f"Your spec files: {', '.join(own_specs)}\n\n{retry_ctx}"
                        if _smoke_failed:
                            retry_ctx = (
                                "Note: some inherited smoke tests also failed (non-blocking, "
                                "not your responsibility).\n\n" + retry_ctx
                            )
                        update_change_field(state_file, change_name, "retry_context", retry_ctx)
                        update_change_field(state_file, change_name, "status", "integration-e2e-failed")
                        update_change_field(state_file, change_name, "integration_gate_fail", "e2e-redispatch")
                        if event_bus:
                            event_bus.emit("VERIFY_GATE", change=change_name, data={
                                "gate": "e2e", "result": "redispatch", "phase": "integration",
                                "retry": e2e_retry + 1})
                        return False
                    else:
                        # Exhausted redispatch retries — terminal failure, remove from queue
                        logger.error("Integration gate: e2e FAILED for %s — redispatch retries exhausted (%d/%d)",
                                     change_name, e2e_retry, e2e_retry_limit)
                        update_change_field(state_file, change_name, "status", "integration-failed")
                        update_change_field(state_file, change_name, "integration_gate_fail", "e2e-exhausted")
                        _remove_from_merge_queue(state_file, change_name)
                        if event_bus:
                            event_bus.emit("CHANGE_INTEGRATION_FAILED", change=change_name, data={
                                "gate": "e2e", "retry_count": e2e_retry, "limit": e2e_retry_limit})
                        return False
                else:
                    logger.warning(
                        "Integration gate: e2e FAILED for %s (non-blocking per gate config)",
                        change_name,
                    )
                    update_change_field(state_file, change_name, "integration_gate_fail", "e2e-warn")

    # Coverage gate: validate test coverage against test-plan.json (feature changes only)
    _e2e_passed = locals().get('e2e_pass', False)
    if _e2e_passed:
        _change_type = getattr(change, 'change_type', '') or 'feature'
        _change_reqs = getattr(change, 'requirements', None) or []
        _cov_threshold = 0.8
        try:
            with locked_state(state_file) as _st:
                _cov_threshold = float(
                    _st.extras.get("directives", {}).get("e2e_coverage_threshold", 0.8)
                )
        except Exception:
            pass

        if (
            _change_type == "feature"
            and _change_reqs
            and _cov_threshold > 0.0
        ):
            _digest_dir = os.path.join(os.path.dirname(state_file), "set", "orchestration", "digest")
            if not os.path.isdir(_digest_dir):
                # Legacy fallback
                try:
                    from .paths import SetRuntime
                    _digest_dir = SetRuntime().digest_dir
                    logger.warning("Coverage gate: primary digest_dir missing, using SetRuntime fallback: %s", _digest_dir)
                except Exception:
                    pass
            _plan_path = os.path.join(_digest_dir, "test-plan.json")
            logger.debug("Coverage gate: digest_dir=%s, plan_exists=%s", _digest_dir, os.path.isfile(_plan_path))

            if os.path.isfile(_plan_path):
                try:
                    from .test_coverage import (
                        TestPlan, TestCase as _TC, build_test_coverage, validate_coverage,
                        parse_test_plan,
                    )
                    _plan = TestPlan.from_dict(json.loads(Path(_plan_path).read_text()))
                    # Per-change reqs — consistent with _parse_test_coverage_if_applicable
                    _req_set = set(_change_reqs)
                    _plan_entries = [e for e in _plan.entries if e.req_id in _req_set]

                    if _plan_entries:
                        # Parse test results from own-phase output
                        _e2e_out = ((result.stdout or "") + (result.stderr or ""))
                        _test_results = {}
                        if profile and hasattr(profile, "parse_test_results"):
                            _test_results = profile.parse_test_results(_e2e_out)

                        # Try JOURNEY-TEST-PLAN.md first, fallback to test-plan.json entries
                        _journey_path = Path(os.path.dirname(state_file)) / "tests" / "e2e" / "JOURNEY-TEST-PLAN.md"
                        _test_cases, _non_testable = parse_test_plan(_journey_path)
                        if not _test_cases:
                            # Build TestCases from test-plan.json (AC-ID binding needs these)
                            for _entry in _plan.entries:
                                _test_cases.append(_TC(
                                    scenario_slug=_entry.scenario_slug,
                                    req_id=_entry.req_id,
                                    risk=_entry.risk,
                                    test_file="",
                                    test_name=_entry.scenario_name,
                                    category=_entry.categories[0] if _entry.categories else "happy",
                                    ac_id=_entry.ac_id,
                                ))
                            _non_testable = _plan.non_testable
                        _coverage = build_test_coverage(
                            test_cases=_test_cases,
                            non_testable=_non_testable,
                            test_results=_test_results,
                            digest_req_ids=list(_req_set),
                            plan_file=_plan_path,
                        )

                        _cov_pct = _coverage.coverage_pct / 100.0 if _coverage.coverage_pct > 1 else _coverage.coverage_pct
                        update_change_field(state_file, change_name, "coverage_pct", _coverage.coverage_pct)

                        if _cov_pct >= _cov_threshold:
                            logger.info(
                                "Integration gate: coverage PASSED for %s (%.0f%% >= %.0f%%)",
                                change_name, _cov_pct * 100, _cov_threshold * 100,
                            )
                            update_change_field(state_file, change_name, "coverage_check_result", "pass")
                        else:
                            # Coverage insufficient — redispatch
                            _missing = [
                                e for e in _plan_entries
                                if e.req_id not in set(_coverage.covered_reqs)
                            ]
                            _missing_lines = "\n".join(
                                f"- {e.req_id}: {e.scenario_name} [{e.risk}] — {e.min_tests} test(s)"
                                for e in _missing[:20]
                            )
                            _cov_retry = change.extras.get("integration_e2e_retry_count", 0)
                            if _cov_retry < e2e_retry_limit:
                                logger.warning(
                                    "Integration gate: coverage FAILED for %s (%.0f%% < %.0f%%) — "
                                    "redispatching (attempt %d/%d)",
                                    change_name, _cov_pct * 100, _cov_threshold * 100,
                                    _cov_retry + 1, e2e_retry_limit,
                                )
                                _cov_ctx = (
                                    f"E2E tests pass but coverage is insufficient "
                                    f"({_cov_pct*100:.0f}% vs {_cov_threshold*100:.0f}% required).\n\n"
                                    f"Missing test scenarios:\n{_missing_lines}\n\n"
                                )
                                if own_specs:
                                    _cov_ctx += f"Your spec files: {', '.join(own_specs)}\n"
                                _cov_ctx += "Write tests for the missing scenarios and commit."
                                update_change_field(state_file, change_name, "integration_e2e_retry_count", _cov_retry + 1)
                                update_change_field(state_file, change_name, "retry_context", _cov_ctx)
                                update_change_field(state_file, change_name, "status", "integration-coverage-failed")
                                update_change_field(state_file, change_name, "integration_gate_fail", "coverage-redispatch")
                                update_change_field(state_file, change_name, "coverage_check_result", "fail")
                                if event_bus:
                                    event_bus.emit("VERIFY_GATE", change=change_name, data={
                                        "gate": "coverage", "result": "redispatch",
                                        "coverage_pct": _cov_pct * 100, "threshold": _cov_threshold * 100,
                                        "retry": _cov_retry + 1})
                                return False
                            else:
                                logger.error(
                                    "Integration gate: coverage FAILED for %s — retries exhausted",
                                    change_name,
                                )
                                update_change_field(state_file, change_name, "coverage_check_result", "fail")
                except Exception:
                    logger.debug("Coverage gate check failed (non-fatal)", exc_info=True)
            else:
                logger.debug("Coverage gate: no test-plan.json found, skipping")
        else:
            # Coverage check skipped for feature change — warn (task 2.3)
            if _change_type == "feature" and _change_reqs:
                if _cov_threshold == 0.0:
                    logger.warning(
                        "Coverage check skipped for feature %s — threshold=0.0",
                        change_name,
                    )
                # else: no requirements, so skip is expected
            elif _change_type != "feature":
                logger.debug("Coverage gate: skipping for %s (type=%s)", change_name, _change_type)
            elif _cov_threshold == 0.0:
                logger.debug("Coverage gate: disabled (threshold=0.0)")

    # Guard: warn if no gates actually executed for non-infrastructure changes
    if gates_executed == 0:
        change_type = getattr(change, 'change_type', '') or 'feature'
        if change_type not in ('infrastructure', 'config', 'docs'):
            logger.warning(
                "Integration gate: NO gates executed for %s (type=%s) — "
                "check project-type.yaml and profile detection. "
                "Changes may be merging without quality validation.",
                change_name, change_type,
            )
            if event_bus:
                event_bus.emit("GATE_SKIP_WARNING", change=change_name, data={
                    "reason": "no_gates_executed", "change_type": change_type,
                    "gates_executed": 0,
                })

    # Gate pipeline summary (task 2.1)
    _pipeline_elapsed = int((_time.monotonic() - _pipeline_start) * 1000)
    update_change_field(state_file, change_name, "gate_total_ms", _pipeline_elapsed)

    # Build detailed summary line
    _build_r = change.build_result or "skip"
    _test_r = change.test_result or "skip"
    _e2e_r = change.e2e_result or "skip"
    _build_ms = change.gate_build_ms or 0
    _test_ms = change.gate_test_ms or 0
    _e2e_ms = change.gate_e2e_ms or 0
    _cov_r = change.extras.get("coverage_check_result", "skip")
    _cov_pct = change.extras.get("coverage_pct", "?")
    _overall = "PASSED" if gates_executed == 0 or _gates_passed_count == gates_executed else "FAILED"
    logger.info(
        "Gate pipeline for %s: build=%s(%dms) test=%s(%dms) "
        "e2e=%s(%dms) coverage=%s(%s%%) — %s",
        change_name, _build_r, _build_ms, _test_r, _test_ms,
        _e2e_r, _e2e_ms, _cov_r, _cov_pct, _overall,
    )

    # Collect test artifacts right after gates (screenshots exist now).
    # This is the PRIMARY collection point — the post-merge call is a fallback
    # in case the worktree is cleaned up between gates and merge.
    _collect_test_artifacts(change_name, wt_path, state_file)

    return True


def _is_no_op_change(wt_path: str, change_name: str) -> bool:
    """Check if a change has 0 new commits beyond the merge base.

    Returns True if the worktree branch has no commits that aren't already on main.
    This happens when a replan dispatches a change for work that's already been merged.
    """
    main_branch = _get_main_branch(cwd=wt_path)
    result = run_command(
        ["git", "rev-list", "--count", f"{main_branch}..HEAD"],
        timeout=10, cwd=wt_path,
    )
    if result.exit_code != 0:
        return False  # Can't determine — assume it has commits
    try:
        count = int(result.stdout.strip())
    except ValueError:
        return False
    if count == 0:
        logger.warning("No-op change %s — 0 new commits beyond %s, skipping gates", change_name, main_branch)
        return True
    return False


def execute_merge_queue(state_file: str, *, event_bus: Any = None) -> int:
    """Drain merge queue. Serialized: integrate → verify → ff-only per change.

    Each change integrates fresh main (including prior merges in this queue drain),
    runs integration gates (build/test/e2e), then ff-only merges.
    """
    from .profile_loader import load_profile

    profile = load_profile()
    logger.debug("Profile for merge queue: %s (cwd=%s)", type(profile).__name__, os.getcwd())
    state = load_state(state_file)
    merged = 0

    # Check which changes are owned by the issue pipeline
    from .engine import _get_issue_owned_changes
    issue_owned = _get_issue_owned_changes()

    for name in list(state.merge_queue):
        change = _find_change(state, name)
        if not change:
            _remove_from_merge_queue(state_file, name)
            continue

        if name in issue_owned:
            logger.info("skipping merge for %s — owned by issue pipeline", name)
            continue

        # Check retry counter — skip changes that exhausted merge retries
        retry_count = change.extras.get("merge_retry_count", 0)
        if retry_count >= MAX_MERGE_RETRIES:
            logger.warning(
                "Merge retry limit reached for %s (%d/%d) — marking integration-failed",
                name, retry_count, MAX_MERGE_RETRIES,
            )
            update_change_field(state_file, name, "status", "integration-failed", event_bus=event_bus)
            if event_bus:
                event_bus.emit("CHANGE_INTEGRATION_FAILED", change=name,
                               data={"retry_count": retry_count, "max_retries": MAX_MERGE_RETRIES})
            _remove_from_merge_queue(state_file, name)
            continue

        # Pre-merge dependency validation — all deps must be in terminal status
        TERMINAL_STATUSES = {"merged", "done", "skip_merged", "completed", "skipped"}
        deps = change.depends_on or []
        if deps:
            dep_statuses = {}
            for dep_name in deps:
                dep_change = _find_change(state, dep_name)
                dep_statuses[dep_name] = dep_change.status if dep_change else "unknown"
            unmerged = {d: s for d, s in dep_statuses.items() if s not in TERMINAL_STATUSES}
            if unmerged:
                deps_str = ", ".join(f"{d} ({s})" for d, s in unmerged.items())
                logger.warning(
                    "Pre-merge dep check: %s blocked — waiting for %s",
                    name, deps_str,
                )
                update_change_field(state_file, name, "status", "dep-blocked", event_bus=event_bus)
                _remove_from_merge_queue(state_file, name)
                continue

        wt_path = change.worktree_path or ""

        # Skip integration+gates if ff_retry already exhausted — would be instant merge-blocked
        ff_exhausted = change.extras.get("ff_retry_count", 0) >= 3
        if ff_exhausted:
            logger.info(
                "Skipping integration gates for %s — ff_retry exhausted, will fail immediately",
                name,
            )

        # Step 1: Integrate current main into branch
        if wt_path and not os.path.isdir(wt_path) and not ff_exhausted:
            # Worktree was cleaned up but change is done — cannot run gates without worktree
            logger.error(
                "Worktree missing for %s (%s) — cannot run integration gates. "
                "Recreating worktree for gate execution.",
                name, wt_path,
            )
            # Try to recreate worktree from branch
            branch_name = f"change/{name}"
            try:
                from .subprocess_utils import run_command
                run_command(["git", "worktree", "add", wt_path, branch_name], timeout=30)
                logger.info("Recreated worktree for %s at %s", name, wt_path)
            except Exception as e:
                logger.error("Failed to recreate worktree for %s: %s — merging without gates", name, e)

        if wt_path and os.path.isdir(wt_path) and not ff_exhausted:
            integration = _integrate_for_merge(wt_path, name, event_bus=event_bus)
            if integration == "conflict":
                # Delegate to conflict handler (agent rebase)
                conflict_result = _handle_merge_conflict(name, state_file, wt_path)
                if not conflict_result.success:
                    _remove_from_merge_queue(state_file, name)
                continue

            # Step 2: No-op detection — skip entirely if 0 new commits
            _no_op = _is_no_op_change(wt_path, name)
            if _no_op:
                # No commits = never implemented. Mark as skipped, NOT merged.
                update_change_field(state_file, name, "status", "skipped", event_bus=event_bus)
                update_change_field(state_file, name, "gate_total_ms", 0, event_bus=event_bus)
                update_change_field(state_file, name, "test_result", "skip_noop", event_bus=event_bus)
                logger.warning("No-op change %s marked as 'skipped' — 0 commits, never implemented", name)
                _remove_from_merge_queue(state_file, name)
                continue

            _gates_passed = True
            if not _no_op:  # always run gates for non-no-op changes
                # Integration gates (build + test + e2e)
                import time as _time
                _gate_start = _time.monotonic()
                _e2e_limit = state.extras.get("directives", {}).get("e2e_retry_limit", 3)
                _gates_passed = _run_integration_gates(name, change, wt_path, state_file, profile, event_bus=event_bus, e2e_retry_limit=_e2e_limit)
                _gate_elapsed_ms = int((_time.monotonic() - _gate_start) * 1000)
                update_change_field(state_file, name, "gate_total_ms", _gate_elapsed_ms)
                # gates_executed count is logged inside _run_integration_gates
            if not _gates_passed:
                # Check if the gate set integration-e2e-failed (redispatch path)
                refreshed = load_state(state_file)
                refreshed_change = _find_change(refreshed, name)
                if refreshed_change and refreshed_change.status == "integration-e2e-failed":
                    # Agent will be redispatched by monitor loop — don't set merge-blocked
                    logger.info("Integration gate: %s queued for e2e redispatch", name)
                else:
                    update_change_field(state_file, name, "status", "merge-blocked")
                _remove_from_merge_queue(state_file, name)
                continue

        # Step 3: ff-only merge
        try:
            result = merge_change(name, state_file, event_bus=event_bus)
            if result.success:
                merged += 1
                if event_bus:
                    event_bus.emit("MERGE_SUCCESS", change=name, data={})
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

    # Re-add merge-blocked changes to queue for retry (with retry counter)
    for change in state.changes:
        if change.status == "merge-blocked" and change.name not in state.merge_queue:
            # Identical output detection — if last 3 gate outputs are the same, stop retrying
            gate_hashes = change.extras.get("gate_output_hashes") or []
            if len(gate_hashes) >= 3 and len(set(gate_hashes[-3:])) == 1:
                gate_fail = change.extras.get("integration_gate_fail", "unknown")
                logger.error(
                    "Identical gate output for %s across 3 retry cycles (%s) — marking integration-failed",
                    change.name, gate_fail,
                )
                update_change_field(state_file, change.name, "integration_gate_fail", f"{gate_fail}_identical_output")
                update_change_field(state_file, change.name, "status", "integration-failed", event_bus=event_bus)
                continue

            # Hard cap — total attempts across all retry cycles
            total = int(change.extras.get("total_merge_attempts") or 0)
            if total >= MAX_TOTAL_MERGE_ATTEMPTS:
                logger.error(
                    "Hard merge attempt cap reached for %s (%d/%d) — marking integration-failed",
                    change.name, total, MAX_TOTAL_MERGE_ATTEMPTS,
                )
                update_change_field(state_file, change.name, "status", "integration-failed", event_bus=event_bus)
                continue

            retry_count = change.extras.get("merge_retry_count", 0)
            if retry_count >= MAX_MERGE_RETRIES:
                logger.warning(
                    "Merge retry limit reached for %s (%d/%d) — marking integration-failed",
                    change.name, retry_count, MAX_MERGE_RETRIES,
                )
                update_change_field(state_file, change.name, "status", "integration-failed", event_bus=event_bus)
                continue
            # Increment retry counter + total attempts
            with locked_state(state_file) as st:
                ch = _find_change(st, change.name)
                if ch:
                    ch.extras["merge_retry_count"] = retry_count + 1
                    ch.extras["total_merge_attempts"] = total + 1
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

    if not install_cmd:
        logger.debug("_post_merge_deps_install: no lockfile detected — skipping install")
        return

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
            os.path.dirname(state_file), "set", "orchestration"
        )
        findings_path = os.path.join(findings_dir, "review-findings.jsonl")

        if not os.path.isfile(findings_path):
            logger.debug("_persist_change_review_learnings: findings file missing: %s", findings_path)
            return
        patterns = _extract_change_review_patterns(findings_path, change_name)
        if not patterns:
            logger.debug("_persist_change_review_learnings: no patterns for %s", change_name)
            return

        profile = load_profile()
        project_path = os.path.dirname(state_file)
        profile.persist_review_learnings(patterns, project_path)
        logger.info(
            "Persisted %d review learnings for %s", len(patterns), change_name
        )

        # Auto-commit project JSONL to main if it was written
        proj_jsonl = os.path.join(
            project_path, "set", "orchestration", "review-learnings.jsonl"
        )
        if os.path.isfile(proj_jsonl):
            from .subprocess_utils import run_git
            run_git("add", proj_jsonl, cwd=project_path)
            # Only commit if there are staged changes (--quiet returns exit 1 if there are diffs)
            diff_r = run_git("diff", "--cached", "--quiet", cwd=project_path, best_effort=True)
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




def _parse_test_coverage_if_applicable(change_name: str, state_file: str) -> None:
    """Parse test coverage data after acceptance-tests change merges."""
    try:
        state = load_state(state_file)
        # Find the change
        change = next((c for c in state.changes if c.name == change_name), None)
        if not change:
            return

        # Run for any change that has E2E results
        if not change.e2e_result:
            return

        logger.info("Parsing test coverage for change: %s", change_name)

        from pathlib import Path
        from .test_coverage import parse_test_plan, build_test_coverage, TestCase, TestPlan, validate_coverage

        # Read test plan — use project root from state file location
        project_root = Path(state_file).parent
        plan_path = project_root / "tests" / "e2e" / "JOURNEY-TEST-PLAN.md"
        test_cases, non_testable = parse_test_plan(plan_path)

        # Fallback: if no JOURNEY-TEST-PLAN.md, generate TestCases from test-plan.json
        # so scenario-level binding can work via slug matching
        if not test_cases:
            plan_json = project_root / "set" / "orchestration" / "digest" / "test-plan.json"
            if plan_json.is_file():
                try:
                    import json as _json_tp
                    _tp_data = _json_tp.loads(plan_json.read_text(encoding="utf-8"))
                    _tp = TestPlan.from_dict(_tp_data)
                    for entry in _tp.entries:
                        test_cases.append(TestCase(
                            scenario_slug=entry.scenario_slug,
                            req_id=entry.req_id,
                            risk=entry.risk,
                            test_file="",
                            test_name=entry.scenario_name,
                            category=entry.categories[0] if entry.categories else "happy",
                            ac_id=entry.ac_id,
                        ))
                    non_testable = _tp.non_testable
                    logger.info("Loaded %d test cases from test-plan.json (no JOURNEY-TEST-PLAN.md)", len(test_cases))
                except Exception:
                    logger.debug("Failed to load test-plan.json fallback", exc_info=True)

        # Parse test results via profile (even without JOURNEY-TEST-PLAN.md,
        # build_test_coverage can extract REQ-IDs directly from test names)
        test_results: dict[tuple[str, str], str] = {}
        try:
            from .profile_loader import load_profile
            profile = load_profile(str(project_root))
            logger.debug("_parse_test_coverage: profile=%s from %s", type(profile).__name__, project_root)
            # Get E2E output — try top-level field first, then extras
            e2e_output = getattr(change, "e2e_output", "") or ""
            if not e2e_output:
                e2e_output = change.extras.get("integration_e2e_output", "")
            if not e2e_output:
                e2e_output = change.extras.get("e2e_output", "")
            if not e2e_output:
                e2e_output = change.extras.get("smoke_output", "")
            if e2e_output:
                test_results = profile.parse_test_results(e2e_output)
        except Exception:
            logger.debug("Test result parsing failed (non-critical)", exc_info=True)

        if not test_cases and not non_testable and not test_results:
            logger.info("No test plan and no test results — skipping coverage parsing")
            return

        # Determine REQ-ID set for coverage calculation.
        # Per-change requirements take priority — each change is only responsible
        # for its own REQs. Digest-level (all REQs) only used for acceptance-test
        # changes that validate cross-cutting coverage.
        change_reqs = getattr(change, 'requirements', None) or []
        change_type = getattr(change, 'change_type', '') or ''

        if change_reqs and change_type != "acceptance-tests":
            # Per-change: only check this change's own requirements
            coverage_req_ids = list(set(change_reqs))
            logger.info(
                "Coverage parsing for %s: using %d per-change reqs (change has own requirements)",
                change_name, len(coverage_req_ids),
            )
        else:
            # Global: acceptance-test changes or changes without own reqs
            coverage_req_ids = []
            try:
                digest_dir = project_root / "set" / "orchestration" / "digest"
                req_file = digest_dir / "requirements.json"
                if req_file.is_file():
                    import json
                    with open(req_file) as f:
                        req_data = json.load(f)
                    req_list = req_data
                    if isinstance(req_data, dict) and "requirements" in req_data:
                        req_list = req_data["requirements"]
                    if isinstance(req_list, list):
                        for r in req_list:
                            if isinstance(r, dict):
                                if "requirements" in r:
                                    coverage_req_ids.extend(
                                        rr.get("id", "") for rr in r["requirements"] if isinstance(rr, dict)
                                    )
                                elif "id" in r:
                                    coverage_req_ids.append(r["id"])
            except Exception:
                logger.debug("Failed to read digest requirements", exc_info=True)

            # Fallback: collect REQ IDs from all changes in state
            if not coverage_req_ids:
                try:
                    for ch in state.changes:
                        if ch.requirements:
                            coverage_req_ids.extend(ch.requirements)
                except Exception:
                    pass
            coverage_req_ids = list(set(coverage_req_ids))
            logger.info(
                "Coverage parsing for %s: using %d digest-level reqs (type=%s)",
                change_name, len(coverage_req_ids), change_type or "no-own-reqs",
            )

        # Build coverage
        coverage = build_test_coverage(
            test_cases=test_cases,
            non_testable=non_testable,
            test_results=test_results,
            digest_req_ids=coverage_req_ids,
            plan_file=str(plan_path),
        )

        # Run coverage validation against test plan if available
        validation_data = None
        try:
            plan_json = project_root / "set" / "orchestration" / "digest" / "test-plan.json"
            if plan_json.is_file():
                import json as _json
                plan_dict = _json.loads(plan_json.read_text(encoding="utf-8"))
                test_plan = TestPlan.from_dict(plan_dict)
                validation = validate_coverage(test_plan, coverage)
                validation_data = validation.to_dict()
        except Exception:
            logger.debug("Coverage validation failed (non-critical)", exc_info=True)

        # Store in per-change extras (not state-level)
        with locked_state(state_file) as st:
            ch = next((c for c in st.changes if c.name == change_name), None)
            if ch:
                ch.extras["test_coverage"] = coverage.to_dict()
                if validation_data:
                    ch.extras["coverage_validation"] = validation_data

        logger.info(
            "Test coverage parsed: %d tests, %d/%d reqs covered (%.1f%%), %d gaps",
            coverage.total_tests,
            len(coverage.covered_reqs),
            len(coverage.covered_reqs) + len(coverage.uncovered_reqs),
            coverage.coverage_pct,
            len(coverage.uncovered_reqs),
        )
    except Exception:
        logger.debug("Test coverage parsing failed (non-critical)", exc_info=True)


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
            _set_completed_at_if_missing(state_file, change_name)
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


