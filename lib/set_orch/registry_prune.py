"""Loss-free pruning of the project registry and orphaned git worktree records.

The registry (``~/.config/set-core/projects.json``) is append-only in practice:
every ``set-project init`` and every E2E runner adds an entry and nothing removes
one. Orphaned git worktree records accumulate the same way.

The operating constraint, stated by the user and enforced here by construction
rather than by intention: **nothing may be lost from disk, and a project whose
directory exists may not be deleted.** So:

- Deregistration keys on exactly one fact — the directory does not exist. Not
  age, not emptiness, not a name pattern. See :func:`classify_entries`.
- A path whose *parent* is also missing reads as *unknown*, not *gone* — an
  unmounted filesystem is indistinguishable from a deleted directory at the leaf,
  and the two demand opposite actions. See :data:`Classification.unreachable`.
- Entries whose directory exists are *archived* (a reversible flag on the entry),
  never removed. See :func:`apply_archive`.
- ``git worktree prune`` is the only git mutation, it runs only where git itself
  has flagged records prunable, and it never touches a branch or a directory.

There is deliberately no code path in this module that deletes a file, a
directory, a worktree or a branch. ``tests/unit/test_registry_prune_loss_free.py``
proves that with a filesystem hash rather than by reading the code.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

# Issue states that mean a human still has something to look at. Mirrors the set
# used by the projects API for its `issues_open` count; anything not listed here
# is terminal (resolved / dismissed / muted / skipped / cancelled) or failed —
# and `failed` IS open, because a failed issue is precisely the thing that must
# not be hidden behind an archive flag.
OPEN_ISSUE_STATES = frozenset({
    "new", "investigating", "diagnosed", "awaiting_approval",
    "fixing", "verifying", "deploying", "failed",
})

# Every git invocation this module is allowed to make. A test asserts the argv of
# each real call is one of these shapes — a destructive verb reaching git from
# here should fail the suite, not a review.
_ALLOWED_GIT_VERBS = frozenset({"worktree"})
_FORBIDDEN_GIT_TOKENS = frozenset({"remove", "--expire", "-D", "-f", "--force", "branch", "clean"})


def e2e_runs_root() -> Path:
    """The framework's own E2E run root.

    Location — not age — is what separates test fixtures from real projects:
    measured 2026-07-24, `consumer-c` (62d) and `consumer-i` (62d) are real
    projects exactly as old as the E2E runs to be archived.
    """
    return Path.home() / ".local" / "share" / "set-core" / "e2e-runs"


# ─── Report ───────────────────────────────────────────────────────────


@dataclass
class ArchiveRefusal:
    name: str
    reason: str


@dataclass
class PruneReport:
    """What a prune did, or would do. Callers read this, never parsed prose."""

    deregistered: list[str] = field(default_factory=list)
    unreachable: list[str] = field(default_factory=list)
    archived: list[str] = field(default_factory=list)
    archive_refused: list[ArchiveRefusal] = field(default_factory=list)
    worktrees_pruned: dict[str, list[str]] = field(default_factory=dict)
    backup_path: Optional[str] = None
    preview: bool = False

    @property
    def worktree_count(self) -> int:
        return sum(len(v) for v in self.worktrees_pruned.values())

    @property
    def mutates(self) -> bool:
        """Would this report's actions write anything at all?"""
        return bool(self.deregistered or self.archived or self.worktree_count)

    def to_dict(self) -> dict:
        return {
            "deregistered": list(self.deregistered),
            "unreachable": list(self.unreachable),
            "archived": list(self.archived),
            "archive_refused": [{"name": r.name, "reason": r.reason} for r in self.archive_refused],
            "worktrees_pruned": {k: list(v) for k, v in self.worktrees_pruned.items()},
            "backup_path": self.backup_path,
            "preview": self.preview,
        }


@dataclass
class Classification:
    """Registry entries split by what is actually true of their path."""

    deregistrable: list[dict] = field(default_factory=list)
    unreachable: list[dict] = field(default_factory=list)
    kept: list[dict] = field(default_factory=list)


# ─── Classification ───────────────────────────────────────────────────


def classify_entries(projects: Iterable[dict]) -> Classification:
    """Split registry entries on the single fact that may drive deregistration.

    An entry is deregistrable **iff** its path is not an existing directory AND
    its parent directory does exist. The parent check is what keeps an unmounted
    filesystem from looking like a deleted project: `isdir()` returns False for
    both, and being wrong toward "remove" costs a registration with no record it
    ever existed, while being wrong toward "keep" costs a stale row in a list.
    """
    out = Classification()
    for entry in projects:
        raw = (entry.get("path") or "").strip()
        if not raw:
            # No path at all: nothing can be verified about it, so it is kept.
            logger.warning("registry entry has no path, keeping: name=%s", entry.get("name"))
            out.unreachable.append(entry)
            continue
        path = Path(raw).expanduser()
        if path.is_dir():
            out.kept.append(entry)
            continue
        parent = path.parent
        if parent.is_dir():
            logger.info(
                "registry entry deregistrable: name=%s path=%s (parent exists)",
                entry.get("name"), raw,
            )
            out.deregistrable.append(entry)
        else:
            logger.warning(
                "registry entry unreachable, keeping: name=%s path=%s (parent %s missing — "
                "possibly an unmounted filesystem)",
                entry.get("name"), raw, parent,
            )
            out.unreachable.append(entry)
    return out


# ─── Worktrees ────────────────────────────────────────────────────────


def _run_git(project_path: Path, args: list[str]) -> subprocess.CompletedProcess:
    """Run a git subcommand, refusing anything outside this module's remit.

    The guard is here rather than in a comment because a later edit that reaches
    for `worktree remove` should fail loudly at the call site.
    """
    if not args or args[0] not in _ALLOWED_GIT_VERBS:
        raise ValueError(f"git verb not permitted from registry_prune: {args!r}")
    forbidden = _FORBIDDEN_GIT_TOKENS.intersection(args)
    if forbidden:
        raise ValueError(f"destructive git token not permitted from registry_prune: {sorted(forbidden)!r}")
    cmd = ["git", "-C", str(project_path), *args]
    logger.debug("registry_prune git: %s", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def prunable_worktrees(project_path: Path) -> list[str]:
    """Worktree paths git itself has flagged prunable, in this repository.

    Only git's own `prunable` flag counts. This module never decides for itself
    that a worktree is stale, and never passes an expiry — so a worktree being
    created right now is not a candidate.
    """
    try:
        proc = _run_git(project_path, ["worktree", "list", "--porcelain"])
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("worktree list failed, skipping: path=%s err=%s", project_path, exc)
        return []
    if proc.returncode != 0:
        # Not a git repository, or git refused. Nothing to do, and nothing to fix.
        logger.debug("worktree list rc=%s path=%s", proc.returncode, project_path)
        return []
    out: list[str] = []
    current: Optional[str] = None
    for line in proc.stdout.splitlines():
        if line.startswith("worktree "):
            current = line[len("worktree "):].strip()
        elif line.startswith("prunable") and current:
            out.append(current)
            current = None
        elif not line.strip():
            current = None  # blank line ends the record
    return out


def prune_worktrees(project_path: Path, *, preview: bool = False) -> list[str]:
    """Prune orphaned worktree records. Returns the paths that were (or would be) pruned.

    A repository with no prunable records is not mutated at all — git is not even
    invoked a second time.
    """
    candidates = prunable_worktrees(project_path)
    if not candidates:
        return []
    if preview:
        return candidates
    try:
        proc = _run_git(project_path, ["worktree", "prune"])
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("worktree prune failed: path=%s err=%s", project_path, exc)
        return []
    if proc.returncode != 0:
        logger.warning(
            "worktree prune rc=%s path=%s stderr=%s",
            proc.returncode, project_path, proc.stderr.strip()[:200],
        )
        return []
    logger.info("pruned %d orphaned worktree records: path=%s", len(candidates), project_path)
    return candidates


# ─── Archiving ────────────────────────────────────────────────────────


def _parse_days(spec: str) -> int:
    """Parse an age threshold such as '30d' or '30'. Raises on anything else."""
    s = str(spec).strip().lower()
    if s.endswith("d"):
        s = s[:-1]
    if not s.isdigit():
        raise ValueError(f"invalid age threshold: {spec!r} (expected e.g. '30d')")
    days = int(s)
    if days < 0:
        raise ValueError(f"age threshold must not be negative: {spec!r}")
    return days


def _entry_age_days(entry: dict) -> Optional[float]:
    """Age of an entry, by the newest mtime of its directory tree markers.

    Returns None when the age cannot be established — and an unknown age never
    satisfies a threshold, so it cannot cause an archive.
    """
    raw = (entry.get("path") or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    try:
        newest = path.stat().st_mtime
    except OSError:
        return None
    # A run directory's own mtime goes stale while work continues inside it, so
    # take the newest of the directory and its orchestration state file.
    try:
        from .paths import LineagePaths
        state = Path(LineagePaths(str(path)).state_file)
        if state.exists():
            newest = max(newest, state.stat().st_mtime)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("state mtime unavailable for %s: %s", path, exc)
    return (time.time() - newest) / 86400.0


def _open_issue_count(project_path: Path) -> int:
    registry = project_path / ".set" / "issues" / "registry.json"
    if not registry.exists():
        return 0
    try:
        data = json.loads(registry.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("issue registry unreadable, treating as blocking: path=%s err=%s", project_path, exc)
        # Unreadable is not zero. A gap is not a zero — refuse the archive.
        return -1
    issues = data.get("issues", []) if isinstance(data, dict) else []
    return sum(1 for i in issues if isinstance(i, dict) and i.get("state") in OPEN_ISSUE_STATES)


def _live_process(project_path: Path) -> Optional[str]:
    """Name of a live sentinel/orchestrator for this project, or None.

    Resolves the paths through `paths` directly rather than through the API
    helpers, so this stays importable without the web layer.
    """
    from .paths import LineagePaths, SetRuntime

    def alive(pid) -> bool:
        try:
            os.kill(int(pid), 0)
            return True
        except (ProcessLookupError, PermissionError, TypeError, ValueError, OSError):
            return False

    try:
        sentinel_dir = Path(SetRuntime(str(project_path)).sentinel_dir)
    except Exception:  # pragma: no cover - defensive
        sentinel_dir = project_path / ".set" / "sentinel"
    try:
        pid_file = sentinel_dir / "sentinel.pid"
        if pid_file.exists() and alive(pid_file.read_text().strip()):
            return "sentinel"
    except OSError as exc:
        logger.debug("sentinel pid check failed for %s: %s", project_path, exc)
    try:
        sp = Path(LineagePaths(str(project_path)).state_file)
        if sp.exists():
            data = json.loads(sp.read_text())
            if alive(data.get("orchestrator_pid")):
                return "orchestrator"
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("state pid check failed for %s: %s", project_path, exc)
    return None


def archive_candidates(
    projects: Iterable[dict],
    threshold: Optional[str],
    *,
    root: Optional[Path] = None,
) -> tuple[list[dict], list[ArchiveRefusal]]:
    """Entries eligible for archiving, and the refusals with their reasons.

    Both conditions are required and neither has a default: an explicit age
    threshold from the operator, AND a location under the framework's E2E run
    root. Called with ``threshold=None`` this returns nothing at all, which is
    what makes a bare prune incapable of archiving.
    """
    if threshold is None:
        return [], []
    days = _parse_days(threshold)
    e2e_root = (root or e2e_runs_root()).resolve()
    eligible: list[dict] = []
    refused: list[ArchiveRefusal] = []
    for entry in projects:
        if entry.get("archived"):
            continue
        raw = (entry.get("path") or "").strip()
        if not raw:
            continue
        path = Path(raw).expanduser()
        if not path.is_dir():
            continue  # deregistration's business, not archiving's
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if e2e_root not in resolved.parents:
            continue
        age = _entry_age_days(entry)
        if age is None or age < days:
            continue
        name = entry.get("name", path.name)
        open_issues = _open_issue_count(path)
        if open_issues != 0:
            reason = (
                "issue registry unreadable"
                if open_issues < 0
                else f"{open_issues} open issue(s)"
            )
            refused.append(ArchiveRefusal(name=name, reason=reason))
            logger.info("archive refused: name=%s reason=%s", name, reason)
            continue
        running = _live_process(path)
        if running:
            refused.append(ArchiveRefusal(name=name, reason=f"{running} is running"))
            logger.info("archive refused: name=%s reason=%s running", name, running)
            continue
        eligible.append(entry)
    return eligible, refused


def apply_archive(entry: dict) -> dict:
    """Mark an entry archived in place. Every other field is left untouched."""
    entry["archived"] = True
    entry["archivedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return entry


def clear_archive(entry: dict) -> dict:
    """Exact inverse of :func:`apply_archive`."""
    entry.pop("archived", None)
    entry.pop("archivedAt", None)
    return entry


def is_archived(entry: dict) -> bool:
    return bool(entry.get("archived"))


# ─── Backup ───────────────────────────────────────────────────────────


# The backup lives in `project_registry` — one implementation, and reachable
# without the web layer. Re-exported so callers of this module find it here.
from .project_registry import backup_registry  # noqa: E402


# ─── Orchestration ────────────────────────────────────────────────────


def _clear_dangling_default(
    removed: Iterable[str], registry_file: Optional[Path] = None
) -> Optional[str]:
    """Drop the `default` pointer when it names an entry that just went away.

    "Went away" covers both deregistration and archiving: `save_projects`
    deliberately preserves `default`, so either leaves a pointer that reads
    exactly like a configured one to every caller downstream while naming
    something no command will show.

    Returns the cleared name so the caller can REPORT it. A default that
    disappears silently is a configuration change nobody can trace later.
    """
    from .project_registry import PROJECTS_FILE
    src = Path(registry_file) if registry_file else PROJECTS_FILE
    removed = set(removed)
    if not removed or not src.exists():
        return None
    try:
        data = json.loads(src.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict) or data.get("default") not in removed:
        return None
    cleared = data.get("default")
    logger.warning("clearing default project, it is no longer listed: %s", cleared)
    data["default"] = None
    src.write_text(json.dumps(data, indent=2))
    return cleared


@dataclass
class NameArchiveReport:
    """Outcome of an archive/unarchive by name."""

    archived: list[str] = field(default_factory=list)
    unarchived: list[str] = field(default_factory=list)
    refused: list[ArchiveRefusal] = field(default_factory=list)
    noop: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    default_cleared: Optional[str] = None
    backup_path: Optional[str] = None
    preview: bool = False

    @property
    def mutates(self) -> bool:
        return bool(self.archived or self.unarchived)


def archive_by_name(
    names: Iterable[str],
    *,
    undo: bool = False,
    preview: bool = False,
    registry_file: Optional[Path] = None,
) -> NameArchiveReport:
    """Archive (or unarchive) specific entries the operator named.

    This is a different act from the threshold-driven bulk path, and its refusal
    rules differ deliberately:

    - **Open issues warn, they do not block.** Naming the project IS the decision,
      and the issues stay visible — the sidebar's total reads a separate endpoint.
      The bulk path keeps its refusal, because there nobody looked at the entry.
    - **A live sentinel/orchestrator refuses, with no override.** Hiding work that
      is running right now makes the dashboard lie about the machine's state.
    - **A missing directory refuses**, pointing at `set-project prune` — archiving
      is for entries whose directory is alive; hiding a dead one behind a flag is
      the worst of both.
    - **An unknown name aborts everything before the first write**, so a typo
      cannot half-apply across the other named entries.
    """
    from . import project_registry

    projects = project_registry.load_projects(registry_file)
    by_name = {p.get("name", ""): p for p in projects}
    report = NameArchiveReport(preview=preview)

    wanted = list(names)
    report.unknown = [n for n in wanted if n not in by_name]
    if report.unknown:
        # Nothing is written — not even for the names that DO exist.
        logger.warning("archive by name aborted, unknown: %s", ", ".join(report.unknown))
        return report

    for name in wanted:
        entry = by_name[name]
        if undo:
            if not is_archived(entry):
                report.noop.append(name)
                continue
            clear_archive(entry)
            report.unarchived.append(name)
            continue

        if is_archived(entry):
            report.noop.append(name)
            continue
        path = Path((entry.get("path") or "").strip()).expanduser()
        if not path.is_dir():
            report.refused.append(ArchiveRefusal(
                name=name,
                reason="directory does not exist — deregister it with `set-project prune`",
            ))
            continue
        running = _live_process(path)
        if running:
            report.refused.append(ArchiveRefusal(
                name=name, reason=f"{running} is running — stop it first",
            ))
            continue
        open_issues = _open_issue_count(path)
        if open_issues != 0:
            report.warnings.append(
                f"{name}: {'issue registry unreadable' if open_issues < 0 else f'{open_issues} open issue(s)'}"
                " — archived anyway, the issue count on the dashboard is unaffected"
            )
        apply_archive(entry)
        report.archived.append(name)

    if preview or not report.mutates:
        return report

    report.backup_path = backup_registry(registry_file)
    project_registry.save_projects(projects, registry_file)
    if report.archived:
        report.default_cleared = _clear_dangling_default(report.archived, registry_file)
    logger.info(
        "archive by name: archived=%d unarchived=%d refused=%d",
        len(report.archived), len(report.unarchived), len(report.refused),
    )
    return report


def format_name_report(report: NameArchiveReport, *, undo: bool = False) -> str:
    """Human-readable outcome. Every category is named, including the empty ones
    that mean "asked for, not done"."""
    lines: list[str] = []
    if report.unknown:
        lines.append(f"Not found in the registry: {', '.join(report.unknown)}")
        lines.append("Nothing was written — fix the name(s) and run again.")
        return "\n".join(lines)
    done = report.unarchived if undo else report.archived
    if done:
        verb = ("Would unarchive" if report.preview else "Unarchived") if undo else \
               ("Would archive" if report.preview else "Archived")
        lines.append(f"{verb} {len(done)} entr(ies) — nothing removed from disk:")
        lines += [f"    - {n}" for n in done]
    if report.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines += [f"    ! {w}" for w in report.warnings]
    if report.refused:
        lines.append("")
        lines.append(f"REFUSED for {len(report.refused)}:")
        lines += [f"    - {r.name}: {r.reason}" for r in report.refused]
    if report.noop:
        lines.append("")
        state = "not archived" if undo else "already archived"
        lines.append(f"No change ({state}): {', '.join(report.noop)}")
    if report.default_cleared:
        lines.append("")
        lines.append(
            f"NOTE: cleared the default project — it named '{report.default_cleared}', "
            "which is now archived. Set a new one with `set-project default <name>`."
        )
    if report.backup_path:
        lines.append("")
        lines.append(f"Registry backed up to: {report.backup_path}")
    return "\n".join(lines) if lines else "Nothing to do."


def run_prune(
    *,
    preview: bool = False,
    archive_older_than: Optional[str] = None,
    registry_file: Optional[Path] = None,
) -> PruneReport:
    """Classify, then act. In preview mode no write path is taken at all.

    Order matters: the backup is written before the first mutation, and a backup
    failure aborts before anything has changed.
    """
    from . import project_registry

    projects = project_registry.load_projects(registry_file)

    report = PruneReport(preview=preview)
    cls = classify_entries(projects)
    report.deregistered = [p.get("name", "") for p in cls.deregistrable]
    report.unreachable = [p.get("name", "") for p in cls.unreachable if p.get("path")]

    survivors = cls.kept + cls.unreachable
    eligible, refused = archive_candidates(survivors, archive_older_than)
    report.archive_refused = refused
    report.archived = [p.get("name", "") for p in eligible]

    # Worktree records: only in projects whose directory exists.
    for entry in cls.kept:
        path = Path(entry["path"]).expanduser()
        pruned = prune_worktrees(path, preview=True)  # discover first, always
        if pruned:
            report.worktrees_pruned[entry.get("name", path.name)] = pruned

    if preview:
        logger.info(
            "prune preview: deregister=%d unreachable=%d archive=%d refused=%d worktrees=%d",
            len(report.deregistered), len(report.unreachable),
            len(report.archived), len(report.archive_refused), report.worktree_count,
        )
        return report

    if not report.mutates:
        logger.info("prune: nothing to do")
        return report

    # Backup BEFORE the first mutation; a failure here aborts untouched.
    report.backup_path = backup_registry(registry_file)

    if report.deregistered or report.archived:
        for entry in eligible:
            apply_archive(entry)
        project_registry.save_projects(survivors, registry_file)
        _clear_dangling_default(report.deregistered, registry_file)
        logger.info(
            "registry written: deregistered=%d archived=%d remaining=%d",
            len(report.deregistered), len(report.archived), len(survivors),
        )

    for name in list(report.worktrees_pruned):
        entry = next((e for e in cls.kept if e.get("name", "") == name), None)
        if entry is None:
            continue
        actually = prune_worktrees(Path(entry["path"]).expanduser(), preview=False)
        report.worktrees_pruned[name] = actually

    return report


# ─── CLI ──────────────────────────────────────────────────────────────


def format_plan(report: PruneReport) -> str:
    """Human-readable plan. Reports gaps as gaps — an empty section says so."""
    lines: list[str] = []
    verb = "Would deregister" if report.preview else "Deregistered"
    if report.deregistered:
        lines.append(f"{verb} {len(report.deregistered)} entr(ies) whose directory is gone:")
        lines += [f"    - {n}" for n in report.deregistered]
    else:
        lines.append("No registry entry has a missing directory.")
    if report.unreachable:
        lines.append("")
        lines.append(
            f"KEPT — {len(report.unreachable)} entr(ies) unreachable (parent directory missing "
            "too; possibly an unmounted filesystem):"
        )
        lines += [f"    - {n}" for n in report.unreachable]
    if report.worktrees_pruned:
        lines.append("")
        verb = "Would prune" if report.preview else "Pruned"
        lines.append(f"{verb} {report.worktree_count} orphaned worktree record(s):")
        for proj, paths in report.worktrees_pruned.items():
            lines.append(f"    {proj}:")
            lines += [f"      - {p}" for p in paths]
    if report.archived:
        lines.append("")
        verb = "Would archive" if report.preview else "Archived"
        lines.append(f"{verb} {len(report.archived)} E2E run(s) — entry and files kept, hidden from the dashboard:")
        lines += [f"    - {n}" for n in report.archived]
    if report.archive_refused:
        lines.append("")
        lines.append(f"Archive REFUSED for {len(report.archive_refused)}:")
        lines += [f"    - {r.name}: {r.reason}" for r in report.archive_refused]
    if report.backup_path:
        lines.append("")
        lines.append(f"Registry backed up to: {report.backup_path}")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="set-project prune",
        description="Remove registry entries whose directory is gone and prune orphaned "
                    "worktree records. Never deletes anything from disk.",
    )
    parser.add_argument("--dry-run", action="store_true", help="report only; writes nothing")
    parser.add_argument(
        "--archive-e2e-older-than", metavar="Nd", default=None,
        help="also archive E2E runs older than N days (reversible flag; no default)",
    )
    parser.add_argument("--yes", "-y", action="store_true", help="skip the confirmation prompt")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    try:
        plan = run_prune(preview=True, archive_older_than=args.archive_e2e_older_than)
    except ValueError as exc:
        print(f"error: {exc}")
        return 2

    if args.dry_run:
        print(format_plan(plan) if not args.json else json.dumps(plan.to_dict(), indent=2))
        return 0

    if not plan.mutates:
        print(format_plan(plan))
        return 0

    if not args.yes:
        print(format_plan(plan))
        print()
        try:
            answer = input("Proceed? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted; nothing was written.")
            return 1
        if answer not in ("y", "yes"):
            print("Aborted; nothing was written.")
            return 1

    try:
        report = run_prune(preview=False, archive_older_than=args.archive_e2e_older_than)
    except OSError as exc:
        print(f"error: registry backup failed, nothing was changed: {exc}")
        return 3
    print(format_plan(report) if not args.json else json.dumps(report.to_dict(), indent=2))
    return 0


def main_archive(argv: Optional[list[str]] = None, *, undo: bool = False) -> int:
    """Entry point for `set-project archive` / `unarchive`."""
    import argparse

    verb = "unarchive" if undo else "archive"
    parser = argparse.ArgumentParser(
        prog=f"set-project {verb}",
        description=(
            f"{verb.capitalize()} named registry entries. Archiving hides an entry from the "
            "dashboard; the entry and every file on disk are kept, and it is reversible."
        ),
    )
    parser.add_argument("names", nargs="+", metavar="NAME")
    parser.add_argument("--dry-run", action="store_true", help="report only; writes nothing")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    report = archive_by_name(args.names, undo=undo, preview=args.dry_run)
    if args.json:
        from dataclasses import asdict
        print(json.dumps(asdict(report), indent=2))
    else:
        print(format_name_report(report, undo=undo))
    if report.unknown:
        return 2
    return 1 if report.refused and not report.mutates else 0


if __name__ == "__main__":  # pragma: no cover
    import sys as _sys
    _mode = _sys.argv[1] if len(_sys.argv) > 1 else ""
    if _mode in ("archive", "unarchive"):
        raise SystemExit(main_archive(_sys.argv[2:], undo=(_mode == "unarchive")))
    raise SystemExit(main())
