"""The document that teaches a gate's input must produce input the gate accepts.

A guard can be correct in every respect and still reject every legitimate submission,
because the document a person or an agent actually reads teaches a different shape. The
guard looks fine, the runs look like ordinary failures, and nothing points at the rule
book — this is the shape a peer measured on their own citation gate and it existed here
too, on the spec-verify sentinels.

**What was wrong here, kept because the refuted state is the durable half.** The
orchestrator's prompt asks for `CRITICAL_COUNT` and `VERIFY_RESULT` as the final two
lines, and the downgrade path that lets a warnings-only report through needs the count
(`verifier.py:3740`). The `/opsx:verify` skill — the file the agent actually loads —
taught `VERIFY_RESULT` alone as "the final line" and mentioned `CRITICAL_COUNT` **zero
times**. An agent following the skill exactly could not produce the input the mechanism
needs. It fails CLOSED (extra blocked merges and retries, never a bad merge), which is
why it survived: the failures look like ordinary verification failures.

These tests assert the two documents agree with the parsers, using the parsers themselves
rather than a second copy of the regex — a copied pattern is the third place, and the
third place drifts too.
"""

import re
from pathlib import Path

import pytest

from set_orch.verifier import _parse_critical_count, _parse_verify_verdict

SKILL = Path(__file__).resolve().parents[2] / ".claude/skills/openspec-verify-change/SKILL.md"
VERIFIER = Path(__file__).resolve().parents[2] / "lib/set_orch/verifier.py"


def _skill_text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_the_skill_teaches_the_count_at_all():
    """The whole defect in one assertion: the word was absent from the teaching document."""
    assert "CRITICAL_COUNT" in _skill_text(), (
        "the skill teaches the gate's input and never mentions the count the gate's "
        "downgrade path requires — see this module's docstring")


def test_what_the_skill_teaches_parses_as_the_parser_expects():
    """Round-trip: build the sentinel block the skill teaches, feed it to the real parsers.

    Asserted against `_parse_critical_count` / `_parse_verify_verdict` themselves, so a
    future tightening of either regex fails here instead of silently invalidating the
    documentation.
    """
    emitted = "Some report body.\n\nCRITICAL_COUNT: 0\nVERIFY_RESULT: PASS\n"

    assert _parse_critical_count(emitted) == 0
    assert _parse_verify_verdict(emitted) == "pass"


def test_the_downgrade_path_is_reachable_from_what_the_skill_teaches():
    """FAIL + a zero count is the one combination the downgrade needs. It must parse."""
    emitted = "3 warnings, no criticals.\n\nCRITICAL_COUNT: 0\nVERIFY_RESULT: FAIL\n"

    assert _parse_verify_verdict(emitted) == "fail"
    assert _parse_critical_count(emitted) == 0, (
        "warnings-only reports could never be downgraded, so the gate would block on them")


def test_the_skill_does_not_still_say_the_verdict_is_the_final_LINE():
    """Two documents teaching different line counts makes the agent choose.

    Both parsers scan the tail and take the last match, so the order is survivable — but a
    skill saying "final line" while the prompt says "final two lines" is the same
    disagreement that produced the missing count.
    """
    text = _skill_text()

    assert not re.search(r"VERIFY_RESULT[^\n]*as the final line", text), (
        "the skill still teaches a one-line sign-off while the prompt asks for two")


def test_the_prompt_and_the_skill_teach_the_same_two_sentinels():
    """Neither document is the source of truth alone; they must simply not disagree."""
    prompt_source = VERIFIER.read_text(encoding="utf-8")
    skill = _skill_text()

    for sentinel in ("CRITICAL_COUNT:", "VERIFY_RESULT:"):
        assert sentinel in prompt_source, f"{sentinel} vanished from the orchestrator prompt"
        assert sentinel in skill, f"{sentinel} is not taught by the skill"


@pytest.mark.parametrize("decorated", [
    "CRITICAL_COUNT: 0 — but I could not check the auth module",
    "> CRITICAL_COUNT: 0",
])
def test_a_decorated_count_line_is_still_refused(decorated):
    """The skill now says "nothing else on the line". That instruction has to be true.

    A skill teaching a stricter shape than the parser enforces would be harmless; teaching
    a looser one sends the agent to write something rejected. Here the parser is the strict
    one, so the instruction matches it — asserted, because the two are edited separately.
    """
    assert _parse_critical_count(f"body\n\n{decorated}\nVERIFY_RESULT: FAIL\n") is None
