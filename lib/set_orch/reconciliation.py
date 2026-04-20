"""Replan state reconciliation (section 6 of fix-replan-stuck-gate-and-decomposer).

When a replan produces a change-name set that diverges from the prior plan,
the orchestrator must reconcile stale state:

- Worktrees whose change is no longer in the plan → stash any uncommitted
  work, archive the directory, then `git worktree remove --force`.
- `change/<name>` branches not in the plan → delete.
- `openspec/changes/<name>/` dirs not in the plan AND not archived in
  `state-archive.jsonl` → remove.

Reconciliation ALWAYS writes a manifest (`orchestration-cleanup-<epoch>.log`)
BEFORE any destructive operation, so the user can audit every branch and
directory that was touched. The `divergent_plan_dir_cleanup=dry-run`
directive makes reconciliation write the manifest but skip the destructive
operations — useful for verification before flipping to `enabled`.

The stash-failure fallback creates a rescue branch `wip/<name>-<epoch>`
with an unverified commit of the worktree's dirty tree, so no work is
irretrievably lost even if `git stash push -u` hits an I/O error.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReconciliationSummary:
    """Structured result of an orphan-cleanup / replan-reconciliation run.

    Fields mirror the task-6.4 requirement. Default values are the
    observed counts — zero means "nothing happened in that category".
    """

    worktrees_removed: int = 0
    dirty_skipped: int = 0
    dirty_forced: int = 0
    pids_cleared: int = 0
    steps_fixed: int = 0
    artifacts_collected: int = 0
    merge_queue_entries_restored: int = 0
    issues_released: int = 0
    branches_deleted: int = 0
    change_dirs_removed: int = 0
    manifest_path: str = ""
    dry_run: bool = False
    stash_refs: list[str] = field(default_factory=list)
    rescue_branches: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "worktrees_removed": self.worktrees_removed,
            "dirty_skipped": self.dirty_skipped,
            "dirty_forced": self.dirty_forced,
            "pids_cleared": self.pids_cleared,
            "steps_fixed": self.steps_fixed,
            "artifacts_collected": self.artifacts_collected,
            "merge_queue_entries_restored": self.merge_queue_entries_restored,
            "issues_released": self.issues_released,
            "branches_deleted": self.branches_deleted,
            "change_dirs_removed": self.change_dirs_removed,
            "manifest_path": self.manifest_path,
            "dry_run": self.dry_run,
            "stash_refs": list(self.stash_refs),
            "rescue_branches": list(self.rescue_branches),
        }


def divergent_names(
    old_plan_names: Iterable[str], new_plan_names: Iterable[str],
) -> set[str]:
    """Return the set of change names that appear in exactly one of the two
    plans. Non-empty output means the two plans have diverged and stale
    state reconciliation is required.

    Uses symmetric difference — `old ^ new` in set terms.
    """
    return set(old_plan_names) ^ set(new_plan_names)


def _git(cwd: str, *args: str, timeout: int = 10) -> subprocess.CompletedProcess:
    """Wrapper around `git -C <cwd> <args>` returning the CompletedProcess."""
    return subprocess.run(
        ["git", "-C", cwd, *args],
        capture_output=True, text=True, timeout=timeout,
    )


def _stash_worktree(wt_path: str, reason: str) -> tuple[bool, str]:
    """Attempt `git stash push -u -m 'auto-stash: <reason>'` inside `wt_path`.

    Returns (success, stash_ref_or_error). The stash ref is "stash@{0}" when
    the stash succeeds.
    """
    try:
        r = _git(
            wt_path, "stash", "push", "-u", "-m", f"auto-stash: {reason}",
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, f"stash-subprocess-error: {exc}"
    if r.returncode != 0:
        return False, r.stderr.strip()[:400] or r.stdout.strip()[:400]
    return True, "stash@{0}"


def _create_rescue_branch(wt_path: str, change_name: str) -> tuple[bool, str]:
    """Fallback when stash fails: create `wip/<name>-<epoch>` with an
    unverified commit of the worktree's dirty tree. Returns (success,
    branch-name-or-error). Uses `--no-verify` only inside this rescue
    path (never the normal commit flow).
    """
    branch = f"wip/{change_name}-{int(time.time())}"
    try:
        r_co = _git(wt_path, "checkout", "-b", branch, timeout=15)
        if r_co.returncode != 0:
            return False, f"checkout -b: {r_co.stderr.strip()[:300]}"
        _git(wt_path, "add", "-A", timeout=15)
        r_ci = _git(
            wt_path, "commit", "--no-verify",
            "-m", f"auto-rescue: divergent-replan cleanup of {change_name}",
            timeout=30,
        )
        if r_ci.returncode != 0:
            return False, f"commit: {r_ci.stderr.strip()[:300]}"
        return True, branch
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, f"rescue-subprocess-error: {exc}"


def _worktree_is_dirty(wt_path: str) -> bool:
    try:
        r = _git(wt_path, "status", "--porcelain", timeout=10)
    except (subprocess.TimeoutExpired, OSError):
        return False
    return r.returncode == 0 and bool(r.stdout.strip())


def _list_worktrees(project_dir: str) -> list[tuple[str, str]]:
    """Return [(wt_path, branch_name_without_prefix), ...] for worktrees
    matching `<project>-wt-<name>`.
    """
    try:
        r = _git(project_dir, "worktree", "list", "--porcelain", timeout=10)
    except (subprocess.TimeoutExpired, OSError):
        return []
    if r.returncode != 0:
        return []
    project_name = os.path.basename(project_dir.rstrip("/"))
    wt_prefix = f"{project_name}-wt-"
    out: list[tuple[str, str]] = []
    path = ""
    for line in r.stdout.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):].strip()
            base = os.path.basename(path)
            if base.startswith(wt_prefix):
                out.append((path, base[len(wt_prefix):]))
    return out


def _branch_exists(project_dir: str, branch: str) -> bool:
    try:
        r = _git(
            project_dir, "rev-parse", "--verify", branch,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return r.returncode == 0


def _list_change_branches(project_dir: str) -> list[str]:
    """Return branch names of the form `change/<name>`.

    `git branch --list` prefixes the current branch with `* ` and branches
    checked out in a linked worktree with `+ `. Strip both prefixes and
    any whitespace so the returned names are clean refs.
    """
    try:
        r = _git(project_dir, "branch", "--list", "change/*", timeout=10)
    except (subprocess.TimeoutExpired, OSError):
        return []
    if r.returncode != 0:
        return []
    out: list[str] = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(("* ", "+ ")):
            line = line[2:].strip()
        # Trailing worktree hint like `(worktree: path)` can appear —
        # split on whitespace and take the first token.
        name = line.split()[0] if line else ""
        if name.startswith("change/"):
            out.append(name)
    return out


def _archived_change_names(project_dir: str) -> set[str]:
    """Parse `state-archive.jsonl` for names we must NOT delete.

    Each line is a JSON record containing `name`. Missing file → empty set.
    """
    archive_path = os.path.join(project_dir, "state-archive.jsonl")
    if not os.path.isfile(archive_path):
        return set()
    names: set[str] = set()
    try:
        with open(archive_path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if isinstance(rec, dict) and rec.get("name"):
                        names.add(rec["name"])
                except json.JSONDecodeError:
                    continue
    except OSError as exc:
        logger.debug("archive parse failed %s: %s", archive_path, exc)
    return names


def write_cleanup_manifest(
    project_dir: str,
    *,
    timestamp: Optional[int] = None,
    operations: Iterable[dict] | None = None,
) -> str:
    """Write a structured manifest describing every branch + directory that
    will be removed. Returns the manifest path. Called BEFORE any
    destructive op so the operator can audit the intended state change
    even when the process crashes mid-cleanup.
    """
    ts = int(timestamp or time.time())
    manifest_path = os.path.join(project_dir, f"orchestration-cleanup-{ts}.log")
    lines = [
        f"orchestration cleanup manifest @ {ts}",
        "# each line describes a single destructive op with rationale",
        "",
    ]
    for op in operations or []:
        op_type = op.get("op", "?")
        target = op.get("target", "")
        why = op.get("reason", "")
        lines.append(f"{op_type}\t{target}\t{why}")
    try:
        Path(manifest_path).write_text("\n".join(lines) + "\n")
    except OSError as exc:
        logger.warning("manifest write failed %s: %s", manifest_path, exc)
    return manifest_path


def reconcile_divergent_plan(
    project_dir: str,
    new_plan_names: Iterable[str],
    *,
    dry_run: bool = False,
) -> ReconciliationSummary:
    """Perform divergent-plan reconciliation: archive stale worktrees,
    delete orphan branches, and remove orphan `openspec/changes/<name>/`
    dirs.

    Always writes a manifest first. When `dry_run=True` the manifest is
    still written but no destructive ops run.

    Returns a ReconciliationSummary counting each category of action.
    """
    summary = ReconciliationSummary(dry_run=dry_run)
    new_plan_set = set(new_plan_names)
    archived_set = _archived_change_names(project_dir)

    # 1) Enumerate worktrees + branches + change dirs not in the new plan.
    worktrees = _list_worktrees(project_dir)
    stale_worktrees = [(p, n) for p, n in worktrees if n not in new_plan_set]

    change_branches = _list_change_branches(project_dir)
    stale_branches = [
        b for b in change_branches
        if b[len("change/"):] not in new_plan_set
    ]

    openspec_changes_dir = os.path.join(project_dir, "openspec", "changes")
    stale_dirs: list[str] = []
    if os.path.isdir(openspec_changes_dir):
        for entry in os.listdir(openspec_changes_dir):
            full = os.path.join(openspec_changes_dir, entry)
            if not os.path.isdir(full):
                continue
            # Skip fix-iss-* escalations regardless of plan membership —
            # they are auto-generated diagnosis children of failed parents
            # and should not be swept away on replan.
            if entry.startswith("fix-iss-"):
                continue
            if entry in new_plan_set:
                continue
            if entry in archived_set:
                continue
            stale_dirs.append(full)

    # 2) Write manifest BEFORE any destructive op.
    ops: list[dict] = []
    for p, n in stale_worktrees:
        ops.append({"op": "remove_worktree", "target": p, "reason": "not-in-new-plan"})
    for b in stale_branches:
        ops.append({"op": "delete_branch", "target": b, "reason": "not-in-new-plan"})
    for d in stale_dirs:
        ops.append({"op": "remove_change_dir", "target": d, "reason": "not-in-new-plan"})
    summary.manifest_path = write_cleanup_manifest(
        project_dir, operations=ops,
    )
    if dry_run:
        logger.info(
            "Reconciliation dry-run: %d ops recorded in %s",
            len(ops), summary.manifest_path,
        )
        return summary

    # 3) Execute: worktrees first (stash/rescue, archive, prune).
    for wt_path, change_name in stale_worktrees:
        if not os.path.isdir(wt_path):
            continue
        if _worktree_is_dirty(wt_path):
            ok, info = _stash_worktree(
                wt_path, f"divergent-replan {int(time.time())}",
            )
            if ok:
                summary.stash_refs.append(f"{change_name}:{info}")
            else:
                logger.warning(
                    "stash failed for %s (%s) — creating rescue branch",
                    change_name, info,
                )
                ok2, branch_or_err = _create_rescue_branch(wt_path, change_name)
                if ok2:
                    summary.rescue_branches.append(branch_or_err)
                else:
                    logger.error(
                        "rescue-branch fallback also failed for %s: %s",
                        change_name, branch_or_err,
                    )
                    summary.dirty_skipped += 1
                    continue
            summary.dirty_forced += 1

        # Archive the worktree by renaming (preserves all files on disk)
        archived = f"{wt_path}.removed.{int(time.time())}"
        try:
            os.rename(wt_path, archived)
        except OSError as exc:
            logger.warning("archive-rename failed for %s: %s", change_name, exc)
        # Prune the git admin entry
        try:
            _git(project_dir, "worktree", "prune", timeout=30)
            summary.worktrees_removed += 1
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.warning("worktree prune failed: %s", exc)

    # 4) Delete stale branches.
    for branch in stale_branches:
        if not _branch_exists(project_dir, branch):
            continue
        try:
            r = _git(project_dir, "branch", "-D", branch, timeout=10)
            if r.returncode == 0:
                summary.branches_deleted += 1
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.warning("branch delete failed %s: %s", branch, exc)

    # 5) Remove stale openspec/changes/<name>/ dirs.
    import shutil
    for change_dir in stale_dirs:
        try:
            shutil.rmtree(change_dir)
            summary.change_dirs_removed += 1
        except OSError as exc:
            logger.warning("change-dir remove failed %s: %s", change_dir, exc)

    logger.warning(
        "Reconciliation: %d worktrees removed, %d dirty forced, %d branches "
        "deleted, %d change dirs removed (manifest=%s)",
        summary.worktrees_removed, summary.dirty_forced,
        summary.branches_deleted, summary.change_dirs_removed,
        summary.manifest_path,
    )
    return summary
