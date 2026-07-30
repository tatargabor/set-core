"""An unrecognised `change_type` resolves silently — and not to what everyone assumes.

Raised by a peer reading this code, and their inference is the reason this file exists:
they read `change_type = getattr(change, "change_type", None) or "feature"` and concluded
an unknown type falls back to `feature`'s gate set. It does not. That `or` covers only an
ABSENT or empty value; a *present but unrecognised* one skips `UNIVERSAL_DEFAULTS` entirely
and keeps the all-"run" baseline — which is STRICTER than `feature`, because `feature`
softens `rules` to "warn".

Both halves matter and they pull in opposite directions:

- The outcome is safe. An unknown type gets the most blocking configuration, so a typo
  cannot loosen a gate.
- The silence is not. A typo and a deliberately-named lane are indistinguishable from the
  operator's chair, and the operator sees gates they never configured with nothing in the
  log naming the cause.

So the fix is a warning, not a behaviour change. These tests pin the actual resolution as
measured, so the next person who reasons from the `or "feature"` line gets a failing test
instead of a plausible wrong answer.
"""

import logging
import types

import pytest

from set_orch.gate_profiles import (
    CONDITIONAL_CHANGE_TYPES,
    UNIVERSAL_DEFAULTS,
    resolve_gate_config,
)

#: The stand-in for "a type this dictionary does not hold" — and it is asserted to still be
#: unknown before it is used.
#:
#: This constant exists because the original version of the test below used the literal
#: `"bugfix"` as its example of an unknown type. That was true when it was written and stopped
#: being true the day a `bugfix` profile was added, at which point the test was comparing two
#: KNOWN types and its name promised something it no longer measured. It failed loudly here only
#: because the new type also carries an entry condition; a plain new type would have made it
#: pass while measuring nothing. **An example chosen because it is absent needs a guard that it
#: is still absent** — the same rule as counting from the data rather than from a declaration.
UNKNOWN_EXAMPLE = "a-type-no-dictionary-holds"


def _change(change_type):
    return types.SimpleNamespace(change_type=change_type, skip_gates=None, gate_hints=None)


def _gates(change_type):
    return dict(resolve_gate_config(_change(change_type))._gates)


def test_the_unknown_example_is_actually_unknown():
    """The guard described above, as its own test so its failure names the real cause."""
    assert UNKNOWN_EXAMPLE not in UNIVERSAL_DEFAULTS, (
        f"{UNKNOWN_EXAMPLE!r} became a real change type — every test below that uses it as an "
        f"'unknown type' is now measuring a known one. Pick a new stand-in; do not delete this."
    )


def test_an_unknown_type_does_NOT_resolve_to_the_feature_gate_set():
    """The refuted inference, held in a test so it cannot be re-derived.

    `feature` softens `rules`; an unknown type does not. Anyone planning around the
    assumed fallback would expect a warn where a blocker stands.
    """
    unknown = _gates(UNKNOWN_EXAMPLE)
    feature = _gates("feature")

    assert unknown != feature
    assert feature["rules"] == "warn"
    assert unknown["rules"] == "run", (
        "an unrecognised type keeps the all-run baseline — stricter, not feature-like")


def test_an_unknown_type_leaves_every_universal_gate_blocking():
    """The fail direction, stated as an assertion rather than as a comment."""
    assert set(_gates("a-lane-nobody-registered").values()) == {"run"}


def test_an_ABSENT_type_is_the_case_that_really_does_default_to_feature():
    """The `or "feature"` line is not wrong — it just answers a different question."""
    absent = dict(resolve_gate_config(
        types.SimpleNamespace(change_type=None, skip_gates=None, gate_hints=None))._gates)

    assert absent == _gates("feature")


def test_an_unknown_type_is_reported_rather_than_resolved_in_silence(caplog):
    """The actual defect: a typo and a deliberate new lane looked identical in the log."""
    with caplog.at_level(logging.WARNING, logger="set_orch.gate_profiles"):
        _gates("infrastructur")  # a plausible typo of a real type

    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "infrastructur" in logged
    assert "blocking" in logged, "the message must say what the operator will actually see"


@pytest.mark.parametrize(
    "known", sorted(set(UNIVERSAL_DEFAULTS) - CONDITIONAL_CHANGE_TYPES))
def test_a_KNOWN_type_stays_silent(known, caplog):
    """A warning that fires on every ordinary change is a warning nobody reads.

    Conditional types are excluded because they cannot be resolved without a worktree at all —
    see the companion test below, which covers them rather than leaving a hole. Excluding a case
    from a parametrize and saying nothing is how coverage disappears while the count goes up.
    """
    with caplog.at_level(logging.WARNING, logger="set_orch.gate_profiles"):
        _gates(known)

    assert [r for r in caplog.records if "not one of" in r.getMessage()] == []


@pytest.mark.parametrize("conditional", sorted(CONDITIONAL_CHANGE_TYPES))
def test_a_GRANTED_conditional_type_also_stays_silent(conditional, tmp_path, caplog):
    """The case the parametrize above excludes, covered here with its condition satisfied.

    A conditional type is a known type, so resolving it must not produce the unknown-type
    warning either — and the only way to reach that code path is to pay for the lane.
    """
    import json

    (tmp_path / "set").mkdir(parents=True)
    (tmp_path / "set" / "lane-signals.json").write_text(json.dumps({"exit": {
        "lane": "restoring",
        "condition": {"kind": "fixed-defect-without-test"},
        "scope": "per-change-verification",
        "baseline": [],
        "promotion": {"severity": "enforce", "measure": "a week at WARN"},
        "triggering_case": "2026-05-14 BUG-1 returned with no test",
        "exclusions": ["docs/**"],
        # Required for the lane to be granted at all: no condition handler is registered in
        # this version, so an unevaluated signal blocks only where its project declares this.
        "sole_enforcement": True,
    }}))
    (tmp_path / "set" / "change-type-lanes.json").write_text(
        json.dumps({conditional: ["exit"]}))

    class _Profile:
        def lane_promotions(self):
            return {"exit": {"measured": "2026-06-01"}}

    with caplog.at_level(logging.WARNING, logger="set_orch.gate_profiles"):
        resolve_gate_config(_change(conditional), profile=_Profile(), tree=tmp_path)

    assert [r for r in caplog.records if "not one of" in r.getMessage()] == []
