"""How a module declares itself, and what an installer refuses.

A **module** is a capability that reaches a project. It splits in two, and the split follows
ownership rather than file type:

- an **executable part**, installed once per machine and run from there — never copied into a
  project, because a copy is a version nobody can report on;
- a **project-owned part**, placed in the project — its declaration of which modules and
  versions it wants, its configuration, and files an agent reads from the project itself.

Everything here is about the *declaration*: what a module says about itself, and which of
those statements an installer must refuse rather than guess at. The copying itself belongs to
the deploy engines, and the per-file decision to `set_orch.deploy_ledger`, which already
decides from a recorded hash.

**The governing rule is that a declared guard which does not take effect is worse than no
guard.** It has already happened here: two templates named their protected paths in a
top-level list that nothing read, so the manifest promised a protection the installer did not
apply and a forced re-init overwrote the file anyway. A promise that reads as a measure is the
expensive failure, so validation refuses a guard the installer does not implement instead of
ignoring it.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

logger = logging.getLogger(__name__)

__all__ = [
    "KNOWN_GUARDS",
    "Announcement",
    "FileDeclaration",
    "ModuleDeclaration",
    "DeclarationError",
    "VersionComparison",
    "StampComparison",
    "load_declaration",
    "validate_declaration",
    "check_requirements",
    "compare_versions",
    "compare_generator_stamps",
    "read_generator_stamp",
]

#: The guards the installer actually implements. A declaration naming anything else is
#: refused — see `validate_declaration`. `replace` is the explicit way to say "no guard":
#: without it, "overwrite me freely" and "nobody stated a treatment" would be the same text,
#: and the refusal in `E_NO_TREATMENT` could not exist.
KNOWN_GUARDS: frozenset[str] = frozenset({"protected", "merge", "once", "replace"})

#: Guards that cannot both be in force on one file. `replace` says "no guard"; anything
#: alongside it is a contradiction rather than a refinement.
_CONTRADICTORY = (("replace", "protected"), ("replace", "merge"), ("replace", "once"))

# Error codes, named so a report can be grouped without matching on prose.
E_NO_TREATMENT = "no-treatment-stated"
E_UNKNOWN_GUARD = "unknown-guard"
E_CONTRADICTORY_GUARDS = "contradictory-guards"
E_GUARD_INAPPLICABLE = "guard-cannot-be-applied"
E_NO_VERSION = "no-version-declared"
E_NO_PATH = "file-entry-without-a-path"
E_MISSING_REQUIREMENT = "required-module-absent"


@dataclass(frozen=True)
class DeclarationError:
    """One reason an install must not proceed. `path` is empty for module-level errors."""

    code: str
    message: str
    path: str = ""

    def __str__(self) -> str:  # pragma: no cover - formatting only
        where = f" [{self.path}]" if self.path else ""
        return f"{self.code}{where}: {self.message}"


@dataclass(frozen=True)
class FileDeclaration:
    """One declared file and the treatment later installs must give it."""

    path: str
    guards: frozenset[str] = frozenset()
    #: Guard names the declaration used that are not in `KNOWN_GUARDS`. Kept rather than
    #: dropped, so validation can name them; dropping them is how a guard goes silently
    #: missing.
    unknown_guards: frozenset[str] = frozenset()

    @property
    def states_a_treatment(self) -> bool:
        return bool(self.guards) or bool(self.unknown_guards)


@dataclass(frozen=True)
class Announcement:
    """What a module wants an agent working in the project to know about it."""

    body: str
    file: str = "CLAUDE.md"


@dataclass
class ModuleDeclaration:
    """What a module says about itself: its files, its requirements, its version."""

    name: str
    version: Optional[str] = None
    files: list[FileDeclaration] = field(default_factory=list)
    requires: tuple[str, ...] = ()
    #: Paths the module ships as its executable part. These are installed once per machine
    #: and MUST NOT appear among `files` — an installer that copies them into a project has
    #: created a second copy whose version nothing can report.
    executable: tuple[str, ...] = ()
    #: Set when the module must be announced in the project's agent instruction file.
    announce: Optional["Announcement"] = None
    source: Optional[Path] = None

    def file_paths(self) -> list[str]:
        return [f.path for f in self.files]


# ── loading ───────────────────────────────────────────────────────────────────────────────


def load_declaration(
    manifest: Mapping[str, Any],
    *,
    name: str,
    source: Optional[Path] = None,
    modules: Optional[Sequence[str]] = None,
) -> ModuleDeclaration:
    """Read a manifest mapping into a declaration.

    Both manifest spellings are honoured, because both are already in use and neither is
    wrong: a per-entry flag (`protected: true`) and a top-level list of protected paths. A
    path named in the top-level list therefore *states a treatment* even when its entry is a
    bare string — the alternative would refuse two templates that are protecting their files
    correctly, just tersely.

    `modules` selects optional module sections; omitting it takes only `core`, which is what
    "install only the modules a project asked for" means at the declaration level.
    """
    declared_protected = {
        str(p) for p in (manifest.get("protected") or []) if isinstance(p, (str, int))
    }

    raw_entries: list[Any] = list(manifest.get("core") or [])
    available = manifest.get("modules") or {}
    for mid in (modules or ()):
        section = available.get(mid) or {}
        raw_entries.extend(section.get("files") or [])

    files: list[FileDeclaration] = []
    for raw in raw_entries:
        files.append(_parse_entry(raw, declared_protected))

    raw_announce = manifest.get("announce")
    announce: Optional[Announcement] = None
    if isinstance(raw_announce, Mapping) and _str_or_none(raw_announce.get("body")):
        announce = Announcement(
            body=str(raw_announce["body"]),
            file=str(raw_announce.get("file") or "CLAUDE.md"),
        )
    elif _str_or_none(raw_announce) if isinstance(raw_announce, str) else None:
        announce = Announcement(body=str(raw_announce))

    decl = ModuleDeclaration(
        name=name,
        version=_str_or_none(manifest.get("version")),
        announce=announce,
        files=files,
        requires=tuple(str(r) for r in (manifest.get("requires") or [])),
        executable=tuple(str(e) for e in (manifest.get("executable") or [])),
        source=source,
    )
    logger.debug(
        "load_declaration(%s): version=%r files=%d requires=%s executable=%d",
        name, decl.version, len(decl.files), decl.requires, len(decl.executable),
    )
    return decl


def _parse_entry(raw: Any, declared_protected: set[str]) -> FileDeclaration:
    if isinstance(raw, str):
        path = raw
        stated: set[str] = set()
        unknown: set[str] = set()
    elif isinstance(raw, Mapping):
        path = str(raw.get("path", ""))
        stated = {k for k in raw.keys() if k != "path" and raw.get(k)}
        unknown = {k for k in stated if k not in KNOWN_GUARDS}
        stated = stated - unknown
    else:
        path, stated, unknown = str(raw), set(), set()

    if path in declared_protected:
        stated = stated | {"protected"}
    return FileDeclaration(
        path=path, guards=frozenset(stated), unknown_guards=frozenset(unknown),
    )


def _str_or_none(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


# ── validation ────────────────────────────────────────────────────────────────────────────


def validate_declaration(
    decl: ModuleDeclaration,
    *,
    implemented_guards: Iterable[str] = KNOWN_GUARDS,
    template_dir: Optional[Path] = None,
) -> list[DeclarationError]:
    """Every reason this declaration must not be installed. Empty means it validates.

    Four refusals, all of them the kind that would otherwise be a default:

    - a file entry stating **no treatment** — because "overwrite" and "nobody decided" would
      otherwise be the same text, and the installer would pick the destructive reading;
    - a **guard the installer does not implement** — the measured defect this file's docstring
      opens with;
    - **contradictory guards**, where `replace` sits beside a guard;
    - a **guard that cannot be applied** to the file it names, checked only when the template
      directory is supplied: `merge` on a file that is not there to merge into is a guard that
      will not take effect, which is the same class as an unimplemented one.
    """
    implemented = frozenset(implemented_guards)
    errors: list[DeclarationError] = []

    if not decl.version:
        errors.append(DeclarationError(
            E_NO_VERSION,
            f"module {decl.name!r} declares no version; a version that cannot be read is "
            f"reported as unknown, never as matching",
        ))

    for f in decl.files:
        if not f.path:
            errors.append(DeclarationError(
                E_NO_PATH, f"module {decl.name!r} has a file entry with no path"))
            continue

        unknown = set(f.unknown_guards) | (set(f.guards) - implemented)
        if unknown:
            errors.append(DeclarationError(
                E_UNKNOWN_GUARD,
                f"declares guard(s) {sorted(unknown)} that the installer does not implement; "
                f"implemented: {sorted(implemented)}",
                path=f.path,
            ))

        if not f.states_a_treatment:
            errors.append(DeclarationError(
                E_NO_TREATMENT,
                "states no treatment for later installs; state one of "
                f"{sorted(KNOWN_GUARDS)} (use `replace: true` to mean 'no guard')",
                path=f.path,
            ))

        for a, b in _CONTRADICTORY:
            if a in f.guards and b in f.guards:
                errors.append(DeclarationError(
                    E_CONTRADICTORY_GUARDS,
                    f"declares {a!r} and {b!r} together; {a!r} means 'no guard'",
                    path=f.path,
                ))

        if template_dir is not None and "merge" in f.guards:
            src = Path(template_dir) / f.path
            if not src.is_file():
                errors.append(DeclarationError(
                    E_GUARD_INAPPLICABLE,
                    "declares `merge` but the module ships no such file, so the guard cannot "
                    "take effect",
                    path=f.path,
                ))

    for e in decl.executable:
        if e in decl.file_paths():
            errors.append(DeclarationError(
                E_GUARD_INAPPLICABLE,
                "is declared as the module's executable part AND as an installed file; the "
                "executable part is run from the machine-wide installation, never copied",
                path=e,
            ))

    if errors:
        logger.error(
            "validate_declaration(%s): %d error(s) — install refused: %s",
            decl.name, len(errors), [e.code for e in errors],
        )
    return errors


def check_requirements(
    decl: ModuleDeclaration, installed: Iterable[str],
) -> list[DeclarationError]:
    """A declared requirement is mandatory. Absent → refuse, naming what is missing."""
    have = set(installed)
    missing = [r for r in decl.requires if r not in have]
    if missing:
        logger.error(
            "check_requirements(%s): missing %s (installed: %s)",
            decl.name, missing, sorted(have),
        )
    return [
        DeclarationError(
            E_MISSING_REQUIREMENT,
            f"module {decl.name!r} requires {r!r}, which this project does not have",
        )
        for r in missing
    ]


# ── versions ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class VersionComparison:
    """The result of comparing what a project expects with what is installed."""

    module: str
    expected: Optional[str]
    installed: Optional[str]

    @property
    def state(self) -> str:
        """`"match"`, `"mismatch"` or `"unknown"`.

        A version that cannot be read is **unknown**, never a match. The direction matters:
        reporting "unknown" as "matching" hides exactly the case someone is looking for.
        """
        if self.expected is None or self.installed is None:
            return "unknown"
        return "match" if self.expected == self.installed else "mismatch"

    def describe(self) -> str:
        if self.state == "unknown":
            missing = []
            if self.expected is None:
                missing.append("the project's expectation")
            if self.installed is None:
                missing.append("the machine-wide installation")
            return (
                f"{self.module}: version unknown — could not read {' and '.join(missing)}"
            )
        if self.state == "mismatch":
            return (
                f"{self.module}: the project expects {self.expected}, "
                f"{self.installed} is installed machine-wide"
            )
        return f"{self.module}: {self.installed}"


def compare_versions(
    module: str, expected: Optional[str], installed: Optional[str],
) -> VersionComparison:
    cmp = VersionComparison(module=module, expected=expected, installed=installed)
    if cmp.state != "match":
        logger.warning("compare_versions: %s", cmp.describe())
    return cmp


# ── generator stamps ──────────────────────────────────────────────────────────────────────

#: `generatedBy: "1.9.0"` — quoted or bare, at the start of a line, in a file's leading
#: front matter. Anchored at line start on purpose: a stamp *quoted inside prose* is a
#: mention, not a stamp, and this repository has paid for the opposite reading.
_STAMP = re.compile(r"^\s*generatedBy\s*:\s*[\"']?([^\"'\s#]+)", re.MULTILINE)

#: How far into a file a stamp is looked for. A stamp is front matter; a match deeper in the
#: body is prose about a stamp.
_STAMP_SCAN_BYTES = 4096


@dataclass(frozen=True)
class StampComparison:
    """Whether an incoming generated artifact may replace what is at the destination."""

    path: str
    destination: Optional[str]
    incoming: Optional[str]
    verdict: str  # "replace" | "refuse" | "unknown"
    reason: str


def read_generator_stamp(path: str | Path) -> Optional[str]:
    """The generator version a file was produced by, or `None` if it carries none."""
    try:
        head = Path(path).read_text(encoding="utf-8", errors="replace")[:_STAMP_SCAN_BYTES]
    except OSError:
        return None
    m = _STAMP.search(head)
    return m.group(1) if m else None


def _version_tuple(v: str) -> tuple:
    return tuple(int(p) if p.isdigit() else p for p in re.split(r"[.\-+]", v))


def compare_generator_stamps(
    path: str, destination_stamp: Optional[str], incoming_stamp: Optional[str],
) -> StampComparison:
    """Refuse to replace a newer generated artifact with an older generator's output.

    A missing stamp on **either** side is `unknown`, and unknown leaves the destination
    alone. That is the conservative direction and it is the point: an unstamped destination
    might be newer, and an install that guesses "probably fine" is how a project loses a
    regenerated artifact to a stale template.
    """
    if destination_stamp is None or incoming_stamp is None:
        which = "destination" if destination_stamp is None else "incoming file"
        return StampComparison(
            path, destination_stamp, incoming_stamp, "unknown",
            f"no generator stamp on the {which}; the destination is left alone",
        )
    if destination_stamp == incoming_stamp:
        return StampComparison(
            path, destination_stamp, incoming_stamp, "replace",
            "same generator version on both sides",
        )
    try:
        newer_at_destination = _version_tuple(destination_stamp) > _version_tuple(incoming_stamp)
    except TypeError:
        return StampComparison(
            path, destination_stamp, incoming_stamp, "unknown",
            f"cannot order {destination_stamp!r} against {incoming_stamp!r}; "
            "the destination is left alone",
        )
    if newer_at_destination:
        logger.warning(
            "compare_generator_stamps(%s): refusing to replace %s with older %s",
            path, destination_stamp, incoming_stamp,
        )
        return StampComparison(
            path, destination_stamp, incoming_stamp, "refuse",
            f"the destination was generated by {destination_stamp}, the incoming file by "
            f"{incoming_stamp} — replacing it would be a downgrade",
        )
    return StampComparison(
        path, destination_stamp, incoming_stamp, "replace",
        f"incoming {incoming_stamp} is newer than {destination_stamp}",
    )
