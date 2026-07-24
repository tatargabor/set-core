"""The verify sentinel decides whether work reaches main. It is also a word in prose.

`VERIFY_RESULT: PASS|FAIL` is emitted by an LLM into free text, so the token also turns
up in the instructions the model quotes back, in a fenced example of the format, and in
an echo of an earlier run. It used to be read with a bare substring test that checked
PASS first — so an output explaining the rule before failing returned pass, and the
change merged.

That is fail-OPEN on the gate that guards main, which is why it is worth more than the
count sentinel next to it: `_parse_critical_count` had already been hardened against
exactly this, and the verdict had not. The two now share their rules so they cannot
drift apart again.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from set_orch.verifier import (  # noqa: E402
    _classify_spec_verify_outcome,
    _parse_critical_count,
    _parse_verify_verdict,
)


def test_a_plain_verdict_is_read():
    assert _parse_verify_verdict("VERIFY_RESULT: PASS") == "pass"
    assert _parse_verify_verdict("VERIFY_RESULT: FAIL") == "fail"


def test_the_rule_quoted_before_the_verdict_does_not_become_the_verdict():
    """The exact shape that made a failing verification merge."""
    output = (
        "The rule is to emit VERIFY_RESULT: PASS when nothing is critical.\n"
        "There are 3 critical findings.\n"
        "VERIFY_RESULT: FAIL\n"
    )

    assert _parse_verify_verdict(output) == "fail"


def test_the_last_sentinel_wins_because_the_signoff_is_last():
    output = "VERIFY_RESULT: FAIL\nOn retry the issue was fixed.\nVERIFY_RESULT: PASS\n"

    assert _parse_verify_verdict(output) == "pass"


def test_a_quoted_line_is_not_a_verdict():
    """A `>` prefix is someone reporting a verdict, not casting one."""
    assert _parse_verify_verdict("> VERIFY_RESULT: PASS\n") is None


def test_an_inline_mention_is_not_a_verdict():
    assert _parse_verify_verdict("I will now emit VERIFY_RESULT: PASS shortly.\n") is None


def test_absence_is_None_not_a_guess():
    """None routes to the classifier fallback; a default would route to a merge."""
    assert _parse_verify_verdict("no sentinel here") is None
    assert _parse_verify_verdict("") is None


def test_a_sentinel_buried_far_from_the_end_is_not_the_signoff():
    """The prompt asks for it second-to-last; a quoted document is not a sign-off."""
    output = "VERIFY_RESULT: PASS\n" + ("x" * 5000)

    assert _parse_verify_verdict(output) is None


def test_leading_whitespace_is_tolerated_because_the_model_indents():
    assert _parse_verify_verdict("   VERIFY_RESULT: FAIL\n") == "fail"


def test_a_longer_word_starting_with_the_verdict_does_not_match():
    assert _parse_verify_verdict("VERIFY_RESULT: PASSED_EARLIER\n") is None


def test_the_two_sentinel_parsers_agree_on_what_counts_as_quoted():
    """They guard one decision together; a difference between them is a hole."""
    quoted = "> VERIFY_RESULT: FAIL\n> CRITICAL_COUNT: 0\n"

    assert _parse_verify_verdict(quoted) is None
    assert _parse_critical_count(quoted) is None


class _Result:
    timed_out = False


def test_classification_no_longer_calls_a_quoted_mention_a_verdict():
    """Otherwise an explanation is classified as a verdict and never reaches fallback."""
    output = "I will emit VERIFY_RESULT: PASS if all is well.\n"

    assert _classify_spec_verify_outcome(_Result(), output)[0] == "ambiguous"


def test_classification_still_recognises_a_real_verdict():
    assert _classify_spec_verify_outcome(_Result(), "VERIFY_RESULT: FAIL\n")[0] == "verdict"


# ── the second half of the same lesson: a line that STARTS with the sentinel ──
#
# Anchoring at line start stops a quoted verdict. It does not stop a line that opens with
# the sentinel and then says something else — including something that means the opposite.
# A peer running an unrelated gate hit the negation-blind version of this and described
# the shape; it was still open here, on the gate that decides whether work reaches main.

def test_a_sentence_that_STARTS_with_the_sentinel_is_not_a_verdict():
    """The regex cannot read the negation, so the sentence means the opposite of the
    thing it matched — and matched in the pass direction."""
    assert _parse_verify_verdict("VERIFY_RESULT: PASS is NOT what I emit here.\n") is None


def test_a_verdict_followed_by_a_retraction_is_not_a_verdict():
    output = "VERIFY_RESULT: PASS — wait, actually there are 3 criticals.\n"

    assert _parse_verify_verdict(output) is None


def test_trailing_whitespace_still_counts_because_that_is_not_prose():
    assert _parse_verify_verdict("VERIFY_RESULT: FAIL   \n") == "fail"
    assert _parse_verify_verdict("VERIFY_RESULT: PASS\r\n") == "pass"


def test_a_count_with_a_caveat_after_it_is_not_a_count():
    """This one is worse than it looks: a zero DOWNGRADES an explicit FAIL to pass, so
    the sentence describing what could not be checked was the thing that hid it."""
    output = "CRITICAL_COUNT: 0 — but I could not check the auth module\n"

    assert _parse_critical_count(output) is None


def test_a_missing_count_still_blocks_so_tightening_can_only_fail_closed():
    """The caller treats None as 'keep blocking'. That is what makes the stricter match
    safe: every input this newly rejects lands on the conservative side."""
    assert _parse_critical_count("no sentinel at all\n") is None
