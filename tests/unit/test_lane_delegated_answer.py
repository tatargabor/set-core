"""The delegation path: the framework takes the project's published answer.

The rule these tests hold is not "read a field from JSON". It is that set-core must NOT
compute an answer the project already publishes — measured on a consumer before this
existed, where two implementations of one business figure drifted to 412% and 164% and a
customer noticed before either team did. So the load-bearing tests here are the *negative*
ones: that no handler runs when an answer is declared, and that a failed answer produces no
substitute.

The second thing they hold came from the same peer, with its own measurement: their whole
read contract lived on one machine and was absent from the remote branch, so a clone finds
nothing to ask rather than getting a wrong answer. A tree that does not publish must
therefore be distinguishable from a command that is broken — otherwise the gate says the
same thing about a project that never opted in and one whose gate just died, and it says it
in the reassuring direction.
"""

import json
import types

import pytest

from set_orch import lane_gate as lg
from set_orch import lane_signals as ls


def _answer_decl(**overrides):
    raw = {
        "lane": "restoring",
        "condition": {"kind": "fixed_defect_without_citing_test"},
        "scope": "per-change-verification",
        "baseline": [],
        "promotion": {"measure": "half real for two weeks"},
        "triggering_case": "2026-07-12 INC-9: twelve fixed defects, no citing test",
        "exclusions": ["docs/**"],
        "answer": {"command": "bugs", "field": "laneSignals.fixedWithoutTest"},
    }
    raw.update(overrides)
    return raw


def _tree(tmp_path, signals):
    (tmp_path / "set").mkdir(exist_ok=True)
    (tmp_path / "set" / "lane-signals.json").write_text(json.dumps(signals))
    return str(tmp_path)


def _config(commands=("bugs",), write_commands=()):
    return types.SimpleNamespace(commands=tuple(commands),
                                 write_commands=tuple(write_commands))


def _ok(data):
    return types.SimpleNamespace(ok=True, data=data, error_class=None)


def _failure(error_class):
    return types.SimpleNamespace(ok=False, data=None, error_class=error_class)


@pytest.fixture
def contract(monkeypatch):
    """A stub status contract. `calls` records every command actually invoked."""
    state = types.SimpleNamespace(config=_config(), result=_ok({}), calls=[])

    from set_orch import project_status

    monkeypatch.setattr(project_status, "resolve_status_config",
                        lambda path: state.config)

    def _query(path, command, args=None, config=None):
        state.calls.append(command)
        return state.result

    monkeypatch.setattr(project_status, "query", _query)
    return state


def _report(tmp_path, contract, **overrides):
    return lg.build_report(_tree(tmp_path, {"fixed-without-test": _answer_decl(**overrides)}))


# ── the agreement itself ───────────────────────────────────────────────────────────

def test_the_published_answer_is_taken_and_the_handler_is_not_consulted(
        tmp_path, contract, monkeypatch):
    """A declared answer wins over a handler for the same kind — the order is the rule.

    If a handler ran while the project publishes the value, set-core would be holding a
    second implementation of the project's own rule, which is the exact defect the
    delegation exists to prevent. So this asserts the handler was NOT called, not merely
    that the published number came out.
    """
    ran = []
    monkeypatch.setitem(lg._KIND_HANDLERS, "fixed_defect_without_citing_test",
                        lambda signal, path: ran.append(path) or ["HANDLER-COMPUTED"])
    contract.result = _ok({"laneSignals": {"fixedWithoutTest": ["BUG-1", "BUG-2"]}})

    report = _report(tmp_path, contract)

    assert ran == [], "a handler ran while the project publishes the answer"
    assert contract.calls == ["bugs"]
    assert [o.status for o in report.outcomes] == ["fired"]
    assert report.fired[0].violations == ("BUG-1", "BUG-2")


def test_an_empty_published_list_is_did_not_fire_not_unevaluated(tmp_path, contract):
    """The project answering "none" is a measurement, and it must read as one."""
    contract.result = _ok({"laneSignals": {"fixedWithoutTest": []}})
    report = _report(tmp_path, contract)
    assert [o.status for o in report.outcomes] == ["did_not_fire"]


def test_the_published_list_is_baselined_and_excluded_like_any_other_finding(
        tmp_path, contract):
    """Delegation changes where the violations come from, not what happens to them.

    Both mechanisms match on the identifier, which is why a structured entry is refused
    below: it would escape the baseline and the exclusions at once, silently.
    """
    contract.result = _ok(
        {"laneSignals": {"fixedWithoutTest": ["BUG-1", "BUG-2", "docs/known.md"]}})
    report = _report(tmp_path, contract, baseline=["BUG-1"])

    assert report.fired[0].violations == ("BUG-2",)
    assert report.summary()["declared_debt"] == 1
    assert report.summary()["checked_debt"] == 1


# ── no fallback, ever ──────────────────────────────────────────────────────────────

def test_a_failed_answer_produces_no_framework_side_computation(
        tmp_path, contract, monkeypatch):
    """The negative half of the rule, and the one a later refactor would quietly undo.

    "Fall back to the handler when the command fails" reads like robustness and IS the
    second implementation — worse, one that only runs when nobody is watching.
    """
    ran = []
    monkeypatch.setitem(lg._KIND_HANDLERS, "fixed_defect_without_citing_test",
                        lambda signal, path: ran.append(path) or [])
    contract.result = _failure("nonzero-exit")

    report = _report(tmp_path, contract)

    assert ran == [], "a framework-side computation was substituted for a failed answer"
    assert [o.status for o in report.outcomes] == ["unevaluated"]
    assert report.unevaluated[0].reason_class == "unusable-answer"


@pytest.mark.parametrize("error_class", ["timeout", "nonzero-exit", "invalid-envelope",
                                         "missing-data", "project-reported-failure"])
def test_a_broken_answer_is_never_a_pass(tmp_path, contract, error_class):
    contract.result = _failure(error_class)
    result = lg.execute_lane_gate(
        "c", types.SimpleNamespace(change_type="feature"),
        _tree(tmp_path, {"s": _answer_decl()}))
    assert result.status != "pass"


# ── the three states the peer asked for ────────────────────────────────────────────

def test_a_tree_that_publishes_nothing_is_distinct_from_a_command_that_is_broken(
        tmp_path, contract):
    """The peer's measured case: the publishing half existed on one machine only.

    Both are unevaluated — neither is a pass — but they are statements about different
    subjects: one about the checkout, one about the change. Merged, a project that never
    opted in reports identically to one whose gate just died.
    """
    contract.config = None
    absent = _report(tmp_path, contract)

    contract.config = _config()
    contract.result = _failure("nonzero-exit")
    broken = _report(tmp_path, contract)

    assert absent.unevaluated[0].reason_class == "not-published"
    assert broken.unevaluated[0].reason_class == "unusable-answer"
    assert absent.unevaluated[0].reason_class != broken.unevaluated[0].reason_class


def test_a_missing_interpreter_reads_as_not_publishing_rather_than_broken(
        tmp_path, contract):
    """`command-not-found` is the script or interpreter being absent from the tree.

    That is the clone case, not a defect in the change — measured on the peer's remote
    branch, where the contract's entry point was simply not committed.
    """
    contract.result = _failure("command-not-found")
    assert _report(tmp_path, contract).unevaluated[0].reason_class == "not-published"


def test_the_two_states_are_printed_under_different_markers(tmp_path, contract):
    """The distinction has to survive into the output, which is where it is read."""
    contract.config = None
    text = lg.format_output(_report(tmp_path, contract))
    assert "[NOT PUBLISHED BY THIS TREE]" in text
    assert "[UNEVALUATED]" not in text


def test_not_published_is_still_not_a_pass(tmp_path, contract):
    contract.config = None
    result = lg.execute_lane_gate(
        "c", types.SimpleNamespace(change_type="feature"),
        _tree(tmp_path, {"s": _answer_decl()}))
    assert result.status != "pass"


# ── what the gate refuses to invoke or accept ──────────────────────────────────────

def test_a_write_command_is_never_invoked(tmp_path, contract):
    """A gate that mutated the tree it is judging is the worst place to find this out."""
    contract.config = _config(commands=(), write_commands=("bugs",))
    report = _report(tmp_path, contract)
    assert contract.calls == []
    assert report.unevaluated[0].reason_class == "unusable-answer"


def test_a_command_the_contract_does_not_declare_is_unusable_not_neutral(
        tmp_path, contract):
    """Two of the project's own declarations disagreeing is a finding, not silence."""
    contract.config = _config(commands=("releases",))
    report = _report(tmp_path, contract)
    assert contract.calls == []
    assert report.unevaluated[0].reason_class == "unusable-answer"


def test_a_count_instead_of_a_list_is_unusable(tmp_path, contract):
    """A zero with no breakdown is the shape error, not the number.

    A count cannot be baselined and cannot be excluded, so it would report a figure nobody
    can act on or forgive — and a published `0` would read as proof there is nothing to
    answer.
    """
    contract.result = _ok({"laneSignals": {"fixedWithoutTest": 0}})
    report = _report(tmp_path, contract)
    assert report.unevaluated[0].reason_class == "unusable-answer"
    assert [o.status for o in report.outcomes] == ["unevaluated"]


def test_a_structured_violation_escapes_baseline_and_exclusions_so_it_is_refused(
        tmp_path, contract):
    contract.result = _ok({"laneSignals": {"fixedWithoutTest": [{"id": "BUG-1"}]}})
    assert _report(tmp_path, contract).unevaluated[0].reason_class == "unusable-answer"


def test_a_path_that_is_absent_from_the_answer_is_unevaluated_not_empty(
        tmp_path, contract):
    """Missing is not zero. An absent path yielding `[]` would be a false absence."""
    contract.result = _ok({"somethingElse": []})
    report = _report(tmp_path, contract)
    assert [o.status for o in report.outcomes] == ["unevaluated"]


# ── the declaration side ───────────────────────────────────────────────────────────

def test_a_malformed_answer_is_refused_rather_than_ignored(tmp_path):
    """Ignoring it would fall back to "no delegation", which is the recomputation."""
    with pytest.raises(ls.SignalRefused):
        ls.parse_signal("s", _answer_decl(answer={"command": "bugs"}))
    with pytest.raises(ls.SignalRefused):
        ls.parse_signal("s", _answer_decl(answer=["bugs", "field"]))
    with pytest.raises(ls.SignalRefused):
        ls.parse_signal("s", _answer_decl(answer={"command": "rm -rf /", "field": "x"}))


def test_a_projection_in_the_answer_field_is_refused(tmp_path):
    """A filter here is the project's rule re-expressed in the framework's syntax."""
    for path in ("bugs[].hasRegressionTest", "bugs[?fixed].id", "lane.*.ids", "a..b"):
        with pytest.raises(ls.SignalRefused):
            ls.parse_signal("s", _answer_decl(answer={"command": "bugs", "field": path}))


def test_an_absent_answer_is_legitimate(tmp_path):
    """Most conditions the framework evaluates itself need no delegation."""
    raw = _answer_decl()
    del raw["answer"]
    assert ls.parse_signal("s", raw).answer is None


def test_the_answer_is_not_reported_as_an_uninterpreted_field(tmp_path):
    """`answer` is read, so listing it under [NOT READ] would be a false claim."""
    assert ls.parse_signal("s", _answer_decl()).extra == {}


# ── sole enforcement ───────────────────────────────────────────────────────────────

def test_sole_enforcement_makes_an_unevaluable_signal_block(tmp_path, contract):
    """The price the peer named for accepting silence elsewhere.

    Their yes holds *because their own blocking gate covers the same class*, so framework
    silence costs earlier warning rather than protection. Where a signal is the only
    enforcement, silence is a real hole.
    """
    contract.result = _failure("timeout")
    report = _report(tmp_path, contract, sole_enforcement=True)
    assert report.unevaluated[0].blocking is True
    assert report.blocks is True
    assert "[BLOCKED — UNEVALUATED]" in lg.format_output(report)


def test_without_sole_enforcement_the_same_silence_does_not_block(tmp_path, contract):
    contract.result = _failure("timeout")
    report = _report(tmp_path, contract)
    assert report.unevaluated[0].blocking is False
    assert report.blocks is False


def test_sole_enforcement_does_not_block_a_signal_that_is_out_of_scope(
        tmp_path, contract):
    """Out-of-scope silence is not a hole — the signal runs in its own phase.

    Blocking here would fail every integration run for a signal declared for per-change
    verification, which is how a gate gets switched off in its first week.
    """
    report = lg.build_report(
        _tree(tmp_path, {"s": _answer_decl(sole_enforcement=True)}),
        phase="integration")
    assert report.unevaluated[0].reason_class == "out-of-scope"
    assert report.blocks is False


def test_sole_enforcement_blocks_when_the_tree_does_not_publish(tmp_path, contract):
    """Neutral describes the DIAGNOSIS, not the consequence.

    A project that declared this signal its only enforcement and then shipped a checkout
    without the publishing half has no enforcement at all. Naming the state honestly and
    still refusing to pass are not in tension.
    """
    contract.config = None
    report = _report(tmp_path, contract, sole_enforcement=True)
    assert report.blocks is True
    assert "[BLOCKED — NOT PUBLISHED]" in lg.format_output(report)


def test_a_non_bool_sole_enforcement_is_refused(tmp_path):
    """`"false"` is a true string, and this flag decides whether the gate blocks."""
    for value in ("false", 0, 1, "yes", None):
        with pytest.raises(ls.SignalRefused):
            ls.parse_signal("s", _answer_decl(sole_enforcement=value))


# ── a near miss on an optional field is a refusal, not a silent absence ────────────

def test_a_key_aimed_at_the_delegation_field_is_refused_not_stored(tmp_path):
    """Peer-measured: a mistyped delegation key reads as "no delegation".

    That is the reassuring direction one step earlier than the malformed-answer refusal —
    the signal parses, `answer` is None, and evaluation silently takes the handler route,
    which is the recomputation the whole delegation exists to prevent.

    Keys chosen for SHAPE, not from any project's vocabulary: a prefix, a plural, a suffix,
    and a case/separator variant.
    """
    for key in ("prior_answer", "answers", "answer_field", "Answer", "ANSWER"):
        raw = _answer_decl()
        raw[key] = raw.pop("answer")
        with pytest.raises(ls.SignalRefused) as caught:
            ls.parse_signal("s", raw)
        assert key in str(caught.value)


def test_a_key_aimed_at_the_blocking_flag_is_refused(tmp_path):
    """The same hole in the worse direction.

    A mistyped flag reads as False, so a signal its project declared the only enforcement of
    its class stops blocking — and nothing reports it. `[NOT READ]` would not cover this: it
    is a report, not a gate.
    """
    for key in ("soleEnforcement", "sole-enforcement", "enforcement"):
        with pytest.raises(ls.SignalRefused):
            ls.parse_signal("s", _answer_decl(**{key: True}))


def test_a_declared_key_that_resembles_nothing_is_still_kept(tmp_path):
    """The refusal must not swallow the preservation it was added next to."""
    signal = ls.parse_signal("s", _answer_decl(canonical_implementation="scripts/x.sh"))
    assert signal.extra == {"canonical_implementation": "scripts/x.sh"}


def test_required_fields_are_deliberately_not_near_miss_checked(tmp_path):
    """Stated as a test because the omission looks like an oversight otherwise.

    A typo on a required field leaves the real field missing, which is already refused by
    name. Checking those too would buy nothing and cost over-refusals: `lane` normalises to
    four characters, so any project key containing it — `plane_config` — would collide.
    """
    assert set(ls.SILENTLY_OPTIONAL_FIELDS).isdisjoint(ls.REQUIRED_FIELDS)
    raw = _answer_decl(plane_config="x", scope_notes="y")
    assert set(ls.parse_signal("s", raw).extra) == {"plane_config", "scope_notes"}


def test_every_optional_signal_field_is_near_miss_checked(tmp_path):
    """Pins the list to `LaneSignal` itself, so a new optional field cannot reopen the hole.

    This is the "hold the wrong pattern in a test" discipline: a hand-maintained list is a
    second copy, and a second copy drifts. Adding an optional field without extending
    `SILENTLY_OPTIONAL_FIELDS` fails here instead of silently going unchecked.
    """
    import dataclasses

    optional = {f.name for f in dataclasses.fields(ls.LaneSignal)
                if f.name not in ls.REQUIRED_FIELDS and f.name not in ("name", "extra")}
    assert optional == set(ls.SILENTLY_OPTIONAL_FIELDS), (
        "an optional LaneSignal field is not covered by the near-miss refusal — a typo on "
        "it would read as absent, silently")
