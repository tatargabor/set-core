"""What a project asked for, what is installed, and what an install did not do.

Three records, deliberately kept apart because they answer different questions and drift
independently:

- **the project's declaration** — which modules and versions a project *wants*. Project-owned,
  edited by the project, and the only thing an install reads to decide what to install;
- **the install record** — which modules are *installed* and at which version. Written by the
  installer, read by anyone asking what a project is running;
- **the report of one install run** — what was written, and every file that was not, with its
  reason.

The third one exists because of a rule this framework treats as load-bearing: **a silent skip
is a defect of the same class as a silent overwrite**. Both leave a project in a state nobody
chose, and the skip is the more dangerous of the two precisely because it looks like nothing
happened. An install that writes nothing therefore says so out loud rather than exiting quietly.

Runtime state — locks, run records, pending answers — is deliberately absent here. It is not an
install artifact: an install neither creates nor removes it.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

from .module_declaration import (
    ModuleDeclaration,
    VersionComparison,
    compare_versions,
)

logger = logging.getLogger(__name__)

__all__ = [
    "PROJECT_DECLARATION_REL",
    "INSTALL_RECORD_REL",
    "ProjectDeclaration",
    "InstallRecord",
    "Skip",
    "InstallReport",
    "read_project_declaration",
    "read_install_record",
    "plan_files",
    "version_report",
]

#: Project-owned: what this project asks for. Edited by the project.
PROJECT_DECLARATION_REL = "set/modules.yaml"

#: Installer-owned: what is actually installed here. Beside the deploy ledger, and separate
#: from it on purpose — the ledger is safety-critical per-file provenance, and adding an
#: unrelated section to it is how a load-bearing file grows a reason to be rewritten.
INSTALL_RECORD_REL = "set/.installed-modules.json"


@dataclass
class ProjectDeclaration:
    """What a project asked for: module ids, and the version it expects of each."""

    wants: dict[str, Optional[str]] = field(default_factory=dict)
    source: Optional[Path] = None
    #: `False` when the project has declared nothing at all. Distinct from "declared an empty
    #: set", because "not adopted" and "adopted and wants nothing" are different states and a
    #: reader must not take the first for the second.
    present: bool = False

    def asked_for(self, module: str) -> bool:
        return module in self.wants


@dataclass
class InstallRecord:
    """Which modules are installed in a project, at which version, and what was announced."""

    modules: dict[str, Optional[str]] = field(default_factory=dict)
    #: module -> the exact body the installer last wrote into that module's section. Kept so
    #: a diverged section can be recognised. Without it, "the project edited this" and "the
    #: module's own text changed" are the same observation, and the installer would have to
    #: guess — in the direction that erases a deliberate edit.
    announcements: dict[str, str] = field(default_factory=dict)
    path: Optional[Path] = None

    def as_lines(self) -> list[str]:
        """Human-readable, one module per line — the readable form requirement 1.8 asks for."""
        if not self.modules:
            return ["no modules installed"]
        return [
            f"{name} {version or '(version unknown)'}"
            for name, version in sorted(self.modules.items())
        ]

    def save(self, project_root: str | Path) -> Path:
        path = Path(project_root) / INSTALL_RECORD_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(
            json.dumps(
                {"modules": self.modules, "announcements": self.announcements},
                indent=2, sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        tmp.replace(path)
        self.path = path
        logger.info("install record written: %s (%d module(s))", path, len(self.modules))
        return path


@dataclass(frozen=True)
class Skip:
    """One file the install did not write, and why."""

    path: str
    reason: str


@dataclass
class InstallReport:
    """What one install run did. Never silent, in either direction."""

    module: str
    written: list[str] = field(default_factory=list)
    skipped: list[Skip] = field(default_factory=list)

    def skip(self, path: str, reason: str) -> None:
        self.skipped.append(Skip(path=path, reason=reason))
        logger.info("install skip [%s] %s — %s", self.module, path, reason)

    def wrote(self, path: str) -> None:
        self.written.append(path)

    @property
    def changed_nothing(self) -> bool:
        return not self.written

    def as_lines(self) -> list[str]:
        """Every skip named with its reason, and an explicit line when nothing was written."""
        lines: list[str] = []
        for p in self.written:
            lines.append(f"wrote    {p}")
        for s in self.skipped:
            lines.append(f"skipped  {s.path} — {s.reason}")
        if self.changed_nothing:
            lines.append(
                f"{self.module}: this install wrote no files "
                f"({len(self.skipped)} skipped, each named above)"
            )
        return lines


# ── reading the two records ───────────────────────────────────────────────────────────────


def read_project_declaration(project_root: str | Path) -> ProjectDeclaration:
    """What the project asked for. An absent file is reported as absent, never as empty."""
    path = Path(project_root) / PROJECT_DECLARATION_REL
    if not path.is_file():
        logger.debug("no project declaration at %s", path)
        return ProjectDeclaration(source=path, present=False)
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.warning("project declaration at %s is unreadable (%s)", path, exc)
        return ProjectDeclaration(source=path, present=False)

    raw = data.get("modules") if isinstance(data, Mapping) else None
    wants: dict[str, Optional[str]] = {}
    if isinstance(raw, Mapping):
        for name, spec in raw.items():
            if isinstance(spec, Mapping):
                v = spec.get("version")
                wants[str(name)] = str(v) if v is not None else None
            elif spec is None:
                wants[str(name)] = None
            else:
                wants[str(name)] = str(spec)
    elif isinstance(raw, Sequence) and not isinstance(raw, str):
        for name in raw:
            wants[str(name)] = None
    return ProjectDeclaration(wants=wants, source=path, present=True)


def read_install_record(project_root: str | Path) -> InstallRecord:
    """Which modules are installed. A missing record means nothing is recorded as installed."""
    path = Path(project_root) / INSTALL_RECORD_REL
    if not path.is_file():
        return InstallRecord(path=path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("install record at %s is unreadable (%s) — treating as empty", path, exc)
        return InstallRecord(path=path)
    raw = data.get("modules") if isinstance(data, Mapping) else None
    modules: dict[str, Optional[str]] = {}
    if isinstance(raw, Mapping):
        for name, v in raw.items():
            modules[str(name)] = str(v) if v is not None else None
    raw_ann = data.get("announcements") if isinstance(data, Mapping) else None
    announcements: dict[str, str] = {}
    if isinstance(raw_ann, Mapping):
        for name, v in raw_ann.items():
            announcements[str(name)] = str(v)
    return InstallRecord(modules=modules, announcements=announcements, path=path)


# ── what an install may touch ─────────────────────────────────────────────────────────────


def plan_files(decl: ModuleDeclaration) -> list[str]:
    """The paths this module places in a project — its executable part excluded.

    The exclusion is the mechanism behind "the executable part is not copied", not a comment
    asking for it: a path declared as executable never reaches the copier, whatever else the
    manifest says about it.
    """
    executable = set(decl.executable)
    planned = [f.path for f in decl.files if f.path and f.path not in executable]
    dropped = [f.path for f in decl.files if f.path in executable]
    if dropped:
        logger.warning(
            "plan_files(%s): %s declared both as executable and as installed files — "
            "not copied into the project", decl.name, dropped,
        )
    return planned


def version_report(
    project: ProjectDeclaration, installed: Mapping[str, Optional[str]],
    modules: Optional[Iterable[str]] = None,
) -> list[VersionComparison]:
    """Compare what the project expects against what is installed machine-wide.

    A module the project asked for but which is not installed compares as **unknown**, and so
    does a module whose version cannot be read on either side. Unknown is never reported as a
    match: the whole reason to ask is the case where they differ, and rendering "cannot tell"
    as "fine" removes exactly that answer.
    """
    names = list(modules) if modules is not None else sorted(
        set(project.wants) | set(installed)
    )
    return [
        compare_versions(n, project.wants.get(n), installed.get(n)) for n in names
    ]


def perform_announcement(
    decl: "ModuleDeclaration", target_dir: str | Path, *, dry_run: bool = False,
) -> tuple[list[str], Optional[str]]:
    """Announce `decl` in the project, returning (messages, body-that-was-written).

    Returns `(…, None)` when nothing was written — an unchanged section, a section the
    project edited, or no instruction file at all. Each of those is *reported*, never
    silent: an announcement that did not happen is exactly the kind of thing a project
    discovers months later, when an agent working there has never heard of the module.
    """
    from .module_announce import announce_module  # local: keeps the import graph shallow

    if decl.announce is None:
        return [], None

    root = Path(target_dir)
    path = root / decl.announce.file
    if dry_run:
        return [f"  Would announce {decl.name} in {decl.announce.file}"], None

    record = read_install_record(root)
    result = announce_module(
        path, decl.name, decl.announce.body,
        last_written=record.announcements.get(decl.name),
    )
    if result.outcome == "written":
        return [f"  Announced {decl.name} in {decl.announce.file}"], decl.announce.body
    if result.outcome == "unchanged":
        return [f"  Announcement for {decl.name} already current"], decl.announce.body
    return [f"  Not announced ({decl.name}): {result.detail}"], None
