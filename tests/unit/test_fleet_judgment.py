"""One model pass a cycle, over a structural floor it may not override.

Every test here is about a direction of failure rather than a feature. The
module's whole job is to add items the structural pass cannot reach, and each
way it can go wrong resolves toward keeping an agent visible — because the
opposite mistake removes an agent that needs a person, and nothing on the
screen would show it had been removed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from set_orch.fleet import judgment as j
from set_orch.fleet import state as agent_state


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _log(tmp_path: Path, name: str, text: str = "Shall I go ahead?") -> str:
    p = tmp_path / name
    p.write_text(json.dumps({
        "type": "assistant", "timestamp": "2026-08-20T08:00:00.000Z",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }) + "\n")
    return str(p)


def _subject(pid: int, tmp_path: Path, *, state: str = agent_state.QUIET, text: str = "Shall I go ahead?") -> j.Subject:
    return j.Subject(pid=pid, project="p", state=state, session_log=_log(tmp_path, f"s{pid}.jsonl", text))


def _runner(payload, calls):
    def call(prompt, model):
        calls.append((prompt, model))
        return payload if isinstance(payload, str) else json.dumps(payload)
    return call


# --------------------------------------------------------------------------- #
# one pass per cycle
# --------------------------------------------------------------------------- #

def test_many_candidates_one_invocation(tmp_path):
    calls = []
    subjects = [_subject(i, tmp_path) for i in (1, 2, 3, 4)]
    res = j.run_pass(subjects, {}, runner=_runner({str(i): "asking" for i in (1, 2, 3, 4)}, calls), model="sonnet")
    assert res.invocations == 1
    assert len(calls) == 1
    assert all(res.verdicts[i].verdict == j.ASKING for i in (1, 2, 3, 4))


def test_no_candidates_no_invocation(tmp_path):
    calls = []
    subjects = [_subject(1, tmp_path, state=agent_state.WORKING)]
    res = j.run_pass(subjects, {}, runner=_runner({}, calls), model="sonnet")
    assert res.invocations == 0
    assert calls == []
    # An empty pass is MEASURED — we looked. That is not the same fact as a
    # failure, and the surface renders them differently.
    assert res.measured is True


def test_a_pass_does_not_depend_on_the_previous_one(tmp_path):
    """Stateless: the second prompt carries nothing from the first.

    ⚠ The obvious assertion — that the second prompt does not contain
    `"finished"` — is worthless and was written that way first: every class
    name appears in the instruction block, so it fails against a correct
    implementation. The discriminator has to be something only the previous
    REPLY could have put there, hence the sentinel.
    """
    calls = []
    sentinel = "REPLY-ONLY-SENTINEL-4417"
    subjects = [_subject(1, tmp_path)]

    def run(prompt, model):
        calls.append((prompt, model))
        return json.dumps({"1": "finished", "note": sentinel})

    j.run_pass(subjects, {}, runner=run, model="sonnet")
    j.run_pass(subjects, {}, runner=run, model="sonnet")
    assert len(calls) == 2
    assert calls[0][0] == calls[1][0]
    assert sentinel not in calls[1][0]


# --------------------------------------------------------------------------- #
# the candidate filter
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("state", [agent_state.WORKING, agent_state.UNKNOWN, agent_state.WAITING])
def test_a_non_quiet_agent_is_not_a_candidate(tmp_path, state):
    subjects = [_subject(1, tmp_path, state=state)]
    candidates, skipped, _ = j.select_candidates(subjects, {})
    assert candidates == []
    assert 1 in skipped


def test_an_unchanged_log_is_not_re_judged(tmp_path):
    subject = _subject(1, tmp_path)
    mark = j.watermark_of(subject.session_log)
    candidates, skipped, _ = j.select_candidates([subject], {1: mark})
    assert candidates == []
    assert "has not moved" in skipped[1]


def test_a_moved_log_is_re_judged(tmp_path):
    subject = _subject(1, tmp_path)
    stale = j.Watermark(mtime=0.0, size=0)
    candidates, _, _ = j.select_candidates([subject], {1: stale})
    assert [c.pid for c in candidates] == [1]


def test_an_unreadable_log_is_excluded_with_a_reason_not_carried_forward(tmp_path):
    """No information is not 'unchanged'. Carrying it forward would keep a
    stale verdict standing for an agent nobody can measure."""
    subject = j.Subject(pid=1, project="p", state=agent_state.QUIET,
                        session_log=str(tmp_path / "gone.jsonl"))
    candidates, skipped, _ = j.select_candidates([subject], {})
    assert candidates == []
    assert "could not be read" in skipped[1]


def test_a_structurally_certain_blockage_skips_the_model(tmp_path):
    calls = []
    subjects = [_subject(1, tmp_path, state=agent_state.ASKING)]
    res = j.run_pass(subjects, {}, runner=_runner({}, calls), model="sonnet")
    assert calls == []
    assert res.verdicts[1].verdict == j.ASKING
    assert res.verdicts[1].source == "structural"


def test_the_cap_names_what_it_did_not_cover(tmp_path):
    """A bounded pass that hides its boundary reads as a complete one."""
    subjects = [_subject(i, tmp_path) for i in range(1, 6)]
    candidates, _, not_covered = j.select_candidates(subjects, {}, max_candidates=2)
    assert len(candidates) == 2
    assert not_covered == [3, 4, 5]


# --------------------------------------------------------------------------- #
# the floor the model may not move
# --------------------------------------------------------------------------- #

def test_a_model_verdict_cannot_unqueue_a_measured_blockage():
    structural = {7: j.Verdict(pid=7, verdict=j.ASKING, source="structural")}
    opinion = {7: j.Verdict(pid=7, verdict=j.FINISHED, source="model")}
    out = j.reconcile(opinion, structural)
    assert out[7].verdict == j.ASKING
    assert out[7].source == "structural"
    assert out[7].disagreed == j.FINISHED


def test_agreement_leaves_no_phantom_disagreement():
    structural = {7: j.Verdict(pid=7, verdict=j.ASKING, source="structural")}
    out = j.reconcile({7: j.Verdict(pid=7, verdict=j.ASKING, source="model")}, structural)
    assert out[7].disagreed is None


# --------------------------------------------------------------------------- #
# every failure resolves toward unclassified, never toward finished
# --------------------------------------------------------------------------- #

def test_an_unrecognised_class_is_surfaced_not_mapped(tmp_path):
    subjects = [_subject(1, tmp_path)]
    v = j.parse_response(json.dumps({"1": "probably-done"}), subjects)
    assert v[1].verdict == j.UNCLASSIFIED
    assert v[1].verdict != j.FINISHED


def test_a_missing_verdict_is_not_a_negative_verdict(tmp_path):
    subjects = [_subject(1, tmp_path), _subject(2, tmp_path)]
    v = j.parse_response(json.dumps({"1": "asking"}), subjects)
    assert v[1].verdict == j.ASKING
    assert v[2].verdict == j.UNCLASSIFIED
    assert v[2].source == "absent"


@pytest.mark.parametrize("raw", ["", None, "not json at all", "{broken", '["a","list"]'])
def test_an_unusable_reply_leaves_everyone_unclassified(tmp_path, raw):
    subjects = [_subject(1, tmp_path)]
    v = j.parse_response(raw, subjects)
    assert v[1].verdict == j.UNCLASSIFIED


def test_a_verdict_about_somebody_who_was_not_asked_is_dropped(tmp_path):
    subjects = [_subject(1, tmp_path)]
    v = j.parse_response(json.dumps({"1": "asking", "999": "finished"}), subjects)
    assert set(v) == {1}


def test_a_reply_wrapped_in_prose_is_still_read(tmp_path):
    """The model is told JSON only; this is what happens when it adds a
    sentence anyway. Reading it is right — inventing a class is not."""
    subjects = [_subject(1, tmp_path)]
    v = j.parse_response('Here you go:\n```json\n{"1": "asking"}\n```\n', subjects)
    assert v[1].verdict == j.ASKING


# --------------------------------------------------------------------------- #
# a pass that could not run
# --------------------------------------------------------------------------- #

def test_a_failed_pass_is_visible_and_not_an_empty_queue(tmp_path):
    def boom(prompt, model):
        raise RuntimeError("no")

    res = j.run_pass([_subject(1, tmp_path)], {}, runner=boom, model="sonnet")
    assert res.measured is False
    assert res.reason


def test_a_pass_returning_nothing_is_unmeasured(tmp_path):
    res = j.run_pass([_subject(1, tmp_path)], {}, runner=lambda p, m: None, model="sonnet")
    assert res.measured is False


def test_a_failed_pass_still_carries_the_structural_verdicts(tmp_path):
    """The floor does not depend on the model, so a failure must not lose it."""
    def boom(prompt, model):
        raise RuntimeError("no")

    subjects = [_subject(1, tmp_path, state=agent_state.ASKING), _subject(2, tmp_path)]
    res = j.run_pass(subjects, {}, runner=boom, model="sonnet")
    assert res.measured is False
    assert res.verdicts[1].verdict == j.ASKING


# --------------------------------------------------------------------------- #
# confidentiality
# --------------------------------------------------------------------------- #

SECRET = "PARTNER-ACME-ORDER-99178-DO-NOT-PERSIST"


def test_no_log_line_carries_session_content(tmp_path, caplog):
    """The pass reads a consumer's session text; the framework writes none of it.

    Driven through every path that logs — a cap being exceeded, an unreadable
    log, an unrecognised class, and a raised exception — because the failure
    paths are where a body normally leaks into a diagnostic.
    """
    caplog.set_level("DEBUG")
    subjects = [_subject(i, tmp_path, text=f"{SECRET} number {i}") for i in range(1, 6)]

    j.run_pass(subjects, {}, runner=lambda p, m: json.dumps({"1": "nonsense-class"}),
               model="sonnet", max_candidates=2)
    j.run_pass(subjects, {}, runner=lambda p, m: (_ for _ in ()).throw(RuntimeError(SECRET)),
               model="sonnet")
    j.select_candidates(
        [j.Subject(pid=9, project="p", state=agent_state.QUIET, session_log=str(tmp_path / "gone"))], {},
    )

    blob = "\n".join(r.getMessage() for r in caplog.records)
    assert SECRET not in blob, blob


def test_a_verdict_retains_a_class_and_an_identity_not_prose(tmp_path):
    subjects = [_subject(1, tmp_path, text=SECRET)]
    res = j.run_pass(subjects, {}, runner=lambda p, m: json.dumps({"1": "asking"}), model="sonnet")
    assert SECRET not in repr(res.verdicts)
    assert res.verdicts[1].verdict == j.ASKING


def test_the_prompt_does_carry_the_excerpt_and_that_is_the_point(tmp_path):
    """The counterpart of the test above, so neither is vacuous.

    Confidentiality here is about what is WRITTEN DOWN, not about what the
    model reads — and a test asserting the secret is absent everywhere would
    also pass if the prompt were empty, which would make the feature useless
    and the test meaningless.
    """
    subjects = [_subject(1, tmp_path, text=SECRET)]
    assert SECRET in j.build_prompt(subjects)


def test_a_reply_nothing_could_be_read_from_is_unmeasured_not_calm(tmp_path):
    """The quiet-vanish this module would otherwise have.

    `unclassified` agents are not queued. So a reply that parses to nothing
    leaves an empty queue — indistinguishable, on screen, from a fleet where
    nobody needs anything. Reported as unmeasured, while the unclassified
    verdicts are still returned so the agents stay visible.
    """
    subjects = [_subject(1, tmp_path), _subject(2, tmp_path)]
    res = j.run_pass(subjects, {}, runner=lambda p, m: "sorry, I could not do that", model="sonnet")
    assert res.measured is False
    assert res.reason
    assert res.verdicts[1].verdict == j.UNCLASSIFIED
    assert res.verdicts[2].verdict == j.UNCLASSIFIED


def test_one_usable_verdict_is_enough_for_the_pass_to_count_as_measured(tmp_path):
    """The other direction, so the check above is not a blanket pessimism."""
    subjects = [_subject(1, tmp_path), _subject(2, tmp_path)]
    res = j.run_pass(subjects, {}, runner=lambda p, m: json.dumps({"1": "asking"}), model="sonnet")
    assert res.measured is True
    assert res.verdicts[1].verdict == j.ASKING
    assert res.verdicts[2].verdict == j.UNCLASSIFIED
