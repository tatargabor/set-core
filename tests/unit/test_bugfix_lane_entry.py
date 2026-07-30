"""A lane entry cannot exist without its behavioural delta.

The change `bugfix-lane-with-a-real-delta`, sections 2–4. What is under test is not "does
`bugfix` have a profile" — that is one dictionary entry and would be a false gate on its own.
It is that the entry is **structurally incapable of being an empty name**: declaring it without
an enforced exit obligation is refused, and no other change type's profile is substituted.

**The baseline in `PRE_CHANGE_RESOLUTION` was measured, not written.** It was dumped from a
detached worktree at the commit before this change, with `PYTHONPATH` pointed at that worktree's
own `lib` and the import asserted to come from there — because an editable install otherwise
resolves the package from the development tree and the "baseline" runs the working tree's code.
Additive changes leave old tests passing against new code, so that mistake reports "no
regression" having compared one version with itself.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "lib"))

from set_orch.change_type_lanes import (  # noqa: E402
    ConditionalLaneRefused,
    LaneMapRefused,
    read_lane_map,
    require_exit_obligation,
)
from set_orch.gate_profiles import (  # noqa: E402
    CONDITIONAL_CHANGE_TYPES,
    UNIVERSAL_DEFAULTS,
    resolve_gate_config,
)

#: Measured on the commit preceding this change — see the module docstring. Only the values a
#: project could observe are kept: the gate modes and `test_files_required`.
PRE_CHANGE_RESOLUTION = {
    "infrastructure": ({"build": "skip", "e2e": "skip", "review": "run", "rules": "warn",
                        "scope_check": "run", "spec_verify": "soft", "test": "skip",
                        "test_files": "skip"}, False),
    "schema": ({"build": "run", "review": "run", "rules": "warn", "scope_check": "run",
                "spec_verify": "run", "test": "warn", "test_files": "run"}, False),
    "foundational": ({"build": "run", "review": "run", "rules": "warn", "scope_check": "run",
                      "spec_verify": "run", "test": "run", "test_files": "run"}, True),
    "feature": ({"build": "run", "review": "run", "rules": "warn", "scope_check": "run",
                 "spec_verify": "run", "test": "run", "test_files": "run"}, True),
    "cleanup-before": ({"build": "run", "review": "run", "rules": "warn", "scope_check": "run",
                        "spec_verify": "soft", "test": "warn", "test_files": "run"}, False),
    "cleanup-after": ({"build": "run", "review": "skip", "rules": "skip", "scope_check": "run",
                       "spec_verify": "soft", "test": "warn", "test_files": "run"}, False),
    # An unknown type applies no per-type defaults, so every universal gate stays blocking.
    # This row is the one that makes the change a LOOSENING to be bought rather than spent:
    # before this change, `bugfix` resolved to exactly this.
    "totally-unknown-type": ({"build": "run", "review": "run", "rules": "run",
                              "scope_check": "run", "spec_verify": "run", "test": "run",
                              "test_files": "run"}, True),
}


class _Change:
    def __init__(self, change_type=None, name="a-change"):
        self.change_type = change_type
        self.name = name


class _Profile:
    """A minimal project type: supplies promotion evidence and nothing else."""

    def __init__(self, promotions=None, lanes=None):
        self._promotions = promotions or {}
        self._lanes = lanes

    def lane_promotions(self):
        return self._promotions

    def change_type_lanes(self):
        return self._lanes


def _signal(promotion_severity="enforce", sole_enforcement=True):
    """A well-formed declaration. Shape matters: no path pattern in the condition, so the
    self-inclusion refusal cannot fire, and no numeric threshold, so the volume refusal cannot.

    `sole_enforcement` defaults to True here and that is not incidental. `lane_gate._KIND_HANDLERS`
    is empty by design in this set-core version, so every declared signal is *unevaluated*, and
    `lane_evaluator` blocks on an unevaluated outcome only where the project declared itself the
    sole enforcement of the defect class. Without the flag, nothing this fixture declares could
    fail a gate — so a fixture that omitted it would have been testing a discount granted
    against an obligation that blocks nothing.
    """
    return {
        "lane": "restoring",          # deliberately NOT a set-core change type
        "condition": {"kind": "fixed-defect-without-test"},
        "scope": "per-change-verification",
        "baseline": [],
        "promotion": {"severity": promotion_severity,
                      "measure": "one week of WARN with no false positives"},
        "triggering_case": "2026-05-14 defect BUG-1 returned twice with no regression test",
        "exclusions": ["docs/**"],
        "sole_enforcement": sole_enforcement,
    }


def _tree(tmp_path, signals=None, lane_map=None):
    (tmp_path / "set").mkdir(parents=True, exist_ok=True)
    if signals is not None:
        (tmp_path / "set" / "lane-signals.json").write_text(json.dumps(signals))
    if lane_map is not None:
        (tmp_path / "set" / "change-type-lanes.json").write_text(json.dumps(lane_map))
    return tmp_path


# ── Section 3.4 — the refusal binds the declaration, not the project ──


@pytest.mark.parametrize("change_type", sorted(PRE_CHANGE_RESOLUTION))
def test_a_project_declaring_no_conditional_lane_is_untouched(change_type):
    """Measured against the pre-change resolution, not asserted from the dictionary.

    A project that does not ask for a discount cannot lose protection by not asking — and the
    only way to know that is to compare with what the previous commit actually produced.
    """
    expected_gates, expected_required = PRE_CHANGE_RESOLUTION[change_type]
    cfg = resolve_gate_config(_Change(change_type))
    assert {k: v for k, v in sorted(cfg._gates.items())} == expected_gates
    assert cfg.test_files_required is expected_required


def test_an_absent_change_type_still_resolves_to_feature():
    """The `or "feature"` default is unchanged — an absent value is not a conditional type."""
    cfg = resolve_gate_config(_Change(None))
    assert cfg.get("rules") == "warn"          # the feature set, not the unknown-type set
    assert cfg.get("test_files") == "run"


# ── Section 4.1 — prove the delta is real ──


def test_the_bugfix_profile_differs_from_every_other_one():
    """The direct guard against the failure already in the tree.

    `feature` and `foundational` are byte-identical in this dictionary and nobody noticed until
    it was measured. That pair is named as a KNOWN pre-existing defect rather than silently
    tolerated: an exemption that matches nothing reads as authoritative, and an exemption that
    is not written down reads as intent.
    """
    known_identical = frozenset({frozenset({"feature", "foundational"})})

    for other in UNIVERSAL_DEFAULTS:
        if other == "bugfix":
            continue
        assert UNIVERSAL_DEFAULTS["bugfix"] != UNIVERSAL_DEFAULTS[other], (
            f"bugfix is byte-identical to {other} — a taxonomy entry with no behavioural "
            f"delta is a false gate"
        )

    identical = {frozenset({a, b})
                 for a in UNIVERSAL_DEFAULTS for b in UNIVERSAL_DEFAULTS
                 if a != b and UNIVERSAL_DEFAULTS[a] == UNIVERSAL_DEFAULTS[b]}
    assert identical == known_identical, (
        "the set of byte-identical profile pairs changed. Adding one is a false gate; removing "
        f"the known {sorted(map(sorted, known_identical))} is a fix that must update this test."
    )


def test_the_delta_is_exactly_one_gate_and_it_is_the_proxy_one():
    """Stated as a test because the delta is the whole justification for the entry existing.

    One gate, not a bundle: a bundle cannot be argued for or against. And `spec_verify` stays
    blocking — softening it would loosen the check that catches the very assumption (a fix
    restores the spec) the design refuses to gate on.
    """
    feature = UNIVERSAL_DEFAULTS["feature"]
    bugfix = UNIVERSAL_DEFAULTS["bugfix"]
    differing = {k for k in set(feature) | set(bugfix) if feature.get(k) != bugfix.get(k)}
    assert differing == {"test_files"}, differing
    assert bugfix["test_files"] == "warn"
    assert bugfix["spec_verify"] == "run", "spec_verify must not be softened — see D4"
    assert bugfix["review"] == "run"


# ── Section 2 — the project's mapping ──


def test_the_mapping_is_read_from_the_tree_and_contacts_nothing(tmp_path, monkeypatch):
    """No service, no subprocess — the same constraint the signal reader obeys.

    Asserted by making the escape hatches explode rather than by reading the code, because the
    check that matters is what the function DOES when a network exists.
    """
    import subprocess

    def _explode(*a, **k):  # pragma: no cover - the point is that it is never reached
        raise AssertionError("read_lane_map contacted a subprocess")

    monkeypatch.setattr(subprocess, "run", _explode)
    monkeypatch.setattr(subprocess, "check_output", _explode)

    tree = _tree(tmp_path, lane_map={"bugfix": ["no-fix-without-regression-test"]})
    result = read_lane_map(tree)
    assert result.mapping == {"bugfix": ["no-fix-without-regression-test"]}
    assert not result.refusals


def test_an_absent_mapping_is_absent_not_empty(tmp_path):
    result = read_lane_map(_tree(tmp_path))
    assert result.declared_nothing
    assert result.mapping == {}


def test_a_single_signal_name_as_a_string_is_accepted(tmp_path):
    """A string would iterate per character, silently producing one-letter signal names that
    match nothing — the same reassuring direction as a missing key."""
    result = read_lane_map(_tree(tmp_path, lane_map={"bugfix": "one-signal"}))
    assert result.mapping == {"bugfix": ["one-signal"]}


@pytest.mark.parametrize("typo,resembles", [
    ("bugfixes", ["bugfix"]),                          # plural
    ("bug-fix", ["bugfix"]),                           # separator
    ("BugFix", ["bugfix"]),                            # case
    ("bugfix_lane", ["bugfix"]),                       # suffix
    ("cleanup", ["cleanup-before", "cleanup-after"]),  # truncation — resembles BOTH
])
def test_a_near_miss_key_is_refused_and_names_what_it_resembles(tmp_path, typo, resembles):
    """Refused, not ignored — and the message must name both halves.

    An ignored key means "no exit obligation", which is the refusal path for a conditional
    type. So a typo would present as a project that declared nothing, the refusal would name
    the wrong cause, and the fix would be invisible.

    **The `cleanup` row is the one that earned its place.** It resembles two real types, and the
    first implementation reported only the first match — a silent tie-break inside the only
    thing the refusal produces, which sends the reader to fix the wrong end. Found by this test
    disagreeing with the code, not by review.
    """
    result = read_lane_map(_tree(tmp_path, lane_map={typo: ["s"]}))
    assert not result.mapping
    assert len(result.refusals) == 1
    text = str(result.refusals[0])
    assert typo in text
    for name in resembles:
        assert name in text, f"{name} resembles {typo} but is not named in the refusal"


def test_an_unrecognised_key_is_refused_even_when_it_resembles_nothing(tmp_path):
    """The refusal does not depend on detecting a near miss.

    A closed key space means an unrecognised key can never resolve anything, and a declaration
    that can never resolve anything must not read as a declaration. Making the refusal
    conditional on resemblance would be a narrowing, failing in the reassuring direction.
    """
    result = read_lane_map(_tree(tmp_path, lane_map={"zzz-nothing-like-it": ["s"]}))
    assert not result.mapping
    assert len(result.refusals) == 1
    assert isinstance(result.refusals[0], LaneMapRefused)


def test_one_refused_key_does_not_discard_the_others(tmp_path):
    result = read_lane_map(_tree(tmp_path, lane_map={"bugfix": ["good"], "bugfixes": ["bad"]}))
    assert result.mapping == {"bugfix": ["good"]}
    assert len(result.refusals) == 1


def test_an_empty_mapped_list_is_refused(tmp_path):
    """"No obligation" and "a declaration that says nothing" must not be spelled the same."""
    result = read_lane_map(_tree(tmp_path, lane_map={"bugfix": []}))
    assert not result.mapping
    assert result.refusals


def test_an_unreadable_mapping_file_is_a_refusal_not_an_absence(tmp_path):
    (tmp_path / "set").mkdir(parents=True)
    (tmp_path / "set" / "change-type-lanes.json").write_text("{not json")
    result = read_lane_map(tmp_path)
    assert not result.declared_nothing, "a broken file must not read as 'declared nothing'"
    assert result.refusals


def test_a_broken_profile_supplier_does_not_take_the_tree_down(tmp_path):
    class _Angry:
        def change_type_lanes(self):
            raise RuntimeError("boom")

    result = read_lane_map(_tree(tmp_path, lane_map={"bugfix": ["s"]}), profile=_Angry())
    assert result.mapping == {"bugfix": ["s"]}
    assert any("profile" in str(r) for r in result.refusals)


# ── Section 2.3 — the coupling that must not exist ──


def test_nothing_compares_a_lane_label_to_a_change_type():
    """The implementation a later reader reaches for, refused in a test.

    Comparing `signal.lane` to `change_type` is one line, works perfectly for any project whose
    lanes happen to be called set-core's words, and is the design failing rather than the
    project. It looks like a simplification, which is why a comment would not survive.
    """
    import re

    pattern = re.compile(
        r"(\.lane\s*(==|!=|\bin\b)[^\n]*change_type"
        r"|change_type\s*(==|!=|\bin\b)[^\n]*\.lane\b)"
    )
    offenders = []
    for path in (REPO / "lib").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for lineno, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("*"):
                continue          # the prohibition is written down in comments; that is fine
            if pattern.search(line):
                offenders.append(f"{path.relative_to(REPO)}:{lineno}")
    assert not offenders, (
        "a signal's own lane label is compared to a change type at: " + ", ".join(offenders) +
        " — the mapping is the project's declaration, never the coincidence of two vocabularies"
    )


def test_a_lane_label_equal_to_a_change_type_is_not_a_mapping(tmp_path):
    """The behavioural half of the prohibition, not just the source scan.

    A source scan proves no comparison is WRITTEN; it says nothing about whether the coincidence
    is honoured by some other route. Here the signal's own label is literally `bugfix` and its
    promotion is recorded — everything a lane-label comparison would need — and the declaration
    is still refused, because the project declared no mapping.
    """
    signal = _signal()
    signal["lane"] = "bugfix"          # the coincidence, made as tempting as possible
    tree = _tree(tmp_path, signals={"exit-signal": signal})
    profile = _Profile(promotions={"exit-signal": {"measured": "2026-06-01"}})

    with pytest.raises(ConditionalLaneRefused) as exc:
        resolve_gate_config(_Change("bugfix"), profile=profile, tree=tree)
    assert exc.value.reason_class == ConditionalLaneRefused.NO_MAPPING


def test_the_lane_label_scan_can_actually_fire(tmp_path):
    """Prove the scan above is not structurally blind before believing its zero."""
    import re

    pattern = re.compile(
        r"(\.lane\s*(==|!=|\bin\b)[^\n]*change_type"
        r"|change_type\s*(==|!=|\bin\b)[^\n]*\.lane\b)"
    )
    assert pattern.search("if signal.lane == change.change_type:")
    assert pattern.search("if change_type in (s.lane, other):")
    assert not pattern.search("# the lane label is never compared to change_type")


# ── Section 3 — the conditional entrance ──


def test_a_bugfix_declaration_with_no_exit_obligation_is_refused(tmp_path):
    tree = _tree(tmp_path, signals={"s": _signal()})
    with pytest.raises(ConditionalLaneRefused) as exc:
        resolve_gate_config(_Change("bugfix"), tree=tree)
    assert exc.value.reason_class == ConditionalLaneRefused.NO_MAPPING


def test_the_refusal_substitutes_no_other_profile(tmp_path):
    """The refusal is the whole point: no config is returned at all.

    Falling back is refused for a reason that is not about danger — the substituted chain is
    stricter, so nothing breaks. It is about belief.
    """
    tree = _tree(tmp_path, signals={"s": _signal()})
    with pytest.raises(ConditionalLaneRefused):
        resolve_gate_config(_Change("bugfix"), tree=tree)


def test_a_mapped_and_enforced_signal_buys_the_cheaper_entrance(tmp_path):
    tree = _tree(tmp_path, signals={"s": _signal()}, lane_map={"bugfix": ["s"]})
    profile = _Profile(promotions={"s": {"measured": "2026-06-01, no false positives"}})
    cfg = resolve_gate_config(_Change("bugfix"), profile=profile, tree=tree)
    assert cfg.get("test_files") == "warn"
    assert cfg.test_files_required is False
    assert cfg.get("spec_verify") == "run"


def test_a_warn_severity_exit_signal_does_not_buy_the_discount(tmp_path):
    """The promotion is unrecorded, so the signal evaluates at WARN and the discount is unpaid."""
    tree = _tree(tmp_path, signals={"s": _signal()}, lane_map={"bugfix": ["s"]})
    with pytest.raises(ConditionalLaneRefused) as exc:
        resolve_gate_config(_Change("bugfix"), profile=_Profile(), tree=tree)
    assert exc.value.reason_class == ConditionalLaneRefused.NOT_ENFORCED
    assert "s" in str(exc.value)


def test_an_enforced_signal_that_cannot_FIRE_does_not_buy_the_discount(tmp_path):
    """ENFORCE severity is not the same statement as "this blocks", and the gap between them
    was in the first implementation of this module.

    `_KIND_HANDLERS` is empty by design in this version, so a declared signal is unevaluated;
    an unevaluated outcome blocks only under `sole_enforcement`. Without it, the signal reaches
    ENFORCE by promotion and can never fail a gate — the entrance gets cheaper and nothing stops
    the defect returning. Verifying the severity mechanism while the result stays silent is the
    class this module was written against, arriving inside it.
    """
    tree = _tree(tmp_path, signals={"s": _signal(sole_enforcement=False)},
                 lane_map={"bugfix": ["s"]})
    profile = _Profile(promotions={"s": {"measured": "2026-06-01"}})

    with pytest.raises(ConditionalLaneRefused) as exc:
        resolve_gate_config(_Change("bugfix"), profile=profile, tree=tree)
    assert exc.value.reason_class == ConditionalLaneRefused.UNEVALUABLE
    assert "sole_enforcement" in str(exc.value), (
        "the refusal must name the one thing the project can do about it")


def test_a_delegated_answer_makes_a_signal_eligible(tmp_path):
    """The third route, and the one the first implementation missed.

    `lane_gate._detector_for` tries a declared `answer` BEFORE any handler and independently of
    the handler table, so a delegating signal can fire in every version. Omitting this refused a
    discount that had in fact been paid — safe in direction, and it disqualified exactly the
    route a project would reach for when it already publishes the verified value.
    """
    signal = _signal(sole_enforcement=False)
    signal["answer"] = {"command": "bugs", "field": "fixedWithoutRegressionTest"}
    tree = _tree(tmp_path, signals={"s": signal}, lane_map={"bugfix": ["s"]})
    profile = _Profile(promotions={"s": {"measured": "2026-06-01"}})

    cfg = resolve_gate_config(_Change("bugfix"), profile=profile, tree=tree)
    assert cfg.get("test_files") == "warn"


def test_the_signal_the_entry_accepts_is_the_signal_the_gate_then_RUNS(tmp_path, monkeypatch):
    """The two halves joined, because separately each one is compatible with nothing happening.

    `require_exit_obligation` answers *is there a route by which this can block*. That is a
    statement about eligibility, and this repo's rule book names the class where a mechanism is
    verified while the result stays silent. So the same tree, the same signal and the same
    declared answer are pushed through BOTH: the lane is granted, and the gate then actually
    invokes the project's published command and fires on what it returns.

    The published shape here is the one a project would really send — a bare list of stable
    identifiers under a nested plain path — because `lane_gate` refuses a per-row object and
    forbids a projection in `field`, so anything else would be testing a shape nobody can use.
    """
    import types

    from set_orch import project_status

    signal = _signal(sole_enforcement=False)
    signal["answer"] = {"command": "bugs", "field": "laneSignals.fixedWithoutRegressionTest"}
    tree = _tree(tmp_path, signals={"s": signal}, lane_map={"bugfix": ["s"]})
    profile = _Profile(promotions={"s": {"measured": "2026-06-01"}})

    calls: list = []
    monkeypatch.setattr(project_status, "resolve_status_config",
                        lambda path: types.SimpleNamespace(commands=("bugs",),
                                                           write_commands=()))
    monkeypatch.setattr(project_status, "query",
                        lambda path, command, args=None, config=None: (
                            calls.append(command) or types.SimpleNamespace(
                                ok=True, error_class=None,
                                data={"laneSignals":
                                      {"fixedWithoutRegressionTest": ["BUG-7"]}})))

    # half one: the entrance is granted
    cfg = resolve_gate_config(_Change("bugfix"), profile=profile, tree=tree)
    assert cfg.get("test_files") == "warn"

    # half two: the same signal is then really evaluated, by asking the project
    from set_orch import lane_gate

    report = lane_gate.build_report(str(tree), profile=profile)
    assert calls == ["bugs"], "the published command was never invoked"
    assert [o.status for o in report.outcomes] == ["fired"]
    assert report.fired[0].violations == ("BUG-7",)


def test_a_registered_handler_also_makes_a_signal_eligible(tmp_path, monkeypatch):
    """The other route to blocking, so the check is not secretly a `sole_enforcement` test.

    A project should become eligible when a handler ships, without redeclaring anything — which
    is why the handler table is consulted at call time rather than cached.
    """
    from set_orch import lane_gate

    monkeypatch.setitem(lane_gate._KIND_HANDLERS, "fixed-defect-without-test",
                        lambda signal, path: [])
    tree = _tree(tmp_path, signals={"s": _signal(sole_enforcement=False)},
                 lane_map={"bugfix": ["s"]})
    profile = _Profile(promotions={"s": {"measured": "2026-06-01"}})

    cfg = resolve_gate_config(_Change("bugfix"), profile=profile, tree=tree)
    assert cfg.get("test_files") == "warn"


def test_unevaluable_and_not_enforced_are_distinguishable(tmp_path):
    """Opposite next actions: record the measurement, versus declare sole enforcement."""
    warn = _tree(tmp_path / "a", signals={"s": _signal(promotion_severity="warn")},
                 lane_map={"bugfix": ["s"]})
    silent = _tree(tmp_path / "b", signals={"s": _signal(sole_enforcement=False)},
                   lane_map={"bugfix": ["s"]})
    profile = _Profile(promotions={"s": {"measured": "2026-06-01"}})

    with pytest.raises(ConditionalLaneRefused) as first:
        require_exit_obligation("bugfix", warn, profile)
    with pytest.raises(ConditionalLaneRefused) as second:
        require_exit_obligation("bugfix", silent, profile)

    assert first.value.reason_class == ConditionalLaneRefused.NOT_ENFORCED
    assert second.value.reason_class == ConditionalLaneRefused.UNEVALUABLE


def test_a_signal_whose_own_promotion_asks_for_warn_does_not_qualify(tmp_path):
    tree = _tree(tmp_path, signals={"s": _signal(promotion_severity="warn")},
                 lane_map={"bugfix": ["s"]})
    with pytest.raises(ConditionalLaneRefused) as exc:
        resolve_gate_config(_Change("bugfix"),
                            profile=_Profile(promotions={"s": "evidence"}), tree=tree)
    assert exc.value.reason_class == ConditionalLaneRefused.NOT_ENFORCED


def test_no_mapping_and_not_enforced_are_distinguishable(tmp_path):
    """Merged, a project that has not earned the promotion reads identically to one that
    declared nothing — and those two need opposite next actions."""
    no_map = _tree(tmp_path / "a", signals={"s": _signal()})
    warn = _tree(tmp_path / "b", signals={"s": _signal()}, lane_map={"bugfix": ["s"]})

    with pytest.raises(ConditionalLaneRefused) as first:
        require_exit_obligation("bugfix", no_map)
    with pytest.raises(ConditionalLaneRefused) as second:
        require_exit_obligation("bugfix", warn)

    assert first.value.reason_class != second.value.reason_class
    assert first.value.reason_class == ConditionalLaneRefused.NO_MAPPING
    assert second.value.reason_class == ConditionalLaneRefused.NOT_ENFORCED


def test_a_mapping_naming_an_undeclared_signal_is_its_own_reason(tmp_path):
    tree = _tree(tmp_path, signals={"s": _signal()}, lane_map={"bugfix": ["not-declared"]})
    with pytest.raises(ConditionalLaneRefused) as exc:
        require_exit_obligation("bugfix", tree, _Profile(promotions={"s": "e"}))
    assert exc.value.reason_class == ConditionalLaneRefused.UNKNOWN_SIGNAL
    assert "not-declared" in str(exc.value)


def test_a_refused_mapping_is_not_reported_as_no_mapping(tmp_path):
    """The project declared something; blaming it for declaring nothing names the wrong cause."""
    tree = _tree(tmp_path, signals={"s": _signal()}, lane_map={"bugfixes": ["s"]})
    with pytest.raises(ConditionalLaneRefused) as exc:
        require_exit_obligation("bugfix", tree)
    assert exc.value.reason_class == ConditionalLaneRefused.MAP_REFUSED
    assert "bugfixes" in str(exc.value)


def test_no_tree_is_a_refusal_not_a_grant():
    """A caller that forgets the tree gets a refusal, never a silent discount."""
    with pytest.raises(ConditionalLaneRefused) as exc:
        resolve_gate_config(_Change("bugfix"))
    assert exc.value.reason_class == ConditionalLaneRefused.NO_TREE


def test_the_conditional_set_holds_exactly_one_name():
    """A second name without a second delta would be the false gate the verdict names.

    The ordering constraint is that a differentiated pipeline is built first and alone, and the
    taxonomy comes only once two provably different pipelines exist to choose between. This
    test is where that constraint is enforced rather than remembered.
    """
    assert CONDITIONAL_CHANGE_TYPES == frozenset({"bugfix"})


def test_every_conditional_type_has_a_profile_to_grant():
    """A conditional type with no profile would refuse forever and grant nothing."""
    for name in CONDITIONAL_CHANGE_TYPES:
        assert name in UNIVERSAL_DEFAULTS, name
