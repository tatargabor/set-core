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
