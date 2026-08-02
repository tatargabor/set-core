"""The gate in front of following a file a project pointed at.

A status answer may name a field whose value is a path to a file the project is writing
(`project_status._follow_fields`). Following it means set-core opens a file whose name came from
outside the framework, so this module decides — before anything is opened — whether that path may
be followed at all.

**Two checks, and the second one is the one that is easy to skip.**

1. The path must be, right now, the value of a follow-declared field in the project's own answer.
   Not "a path the answer named once", not "a path under the project root": the live answer. The
   cheaper rule — anything inside the tree — turns a status endpoint into a general file reader
   for the whole repository, and leaves the only check that would have stopped it in the hands of
   whoever calls it. The guard belongs where the effect is.

2. The RESOLVED path must still be inside the project root. A symlink is exactly how "inside the
   tree" stops being true while the string still looks correct, so a check on the string is
   reassuring and wrong. Both sides of the comparison are resolved, because `a/../a/b` and `a/b`
   are the same file and must not be a way to slip past check 1.

Nothing here opens a file for writing, and nothing here keeps what it reads.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .project_status import (
    StatusConfig,
    follow_targets,
    is_valid_command_name,
    query,
    resolve_status_config,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FollowDecision:
    """Whether a path may be followed, and — when it may not — why, in a word a caller can act on.

    **Every field, by name:** `ok`, `path`, `field`, `error`, `error_class`.

    `path` is the RESOLVED absolute path and is set only when `ok` is true; a caller that reaches
    for it on a refusal gets `None` rather than a plausible-looking location.
    """

    ok: bool
    path: Optional[Path] = None
    field: Optional[str] = None
    error: Optional[str] = None
    error_class: Optional[str] = None

    @classmethod
    def refuse(cls, error_class: str, error: str) -> "FollowDecision":
        return cls(ok=False, error=error, error_class=error_class)


#: The failure names this module can produce. Documented here because the contract requires
#: set-core to name its own failures rather than hand a caller an exception to interpret.
#:
#: - `bad-command`      — the command name is not shaped like one; it never reaches a process.
#: - `not-configured`   — the project publishes no status contract at all.
#: - `command-failed`   — the project could not answer, so nothing can be verified against it.
#: - `no-declaration`   — the answer declares no followable field (or none is present in it).
#: - `not-followable`   — the requested path is not the value of any declared field right now.
#: - `outside-project`  — the resolved path leaves the project tree.
#: - `unreadable`       — the path resolves inside the tree but cannot be opened for reading.
ERROR_CLASSES = (
    "bad-command", "not-configured", "command-failed",
    "no-declaration", "not-followable", "outside-project", "unreadable",
)


def _resolved_under(root: Path, candidate: str) -> Optional[Path]:
    """Resolve `candidate` against `root` and return it only if it stays inside.

    `strict=False` on purpose: a file may be created a moment after the answer named it, and
    refusing a not-yet-existing path would make the decision depend on timing rather than on
    location. Existence is the reader's problem; containment is this function's.
    """
    try:
        resolved = (root / candidate).resolve(strict=False)
        root_resolved = root.resolve(strict=False)
    except OSError:
        return None
    if resolved == root_resolved:
        return None
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        return None
    return resolved


def decide(
    project_path: str | Path,
    command: str,
    requested_path: str,
    config: Optional[StatusConfig] = None,
) -> FollowDecision:
    """May this path be followed, according to the project's own current answer?

    Every refusal carries an `error_class` from `ERROR_CLASSES`; no exception escapes, because a
    surface asking to follow something must render the refusal rather than fall over.
    """
    root = Path(project_path)

    if not is_valid_command_name(command):
        return FollowDecision.refuse(
            "bad-command", f"not a contract command name: {command!r}")

    if not isinstance(requested_path, str) or not requested_path.strip():
        return FollowDecision.refuse(
            "not-followable", "no path was requested")

    cfg = config or resolve_status_config(root)
    if cfg is None:
        return FollowDecision.refuse(
            "not-configured", "this project publishes no status contract")

    answer = query(root, command, config=cfg)
    if not answer.ok:
        # The project's own failure, reported as such — never turned into a permissive default.
        return FollowDecision.refuse(
            "command-failed",
            f"the project could not answer '{command}' ({answer.error_class}), so nothing "
            f"can be verified against it",
        )

    targets = follow_targets(answer.data, answer.follow)
    if not targets:
        return FollowDecision.refuse(
            "no-declaration",
            f"'{command}' declares no followable field carrying a path right now",
        )

    wanted = _resolved_under(root, requested_path)
    if wanted is None:
        return FollowDecision.refuse(
            "outside-project",
            "the requested path leaves the project tree once resolved",
        )

    for field_name, declared in targets.items():
        declared_resolved = _resolved_under(root, declared)
        if declared_resolved is not None and declared_resolved == wanted:
            logger.info(
                "status follow: '%s' accepted via declared field '%s'", command, field_name)
            return FollowDecision(ok=True, path=wanted, field=field_name)

    # Shape, never content: the path itself is the project's material.
    logger.info(
        "status follow: '%s' refused — %d declared target(s), none matching", command, len(targets))
    return FollowDecision.refuse(
        "not-followable",
        "the requested path is not what any followable field holds in the current answer",
    )
