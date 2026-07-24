"""The lane gate: what it reports, and the four things it must never do."""

import json
import types

import pytest

from set_orch import lane_gate as lg


def _decl(**overrides):
    raw = {
        "lane": "changing",
        "condition": {"kind": "new_module", "pattern": "src/*"},
        "scope": "per-change-verification",
        "baseline": [],
        "promotion": {"measure": "half real for two weeks"},
        "triggering_case": "2026-07-20 INC-4: a new module shipped with no spec",
        "exclusions": ["docs/**"],
    }
    raw.update(overrides)
    return raw


def _tree(tmp_path, signals=None):
    if signals is not None:
        (tmp_path / "set").mkdir(exist_ok=True)
        (tmp_path / "set" / "lane-signals.json").write_text(json.dumps(signals))
    return str(tmp_path)


def _change(change_type="infrastructure"):
    return types.SimpleNamespace(change_type=change_type)


# ── absence is not a pass ──────────────────────────────────────────────────────────

def test_a_project_with_no_declarations_is_skipped_not_passed(tmp_path):
    """`pass` would be an all-clear about a check that never ran.

    The status is the part that gets counted in a gate summary, so it carries the
    distinction rather than leaving it to the output text.
    """
    result = lg.execute_lane_gate("c", _change(), _tree(tmp_path))

    assert result.status == "skipped"
    assert "not a clean result" in result.output


def test_the_absent_message_does_not_read_as_zero_violations(tmp_path):
    result = lg.execute_lane_gate("c", _change(), _tree(tmp_path))

    assert "0 violations" not in result.output
    assert "no violations" not in result.output.lower()


# ── an unhandled condition is unevaluated, never a pass ────────────────────────────

def test_an_unhandled_condition_kind_is_unevaluated_not_a_pass(tmp_path):
    """Layer 1 reads conditions; it does not know what any project's kind means.

    Returning an empty list for an unknown kind would make every unrecognised condition
    look like a clean result — the reassuring direction, so it is the one to get right.
    """
    tree = _tree(tmp_path, {"sig": _decl()})

    report = lg.build_report(tree, change=_change())

    assert len(report.unevaluated) == 1
    assert report.did_not_fire == []


def test_all_signals_unevaluated_is_SKIPPED_not_a_pass(tmp_path):
    """Nothing fired while nothing could run is the absent case wearing a better status.

    Found by running the gate against a declaring tree instead of reading the code: it
    answered `pass`. That is the shape it meets FIRST in the real world — `_KIND_HANDLERS`
    is empty, so today every declared signal is unevaluated — and `pass` is the reassuring
    direction, in the one place a reader believes an all-clear.

    The earlier tests here checked `report.unevaluated` and `did_not_fire`, never the gate
    STATUS in this state, which is the field a gate summary counts.
    """
    result = lg.execute_lane_gate("c", _change(), _tree(tmp_path, {"sig": _decl()}))

    assert result.status == "skipped"
    assert result.status != "pass"


def test_pass_requires_that_something_actually_ran(monkeypatch, tmp_path):
    """The mirror: `pass` is still reachable, so the fix is not "never pass"."""
    tree = _tree(tmp_path, {"sig": _decl()})
    monkeypatch.setitem(lg._KIND_HANDLERS, "new_module", lambda s, p: [])

    result = lg.execute_lane_gate("c", _change(), tree)

    assert result.status == "pass"


def test_one_evaluated_and_one_not_does_not_earn_a_pass(monkeypatch, tmp_path):
    """A partial run is not a clean run, and the status is what gets counted."""
    tree = _tree(tmp_path, {
        "ran": _decl(condition={"kind": "new_module", "pattern": "src/*"}),
        "could-not": _decl(condition={"kind": "something_this_version_cannot_read"}),
    })
    monkeypatch.setitem(lg._KIND_HANDLERS, "new_module", lambda s, p: [])

    result = lg.execute_lane_gate("c", _change(), tree)

    assert result.status == "skipped"


def test_an_unhandled_kind_does_not_blame_the_projects_tree(tmp_path):
    """Two unevaluable reasons that are opposites must not share one message.

    The evaluator's `None` means "the condition's input is absent" — a statement about the
    project's tree. A missing handler is a statement about set-core. Collapsed into one,
    the message sends someone looking for a file that is not missing.
    """
    tree = _tree(tmp_path, {"sig": _decl()})

    output = lg.format_output(lg.build_report(tree, change=_change()), change=_change())

    assert "input is absent" not in output
    assert "not at fault" in output


def test_the_summary_line_does_not_report_zero_debt_for_debt_it_never_checked(tmp_path):
    """The summary line is the most-read copy, so a false zero costs most there.

    Measured by the peer on a real tree: ten declared baseline entries printed as
    "outstanding baselined debt: 0", because the count was accumulated along the
    evaluation path and no condition handler was registered.
    """
    tree = _tree(tmp_path, {"sig": _decl(baseline=["D-1", "D-2", "D-3"])})

    output = lg.format_output(lg.build_report(tree, change=_change()), change=_change())

    assert "3 declared" in output
    assert "0 checked" in output
    assert "NOT CHECKED" in output
    assert "debt: 0" not in output


def test_the_framework_applies_exclusions_not_each_handler(monkeypatch, tmp_path):
    """The self-inclusion waiver rests on the exclusion actually taking effect.

    `_refuse_if_self_inclusive` stops refusing a self-selecting condition as soon as an
    exclusion covers the declaration file. If honouring exclusions were left to each
    handler, a signal would buy its way past that guard with a promise nothing enforces —
    and it would hold exactly until the second handler was written.

    Raised by an integration peer who hit the mirror on their own side: listing their
    declaration file in `exclusions` short-circuited the whole guard for that signal. An
    escape hatch that disables the protection of the signal it belongs to looks like care
    from the outside.
    """
    tree = _tree(tmp_path, {"sig": _decl(exclusions=["docs/**", "generated/**"])})
    monkeypatch.setitem(lg._KIND_HANDLERS, "new_module",
                        lambda s, p: ["src/real/index.ts", "docs/guide.md",
                                      "generated/api-client.ts"])

    report = lg.build_report(tree, change=_change())

    assert report.fired[0].violations == ("src/real/index.ts",), (
        "a handler that ignores exclusions must not be able to report an excluded path")


def test_an_exclusion_cannot_empty_a_result_a_handler_could_not_produce(monkeypatch,
                                                                        tmp_path):
    """The mirror: filtering must not turn "could not decide" into "found nothing"."""
    tree = _tree(tmp_path, {"sig": _decl()})
    monkeypatch.setitem(lg._KIND_HANDLERS, "new_module", lambda s, p: None)

    report = lg.build_report(tree, change=_change())

    assert len(report.unevaluated) == 1
    assert report.did_not_fire == []


def test_a_non_path_violation_is_not_silently_dropped_by_exclusions(monkeypatch, tmp_path):
    """A handler may return ids, not paths. Only path-shaped values can match a glob."""
    tree = _tree(tmp_path, {"sig": _decl(exclusions=["docs/**"])})
    monkeypatch.setitem(lg._KIND_HANDLERS, "new_module", lambda s, p: ["DEF-77", "BUG-3"])

    report = lg.build_report(tree, change=_change())

    assert set(report.fired[0].violations) == {"DEF-77", "BUG-3"}


def test_the_output_names_unevaluated_signals(tmp_path):
    tree = _tree(tmp_path, {"sig": _decl()})

    output = lg.format_output(lg.build_report(tree, change=_change()), change=_change())

    assert "[UNEVALUATED] sig" in output
    assert "could not be evaluated" in output


# ── a contradiction names the declared type AND the artefact, together ─────────────

def test_a_firing_signal_is_reported_with_the_declared_change_type(monkeypatch, tmp_path):
    """Either half alone reads as normal; only the pair is the finding."""
    tree = _tree(tmp_path, {"sig": _decl()})
    monkeypatch.setitem(lg._KIND_HANDLERS, "new_module", lambda s, p: ["src/billing/index.ts"])

    report = lg.build_report(tree, change=_change("infrastructure"))
    output = lg.format_output(report, change=_change("infrastructure"))

    assert "change_type='infrastructure'" in output
    assert "src/billing/index.ts" in output


def test_the_lane_label_is_printed_as_NOT_compared(monkeypatch, tmp_path):
    """The field name promises a comparison the framework deliberately does not make.

    Nothing maps a project's lane vocabulary onto set-core's change types, and nothing
    should — that mapping is domain. But a reader seeing `lane` and `change_type` adjacent
    assumes one was checked against the other, so the limit goes where the reader is
    standing. Caught by the peer reading this code, not by its author.
    """
    tree = _tree(tmp_path, {"sig": _decl()})
    monkeypatch.setitem(lg._KIND_HANDLERS, "new_module", lambda s, p: ["src/x/index.ts"])

    output = lg.format_output(lg.build_report(tree, change=_change()), change=_change())

    assert "'changing'" in output, "the declared lane label must still be visible"
    assert "not compared" in output


def test_a_warn_signal_does_not_fail_the_gate(monkeypatch, tmp_path):
    tree = _tree(tmp_path, {"sig": _decl()})
    monkeypatch.setitem(lg._KIND_HANDLERS, "new_module", lambda s, p: ["src/x/index.ts"])

    result = lg.execute_lane_gate("c", _change(), tree)

    assert result.status == "warn-fail"


def test_warn_does_not_block_while_baseline_growth_DOES_by_the_real_predicate(monkeypatch,
                                                                              tmp_path):
    """"Warns but does not block" is a claim about the runner, so ask the runner.

    Reading `"warn-fail"` and concluding it warns is the name taken for the behaviour. The
    merge is actually decided by two things together — `status == "fail"` in
    `gate_runner._handle_*`, and `GateConfig.is_blocking(name)` — and the lane gate needs
    them to disagree: a fired WARN signal must pass through, while baseline growth must
    stop the merge regardless of severity. Both halves are asserted against the real
    predicate, because a gate configured warn-only would silently un-block the second one.
    """
    from set_orch.gate_profiles import GateConfig

    tree = _tree(tmp_path, {"sig": _decl()})
    monkeypatch.setitem(lg._KIND_HANDLERS, "new_module", lambda s, p: ["src/x/index.ts"])
    warned = lg.execute_lane_gate("c", _change(), tree)

    assert warned.status != "fail", (
        "a WARN signal must not block the merge until its declared promotion is measured")

    # …and the blocking half is real, not nominal: an unconfigured gate is blocking, so the
    # "fail" the gate emits on baseline growth actually stops the queue.
    assert GateConfig({}).is_blocking(lg.GATE_NAME) is True


def test_baseline_growth_fails_the_gate_even_at_warn(monkeypatch, tmp_path):
    from set_orch import lane_evaluator as ev
    from set_orch.lane_signals import LaneSignal

    signal = LaneSignal(name="sig", lane="changing", condition={"kind": "new_module"},
                        scope="per-change-verification", baseline=(),
                        promotion={"measure": "x"},
                        triggering_case="2026-07-20 INC-4: y", exclusions=("docs/**",))
    report = ev.evaluate([signal], detect=lambda s: [], baseline_additions={"sig": ["N-1"]})

    assert report.blocks is True
    assert "BASELINE GROWTH" in lg.format_output(report, change=_change())


# ── no verdict, and no new obligations on a change ────────────────────────────────

def test_the_output_carries_no_lane_correct_verdict(monkeypatch, tmp_path):
    tree = _tree(tmp_path, {"sig": _decl()})
    monkeypatch.setitem(lg._KIND_HANDLERS, "new_module", lambda s, p: [])

    output = lg.format_output(lg.build_report(tree, change=_change()), change=_change())

    assert "cannot show there is none" in output
    for claim in ("lane is correct", "all clear", "verdict:"):
        assert claim not in output.lower()


def test_the_gate_calls_no_model(tmp_path, monkeypatch):
    """Asserted by making the escape hatches explode, not by reading the source."""
    import subprocess

    def _boom(*a, **kw):
        raise AssertionError("the lane gate must not spawn a model or a service")

    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(subprocess, "Popen", _boom)

    result = lg.execute_lane_gate("c", _change(), _tree(tmp_path, {"sig": _decl()}))

    assert result.status in ("warn-fail", "pass", "skipped")


def test_the_gate_reads_no_new_field_off_the_change(tmp_path):
    """A change carrying only what it carries today must work.

    A gate that needed a new field would put the cost on every change and add another
    thing to get right in advance — the entrance classification this capability replaces.
    """
    bare = types.SimpleNamespace()

    result = lg.execute_lane_gate("c", bare, _tree(tmp_path, {"sig": _decl()}))

    assert result.status in ("warn-fail", "pass", "skipped")


# ── registry wiring ───────────────────────────────────────────────────────────────

def test_the_gate_registers_with_no_per_change_type_defaults():
    """A gate whose job is to doubt the declared type must not be switched off by it.

    Non-empty `defaults` would let `change_type: infrastructure` skip the very gate that
    exists to check whether "infrastructure" was true — the hole it closes, wired in as
    configuration.
    """
    definition = lg.gate_definition()

    assert definition.name == "lane"
    assert definition.defaults == {}
    assert definition.executor is lg.execute_lane_gate


# ── registered in the live pipeline, and inert there ──────────────────────────────

def test_the_lane_gate_is_actually_in_the_universal_gate_list():
    """A gate that exists but is never registered is a "built" claim that overclaims.

    Measured against the real list rather than the definition in isolation, because the
    two can disagree — and today's lesson is that the shorter, more-read artefact is the
    one that drifts.
    """
    from set_orch.verifier import _get_universal_gates

    names = [g.name for g in _get_universal_gates()]

    assert "lane" in names, "the gate is built but nothing runs it"


def test_registering_it_changed_no_other_gate():
    from set_orch.verifier import _get_universal_gates

    names = [g.name for g in _get_universal_gates()]

    for existing in ("build", "test", "scope_check", "test_files", "review", "rules",
                     "spec_verify"):
        assert existing in names
    assert len(names) == len(set(names)), "a duplicate gate name would silently shadow"


def test_adding_the_gate_moved_no_other_gate_in_the_RESOLVED_order():
    """Membership is not order, and order is what actually runs.

    `before:end` is shared with `review`, and the resolver places that group by list
    position — so a new entry there is exactly the kind of change that can shuffle a
    neighbour without changing the set of names. Measured by resolving twice: once with
    the gate, once with it filtered out, and asserting the only difference is the
    insertion.
    """
    from set_orch.gate_runner import _resolve_gate_order
    from set_orch.verifier import _get_universal_gates

    gates = _get_universal_gates()
    with_lane = [g.name for g in _resolve_gate_order(gates)]
    without_lane = [g.name for g in _resolve_gate_order([g for g in gates
                                                         if g.name != "lane"])]

    assert [n for n in with_lane if n != "lane"] == without_lane
    assert with_lane.index("lane") > with_lane.index("review"), (
        "the lane is measured AFTER the work, so the gate belongs late in the chain")


# ── the confidentiality boundary ──────────────────────────────────────────────────

def test_no_declaration_content_is_persisted_into_the_frameworks_own_tree(tmp_path):
    """set-core may READ a project's declarations and must persist nothing derived.

    A signal's condition carries a project's path conventions and defect-store names.
    Asserted by watching for writes anywhere outside the project tree during a run,
    because the carriers that cross this boundary do so without anyone deciding to —
    a cache, a debug dump, an error path that helpfully records the input.
    """
    import builtins
    from pathlib import Path as _P

    repo_root = _P(lg.__file__).resolve().parents[2]
    opened_for_write = []

    real_open = builtins.open

    def watching_open(file, mode="r", *a, **kw):
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            resolved = _P(str(file)).resolve()
            if not str(resolved).startswith(str(_P(tmp_path).resolve())):
                opened_for_write.append(str(resolved))
        return real_open(file, mode, *a, **kw)

    monkey = pytest.MonkeyPatch()
    monkey.setattr(builtins, "open", watching_open)
    try:
        lg.execute_lane_gate("c", _change(), _tree(tmp_path, {"sig": _decl()}))
    finally:
        monkey.undo()

    outside_repo_or_in_it = [p for p in opened_for_write if str(repo_root) in p]
    assert opened_for_write == [], f"wrote outside the project tree: {opened_for_write}"
    assert outside_repo_or_in_it == []


_MARKERS = ("acme-orders", "src/acme/**", "data/acme-defects.jsonl", "ACME-77")


def test_no_declaration_content_reaches_the_frameworks_logs_on_ANY_path(tmp_path, caplog):
    """The whole gate path, not one module — a log leaves the machine, a tmp file does not.

    Every branch is walked in one run: a signal that fires, one whose condition kind has no
    handler, one refused outright, and one attempting baseline growth. The markers are
    checked against every record from every `set_orch.lane_*` logger, because the carrier
    that crosses the confidentiality boundary is whichever one nobody thought about.
    """
    import logging

    declared = {
        _MARKERS[0]: {
            "lane": "restoring",
            "condition": {"kind": "new_module", "pattern": _MARKERS[1],
                          "store": _MARKERS[2]},
            "scope": "per-change-verification",
            "baseline": [_MARKERS[3]],
            "promotion": {"severity": "enforce", "measure": f"until {_MARKERS[3]} clears"},
            "triggering_case": f"2026-07-20 {_MARKERS[3]}: shipped with no test",
            "exclusions": ["docs/**"],
        },
        f"{_MARKERS[0]}-refused": {
            "lane": "restoring",
            "condition": {"kind": "loc_delta", "over": 300, "pattern": _MARKERS[1]},
            "scope": "per-change-verification",
            "baseline": [],
            "promotion": {"measure": "x"},
            "triggering_case": f"2026-07-20 {_MARKERS[3]}",
            "exclusions": ["docs/**"],
        },
    }
    tree = _tree(tmp_path, declared)

    with caplog.at_level(logging.DEBUG):
        result = lg.execute_lane_gate("c", _change(), tree)

    logged = "\n".join(r.getMessage() for r in caplog.records
                       if r.name.startswith("set_orch.lane"))
    assert logged, "the gate must still log its shape — silence is its own defect"
    for marker in _MARKERS:
        assert marker not in logged, f"{marker!r} reached the framework's own log"

    # …and none of it was withheld from the project's own report.
    assert _MARKERS[0] in result.output
