"""Licence provenance (AC-29): the notice travels; the attribution is honest.

PORTED vs NEW is the load-bearing distinction: a module whose logic was ported
from the MIT upstream carries the attribution line as its FIRST line; a module
written new does NOT — a line on a new module would make the attribution
meaningless, and a missing line on a ported one would breach the licence.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

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


def _package_text_files():
    for f in PKG.iterdir():
        if f.is_file() and f.suffix in (".py", ".md", ""):
            yield f, f.read_text(encoding="utf-8")


def test_no_upstream_repository_or_organisation_named_in_the_package():
    """The user's decision (design, 2026-10-07): the public tree credits the
    upstream with the MIT copyright line only.

    The upstream's repository and organisation names are NOT written here: a
    list of them in a public test file is the very naming this test forbids
    (it sat here until 2026-10-18). The guard is structural instead — naming a
    repository or an organisation takes a code-host reference, and the package
    carries none.
    """
    host = re.compile(r"\b(?:github|gitlab|bitbucket|codeberg)\.(?:com|org)\b|\bgit@", re.I)
    for f, text in _package_text_files():
        m = host.search(text)
        assert not m, f"{f.name} carries a code-host reference — the upstream is credited by the copyright line only"


def test_no_private_deny_list_term_in_the_package():
    """The named half of the guard, with the names kept OFF the repository.

    The terms come from the machine's private leak deny-list
    (`~/.config/set-core/leakscan-deny.txt`, read by `set-leakscan`), so the
    partner's names are checked without being written down here. Skipped
    where that list is absent — a public clone has none, and the structural
    test above still runs there.
    """
    deny = Path.home() / ".config" / "set-core" / "leakscan-deny.txt"
    if not deny.is_file():
        pytest.skip("no private deny-list on this machine")
    from importlib.machinery import SourceFileLoader
    scanner = SourceFileLoader(
        "leakscan_for_kb", str(PKG.parents[1] / "bin" / "set-leakscan")).load_module()
    terms, regexes, _notes = scanner.load_deny()
    check = scanner._TermCheck(terms, regexes)
    for f, text in _package_text_files():
        for n, line in enumerate(text.splitlines(), 1):
            m = check.search(line)
            # the value is masked: the assertion message lands in CI logs
            assert not m, f"{f.name}:{n} carries a deny-list term ({scanner.mask(m.group(0))})"
