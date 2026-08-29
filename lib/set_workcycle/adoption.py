"""What a project declares in order to be driven, and what happens when it declares nothing.

Adoption is a **declaration**, not framework code. Nothing here names a project, a path
convention or a tool: everything that varies between projects arrives either through the
project's own declaration or through its resolved profile. That is what makes "a second
project needs no framework change" a fact rather than an aspiration.

**Absence is reported, never guessed.** A project that has declared nothing is not a project
with nothing to do, and the engine must not let a reader take the first for the second. The
same rule covers gates: a project declaring no gate steps runs with none and is told so —
the engine does not infer a command from the project's contents, because a guessed gate that
happens to pass reads exactly like a real one.

**Adoption does not require the project to change how it works.** No task file is
restructured, no artifact renamed, no annotation introduced. A file carrying no dependency
annotations is driven under the serial default, which is what the fail-closed rule in
`groups` exists for.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

__all__ = ["ADOPTION_REL", "Adoption", "ResolvedReading", "read_adoption",
           "resolve_reading_paths"]

#: Project-owned, and the only place the engine learns where a project keeps its changes.
ADOPTION_REL = "set/work-cycle.yaml"


@dataclass
class Adoption:
    """A project's declaration, or the recorded fact that it has none."""

    adopted: bool
    changes_dir: str = ""
    gates: tuple[str, ...] = ()
    #: `True` when the project declared the key at all — distinct from declaring it empty.
    gates_declared: bool = False
    #: Extra places a unit should read, as the PROJECT named them — relative to
    #: its own tree. The engine names none of its own; without a declaration a
    #: unit reads exactly what it read before this existed.
    reading_paths: tuple[str, ...] = ()
    #: `True` when the project declared the key at all — distinct from declaring
    #: it empty, and distinct again from declaring paths that are all missing.
    reading_paths_declared: bool = False
    missing: str = ""
    source: Optional[Path] = None
    extras: dict = field(default_factory=dict)

    def describe(self) -> str:
        if not self.adopted:
            return f"not adopted: {self.missing}"
        if not self.gates_declared:
            # ⚠ This sentence used to say "so no gate runs — none is inferred from the
            # project's contents". That became false the moment a declared gate started
            # winning over a detected one: with no `gates:` key at all, resolution falls
            # through to the project's PROFILE, whose detectors read the project's
            # contents. The engine still names no command of its own, which is the claim
            # worth making — but the old one told a reader no gate would run, and one
            # does. A false value on a surface is worse than a missing one.
            return (f"adopted (changes in {self.changes_dir}); no gate steps declared, so the "
                    f"gate is resolved from the project's profile — the engine names no "
                    f"command of its own")
        return f"adopted (changes in {self.changes_dir}); gates: {', '.join(self.gates) or 'none'}"


def read_adoption(tree: str | Path, *, changes_dir_override: str = "") -> Adoption:
    """Read a project's declaration.

    `changes_dir_override` is a caller *stating* where changes live, which is not a guess and
    is therefore allowed to adopt a project on its own. What is refused is the engine deciding
    for itself.
    """
    root = Path(tree)
    path = root / ADOPTION_REL

    if changes_dir_override:
        return Adoption(adopted=True, changes_dir=changes_dir_override, source=None,
                        gates=(), gates_declared=False)

    if not path.is_file():
        logger.info("no adoption declaration at %s — the project is not adopted", path)
        return Adoption(
            adopted=False, source=path,
            missing=(f"{ADOPTION_REL} — a project is adopted by declaring at least where its "
                     f"changes live; the engine does not guess a location"),
        )

    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.warning("adoption declaration at %s is unreadable (%s)", path, exc)
        return Adoption(adopted=False, source=path,
                        missing=f"{ADOPTION_REL} could not be read: {exc}")

    if not isinstance(data, dict):
        return Adoption(adopted=False, source=path,
                        missing=f"{ADOPTION_REL} is not a mapping")

    changes_dir = str(data.get("changes_dir") or "").strip()
    if not changes_dir:
        return Adoption(
            adopted=False, source=path,
            missing=(f"`changes_dir` in {ADOPTION_REL} — the engine does not guess where a "
                     f"project keeps its changes"),
        )

    raw_gates = data.get("gates")
    gates_declared = "gates" in data
    gates = tuple(str(g) for g in (raw_gates or []) if str(g).strip())

    raw_reading = data.get("reading_paths")
    reading_declared = "reading_paths" in data
    reading = tuple(str(r).strip() for r in (raw_reading or []) if str(r).strip())

    adoption = Adoption(
        adopted=True, changes_dir=changes_dir, gates=gates,
        gates_declared=gates_declared, source=path,
        reading_paths=reading, reading_paths_declared=reading_declared,
        extras={k: v for k, v in data.items()
                if k not in {"changes_dir", "gates", "reading_paths"}},
    )
    logger.info("adoption read from %s: %s", path, adoption.describe())
    return adoption


@dataclass
class ResolvedReading:
    """Which declared reading paths exist, which do not, and which were refused.

    Three lists rather than one filtered list, because a path that vanished and a
    path that was never declared must not look alike downstream — a filter that
    quietly drops its input is indistinguishable from a source that returned
    nothing.
    """

    present: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    refused: tuple[str, ...] = ()
    declared: bool = False

    @property
    def reached_nothing(self) -> bool:
        """Declared paths, none of which resolved. NOT the same as declaring none."""
        return self.declared and not self.present

    def as_lines(self) -> list:
        out = []
        for p in self.missing:
            out.append(f"declared reading path does not exist: {p}")
        for p in self.refused:
            out.append(f"declared reading path refused — outside the project tree: {p}")
        if self.reached_nothing:
            out.append("the reading declaration reached nothing — every declared path is "
                       "missing or refused")
        return out


def resolve_reading_paths(tree, adoption: Adoption) -> ResolvedReading:
    """Resolve a project's declared reading paths against its own tree.

    A path that escapes the tree is REFUSED and named. The check is on the
    resolved location, so a traversal and a symlink pointing outward are caught
    by the same rule — the two are different escapes and a check on the written
    string only catches the first.
    """
    root = Path(tree).resolve()
    present, missing, refused = [], [], []
    for raw in adoption.reading_paths:
        candidate = (root / raw)
        try:
            resolved = candidate.resolve()
        except OSError:
            missing.append(raw)
            continue
        if not resolved.is_relative_to(root):
            logger.warning("reading path %s resolves outside %s — refused", raw, root)
            refused.append(raw)
            continue
        (present if resolved.exists() else missing).append(raw)
    return ResolvedReading(
        present=tuple(present), missing=tuple(missing), refused=tuple(refused),
        declared=adoption.reading_paths_declared,
    )
