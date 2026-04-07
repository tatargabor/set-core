"""Recovery — roll back an orchestration project to the state after a specific change.

Used when a late change broke the build/design and we want to re-run only the
affected changes without losing earlier merged work.

Safe operations:
- Backs up state.json before any mutation
- Creates a git tag before reset (recoverable via reflog)
- Atomic execution: restores state.json on partial failure
- Refuses to run if orchestrator/sentinel is alive

Usage:
    from set_orch.recovery import recover_to_change
    recover_to_change(project_path, "shopping-cart", dry_run=False, yes=True)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .state import Change, OrchestratorState, load_state, locked_state
from .subprocess_utils import run_command, run_git

logger = logging.getLogger(__name__)


class RecoveryError(Exception):
    """Recovery operation failed (validation or execution)."""

    pass


@dataclass
class RecoveryPlan:
    target_change: str
    target_commit: str
    rollback_changes: list[str] = field(default_factory=list)
    branches_to_delete: list[str] = field(default_factory=list)
    worktrees_to_remove: list[str] = field(default_factory=list)
    archive_dirs_to_restore: list[Path] = field(default_factory=list)
    state_changes_to_reset: list[str] = field(default_factory=list)
    backup_tag: str = ""
    first_rolled_back_phase: int = 1


# ─── Validation ────────────────────────────────────────────────────────────


def _is_pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _validate_project(project_path: Path, target_change: str) -> tuple[OrchestratorState, Change]:
    """Validate project is in a recoverable state. Returns (state, target_change_obj)."""
    state_file = project_path / "orchestration-state.json"
    if not state_file.is_file():
        raise RecoveryError(f"No orchestration-state.json in {project_path}")

    try:
        state = load_state(str(state_file))
    except Exception as e:
        raise RecoveryError(f"Failed to load state.json: {e}")

    orch_pid = state.extras.get("orchestrator_pid") or getattr(state, "orchestrator_pid", None)
    if orch_pid and _is_pid_alive(int(orch_pid)):
        raise RecoveryError(
            f"Orchestrator running (PID {orch_pid}). Stop it first."
        )

    sentinel_pid_file = project_path / ".set" / "sentinel.pid"
    if sentinel_pid_file.is_file():
        try:
            pid = int(sentinel_pid_file.read_text().strip())
            if _is_pid_alive(pid):
                raise RecoveryError(
                    f"Sentinel running (PID {pid}). Stop it first."
                )
        except (ValueError, OSError):
            pass

    target = next((c for c in state.changes if c.name == target_change), None)
    if not target:
        available = ", ".join(c.name for c in state.changes if c.status == "merged")
        raise RecoveryError(
            f"Target change '{target_change}' not found. Merged changes: {available}"
        )
    if target.status != "merged":
        raise RecoveryError(
            f"Target '{target_change}' is '{target.status}', not merged — "
            f"cannot recover to non-merged state"
        )

    return state, target


# ─── Plan building ─────────────────────────────────────────────────────────


def _find_target_commit(project_path: Path, target_change: str) -> str:
    """Find the archive commit SHA for the target change."""
    # Try archive commit first (most precise)
    r = run_git(
        "log", "--all", "--grep", f"archive {target_change}",
        "--format=%H", "-1",
        cwd=str(project_path),
    )
    if r.exit_code == 0 and r.stdout.strip():
        return r.stdout.strip().split("\n")[0]

    # Fall back to merge commit
    r = run_git(
        "log", "--all", "--grep", f"merge.*{target_change}|Merged {target_change}",
        "--format=%H", "-1", "-E",
        cwd=str(project_path),
    )
    if r.exit_code == 0 and r.stdout.strip():
        return r.stdout.strip().split("\n")[0]

    # Last resort: any commit mentioning the change name
    r = run_git(
        "log", "--all", "--grep", target_change, "--format=%H", "-1",
        cwd=str(project_path),
    )
    if r.exit_code == 0 and r.stdout.strip():
        return r.stdout.strip().split("\n")[0]

    raise RecoveryError(f"No commit found for change '{target_change}'")


def _find_archive_dirs(project_path: Path, change_name: str) -> list[Path]:
    """Find archived openspec change dirs for a given change name."""
    archive_root = project_path / "openspec" / "changes" / "archive"
    if not archive_root.is_dir():
        return []
    matches = []
    for entry in archive_root.iterdir():
        if entry.is_dir() and entry.name.endswith(f"-{change_name}"):
            matches.append(entry)
    return matches


def _build_recovery_plan(
    state: OrchestratorState,
    target_change: str,
    target_commit: str,
    project_path: Path,
) -> RecoveryPlan:
    target_idx = next(
        i for i, c in enumerate(state.changes) if c.name == target_change
    )

    # All changes after target that have been touched (merged, running, etc.)
    rollback_statuses = {
        "merged", "verifying", "integrating", "running", "done",
        "verify-failed", "integration-failed", "integration-e2e-failed",
        "stalled",
    }
    rollback_changes = [
        c for c in state.changes[target_idx + 1 :]
        if c.status in rollback_statuses
    ]

    if not rollback_changes:
        raise RecoveryError(
            f"Nothing to roll back — no changes after '{target_change}' have been touched"
        )

    # Collect archive dirs
    archive_dirs = []
    for c in rollback_changes:
        archive_dirs.extend(_find_archive_dirs(project_path, c.name))

    # First rolled-back change's phase (where we'll resume from)
    first_phase = rollback_changes[0].phase

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return RecoveryPlan(
        target_change=target_change,
        target_commit=target_commit,
        rollback_changes=[c.name for c in rollback_changes],
        branches_to_delete=[f"change/{c.name}" for c in rollback_changes],
        worktrees_to_remove=[c.worktree_path for c in rollback_changes if c.worktree_path],
        archive_dirs_to_restore=archive_dirs,
        state_changes_to_reset=[c.name for c in rollback_changes],
        backup_tag=f"recovery-backup-{timestamp}",
        first_rolled_back_phase=first_phase,
    )


# ─── Preview ────────────────────────────────────────────────────────────────


def render_preview(plan: RecoveryPlan, project_path: Path) -> str:
    lines = [
        "Recovery Plan",
        "=" * 60,
        f"Project: {project_path}",
        f"Target:  {plan.target_change} (commit {plan.target_commit[:8]})",
        "",
        f"After rollback, ready to re-run ({len(plan.rollback_changes)}):",
    ]
    for c in plan.rollback_changes:
        lines.append(f"  - {c}")
    lines.append("")

    lines.append("Will undo:")
    lines.append("")
    lines.append("  Git:")
    lines.append(f"    - reset main → {plan.target_commit[:8]}")
    for branch in plan.branches_to_delete:
        lines.append(f"    - delete branch {branch}")
    lines.append(f"    - tag rollback point as {plan.backup_tag}")
    lines.append("")

    if plan.worktrees_to_remove:
        lines.append("  Worktrees:")
        for wt in plan.worktrees_to_remove:
            lines.append(f"    - {wt}")
        lines.append("")

    if plan.archive_dirs_to_restore:
        lines.append("  OpenSpec (un-archive):")
        for ad in plan.archive_dirs_to_restore:
            lines.append(f"    - {ad.name} → openspec/changes/")
        lines.append("")

    lines.append("  State:")
    for ch in plan.state_changes_to_reset:
        lines.append(f"    - {ch}: → pending (clear tokens, gates, retries, worktree)")
    lines.append("    - merge_queue: cleared")
    lines.append(f"    - current_phase: → {plan.first_rolled_back_phase}")
    lines.append("    - status: stopped (requires explicit restart)")
    lines.append("")

    lines.append("  Backup:")
    lines.append(f"    - orchestration-state.json → orchestration-state.json.bak.{plan.backup_tag.split('-', 2)[-1]}")
    lines.append(f"    - git tag {plan.backup_tag}")

    return "\n".join(lines)


# ─── Execution ──────────────────────────────────────────────────────────────


def _kill_zombie_agents(state: OrchestratorState, change_names: list[str]) -> None:
    for ch in state.changes:
        if ch.name in change_names and ch.ralph_pid and _is_pid_alive(ch.ralph_pid):
            logger.warning("Killing zombie agent for %s (PID %d)", ch.name, ch.ralph_pid)
            try:
                os.kill(ch.ralph_pid, signal.SIGTERM)
            except OSError as e:
                logger.warning("Failed to kill PID %d: %s", ch.ralph_pid, e)


def _execute_plan(project_path: Path, plan: RecoveryPlan, state: OrchestratorState) -> None:
    state_file = project_path / "orchestration-state.json"
    backup_suffix = plan.backup_tag.split("-", 2)[-1]
    state_backup = project_path / f"orchestration-state.json.bak.{backup_suffix}"

    # Backup state.json
    shutil.copy(str(state_file), str(state_backup))
    logger.info("Backed up state.json → %s", state_backup.name)

    # Create git safety tag
    r = run_git("tag", plan.backup_tag, cwd=str(project_path))
    if r.exit_code != 0:
        logger.warning("Failed to create backup tag: %s", r.stderr)
    else:
        logger.info("Created backup tag: %s", plan.backup_tag)

    try:
        # 1. Kill zombie agents
        _kill_zombie_agents(state, plan.state_changes_to_reset)

        # 2. Remove worktrees
        for wt_path in plan.worktrees_to_remove:
            if not os.path.isdir(wt_path):
                logger.info("Worktree dir already gone: %s", wt_path)
                continue
            r = run_git("worktree", "remove", "--force", wt_path, cwd=str(project_path))
            if r.exit_code == 0:
                logger.info("Removed worktree: %s", wt_path)
            else:
                logger.warning("worktree remove failed (%s): %s", wt_path, r.stderr)

        # 3. Delete branches
        for branch in plan.branches_to_delete:
            r = run_git("branch", "-D", branch, cwd=str(project_path))
            if r.exit_code == 0:
                logger.info("Deleted branch: %s", branch)
            else:
                logger.info("Branch delete skipped (%s): %s", branch, r.stderr.strip())

        # 4. Reset main
        r = run_git("reset", "--hard", plan.target_commit, cwd=str(project_path))
        if r.exit_code != 0:
            raise RecoveryError(f"git reset failed: {r.stderr}")
        logger.info("Reset main to %s", plan.target_commit[:8])

        # 5. Restore archived changes
        changes_root = project_path / "openspec" / "changes"
        for archive_dir in plan.archive_dirs_to_restore:
            # Strip date prefix (e.g., "2026-04-07-1230-admin-products" → "admin-products")
            parts = archive_dir.name.split("-")
            # Find where the change name starts (after numeric date parts)
            for i, p in enumerate(parts):
                if not p.isdigit() and not (len(p) == 4 and p.isdigit()):
                    name_start = i
                    break
            else:
                name_start = 0
            change_name = "-".join(parts[name_start:])
            dest = changes_root / change_name
            if dest.exists():
                logger.warning("Change dir already exists, skipping restore: %s", dest)
                continue
            shutil.move(str(archive_dir), str(dest))
            logger.info("Restored archive: %s → %s", archive_dir.name, dest)

        # 6. Reset state.json
        with locked_state(str(state_file)) as s:
            for ch in s.changes:
                if ch.name in plan.state_changes_to_reset:
                    ch.status = "pending"
                    ch.ralph_pid = None
                    ch.worktree_path = None
                    ch.completed_at = None
                    ch.started_at = None
                    ch.tokens_used = 0
                    ch.input_tokens = 0
                    ch.output_tokens = 0
                    ch.cache_read_tokens = 0
                    ch.cache_create_tokens = 0
                    ch.tokens_used_prev = 0
                    ch.input_tokens_prev = 0
                    ch.output_tokens_prev = 0
                    ch.build_result = None
                    ch.test_result = None
                    ch.e2e_result = None
                    ch.review_result = None
                    ch.test_coverage = None
                    ch.gate_total_ms = 0
                    ch.gate_build_ms = 0
                    ch.gate_test_ms = 0
                    ch.gate_e2e_ms = 0
                    for k in (
                        "merge_retry_count", "integration_retry_count",
                        "integration_e2e_retry_count", "retry_context",
                        "merge_rebase_pending", "stalled_at",
                    ):
                        ch.extras.pop(k, None)
            s.merge_queue = []
            s.status = "stopped"
            s.extras["current_phase"] = plan.first_rolled_back_phase
            logger.info("Reset state for %d changes", len(plan.state_changes_to_reset))

        # 7. Clean up progress/tracking files that reference rolled-back changes
        _reset_progress_files(project_path, plan)

    except Exception as e:
        # Atomic rollback: restore state.json
        shutil.copy(str(state_backup), str(state_file))
        logger.error("Recovery failed mid-way: %s. State restored from backup.", e)
        raise RecoveryError(
            f"Recovery failed: {e}\n"
            f"State.json restored from {state_backup.name}.\n"
            f"To undo git changes: git reset --hard {plan.backup_tag}"
        )


def _reset_progress_files(project_path: Path, plan: RecoveryPlan) -> None:
    """Clean up progress/tracking files that reference rolled-back changes."""
    rolled_back = set(plan.state_changes_to_reset)

    # coverage-merged.json: remove entries for rolled-back REQs
    coverage_merged = project_path / "set" / "orchestration" / "digest" / "coverage-merged.json"
    if coverage_merged.is_file():
        try:
            with open(coverage_merged) as f:
                coverage = json.load(f)
            # Each key is a REQ-ID with a "change" field
            keys_to_remove = [
                k for k, v in coverage.items()
                if isinstance(v, dict) and v.get("change") in rolled_back
            ]
            for k in keys_to_remove:
                del coverage[k]
            with open(coverage_merged, "w") as f:
                json.dump(coverage, f, indent=2)
            if keys_to_remove:
                logger.info("Removed %d coverage entries for rolled-back changes", len(keys_to_remove))
        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.warning("Failed to clean coverage-merged.json: %s", e)

    # review-findings.jsonl: filter out lines for rolled-back changes
    review_findings = project_path / "set" / "orchestration" / "review-findings.jsonl"
    if review_findings.is_file():
        try:
            lines = review_findings.read_text().splitlines()
            kept = [
                l for l in lines
                if not any(f'"change": "{c}"' in l or f'"change":"{c}"' in l for c in rolled_back)
            ]
            review_findings.write_text("\n".join(kept) + "\n" if kept else "")
            removed = len(lines) - len(kept)
            if removed:
                logger.info("Removed %d review findings for rolled-back changes", removed)
        except OSError as e:
            logger.warning("Failed to clean review-findings.jsonl: %s", e)

    # runtime logs for rolled-back changes
    runtime_root = Path.home() / ".local" / "share" / "set-core" / "runtime" / project_path.name
    logs_dir = runtime_root / "logs" / "changes"
    if logs_dir.is_dir():
        for change_name in rolled_back:
            change_log_dir = logs_dir / change_name
            if change_log_dir.is_dir():
                shutil.rmtree(str(change_log_dir))
                logger.info("Removed runtime logs for %s", change_name)

    # Issues registry: remove issues for rolled-back changes
    issues_dir = project_path / ".set" / "issues"
    registry_file = issues_dir / "registry.json"
    if registry_file.is_file():
        try:
            with open(registry_file) as f:
                registry = json.load(f)
            issues = registry.get("issues", [])
            kept = [i for i in issues if i.get("change") not in rolled_back]
            removed = len(issues) - len(kept)
            registry["issues"] = kept
            with open(registry_file, "w") as f:
                json.dump(registry, f, indent=2)
            if removed:
                logger.info("Removed %d issues for rolled-back changes", removed)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to clean issues registry: %s", e)


# ─── Main entry point ──────────────────────────────────────────────────────


def recover_to_change(
    project_path: Path,
    target_change: str,
    *,
    dry_run: bool = False,
    yes: bool = False,
) -> RecoveryPlan:
    """Roll back project to the state after target_change was archived.

    Args:
        project_path: Project root (contains orchestration-state.json)
        target_change: Name of merged change to recover to
        dry_run: If True, show plan but don't execute
        yes: If True, skip confirmation prompt

    Returns:
        The executed RecoveryPlan

    Raises:
        RecoveryError: validation or execution failure
    """
    state, target = _validate_project(project_path, target_change)
    target_commit = _find_target_commit(project_path, target_change)
    plan = _build_recovery_plan(state, target_change, target_commit, project_path)

    print(render_preview(plan, project_path))
    print()

    if dry_run:
        print("[DRY RUN — no changes made]")
        return plan

    if not yes:
        confirm = input("Type 'yes' to proceed: ").strip().lower()
        if confirm != "yes":
            raise RecoveryError("Cancelled by user")

    _execute_plan(project_path, plan, state)

    print()
    print("Recovery complete.")
    print()
    print(f"Project rolled back to: {target_change}")
    print(f"Backup tag: {plan.backup_tag}")
    print()
    print("To undo: git reset --hard " + plan.backup_tag)
    print(f"         cp orchestration-state.json.bak.{plan.backup_tag.split('-', 2)[-1]} orchestration-state.json")
    return plan
