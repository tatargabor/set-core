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

from set_orch.gate_profiles import UNIVERSAL_DEFAULTS, resolve_gate_config


def _change(change_type):
    return types.SimpleNamespace(change_type=change_type, skip_gates=None, gate_hints=None)


def _gates(change_type):
    return dict(resolve_gate_config(_change(change_type))._gates)


def test_an_unknown_type_does_NOT_resolve_to_the_feature_gate_set():
    """The refuted inference, held in a test so it cannot be re-derived.

    `feature` softens `rules`; an unknown type does not. Anyone planning around the
    assumed fallback would expect a warn where a blocker stands.
    """
    unknown = _gates("bugfix")
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


@pytest.mark.parametrize("known", sorted(UNIVERSAL_DEFAULTS))
def test_a_KNOWN_type_stays_silent(known, caplog):
    """A warning that fires on every ordinary change is a warning nobody reads."""
    with caplog.at_level(logging.WARNING, logger="set_orch.gate_profiles"):
        _gates(known)

    assert [r for r in caplog.records if "not one of" in r.getMessage()] == []
