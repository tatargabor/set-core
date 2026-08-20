"""The header's arithmetic must close — every state lands in exactly one bucket.

Written after the defect it guards, which was found by review rather than by a
test: adding a new state value (`asking`) to a producer whose counters were an
`if / else if` chain with no final branch. Every reader of the state — the API
envelope and the web tally — bucketed `working`, `unknown` and `waiting` and
counted anything else nowhere at all. The agent stayed in `agents`, so the
numbers beside it simply stopped adding up, and the direction is the expensive
one: the agent that most needs a person disappears from the header while the
screen looks calm.

So the assertion here is not "asking is counted". It is that **the buckets sum
to the population**, which is a claim about the next state too — the one nobody
has thought of yet.
"""

from __future__ import annotations

import pytest

from set_orch.api.fleet import STATE_BUCKETS, _state_tally
from set_orch.fleet.state import AgentState


def _states(*values: str) -> dict:
    return {i: AgentState(state=v) for i, v in enumerate(values)}


@pytest.mark.parametrize("state", STATE_BUCKETS)
def test_every_declared_bucket_counts_its_own_state(state):
    t = _state_tally(_states(state))
    assert t[state] == 1
    assert t["unbucketed"] == 0


def test_the_buckets_sum_to_the_population():
    """The claim that survives the next new state."""
    population = _states(*STATE_BUCKETS, "working", "quiet", "asking")
    t = _state_tally(population)
    assert sum(t[name] for name in STATE_BUCKETS) + t["unbucketed"] == len(population)


def test_a_state_no_bucket_counts_is_reported_not_swallowed():
    """The failure this file exists for, made loud instead of silent."""
    t = _state_tally(_states("working", "a-state-invented-later"))
    assert t["unbucketed"] == 1
    assert sum(t[name] for name in STATE_BUCKETS) + t["unbucketed"] == 2


def test_asking_is_its_own_bucket_and_not_folded_into_waiting():
    """They are a MEASUREMENT and a DECLARATION and must stay apart.

    `waiting` comes from the runtime's record saying so; `asking` is read off
    the log and needs nobody's word for it. Summing them would make the
    distinction unrecoverable at exactly the moment a reader wants it — when
    deciding whether to trust the number.
    """
    t = _state_tally(_states("asking", "waiting"))
    assert t["asking"] == 1
    assert t["waiting"] == 1


def test_the_bucket_list_and_the_dataclass_agree_on_every_state_the_producer_emits():
    """A second copy, held by a test instead of by a comment asking to be believed.

    `STATE_BUCKETS` is a list in the API layer naming values produced in the
    state layer. Two places, so they can drift — and the drift is invisible,
    because a producer emitting a state the list forgot does not error, it just
    stops being counted.
    """
    from set_orch.fleet import state as st

    produced = {st.WORKING, st.UNKNOWN, st.WAITING, st.ASKING, st.QUIET}
    assert produced == set(STATE_BUCKETS)
