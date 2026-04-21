"""Resolve a run id to the set of Claude Code session dirs + orchestration dir."""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class NoSessionDirsError(RuntimeError):
    """Raised when no Claude Code session dirs match the given run id."""


@dataclass
class ResolvedRun:
    run_id: str
    main_session_dir: Optional[Path]
    worktree_session_dirs: dict[str, Path] = field(default_factory=dict)
    orchestration_dir: Optional[Path] = None

    def iter_all_session_dirs(self) -> list[tuple[str, Path]]:
        """Yield (change-name, dir) for main + worktrees. Main uses the label 'main'."""
        out: list[tuple[str, Path]] = []
        if self.main_session_dir is not None:
            out.append(("main", self.main_session_dir))
        for change, d in sorted(self.worktree_session_dirs.items()):
            out.append((change, d))
        return out


def _encode_path_for_claude_projects(path: Path) -> str:
    """Claude Code encodes a filesystem path as a directory name under ~/.claude/projects/
    by replacing `/` and `.` with `-`.

    Example: `/home/tg/.local/share/set-core/e2e-runs/foo`
             → `-home-tg--local-share-set-core-e2e-runs-foo`
    """
    s = str(path)
    return s.replace("/", "-").replace(".", "-")


def _claude_projects_root() -> Path:
    return Path.home() / ".claude" / "projects"


def _e2e_runs_root() -> Path:
    return Path.home() / ".local" / "share" / "set-core" / "e2e-runs"


def resolve_run(
    run_id: str,
    *,
    claude_projects_root: Optional[Path] = None,
    e2e_runs_root: Optional[Path] = None,
) -> ResolvedRun:
    """Resolve a run id to its session dirs + orchestration dir.

    Raises NoSessionDirsError if no session dirs can be found for the run.
    Emits a WARNING on stderr when the orchestration dir is missing; sessions alone
    are still resolved.
    """
    projects_root = claude_projects_root or _claude_projects_root()
    runs_root = e2e_runs_root or _e2e_runs_root()

    run_path = runs_root / run_id
    base_encoded = _encode_path_for_claude_projects(run_path)

    main_dir: Optional[Path] = None
    worktrees: dict[str, Path] = {}

    if projects_root.is_dir():
        for entry in sorted(projects_root.iterdir()):
            if not entry.is_dir():
                continue
            name = entry.name
            if name == base_encoded:
                main_dir = entry
                continue
            if name.startswith(base_encoded):
                tail = name[len(base_encoded):]
                # Require boundary: must start with `-` (worktree separator).
                # Otherwise this is a name-collision neighbour like `<run>x`.
                if not tail.startswith("-"):
                    continue
                # Worktree suffix is `-wt-<change>`; strip it.
                if tail.startswith("-wt-"):
                    change = tail[len("-wt-"):]
                else:
                    change = tail.lstrip("-")
                if change:
                    worktrees[change] = entry

    orch_dir: Optional[Path] = runs_root / run_id
    if not orch_dir.is_dir():
        msg = f"orchestration dir missing: {orch_dir}"
        logger.warning(msg)
        print(f"WARNING: {msg}", file=sys.stderr)
        orch_dir = None

    if main_dir is None and not worktrees:
        raise NoSessionDirsError(
            f"no Claude Code session dirs found for run {run_id!r} "
            f"(searched {projects_root} for prefix {base_encoded!r})"
        )

    return ResolvedRun(
        run_id=run_id,
        main_session_dir=main_dir,
        worktree_session_dirs=worktrees,
        orchestration_dir=orch_dir,
    )
