"""The set of valid change types has exactly one home.

Written with the change `bugfix-lane-with-a-real-delta`, whose first requirement is this one.
The reason it is a test rather than a comment is the shape of the defect it guards: five
independent copies of the same pipe-separated enum, none of which was wrong, all of which were
*about to be* the moment a type was added. A comment asks to be believed; a test refuses to be
reverted.

**The historical enum is rebuilt here from its six names rather than pasted**, so this file
does not itself become the sixth copy the scan below is looking for. That is not cleverness —
the first draft pasted the literal, and the scan then found itself.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "lib"))

from set_orch.gate_profiles import (  # noqa: E402
    UNIVERSAL_DEFAULTS,
    change_type_enum,
    is_valid_change_type,
    valid_change_types,
)

#: The six names as they stood before this change, in the order the dictionary declared them.
#: Order is asserted below because the enum is read by a planning agent and the order groups
#: the types the way the pipeline uses them.
HISTORICAL_TYPES = (
    "infrastructure", "schema", "foundational", "feature",
    "cleanup-before", "cleanup-after",
)

#: Reconstructed, never pasted — see the module docstring.
HISTORICAL_ENUM = "|".join(HISTORICAL_TYPES)

#: Where a second copy would actually hurt. Deliberately NOT the whole repository: `docs/`,
#: `openspec/` and `tests/` legitimately quote the list while describing or archiving it, and a
#: scan that fires on those is a gate nobody keeps — the same reason the framework refuses a
#: signal that reports its own definition.
SCANNED_ROOTS = ("lib", "modules", "bin", ".claude")

SCANNED_SUFFIXES = (".py", ".md", ".sh", ".json", ".yaml", ".yml")


def _scanned_files() -> list[Path]:
    files: list[Path] = []
    for root in SCANNED_ROOTS:
        base = REPO / root
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in SCANNED_SUFFIXES:
                if "node_modules" in path.parts or "__pycache__" in path.parts:
                    continue
                files.append(path)
    return files


def test_the_enum_is_derived_from_the_dictionary():
    """`change_type_enum()` is the dictionary's keys, in order — not a parallel string."""
    assert change_type_enum().split("|") == list(valid_change_types())
    assert list(valid_change_types()) == list(UNIVERSAL_DEFAULTS)


def test_the_six_historical_types_survive_in_their_historical_order():
    """A type may be ADDED; the six that existed may not be dropped or reordered.

    Reordering is not cosmetic here: the sequence is the planner's dependency hint
    (setup → schema → shared → feature → cleanup), and a reordered enum silently changes
    advice rather than breaking anything.
    """
    present = [t for t in valid_change_types() if t in HISTORICAL_TYPES]
    assert present == list(HISTORICAL_TYPES)


def test_every_historical_type_is_still_valid():
    for name in HISTORICAL_TYPES:
        assert is_valid_change_type(name), name


def test_an_unknown_type_is_not_silently_valid():
    assert not is_valid_change_type("infrastructur")   # the typo the resolver warns about
    assert not is_valid_change_type("")
    assert not is_valid_change_type("config")          # removed from the merger's exemption
    assert not is_valid_change_type("docs")


def test_the_merger_exemption_names_only_real_change_types():
    """The measured defect this change corrects.

    `('infrastructure', 'config', 'docs')` exempted two names no type list contains, so the
    guard's exemption named things nothing can produce. Harmless on the day it was written and
    authoritative-looking a year later, which is why it is a test now and not a comment.
    """
    from set_orch.merger import _ZERO_GATES_EXPECTED_TYPES

    assert _ZERO_GATES_EXPECTED_TYPES, "an empty exemption tuple would warn on every type"
    for name in _ZERO_GATES_EXPECTED_TYPES:
        assert is_valid_change_type(name), (
            f"{name!r} is exempted from the zero-gates warning but is not a change type"
        )


def test_no_second_copy_of_the_enum_exists_in_the_framework():
    """No file under lib/, modules/, bin/ or .claude/ carries the pipe-separated list.

    This is the wrong pattern held in a test. The five copies removed by this change were
    each introduced by someone doing the obvious thing — writing the values into the prompt
    that needs them — so the obvious thing has to fail loudly rather than look identical.
    """
    offenders = []
    for path in _scanned_files():
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        if HISTORICAL_ENUM in text:
            offenders.append(str(path.relative_to(REPO)))
    assert not offenders, (
        "the change-type enum is written out by hand in: " + ", ".join(offenders) +
        " — derive it from set_orch.gate_profiles.change_type_enum() instead"
    )


def test_no_hand_written_pair_of_piped_type_names_remains():
    """The refuted pattern, kept so the scan cannot be 'simplified' back into blindness.

    Searching for one type name (`grep feature`) matches prose, identifiers, and the word in
    ordinary English — 100+ hits, every one legitimate, which is a search nobody finishes. The
    discriminating pattern is the SEPARATOR: two type names joined by a pipe is never prose.

    **This is the check that earned its keep.** The six-name search that preceded it missed a
    THREE-name enum in `_BRIEF_OUTPUT_SCHEMA`, because a pattern built from the shape you expect
    is blind to the variant you did not — and it failed in the reassuring direction, reporting
    five copies when there were six. So this test is deliberately wider than the exact-string
    scan above rather than a duplicate of it.
    """
    pair = re.compile(r"\b(?:%s)\|(?:%s)\b" % ("|".join(map(re.escape, HISTORICAL_TYPES)),
                                               "|".join(map(re.escape, HISTORICAL_TYPES))))
    hits = []
    for path in _scanned_files():
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        if pair.search(text):
            hits.append(str(path.relative_to(REPO)))
    assert not hits, "piped change-type names (a hand-written enum) found in: " + ", ".join(hits)


def test_the_cross_cutting_subset_names_only_real_types():
    """A subset is legitimate; a subset naming a non-existent type is the defect.

    `_BRIEF_OUTPUT_SCHEMA` offers only three types for a cross-cutting change, and that
    narrowing IS the planning advice — widening it to the full enum would have changed
    behaviour while claiming to remove a copy. So membership is asserted, never length.
    """
    from set_orch.templates import _CROSS_CUTTING_TYPES

    assert _CROSS_CUTTING_TYPES, "an empty subset would offer the planner no type at all"
    for name in _CROSS_CUTTING_TYPES:
        assert is_valid_change_type(name), (
            f"{name!r} is offered for cross-cutting changes but is not a change type"
        )


def test_no_template_leaks_a_change_type_token():
    """Every planner template that carries a token is wrapped in the substitution.

    An unwrapped token reaches an agent as `%%CHANGE_TYPES%%`, which is loud — but loud is
    not the same as caught, and the person it is loud to is not the person who broke it.
    """
    from set_orch import templates

    leaked = [
        name for name, value in vars(templates).items()
        if isinstance(value, str) and "%%CHANGE_TYPES" in value and not name.endswith("TOKEN")
    ]
    assert not leaked, f"unsubstituted change-type token in: {leaked}"


def test_the_planner_schemas_carry_the_derived_enum():
    """The four planner output schemas show the planner the current list.

    Together with `test_no_second_copy_...` this closes the chain: no literal copy exists in
    the source, and the constant contains the enum — so it can only have been derived.
    """
    from set_orch import templates

    enum = change_type_enum()
    for name in ("_SPEC_OUTPUT_JSON", "_SPEC_OUTPUT_JSON_DIGEST",
                 "_BRIEF_OUTPUT_JSON", "_DOMAIN_CHANGES_OUTPUT_SCHEMA"):
        assert enum in getattr(templates, name), name


def test_adding_a_type_reaches_the_substitution(monkeypatch):
    """The 'adding a type reaches every consumer' scenario, driven through the dictionary.

    Asserted on the substitution function rather than on the module constants, because those
    are built at import and a monkeypatched dict cannot retroactively change them. The chain
    the previous test establishes is what carries the constants; this test carries the link
    from the dictionary to the string.
    """
    from set_orch import templates

    patched = dict(UNIVERSAL_DEFAULTS)
    patched["hotfix-probe"] = dict(next(iter(UNIVERSAL_DEFAULTS.values())))
    monkeypatch.setattr("set_orch.gate_profiles.UNIVERSAL_DEFAULTS", patched)

    rendered = templates._with_change_types("%%CHANGE_TYPES%% / %%CHANGE_TYPES_LIST%%")
    assert "hotfix-probe" in rendered
    assert "`hotfix-probe`" in rendered


def test_the_deployed_skill_tells_the_reader_how_to_obtain_the_list():
    """The skill file deploys into consumer projects, so its copy drifts on its own clock.

    Asserting the instruction rather than the absence of the enum: absence is already covered,
    and a file that removed the list without saying where to get it would pass that check while
    leaving the planning agent to guess — and a guessed type is not rejected, it silently runs
    the strictest chain.
    """
    skill = (REPO / ".claude" / "skills" / "set" / "decompose" / "SKILL.md").read_text()
    assert "change_type_enum" in skill, "the skill must name the single definition"
    assert "gate_profiles" in skill


@pytest.mark.parametrize("root", SCANNED_ROOTS)
def test_scanned_roots_exist(root):
    """A scan over a directory that does not exist reports clean.

    The detector is proven able to see something before its zero is believed — the same
    reason the baseline leak checker was run un-isolated first.
    """
    assert (REPO / root).is_dir(), f"{root} is scanned but absent — the scan above proves nothing"


def test_the_scan_can_actually_fire(tmp_path, monkeypatch):
    """Prove the enum scan is not structurally blind, using a file it really reads.

    Without this, a passing `test_no_second_copy_...` is indistinguishable from a scan whose
    glob matches nothing.
    """
    target = REPO / "lib" / "set_orch" / "_enum_scan_probe.py"
    assert not target.exists()
    target.write_text(f'PROBE = "{HISTORICAL_ENUM}"\n')
    try:
        found = [p for p in _scanned_files()
                 if HISTORICAL_ENUM in p.read_text(errors="replace")]
        assert target in found, "the scan did not see a file it is supposed to scan"
    finally:
        target.unlink()
    assert not target.exists(), "the probe file must not survive the test"
