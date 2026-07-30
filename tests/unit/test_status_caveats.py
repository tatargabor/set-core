"""`caveats` on the status envelope — carried, never interpreted.

A caveat says a value is CORRECT and means something narrower than its name suggests. The
envelope's three existing "do not read it that way" signals all describe something absent or
wrong, so none of them fits, and without a place to ride the caveat stays in a conversation while
the number travels.

**Why there is no test here grepping the source for a real producer's caveat keys**, which is the
obvious way to assert that the framework holds no vocabulary: those keys are a producer's domain
material — their register's status names — so writing them into this repository in order to prove
the framework does not hold them would be the very thing the confidentiality boundary forbids,
with the test file as the carrier. The property is therefore asserted structurally instead:
arbitrary keys survive unchanged, and the module carries exactly one caveat-key constant, the
command-level `"*"`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "lib"))

from set_orch import project_status as ps  # noqa: E402


def _envelope(**extra):
    """A well-formed envelope, serialised — `parse_envelope` reads the raw text a command
    printed, which is the thing that actually crosses the boundary."""
    payload = {"contractVersion": 1, "command": "bugs", "ok": True,
               "generatedAt": "2026-07-30T12:00:00Z", "data": {"count": 3}}
    payload.update(extra)
    return json.dumps(payload)


def _parse(**extra):
    return ps.parse_envelope("bugs", _envelope(**extra))


# ── the producer writes it; the framework holds none ──


def test_an_envelope_without_caveats_carries_none_and_says_nothing():
    """The first requirement, and the one that lets the two sides move at different speeds.

    A project that has not adopted caveats must see no difference at all — not an empty banner,
    not a "0 caveats" line, not a log entry. Absence is absence.
    """
    result = _parse()
    assert result.caveats == {}
    assert result.ok is True


def test_arbitrary_keys_survive_unchanged():
    """Any vocabulary, any script, any case — the framework validates against no known set.

    Deliberately exercised with keys the framework could not possibly know: accented uppercase,
    lowercase unaccented, and a non-Latin script. A producer's own key spellings are load-bearing
    (one contract distinguishes two families of key by case and accent on purpose), so a
    framework that normalised would match keys nobody sent and miss the ones they did.
    """
    keys = {"ÁRVÍZTŰRŐ_TÜKÖRFÚRÓGÉP": "a", "lower_unaccented": "b", "日本語キー": "c",
            "with space": "d", "MiXeD-CaSe": "e"}
    result = _parse(caveats=dict(keys))
    assert result.caveats == keys


def test_the_only_caveat_key_the_framework_knows_is_the_command_level_one():
    """Structural stand-in for "the framework holds no vocabulary" — see the module docstring.

    If a later change adds a recognised key name, this fails, which is the point: recognising one
    producer's key is one line and it is the wrong line, exactly as it was for `deprecated`.
    """
    assert ps.COMMAND_LEVEL_CAVEAT == "*"
    caveat_constants = [
        name for name, value in vars(ps).items()
        if name.isupper() and isinstance(value, (str, tuple, frozenset, set, list))
        and "caveat" in name.lower()
    ]
    assert caveat_constants == ["COMMAND_LEVEL_CAVEAT"], caveat_constants


# ── malformed input degrades the decoration, never the answer ──


@pytest.mark.parametrize("bad", [[], ["a"], "a string", 7, True])
def test_a_malformed_caveats_value_does_not_take_the_answer_down(bad):
    """The command succeeded and the value is right; the caveat is what qualifies it.

    Refusing the whole answer because its decoration is malformed would turn a cosmetic defect
    into a missing measurement — and a missing measurement is what this entire module exists to
    make visible rather than to manufacture.
    """
    result = _parse(caveats=bad)
    assert result.ok is True
    assert result.data == {"count": 3}
    assert result.caveats == {}


def test_entries_that_are_not_one_sentence_under_one_key_are_dropped_individually():
    """One unusable entry must not discard the usable ones beside it."""
    result = _parse(caveats={
        "good": "this number describes our register",
        "empty-sentence": "",
        "blank-sentence": "   ",
        "": "no key at all",
        "wrong-type": ["not", "a", "sentence"],
    })
    assert result.caveats == {"good": "this number describes our register"}


def test_nothing_is_normalised():
    """Not case, not surrounding whitespace in the key, not the key's shape.

    A key must match what the producer actually sends. Trimming or lowercasing here would create
    a key the producer never emitted, and the caveat would then attach to nothing while looking
    declared — the silent failure this mechanism exists to prevent, produced by the mechanism.
    """
    result = _parse(caveats={"  Padded Key  ": "s"})
    assert list(result.caveats) == ["  Padded Key  "]


# ── it reaches the surface that renders it ──


def test_caveats_reach_the_json_the_dashboard_reads():
    """A field parsed and then dropped one layer up is the same as not parsing it.

    Asserted on the serialised payload rather than on the dataclass, because the dataclass is the
    mechanism and the payload is the result — and this repo has a standing rule about verifying
    the first while staying silent about the second.
    """
    result = _parse(caveats={"*": "register, not the world"})
    payload = ps.StatusSnapshot(results={"bugs": result}).to_dict()
    assert payload["commands"]["bugs"]["caveats"] == {"*": "register, not the world"}


def test_the_serialised_caveats_are_a_copy_not_the_live_mapping():
    """A renderer mutating what it was handed must not edit the parsed answer."""
    result = _parse(caveats={"a": "s"})
    payload = ps.StatusSnapshot(results={"bugs": result}).to_dict()
    payload["commands"]["bugs"]["caveats"]["a"] = "MUTATED"
    assert result.caveats["a"] == "s"
