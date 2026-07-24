"""The lane signal reader: what it refuses, and what it must never claim.

Every test here was written against a requirement in
`openspec/changes/lane-contradiction-detection/`, and each one is checked by stashing the
implementation — a test that also passes without the code proves nothing and looks like
proof forever.
"""

import json

import pytest

from set_orch import lane_signals as ls


def _valid(**overrides):
    """A declaration that passes, so each test can break exactly one thing."""
    raw = {
        "lane": "restoring",
        "condition": {"kind": "fixed_defect_without_test", "store": "data/defects.jsonl"},
        "scope": "per-change-verification",
        "baseline": ["DEF-11", "DEF-42"],
        "promotion": {"measure": "half the signals real for two consecutive weeks"},
        "triggering_case": "2026-07-20 DEF-77: a fix shipped with no regression test",
        "exclusions": ["docs/**", "openspec/**", "tests/**"],
    }
    raw.update(overrides)
    return raw


# ── the six fields, and why absence is a refusal rather than a default ──────────────

@pytest.mark.parametrize("missing", ls.REQUIRED_FIELDS)
def test_a_missing_required_field_is_refused_by_name(missing):
    raw = _valid()
    del raw[missing]

    with pytest.raises(ls.SignalRefused) as exc:
        ls.parse_signal("sig", raw)

    assert missing in str(exc.value), "the error must name the field, not just fail"


def test_missing_exclusions_is_refused_too():
    """Exclusions are not optional: without them a pattern signal reports its own rule."""
    raw = _valid()
    del raw["exclusions"]

    with pytest.raises(ls.SignalRefused) as exc:
        ls.parse_signal("sig", raw)

    assert "exclusions" in str(exc.value)


# ── the condition is a shape, never a quantity ─────────────────────────────────────

@pytest.mark.parametrize("kind", sorted(ls.VOLUME_KINDS))
def test_a_volume_condition_is_refused_naming_volume(kind):
    """A size threshold fires hardest on the safest population, so it is refused outright.

    Refused by KIND rather than by inspecting the threshold — otherwise the same rule
    arrives expressed as `{"kind": "lines_changed", "over": 300}` versus
    `{"kind": "churn", "min": 300}` and only one is caught.
    """
    with pytest.raises(ls.SignalRefused) as exc:
        ls.parse_signal("sig", _valid(condition={"kind": kind, "over": 300}))

    assert "volume" in str(exc.value).lower()


def test_a_shape_condition_is_accepted():
    signal = ls.parse_signal("sig", _valid(
        condition={"kind": "new_module", "pattern": "src/*/index.ts"}))

    assert signal.condition["kind"] == "new_module"


# ── the triggering case: the date is machine-checked, the reasoning is not ──────────

def test_a_signal_with_no_dated_triggering_case_is_refused():
    with pytest.raises(ls.SignalRefused) as exc:
        ls.parse_signal("sig", _valid(triggering_case="because it seemed sensible"))

    assert "date" in str(exc.value).lower()


def test_a_bare_date_is_accepted_and_reported_as_unexplained():
    """The gate checks the date and REFUSES to judge the reasoning.

    Whether a paragraph explains anything is not mechanically decidable — measured
    elsewhere, two independent proxies for it misclassified in opposite directions. So a
    bare date passes, and `is_explained` is False so review has something to act on
    rather than a silent pass. A gate that implied it had checked the reasoning would be
    the false gate this whole capability exists to remove.
    """
    signal = ls.parse_signal("sig", _valid(triggering_case="2026-01-01"))

    assert signal.is_explained is False

    explained = ls.parse_signal("sig", _valid(
        triggering_case="2026-07-20 DEF-77: a fix shipped with no regression test"))
    assert explained.is_explained is True


# ── a signal must not evaluate the corpus that defines it ──────────────────────────

def test_a_scope_that_swallows_the_declaration_is_refused():
    with pytest.raises(ls.SignalRefused) as exc:
        ls.parse_signal("sig", _valid(scope="set/*.json", exclusions=["docs/**"]),
                        declared_at="set/lane-signals.json")

    assert "itself" in str(exc.value) or "self" in str(exc.value).lower()


def test_a_CONDITION_that_selects_the_declaration_is_refused():
    """The guard has to be aimed at the field that actually selects files.

    Refuted pattern, measured: the first implementation checked `declared_at` against
    `scope` only. `scope` is the PHASE a signal runs in, compared by equality in the
    evaluator — a phase name glob-matches no path, so that refusal could never fire on a
    well-formed declaration, while a condition patterned `set/*.json` declared inside
    `set/lane-signals.json` walked straight through. A guard that cannot fire on any
    legitimate input is a false gate: it is cited as protection and protects nothing.
    """
    with pytest.raises(ls.SignalRefused) as exc:
        ls.parse_signal("sig", _valid(
            condition={"kind": "new_module", "pattern": "set/*.json"},
            scope="per-change-verification",
            exclusions=["docs/**"]),
            declared_at="set/lane-signals.json")

    assert "declaration itself" in str(exc.value)
    assert "pattern" in str(exc.value), "the error must name WHICH key selected it"


def test_the_condition_check_looks_at_every_string_not_a_chosen_key_name():
    """A closed list of key names (`pattern`, `glob`, `paths`) would be a narrowing."""
    with pytest.raises(ls.SignalRefused):
        ls.parse_signal("sig", _valid(
            condition={"kind": "new_module", "watch_here": "set/*.json"},
            exclusions=["docs/**"]),
            declared_at="set/lane-signals.json")


@pytest.mark.parametrize("condition", [
    {"kind": "k", "globs": ["set/*.json"]},
    {"kind": "k", "where": {"glob": "set/*.json"}},
    {"kind": "k", "a": [{"b": {"c": ["set/*.json"]}}]},
])
def test_a_NESTED_self_selecting_pattern_is_refused(condition):
    """Second refuted pattern of the same class, one level down: TRAVERSAL DEPTH.

    Measured by the peer against this code and reproduced here: the checks walked
    `condition.items()` once and stopped, so of six disguises exactly one was refused. The
    list form is not exotic — it is the *likely* way to write several path patterns, so the
    probable shape was the evading shape, in the reassuring direction.

    Worth stating as a rule rather than a fix: **a repair for a narrowing is itself a
    candidate narrowing until its own traversal is checked.** The key-name narrowing was
    closed hours before this one, by the same reasoning, and the replacement inherited the
    defect at a different axis.
    """
    with pytest.raises(ls.SignalRefused) as exc:
        ls.parse_signal("sig", _valid(condition=condition, exclusions=["docs/**"]),
                        declared_at="set/lane-signals.json")

    assert "declaration itself" in str(exc.value)


@pytest.mark.parametrize("condition", [
    {"kind": "k", "limits": [{"over": 500}]},
    {"kind": "k", "where": {"over": 500}},
    {"kind": "k", "a": [{"b": [{"threshold": 7}]}]},
])
def test_a_NESTED_volume_threshold_is_refused(condition):
    """The load-bearing half of the same depth defect — a quantity at any nesting."""
    with pytest.raises(ls.SignalRefused) as exc:
        ls.parse_signal("sig", _valid(condition=condition))

    assert "volume" in str(exc.value).lower()


def test_the_recursive_walk_did_not_turn_legitimate_nesting_into_a_refusal():
    """The mirror, so the fix cannot be "refuse anything nested".

    The second case is the shape a real project declared: a list of test-file globs under
    a `fixed_defect_without_citing_test` condition. If the repair refused that, it would
    have closed the hole by making the feature unusable.
    """
    nested = ls.parse_signal("sig", _valid(
        condition={"kind": "k", "where": {"store": "data/defects.jsonl",
                                          "recursive": True, "depth": None}}))
    assert nested.condition["where"]["recursive"] is True

    listed = ls.parse_signal("sig", _valid(
        condition={"kind": "fixed_defect_without_citing_test",
                   "citing_globs": ["tests/**/*.spec.ts", "tests/**/*.test.ts"]}),
        declared_at="set/lane-signals.json")
    assert len(listed.condition["citing_globs"]) == 2


def test_a_condition_full_of_non_patterns_is_not_a_false_positive():
    """Most condition values are a project's vocabulary, not globs. None may match."""
    signal = ls.parse_signal("sig", _valid(
        condition={"kind": "fixed_defect_without_test", "store": "data/defects.jsonl",
                   "recursive": True, "depth": None}),
        declared_at="set/lane-signals.json")

    assert signal.condition["store"] == "data/defects.jsonl"


def test_an_exclusion_covers_the_condition_check_too(tmp_path):
    """The exclusion is the escape hatch, so it must work on the check that now fires."""
    signal = ls.parse_signal("sig", _valid(
        condition={"kind": "new_module", "pattern": "set/*.json"},
        exclusions=["set/lane-signals.json"]),
        declared_at="set/lane-signals.json")

    assert signal.condition["pattern"] == "set/*.json"


def test_an_exclusion_covering_the_declaration_makes_the_same_scope_legal():
    """The exclusion is the mechanism, so it must actually work — not merely be required."""
    signal = ls.parse_signal("sig", _valid(scope="set/*.json",
                                           exclusions=["set/lane-signals.json"]),
                             declared_at="set/lane-signals.json")

    assert signal.scope == "set/*.json"


# ── reading from the tree ──────────────────────────────────────────────────────────

def test_a_project_declaring_nothing_yields_no_signals_and_no_all_clear(tmp_path):
    """Absence must stay distinguishable from a clean run.

    `declared_nothing` is the field that keeps them apart. Without it a caller sees an
    empty signal list and reports "no violations", which is a false absence in the one
    place a reader would believe it.
    """
    result = ls.read_declarations(tmp_path)

    assert result.signals == []
    assert result.refusals == []
    assert result.declared_nothing is True


def test_recognisable_structure_does_not_synthesise_a_signal(tmp_path):
    """set-core holds no built-in signal, including one inferred from its own conventions."""
    (tmp_path / "openspec").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "set").mkdir()

    result = ls.read_declarations(tmp_path)

    assert result.declared_nothing is True


def test_one_refused_signal_does_not_disable_the_others(tmp_path):
    """A typo must not convert a guarded run into an unguarded one that looks identical."""
    (tmp_path / "set").mkdir()
    bad = _valid()
    del bad["scope"]
    (tmp_path / "set" / "lane-signals.json").write_text(json.dumps({
        "good-one": _valid(),
        "bad-one": bad,
        "good-two": _valid(condition={"kind": "new_module", "pattern": "src/*"}),
    }))

    result = ls.read_declarations(tmp_path)

    assert sorted(s.name for s in result.signals) == ["good-one", "good-two"]
    assert [r.signal_name for r in result.refusals] == ["bad-one"]
    assert result.declared_nothing is False, "refusals are not absence"


def test_the_reader_touches_no_service(tmp_path, monkeypatch):
    """Declarations are read while verifying a worktree — no database, no server.

    Asserted by making the escape hatches explode rather than by reading the source: a
    later refactor that reaches for a contract command would pass a source-inspection
    test and fail this one.
    """
    import socket
    import subprocess

    def _boom(*a, **kw):
        raise AssertionError("the reader must not reach a running system")

    monkeypatch.setattr(socket, "socket", _boom)
    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(subprocess, "Popen", _boom)

    (tmp_path / "set").mkdir()
    (tmp_path / "set" / "lane-signals.json").write_text(json.dumps({"s": _valid()}))

    result = ls.read_declarations(tmp_path)

    assert len(result.signals) == 1


def test_a_broken_profile_does_not_take_the_trees_signals_down(tmp_path):
    class Exploding:
        def lane_signals(self):
            raise RuntimeError("plugin is broken")

    (tmp_path / "set").mkdir()
    (tmp_path / "set" / "lane-signals.json").write_text(json.dumps({"s": _valid()}))

    result = ls.read_declarations(tmp_path, profile=Exploding())

    assert [s.name for s in result.signals] == ["s"]


def test_an_unreadable_declaration_file_is_a_refusal_not_an_absence(tmp_path):
    """Malformed JSON must not read as "this project declares nothing"."""
    (tmp_path / "set").mkdir()
    (tmp_path / "set" / "lane-signals.json").write_text("{not json")

    result = ls.read_declarations(tmp_path)

    assert result.signals == []
    assert len(result.refusals) == 1
    assert result.declared_nothing is False


# ── the confidentiality boundary: read it all, persist none of it ──────────────────

_MARKERS = ("acme-orders", "src/acme/**", "data/acme-defects.jsonl", "ACME-77")


def _declaration_full_of_project_material():
    return {
        _MARKERS[0]: {
            "lane": "restoring",
            "condition": {"kind": "new_module", "pattern": _MARKERS[1],
                          "store": _MARKERS[2]},
            "scope": "per-change-verification",
            "baseline": [_MARKERS[3]],
            "promotion": {"measure": "half real for two weeks"},
            "triggering_case": f"2026-07-20 {_MARKERS[3]}: shipped with no test",
            "exclusions": ["docs/**"],
        }
    }


def test_the_frameworks_own_log_carries_the_shape_and_none_of_the_content(tmp_path, caplog):
    """A log is a persistence carrier that leaves the machine without anyone deciding it.

    So the framework's logger gets counts and reason codes; the values — signal name, path
    pattern, defect-store path, incident id — stay in the returned refusal and the gate's
    output, which are the project's own report about its own tree.
    """
    import logging

    (tmp_path / "set").mkdir()
    (tmp_path / "set" / "lane-signals.json").write_text(
        json.dumps(_declaration_full_of_project_material()))

    with caplog.at_level(logging.DEBUG, logger="set_orch.lane_signals"):
        result = ls.read_declarations(tmp_path)

    assert len(result.signals) == 1, "the signal must still be READ in full"
    assert result.signals[0].condition["pattern"] == _MARKERS[1]

    logged = "\n".join(r.getMessage() for r in caplog.records)
    for marker in _MARKERS:
        assert marker not in logged, f"{marker!r} reached the framework's own log"


def test_a_refusal_logs_its_reason_and_not_the_offending_value(tmp_path, caplog):
    """The refusal is the case where quoting the input is most tempting."""
    import logging

    declared = _declaration_full_of_project_material()
    declared[_MARKERS[0]]["condition"] = {"kind": "loc_delta", "over": 300,
                                          "pattern": _MARKERS[1]}
    (tmp_path / "set").mkdir()
    (tmp_path / "set" / "lane-signals.json").write_text(json.dumps(declared))

    with caplog.at_level(logging.DEBUG, logger="set_orch.lane_signals"):
        result = ls.read_declarations(tmp_path)

    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "volume" in logged, "the reason must be logged — a silent refusal is worse"
    for marker in _MARKERS:
        assert marker not in logged

    # …while the developer still gets the whole story through the returned object.
    assert _MARKERS[0] in str(result.refusals[0])


# ── declared but not read: kept, never silently dropped ────────────────────────────

def test_a_declared_field_this_version_does_not_read_is_KEPT():
    """Discarding it is the false-absence class pointed inward.

    Surfaced when a project attached a reference to the canonical implementation of its own
    condition — attached precisely so a handler and the project's own gate could be
    COMPARED. Silently dropping it removes the comparison that would catch a divergence,
    and the project has no way to tell: its declaration parsed, so it believes the field
    arrived.
    """
    signal = ls.parse_signal("sig", _valid(
        canonical_implementation="scripts/gates/check-x.sh",
        published_answer={"command": "bugs", "field": "data.bugs[].hasTest"}))

    assert signal.extra["canonical_implementation"] == "scripts/gates/check-x.sh"
    assert signal.extra["published_answer"]["command"] == "bugs"


def test_a_known_field_never_lands_in_extra():
    """`extra` is derived from the field list, so a field cannot be both read and preserved.

    A second hard-coded set of names here would be the second copy that drifts — a field
    added to `REQUIRED_FIELDS` but forgotten in that set would appear as unread while being
    read, which is the mirror falsehood.
    """
    signal = ls.parse_signal("sig", _valid())

    assert signal.extra == {}
    for known in ls.REQUIRED_FIELDS + ("exclusions",):
        assert known not in signal.extra


def test_layer_one_does_not_name_any_of_the_preserved_keys():
    """Preserving them must not become interpreting them.

    The moment Layer 1 mentions `canonical_implementation` by name, it holds a project's
    vocabulary — the exact content this module refuses. It stores; the gate names the keys
    in its output; neither reads a value.
    """
    from pathlib import Path as _P
    source = _P(ls.__file__).read_text()

    for project_vocabulary in ("canonical_implementation", "published_answer",
                               "exempt_path_contains", "rename_detection"):
        assert project_vocabulary not in source


# ── the layer boundary ─────────────────────────────────────────────────────────────

def test_layer_one_holds_no_signal_of_its_own():
    """No built-in signal, path pattern, or defect-store name in the module.

    The corpus and the pattern are stated so this negative result can be re-run rather
    than believed: the module's source, checked for the file-ish and store-ish literals a
    smuggled-in signal would need.
    """
    from pathlib import Path as _P
    source = _P(ls.__file__).read_text()

    # The only paths the module may name are its own declaration location.
    assert source.count("set/lane-signals.json") <= 2
    for smuggled in ("src/", "*.ts", "bug-imports", "review-findings", "package.json"):
        assert smuggled not in source, f"Layer 1 must not name {smuggled!r}"


# ── two refuted patterns, held in tests so they cannot be reintroduced ─────────────
#
# Both were live defects in the first implementation, and both failed in the REASSURING
# direction: they accepted a declaration that should have been refused, or refused a
# project that should have been accepted. Neither would have been caught by the tests
# above, which is why they are written down here as fixtures rather than as comments.

@pytest.mark.parametrize("kind", ["loc_delta", "size_delta", "hunk_count", "weight"])
def test_a_volume_condition_under_an_UNLISTED_kind_is_still_refused(kind):
    """A closed list of kind names is a NARROWING, and narrowings lie reassuringly.

    Measured on the first implementation: `loc_delta`, `size_delta` and `hunk_count` were
    all accepted while its commit message claimed a project "cannot smuggle one past by
    expressing the threshold differently". Three of four disguises walked through. The
    discriminator is the SHAPE — a numeric threshold — not membership in a list of words.
    """
    with pytest.raises(ls.SignalRefused) as exc:
        ls.parse_signal("sig", _valid(condition={"kind": kind, "over": 300}))

    assert "volume" in str(exc.value).lower()


def test_a_shape_condition_may_still_carry_non_numeric_settings():
    """The threshold test must not become "any extra key is suspicious"."""
    signal = ls.parse_signal("sig", _valid(
        condition={"kind": "new_module", "pattern": "src/*/index.ts", "recursive": True}))

    assert signal.condition["recursive"] is True


def test_an_empty_baseline_is_a_declaration_of_zero_debt_not_an_omission():
    """The mirror failure: refusing the project that has nothing to baseline.

    A signal introduced into a clean tree legitimately has `baseline: []`, and that is the
    easiest case to adopt one in. The first implementation treated falsy as missing and
    refused it — failing in the direction that looks like strictness and reads as "you may
    not adopt this signal until you already have violations".
    """
    signal = ls.parse_signal("sig", _valid(baseline=[]))

    assert signal.baseline == ()


@pytest.mark.parametrize("field_name", ["lane", "scope", "triggering_case"])
def test_relaxing_the_baseline_did_not_let_empty_scalars_through(field_name):
    """The fix for the previous test is itself a narrowing, so it gets its own guard.

    Accepting `[]` by testing `is None` would also accept `""` for lane and scope, which
    say nothing — a repair that opens a wider hole than it closes.
    """
    with pytest.raises(ls.SignalRefused) as exc:
        ls.parse_signal("sig", _valid(**{field_name: ""}))

    assert field_name in str(exc.value)
