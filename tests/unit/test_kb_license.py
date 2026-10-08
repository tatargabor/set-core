"""Licence provenance (AC-29): the notice travels; the attribution is honest.

PORTED vs NEW is the load-bearing distinction: a module whose logic was ported
from the MIT upstream carries the attribution line as its FIRST line; a module
written new does NOT — a line on a new module would make the attribution
meaningless, and a missing line on a ported one would breach the licence.
"""

from __future__ import annotations

from pathlib import Path

PKG = Path(__file__).resolve().parents[2] / "lib" / "set_kb"

# Modules whose logic is ported from the upstream engine (directly or via the
# intermediate TypeScript port). search.py carries the ranking logic ported
# from the upstream store's search; glob.py was extracted from the ported
# indexer upstream-side and keeps its attribution.
PORTED = ["types.py", "store.py", "search.py", "chunker.py", "frontmatter.py", "lang.py", "glob.py", "indexer.py"]

# Fork-original modules (written for the fork this package descends from, or
# for set-core): they must NOT carry the line.
NEW = ["channels.py", "lang_hu.py", "get_section.py", "runtime.py", "__init__.py"]

LINE_MARK = "Ported from an MIT-licensed upstream"


def test_license_upstream_carries_full_mit_text_and_commit():
    notice = (PKG / "LICENSE-UPSTREAM").read_text(encoding="utf-8")
    assert "MIT License" in notice
    assert "Copyright (c) 2026 Robert Csakany" in notice, "the copyright line the licence requires"
    assert (
        "Permission is hereby granted, free of charge" in notice
        and "THE SOFTWARE IS PROVIDED" in notice
    ), "the permission notice travels WITH the copyright line — the licence requires both"
    assert "02bd182e7747a045277e89861ef51d57ada60f3e" in notice, "the upstream commit identifies the source tree"
    assert "lineage" in notice.lower(), "the port lineage is stated"


def test_ported_modules_carry_attribution_as_first_line():
    for name in PORTED:
        first = (PKG / name).read_text(encoding="utf-8").splitlines()[0]
        assert first.startswith(f"# {LINE_MARK}"), f"{name}: first line must carry the attribution"
        assert "LICENSE-UPSTREAM" in first, f"{name}: the attribution must point at the notice file"


def test_new_modules_do_not_carry_attribution():
    for name in NEW:
        head = "\n".join((PKG / name).read_text(encoding="utf-8").splitlines()[:5])
        assert LINE_MARK not in head, f"{name} is new — an attribution line here would be a false claim"


def test_no_upstream_repository_or_organisation_named_in_the_package():
    """The user's decision (design, 2026-10-07): the public tree credits the
    upstream with the MIT copyright line only."""
    banned = ["pi-agent-dashboard", "BlackBeltTechnology", "github.com/BlackBelt"]
    for f in PKG.iterdir():
        if not f.is_file() or f.suffix not in (".py", ".md", ""):
            continue
        text = f.read_text(encoding="utf-8")
        for b in banned:
            assert b not in text, f"{f.name} names the upstream beyond the copyright line"
