"""Announcing an installed module inside a file the installer does not own.

A module often needs the agent working in a project to know it exists, and the place an agent
looks is the project's own instruction file. That file is **hand-authored**: the installer
writes into a delimited section it owns and must not touch a byte outside it.

Three refusals, and each is a measured failure mode rather than a precaution:

- **The section was edited by the project.** Restoring the installer's own version would erase
  a deliberate edit, and it would do so silently — the file still looks announced. So a
  diverged section is left alone and reported.
- **There is no instruction file.** Creating one as a side effect of installing gives the
  project a file it never asked for, in a location the installer guessed. The honest outcome
  is to say the announcement had nowhere to go.
- **Withdrawing removes the section, not the file.** The rest of the file was never ours.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

__all__ = [
    "AnnouncementResult",
    "section_markers",
    "announce_module",
    "withdraw_announcement",
    "read_section",
]

_BEGIN = "<!-- set-module:{name}:begin -->"
_END = "<!-- set-module:{name}:end -->"


def section_markers(module: str) -> tuple[str, str]:
    """The delimiters this installer owns for `module`."""
    return _BEGIN.format(name=module), _END.format(name=module)


def _section_re(module: str) -> re.Pattern:
    begin, end = (re.escape(m) for m in section_markers(module))
    # Non-greedy, and the markers must each be alone on their line: a marker quoted inside
    # prose is a mention, not a delimiter.
    return re.compile(rf"(?m)^{begin}[ \t]*\n(?P<body>.*?)^{end}[ \t]*$\n?", re.DOTALL)


@dataclass(frozen=True)
class AnnouncementResult:
    """What an announcement attempt did, and — when it did nothing — why."""

    outcome: str  # "written" | "unchanged" | "left-alone" | "no-instruction-file" | "absent"
    module: str
    path: Optional[Path] = None
    detail: str = ""

    @property
    def wrote(self) -> bool:
        return self.outcome == "written"


def read_section(text: str, module: str) -> Optional[str]:
    """The current body of `module`'s section, or `None` when there is no section."""
    m = _section_re(module).search(text)
    return m.group("body") if m else None


def announce_module(
    instruction_file: str | Path,
    module: str,
    body: str,
    *,
    last_written: Optional[str] = None,
) -> AnnouncementResult:
    """Write `body` into `module`'s delimited section, touching nothing outside it.

    `last_written` is what the installer put there on the previous install. When the section's
    current content differs from it, the project has edited inside the section: the installer
    leaves it alone and reports the divergence. Passing `None` means "no record of a previous
    write", which is treated the same way — an unrecorded section is not ours to overwrite.
    """
    path = Path(instruction_file)
    if not path.is_file():
        logger.warning(
            "announce_module(%s): no instruction file at %s — the module could not be "
            "announced; the installer does NOT create one", module, path,
        )
        return AnnouncementResult(
            "no-instruction-file", module, path,
            f"no instruction file at {path}; nothing was created",
        )

    original = path.read_text(encoding="utf-8")
    begin, end = section_markers(module)
    block = f"{begin}\n{body.rstrip()}\n{end}\n"
    pattern = _section_re(module)
    existing = pattern.search(original)

    if existing is None:
        updated = original
        if updated and not updated.endswith("\n"):
            updated += "\n"
        updated += ("\n" if updated and not updated.endswith("\n\n") else "") + block
        _write(path, updated)
        logger.info("announce_module(%s): section created in %s", module, path)
        return AnnouncementResult("written", module, path, "section created")

    current_body = existing.group("body")
    if last_written is not None and current_body.strip() == body.strip():
        return AnnouncementResult("unchanged", module, path, "section already current")

    if last_written is None or current_body.strip() != last_written.strip():
        logger.warning(
            "announce_module(%s): the section in %s differs from what was last written — "
            "leaving it alone", module, path,
        )
        return AnnouncementResult(
            "left-alone", module, path,
            "the section was edited in the project; it was not restored",
        )

    updated = original[:existing.start()] + block + original[existing.end():]
    _write(path, updated)
    logger.info("announce_module(%s): section updated in %s", module, path)
    return AnnouncementResult("written", module, path, "section updated")


def withdraw_announcement(instruction_file: str | Path, module: str) -> AnnouncementResult:
    """Remove only `module`'s section. Every other byte of the file is left as it was."""
    path = Path(instruction_file)
    if not path.is_file():
        return AnnouncementResult("no-instruction-file", module, path, f"no file at {path}")
    original = path.read_text(encoding="utf-8")
    updated, n = _section_re(module).subn("", original)
    if n == 0:
        return AnnouncementResult("absent", module, path, "no section to withdraw")
    _write(path, updated)
    logger.info("withdraw_announcement(%s): section removed from %s", module, path)
    return AnnouncementResult("written", module, path, "section removed")


def _write(path: Path, text: str) -> None:
    """Write via a temporary file and replace.

    Never `open(p, "w")` in the same expression that reads `p` — the write truncates first
    and the read then sees an empty file. Measured elsewhere on a 290 KB log that became
    0 bytes with no exception and no non-zero exit.
    """
    tmp = path.with_name(path.name + ".set-tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
