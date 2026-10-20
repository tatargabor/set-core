"""fleet-latest-mode §1 — the last human input is found beyond the bounded tail.

Measured 2026-10-19 on the live fleet: the tail-only value was absent for 6 of
19 agents, one of them working, because a long tool run fills the 256 KB tail
with tool traffic. These drive `read_state` — the entry point the listing uses —
not the helpers, so a test passes only if the wiring reaches the deep search.
"""

import datetime
import json
import os

import pytest

from set_orch.fleet import state as S
from set_orch.fleet.state import read_state


def _epoch(ts: str) -> float:
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


NOW = _epoch("2026-10-19T12:00:00.000Z")


def _human(ts: str, text: str = "do it"):
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": text}}


def _tool_result(ts: str, size: int = 2000):
    return {"type": "user", "timestamp": ts, "toolUseResult": {"stdout": "x" * size},
            "message": {"role": "user", "content": [{"type": "tool_result", "content": "x" * size}]}}


def _lines(entries) -> str:
    return "".join(json.dumps(e) + "\n" for e in entries)


def _traffic(nbytes: int, ts: str = "2026-10-19T11:59:00.000Z"):
    """More than `nbytes` of tool results: none of it is a person."""
    out, total = [], 0
    while total <= nbytes:
        entry = _tool_result(ts)
        out.append(entry)
        total += len(json.dumps(entry)) + 1
    return out


@pytest.fixture(autouse=True)
def _fresh_cache():
    S._human_cache.clear()
    yield
    S._human_cache.clear()


def test_a_message_buried_under_more_than_the_tail_is_found(tmp_path):
    log = tmp_path / "buried.jsonl"
    log.write_text(_lines([_human("2026-10-19T11:00:00.000Z")] + _traffic(S.TAIL_BYTES * 2)))
    st = read_state(str(log), now=NOW)
    assert st.last_human_input_age == pytest.approx(3600, abs=2)


def test_a_transcript_with_no_human_entry_stays_absent(tmp_path):
    log = tmp_path / "nobody.jsonl"
    log.write_text(_lines(_traffic(S.TAIL_BYTES * 2)))
    st = read_state(str(log), now=NOW)
    assert st.last_human_input_age is None


def test_growth_without_human_text_reuses_the_cache_without_reading(tmp_path):
    log = tmp_path / "grows.jsonl"
    log.write_text(_lines([_human("2026-10-19T11:00:00.000Z")] + _traffic(S.TAIL_BYTES * 2)))
    read_state(str(log), now=NOW)
    before = S.deep_search_bytes_read
    with log.open("a") as fh:
        fh.write(_lines([_tool_result("2026-10-19T11:59:30.000Z")]))
    st = read_state(str(log), now=NOW + 60)
    assert S.deep_search_bytes_read == before
    # The age is recomputed from `now`, not frozen at the cached search.
    assert st.last_human_input_age == pytest.approx(3660, abs=2)


def test_growth_past_the_tail_reads_only_the_gap(tmp_path):
    log = tmp_path / "gap.jsonl"
    log.write_text(_lines([_human("2026-10-19T10:00:00.000Z")] + _traffic(S.TAIL_BYTES * 2)))
    read_state(str(log), now=NOW)
    first_size = os.path.getsize(log)
    # A newer person entry, then more than a tail of traffic on top of it.
    with log.open("a") as fh:
        fh.write(_lines([_human("2026-10-19T11:00:00.000Z")] + _traffic(S.TAIL_BYTES * 2)))
    before = S.deep_search_bytes_read
    st = read_state(str(log), now=NOW)
    assert st.last_human_input_age == pytest.approx(3600, abs=2)
    # Nothing before the first search's end was read again.
    assert S.deep_search_bytes_read - before <= os.path.getsize(log) - first_size


def test_an_inode_change_invalidates_the_cache(tmp_path):
    log = tmp_path / "replaced.jsonl"
    log.write_text(_lines([_human("2026-10-19T11:00:00.000Z")] + _traffic(S.TAIL_BYTES * 2)))
    read_state(str(log), now=NOW)
    replacement = tmp_path / "new.jsonl"
    replacement.write_text(_lines(_traffic(S.TAIL_BYTES * 3)))
    os.replace(replacement, log)
    st = read_state(str(log), now=NOW)
    assert st.last_human_input_age is None


def test_a_human_entry_in_the_tail_still_wins(tmp_path):
    log = tmp_path / "tail.jsonl"
    log.write_text(_lines(_traffic(S.TAIL_BYTES * 2) + [_human("2026-10-19T11:30:00.000Z")]))
    before = S.deep_search_bytes_read
    st = read_state(str(log), now=NOW)
    assert st.last_human_input_age == pytest.approx(1800, abs=2)
    assert S.deep_search_bytes_read == before


def test_a_line_split_across_chunks_is_read_whole(tmp_path):
    """The chunk boundary falls inside the person's line; the carry joins it."""
    log = tmp_path / "split.jsonl"
    head = _lines(_traffic(S.TAIL_BYTES // 2))
    person = _lines([_human("2026-10-19T11:00:00.000Z", text="y" * 5000)])
    log.write_text(head + person + _lines(_traffic(S.TAIL_BYTES * 2)))
    st = read_state(str(log), now=NOW)
    assert st.last_human_input_age == pytest.approx(3600, abs=2)


def test_transcripts_no_longer_listed_are_forgotten(tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    for p in (a, b):
        p.write_text(_lines(_traffic(S.TAIL_BYTES * 2)))
        read_state(str(p), now=NOW)
    S.prune_human_cache([str(a)])
    assert set(S._human_cache) == {str(a)}


def test_the_cache_holds_no_message_text(tmp_path):
    log = tmp_path / "private.jsonl"
    log.write_text(_lines([_human("2026-10-19T11:00:00.000Z", text="secret words")]
                          + _traffic(S.TAIL_BYTES * 2)))
    read_state(str(log), now=NOW)
    assert "secret" not in repr(S._human_cache)
