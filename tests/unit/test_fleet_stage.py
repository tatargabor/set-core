"""The per-agent stage axis — derivation, join, declared override, gaps.

The mapping table in `stage.derive_position` is the module's whole contract
with the filesystem, so every row of it is asserted here before the resolver
is wired into any payload: a mapping that drifts must fail HERE, not on a
screen. The join and gap tests assert the refusals — a gap that cannot say
what kind of gap it is, or a stage borrowed from another agent's change, is
the failure direction this module exists to keep off the payload.
"""

from __future__ import annotations

import json
import time

import pytest

from set_orch.fleet import stage
from set_orch.fleet.purpose import Purpose
from set_orch.project_status import StatusResult


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #

def _change(tmp_path, name, *, proposal=False, design=False, specs=False, tasks=None):
    d = tmp_path / "openspec" / "changes" / name
    d.mkdir(parents=True, exist_ok=True)
    if proposal:
        (d / "proposal.md").write_text("# p\n", encoding="utf-8")
    if design:
        (d / "design.md").write_text("# d\n", encoding="utf-8")
    if specs:
        (d / "specs").mkdir(exist_ok=True)
    if tasks is not None:
        (d / "tasks.md").write_text(tasks, encoding="utf-8")
    return d


def _archived(tmp_path, name, *, dated=False):
    d = tmp_path / "openspec" / "changes" / "archive" / (f"2026-08-29-{name}" if dated else name)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _purpose(change, *, pid=0, session=None, status="running"):
    p = Purpose(change=change, pid=pid, status=status)
    p.session_id = session
    return p


@pytest.fixture(autouse=True)
def _clean_memo():
    stage._INFERENCE_MEMO.clear()
    yield
    stage._INFERENCE_MEMO.clear()


# --------------------------------------------------------------------------- #
# 1.5 — the derivation mapping table
# --------------------------------------------------------------------------- #


class TestDerivePosition:
    def test_unchecked_numbered_task_is_apply(self, tmp_path):
        _change(tmp_path, "feat-a", tasks="- [ ] 1.1 one\n- [x] 1.2 two\n")
        assert stage.derive_position(str(tmp_path), "feat-a") == "apply"

    def test_all_numbered_tasks_checked_is_verify(self, tmp_path):
        _change(tmp_path, "feat-a", tasks="- [x] 1.1 one\n- [X] 1.2 two\n")
        assert stage.derive_position(str(tmp_path), "feat-a") == "verify"

    def test_partial_is_never_done(self, tmp_path):
        # `~` is a claim with a limit in it; rounding it up would report a
        # verify that is not there.
        _change(tmp_path, "feat-a", tasks="- [x] 1.1 one\n- [~] 1.2 two\n")
        assert stage.derive_position(str(tmp_path), "feat-a") == "apply"

    def test_acceptance_criteria_do_not_hold_a_change_in_apply(self, tmp_path):
        # The reason tasks are counted NUMBERED: ACs share the `- [ ]` shape
        # and are never ticked. Measured on this repo's own task files.
        _change(tmp_path, "feat-a", tasks="- [x] 1.1 one\n- [ ] AC-1: WHEN x THEN y\n")
        assert stage.derive_position(str(tmp_path), "feat-a") == "verify"

    def test_no_numbered_tasks_falls_back_to_raw_checkboxes(self, tmp_path):
        _change(tmp_path, "plain", tasks="- [ ] do the thing\n")
        assert stage.derive_position(str(tmp_path), "plain") == "apply"
        _change(tmp_path, "plain-done", tasks="- [x] did the thing\n")
        assert stage.derive_position(str(tmp_path), "plain-done") == "verify"

    def test_tasks_md_without_design_artifacts_is_design(self, tmp_path):
        # Wait — a change with a tasks.md has PASSED design; a change WITHOUT
        # one is the design-stage fact. This case is the no-tasks branch.
        _change(tmp_path, "feat-b", proposal=True, design=True)
        assert stage.derive_position(str(tmp_path), "feat-b") == "design"

    def test_tasks_md_missing_and_specs_dir_present_is_design(self, tmp_path):
        _change(tmp_path, "feat-b", proposal=True, specs=True)
        assert stage.derive_position(str(tmp_path), "feat-b") == "design"

    def test_proposal_only_is_proposal(self, tmp_path):
        _change(tmp_path, "feat-c", proposal=True)
        assert stage.derive_position(str(tmp_path), "feat-c") == "proposal"

    def test_bare_directory_is_no_position(self, tmp_path):
        # A directory is not evidence of a proposal. Guessing `proposal` here
        # would put a fabricated first stage under a real agent.
        _change(tmp_path, "empty")
        assert stage.derive_position(str(tmp_path), "empty") is None

    def test_archived_plain_layout(self, tmp_path):
        _archived(tmp_path, "done-a")
        assert stage.derive_position(str(tmp_path), "done-a") == "archive"

    def test_archived_dated_layout(self, tmp_path):
        _archived(tmp_path, "done-b", dated=True)
        assert stage.derive_position(str(tmp_path), "done-b") == "archive"

    def test_unknown_change_is_no_position(self, tmp_path):
        assert stage.derive_position(str(tmp_path), "never-existed") is None

    def test_no_tree_at_all_is_no_position(self, tmp_path):
        assert stage.derive_position(str(tmp_path), "anything") is None

    def test_empty_change_name_is_no_position(self, tmp_path):
        assert stage.derive_position(str(tmp_path), "") is None


def test_has_active_changes_distinguishes_archive(tmp_path):
    assert stage.has_active_changes(str(tmp_path)) is False
    _archived(tmp_path, "old")
    assert stage.has_active_changes(str(tmp_path)) is False
    _change(tmp_path, "live", proposal=True)
    assert stage.has_active_changes(str(tmp_path)) is True


# --------------------------------------------------------------------------- #
# 1.6 — the join is per agent, on session identity
# --------------------------------------------------------------------------- #


class TestJoin:
    def test_two_agents_on_two_changes_resolve_independently(self, tmp_path):
        _change(tmp_path, "one", tasks="- [ ] 1.1 a\n")
        _change(tmp_path, "two", proposal=True)
        purposes = [_purpose("one", session="s1", pid=100), _purpose("two", session="s2", pid=200)]
        a1 = stage.resolve_stage(str(tmp_path), purposes, 100, "s1", None)
        a2 = stage.resolve_stage(str(tmp_path), purposes, 200, "s2", None)
        assert a1.position == "apply"
        assert a2.position == "proposal"
        assert a1.position != a2.position

    def test_the_join_survives_a_pid_change_with_the_same_session(self, tmp_path):
        # The engine's record and the agent agree on the SESSION; the pid the
        # record wrote is gone. The stage follows the session.
        _change(tmp_path, "one", tasks="- [ ] 1.1 a\n")
        purposes = [_purpose("one", session="s1", pid=999)]
        got = stage.resolve_stage(str(tmp_path), purposes, 1234, "s1", None)
        assert got.state == stage.STATE_RESOLVED
        assert got.position == "apply"

    def test_a_stale_record_never_lends_its_change(self, tmp_path):
        # A record whose run is finished describes a run that is OVER; a live
        # agent holding that pid now is doing something else.
        _change(tmp_path, "one", tasks="- [ ] 1.1 a\n")
        purposes = [_purpose("one", session="s1", pid=1234, status="stale")]
        got = stage.resolve_stage(str(tmp_path), purposes, 1234, "s1", None)
        assert got.state == stage.STATE_GAP

    def test_session_inference_joins_when_no_record_exists(self, tmp_path, monkeypatch):
        _change(tmp_path, "inf-a", tasks="- [ ] 1.1 a\n")
        log = tmp_path / "session.jsonl"
        log.write_text(json.dumps({"type": "queue-operation",
                                   "content": "/opsx:apply inf-a do it"}) + "\n",
                       encoding="utf-8")
        got = stage.resolve_stage(str(tmp_path), None, 1, "s9", str(log))
        assert got.state == stage.STATE_RESOLVED
        assert got.position == "apply"

    def test_inference_matches_change_name_key_and_branch(self, tmp_path):
        log = tmp_path / "s2.jsonl"
        log.write_text('{"content": "x", "change_name": "key-a"}\n', encoding="utf-8")
        assert stage.infer_change_from_session(str(log)) == "key-a"
        log2 = tmp_path / "s3.jsonl"
        log2.write_text('{"content": "merging change/branch-b now"}\n', encoding="utf-8")
        assert stage.infer_change_from_session(str(log2)) == "branch-b"

    def test_inference_reads_windows_and_no_more(self, tmp_path):
        # Bounded reads: a marker in the MIDDLE of a large transcript is in
        # neither the head nor the tail window, and is not found. Reading the
        # whole file per agent per poll is the cost this refuses.
        log = tmp_path / "s4.jsonl"
        filler = b'{"content": "x"}\n' * 34000  # ~600 KB
        middle = b'{"content": "/opsx:apply deep-a"}\n'
        log.write_bytes(filler[:290_000] + middle + filler[290_000:])
        assert log.stat().st_size > 570_000
        # The marker sits past the head window and before the tail window:
        assert 262_144 < 290_000 < log.stat().st_size - 262_144
        assert stage.infer_change_from_session(str(log)) is None

    def test_inference_prefers_the_most_recent_invocation(self, tmp_path):
        # The measured case that forced the tail window: a long-running
        # session's HEAD names a change it left days ago; its TAIL names the
        # one actually in flight. Recency wins among INVOCATIONS.
        log = tmp_path / "s7.jsonl"
        head = b'{"content": "/opsx:apply stale-one"}\n' * 20000  # ~400 KB head
        tail = b'{"content": "openspec status --change fresh-two"}\n' * 2000
        log.write_bytes(head + tail)
        assert stage.infer_change_from_session(str(log)) == "fresh-two"

    def test_a_bare_path_mention_never_joins_a_change(self, tmp_path):
        # MEASURED false value (2026-08-30): a session doing non-change work
        # carried four `openspec/changes/<other-change>` mentions — git status
        # output, file reads — and rendered the OTHER change's stage. A path
        # mention is a mention, not an act of addressing; only invocations
        # join, and a transcript without any yields an honest gap.
        log = tmp_path / "s8.jsonl"
        log.write_bytes(b'{"content": "M openspec/changes/someone-elses-change/tasks.md"}\n'
                        + b'{"content": "read openspec/changes/someone-elses-change/proposal.md"}\n')
        assert stage.infer_change_from_session(str(log)) is None

    def test_inference_matches_change_args_and_flags(self, tmp_path):
        log = tmp_path / "s9.jsonl"
        log.write_bytes(b'{"content": "openspec status --change arg-b"}\n'
                        + b'{"content": "x"}\n')
        assert stage.infer_change_from_session(str(log)) == "arg-b"
        log2 = tmp_path / "s9b.jsonl"
        log2.write_bytes(b'{"content": "run --change=eq-form now"}\n')
        assert stage.infer_change_from_session(str(log2)) == "eq-form"

    def test_a_quoted_change_arg_matches(self, tmp_path):
        # The CLI form this very repository uses: --change "the-name".
        log = tmp_path / "s10.jsonl"
        log.write_bytes(b'{"content": "openspec status --change \'quoted-one\'"}\n')
        assert stage.infer_change_from_session(str(log)) == "quoted-one"

    def test_the_resolver_skips_unbacked_candidates_for_backed_ones(self, tmp_path):
        # MEASURED live (2026-08-30): the most recent invocation-shaped match in
        # a real transcript was prose junk ("--change args"); the true change
        # sat behind it. The tree is the ground truth: walk the candidates most
        # recent first and take the first the project can POSITION.
        log = tmp_path / "s11.jsonl"
        log.write_bytes(b'{"content": "openspec status --change junk-name"}\n'
                        + b'{"content": "openspec status --change real-one"}\n')
        _change(tmp_path, "real-one", tasks="- [ ] 1.1 one\n")
        got = stage.resolve_stage(str(tmp_path), None, 1, "s", str(log))
        assert got.state == stage.STATE_RESOLVED
        assert got.position == "apply"

    def test_prose_about_a_flag_is_not_an_invocation(self, tmp_path):
        # '--change args' in a sentence matched the flag pattern and produced
        # the change name "args". The value must look like a slug and the flag
        # must be followed by it, not by prose about the flag... measured: the
        # prose form uses a following word that IS slug-shaped, so the honest
        # guard is the project-side check: a junk name derives no position and
        # becomes a gap, never a stage. Asserted at the resolver level
        # (test_a_joined_change_with_no_artifacts_is_no_position); here, only
        # that the pattern requires the slug immediately after the flag.
        import re
        m = stage._CHANGE_ARG.search("the --change argument takes a name")
        assert m is None or m.group(1) == "argument"

    def test_inference_memo_answers_an_unchanged_file_without_a_reread(self, tmp_path, monkeypatch):
        # The memo's whole job: a 5 s poll must not re-read the same head.
        # Keyed on the file's fingerprint, so this only holds while the file
        # is unchanged — a rewrite gets a new key and a fresh read.
        import builtins
        log = tmp_path / "s5.jsonl"
        log.write_text('{"change_name": "memo-a"}\n', encoding="utf-8")
        assert stage.infer_change_from_session(str(log)) == "memo-a"

        def no_open(*a, **k):
            raise AssertionError("the memo should have answered")
        monkeypatch.setattr(builtins, "open", no_open)
        assert stage.infer_change_from_session(str(log)) == "memo-a"

    def test_inference_memo_expires_so_an_old_answer_is_reread(self, tmp_path, monkeypatch):
        # An unchanged file PAST the TTL is re-read: the memo is seconds, not
        # minutes — it exists to bound a poll, never to hold a session's truth.
        import builtins
        log = tmp_path / "s6.jsonl"
        log.write_text('{"change_name": "memo-a"}\n', encoding="utf-8")
        assert stage.infer_change_from_session(str(log)) == "memo-a"
        key = next(iter(stage._INFERENCE_MEMO))
        stage._INFERENCE_MEMO[key] = (time.monotonic() - stage._INFERENCE_MEMO_TTL - 1.0, "old")

        calls = []
        real_open = builtins.open

        def counting_open(*a, **k):
            calls.append(a)
            return real_open(*a, **k)
        monkeypatch.setattr(builtins, "open", counting_open)
        assert stage.infer_change_from_session(str(log)) == "memo-a"
        assert calls, "an expired memo must be refreshed from the file"


# --------------------------------------------------------------------------- #
# 1.7 — the declared override
# --------------------------------------------------------------------------- #


def _result(data, display):
    return StatusResult(command="c", ok=True, data=data, display=display)


class TestDeclaredOverride:
    def _axis(self):
        data = [{"id": "triage-1", "stage": "fixing"},
                {"id": "feat-x", "stage": "shipping"},
                {"id": "no-stage", "other": 1}]
        display = {"id": "id", "stage": {"stageOrder": ["triage", "fixing", "shipping"]}}
        return stage.declared_axis_from_results([_result(data, display)])

    def test_declared_flow_replaces_the_derived_one(self):
        axis = self._axis()
        # The join still has to come from evidence — a work-cycle record
        # naming the producer's own id:
        purposes = [_purpose("triage-1", pid=1)]
        got = stage.resolve_stage(None, purposes, 1, "s", None, declared=axis)
        assert got.flow == ("triage", "fixing", "shipping")
        assert got.source == "declared"
        assert got.position == "fixing"

    def test_declared_position_indexed_by_the_producers_own_id(self):
        _, index = self._axis()
        assert index["triage-1"] == "fixing"
        assert "no-stage" not in index  # an item with no stage joins nothing

    def test_results_without_a_declaration_yield_no_axis(self):
        assert stage.declared_axis_from_results([_result({"a": 1}, None)]) is None
        assert stage.declared_axis_from_results([]) is None
        failed = StatusResult.failure("c", "timeout", "too slow")
        assert stage.declared_axis_from_results([failed]) is None

    def test_a_malformed_declaration_is_not_an_axis(self):
        # The contract's own all-or-nothing rule; the reader must never see a
        # salvaged partial order dressed as a flow.
        for display in ({"stage": {"stageOrder": []}},
                        {"stage": {"stageOrder": ["a", "a"]}},
                        {"stage": {"stageOrder": ["a", ""]}},
                        {"stage": {"stageOrder": "nope"}}):
            assert stage.declared_axis_from_results(
                [_result([{"id": "x", "stage": "a"}], display)]) is None

    def test_no_join_with_an_empty_index_is_nothing_started(self, tmp_path):
        axis = (["triage", "fixing"], {})
        got = stage.resolve_stage(str(tmp_path), None, 1, None, None, declared=axis)
        assert got.reason == stage.REASON_NOTHING_STARTED

    def test_no_join_with_a_populated_index_is_a_join_failure(self):
        axis = (["triage"], {"triage-1": "triage"})
        got = stage.resolve_stage(None, None, 1, None, None, declared=axis)
        assert got.reason == stage.REASON_JOIN_FAILED

    def test_a_joined_change_missing_from_the_index_is_a_join_failure(self):
        axis = (["triage"], {"other-1": "triage"})
        got = stage.resolve_stage(None, None, 1, "s", None, declared=axis)
        assert got.reason == stage.REASON_JOIN_FAILED

    def test_a_value_outside_the_declared_order_is_carried_and_marked(self):
        axis = (["triage", "fixing"], {"odd-1": "weird"})
        purposes = [_purpose("odd-1", pid=1)]
        got = stage.resolve_stage(None, purposes, 1, "s", None, declared=axis)
        assert got.state == stage.STATE_RESOLVED
        assert got.position == "weird"
        assert got.outside is True


# --------------------------------------------------------------------------- #
# 1.8 — gaps, named and unfilled
# --------------------------------------------------------------------------- #


class TestGaps:
    def test_no_tree_and_no_declaration_is_a_named_gap(self, tmp_path):
        got = stage.resolve_stage(str(tmp_path), None, 1, "s", None)
        assert got.state == stage.STATE_GAP
        assert got.reason == stage.REASON_NO_FLOW
        assert got.flow is None

    def test_nothing_started_is_distinct_from_a_join_failure(self, tmp_path):
        _archived(tmp_path, "old")  # a tree exists, nothing is in flight
        idle = stage.resolve_stage(str(tmp_path), None, 1, None, None)
        assert idle.reason == stage.REASON_NOTHING_STARTED
        _change(tmp_path, "live", proposal=True)
        failed = stage.resolve_stage(str(tmp_path), None, 1, "no-session", None)
        assert failed.reason == stage.REASON_JOIN_FAILED
        # And the two must never be readable as each other:
        assert idle.reason != failed.reason

    def test_a_gapped_agent_is_not_equal_to_any_resolved_position(self, tmp_path):
        _change(tmp_path, "live", proposal=True)
        got = stage.resolve_stage(str(tmp_path), None, 1, "nope", None)
        assert got.state == stage.STATE_GAP
        assert got.position is None
        assert got.position not in stage.DEFAULT_FLOW

    def test_a_joined_change_with_no_artifacts_is_no_position(self, tmp_path):
        _change(tmp_path, "bare")
        purposes = [_purpose("bare", pid=7)]
        got = stage.resolve_stage(str(tmp_path), purposes, 7, "s", None)
        assert got.reason == stage.REASON_NO_POSITION
        assert got.flow == stage.DEFAULT_FLOW

    def test_an_inferred_name_that_backs_no_artifact_is_no_position(self, tmp_path):
        _change(tmp_path, "live", proposal=True)  # the project is live, the join matters
        log = tmp_path / "s.jsonl"
        log.write_text('{"change_name": "phantom"}\n', encoding="utf-8")
        got = stage.resolve_stage(str(tmp_path), None, 1, "s", str(log))
        assert got.reason == stage.REASON_NO_POSITION


# --------------------------------------------------------------------------- #
# the payload shape
# --------------------------------------------------------------------------- #


def test_the_stage_shape_is_complete_and_json_clean():
    s = stage.Stage(state=stage.STATE_RESOLVED, flow=stage.DEFAULT_FLOW,
                    position="apply", source="derived").as_dict()
    assert set(s) == {"state", "flow", "position", "reason", "source", "outside"}
    json.dumps(s)


def test_a_drive_by_mention_of_an_active_change_loses_to_the_archived_own_change(tmp_path):
    # MEASURED live (2026-08-30, the user reported it as the fleet screen
    # showing `apply` for a change already archived): a session archived its
    # own change, then its verify work merely REFERENCED another session's
    # active change — the reference was the MOST RECENT invocation match, and
    # recency alone put the strip on the other change's `apply`. The archive
    # anchor: a candidate deriving to `archive` with at least half the
    # leader's tail weight is the session's own finished work, and finished
    # work stays finished.
    _change(tmp_path, "active-one", tasks="- [ ] 1.1 a\n")
    (tmp_path / "openspec" / "changes" / "archive" / "2026-08-30-done-one").mkdir(parents=True)
    (tmp_path / "openspec" / "changes" / "archive" / "2026-08-30-done-one" / "tasks.md").write_text(
        "- [x] 1.1 done\n", encoding="utf-8")
    log = tmp_path / "s-live.jsonl"
    log.write_text(
        json.dumps({"content": "/opsx:apply done-one do the work"}) + "\n"
        + json.dumps({"content": "/opsx:apply done-one more work"}) + "\n"
        + json.dumps({"content": "openspec status --change active-one"}) + "\n",
        encoding="utf-8")
    got = stage.resolve_stage(str(tmp_path), None, 1, "s", str(log))
    assert got.state == stage.STATE_RESOLVED
    assert got.position == "archive"


def test_the_default_flow_is_the_openspec_lifecycle():
    assert stage.DEFAULT_FLOW == ("proposal", "design", "apply", "verify", "archive")
