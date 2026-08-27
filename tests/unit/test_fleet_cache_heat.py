"""What a session's prompt-cache state is, and what it is when nobody measured it.

The half worth testing hardest is the absent one. A missing measurement rendered
as a zero-token, long-expired cache reads as "cold, cheap to restart" — the exact
opposite of the truth — and nothing about it looks wrong on screen.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from set_orch.fleet.cache_heat import CacheHeat, read_cache_heat


def _record(*, when: datetime, read: int = 100_000, write: int = 5_000,
            ttl_key: str = "ephemeral_1h_input_tokens",
            model: str | None = "claude-opus-5") -> str:
    """One assistant record, shaped as the runtime writes it."""
    creation = {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0}
    if ttl_key:
        creation[ttl_key] = write
    message: dict = {
        "usage": {
            "input_tokens": 2,
            "cache_read_input_tokens": read,
            "cache_creation_input_tokens": write,
            "output_tokens": 40,
            "cache_creation": creation,
        }
    }
    if model:
        message["model"] = model
    return json.dumps({
        "timestamp": when.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "type": "assistant",
        "message": message,
    })


def _write(tmp_path, lines, name="session.jsonl"):
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(p)


NOW = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)


# ─── reading it ───────────────────────────────────────────────────────────


def test_the_last_record_is_the_one_that_counts(tmp_path):
    path = _write(tmp_path, [
        _record(when=NOW - timedelta(hours=3), read=10, write=10),
        _record(when=NOW - timedelta(minutes=5), read=140_000, write=1_403),
    ])
    heat = read_cache_heat(path)
    assert heat is not None
    assert heat.tokens == 141_403
    assert heat.started_at == NOW - timedelta(minutes=5)


def test_size_is_read_plus_creation(tmp_path):
    path = _write(tmp_path, [_record(when=NOW, read=194_772, write=1_117)])
    assert read_cache_heat(path).tokens == 195_889


def test_the_lifetime_is_read_from_the_record(tmp_path):
    """Not a constant. The runtime writes one hour today and five minutes is the
    API's default; both are legal and the choice is per request."""
    hour = _write(tmp_path, [_record(when=NOW, ttl_key="ephemeral_1h_input_tokens")], "h.jsonl")
    five = _write(tmp_path, [_record(when=NOW, ttl_key="ephemeral_5m_input_tokens")], "m.jsonl")
    assert read_cache_heat(hour).ttl_seconds == 3600
    assert read_cache_heat(five).ttl_seconds == 300


def test_a_read_only_turn_falls_back_to_the_shorter_lifetime(tmp_path):
    """A turn that wrote nothing names no lifetime. The floor is the API default,
    which under-states how long the cache lives rather than promising warmth."""
    path = _write(tmp_path, [_record(when=NOW, write=0, ttl_key="")])
    assert read_cache_heat(path).ttl_seconds == 300


def test_the_model_and_its_price_come_along(tmp_path):
    path = _write(tmp_path, [_record(when=NOW, read=195_889, write=0, ttl_key="")])
    heat = read_cache_heat(path)
    assert heat.model == "claude-opus-5"
    # 5-minute fallback lifetime -> the 1.25x write multiplier.
    assert heat.rewrite_usd == pytest.approx(195_889 / 1e6 * 5.00 * 1.25, abs=1e-3)


def test_an_unpriced_model_yields_tokens_but_no_cost(tmp_path):
    path = _write(tmp_path, [_record(when=NOW, model="claude-nonesuch-9")])
    heat = read_cache_heat(path)
    assert heat.tokens > 0
    assert heat.rewrite_usd is None


# ─── the backward scan ────────────────────────────────────────────────────


def test_the_scan_starts_at_the_END_of_the_file(tmp_path):
    """A transcript is megabytes and this runs per agent per poll.

    Written so it FAILS on a forward scan rather than merely being slower on
    one: the first record in the file carries a different size, so a reader that
    starts at the top returns 999 999 and the assertion catches it.
    """
    filler = [_record(when=NOW - timedelta(hours=2), read=999_999, write=0)]
    filler += [json.dumps({"type": "user", "message": {"content": "x" * 2000}})
               for _ in range(4000)]
    filler += [_record(when=NOW, read=140_000, write=1_403)]
    path = _write(tmp_path, filler)

    assert (tmp_path / "session.jsonl").stat().st_size > 8_000_000
    assert read_cache_heat(path).tokens == 141_403


def test_a_record_beyond_the_tail_window_is_not_measured(tmp_path):
    """Bounded work, and the bound reports absence rather than a wrong number.

    The cap exists so one enormous transcript cannot make the fleet endpoint
    slow. Stated as a test because a silent full-file read is exactly what the
    cap is there to prevent, and nothing else would notice.
    """
    lines = [_record(when=NOW, read=140_000, write=1_403)]
    lines += [json.dumps({"type": "user", "message": {"content": "x" * 4000}})
              for _ in range(1200)]
    path = _write(tmp_path, lines)
    assert (tmp_path / "session.jsonl").stat().st_size > 4 * 1024 * 1024
    assert read_cache_heat(path) is None


# ─── absent, which is not zero ────────────────────────────────────────────


def test_no_path_is_absent():
    assert read_cache_heat(None) is None
    assert read_cache_heat("") is None


def test_a_missing_file_is_absent(tmp_path):
    assert read_cache_heat(str(tmp_path / "nope.jsonl")) is None


def test_an_empty_file_is_absent(tmp_path):
    p = tmp_path / "empty.jsonl"
    p.write_text("", encoding="utf-8")
    assert read_cache_heat(str(p)) is None


def test_a_transcript_with_no_usage_records_is_absent(tmp_path):
    path = _write(tmp_path, [
        json.dumps({"timestamp": NOW.isoformat(), "type": "user", "message": {"content": "hi"}}),
        json.dumps({"timestamp": NOW.isoformat(), "type": "assistant", "message": {"content": "ok"}}),
    ])
    assert read_cache_heat(path) is None


def test_a_truncated_last_line_falls_back_to_the_record_before_it(tmp_path):
    """The file is appended to while this reads it, so a half-written final line
    is ordinary rather than exceptional."""
    good = _record(when=NOW - timedelta(minutes=1), read=140_000, write=1_403)
    p = tmp_path / "session.jsonl"
    p.write_text(good + "\n" + '{"timestamp": "2026-08-27T12:0', encoding="utf-8")
    assert read_cache_heat(str(p)).tokens == 141_403


def test_a_request_that_touched_no_cache_is_absent(tmp_path):
    """Zero cache tokens is not a zero-sized cache — it is a turn with nothing
    to be warm about. Reporting it as cold would be a claim about a cache that
    does not exist."""
    path = _write(tmp_path, [_record(when=NOW, read=0, write=0, ttl_key="")])
    assert read_cache_heat(path) is None


def test_an_unparseable_timestamp_is_absent(tmp_path):
    path = _write(tmp_path, [json.dumps({
        "timestamp": "not-a-time", "type": "assistant",
        "message": {"usage": {"cache_read_input_tokens": 100, "cache_creation_input_tokens": 0}},
    })])
    assert read_cache_heat(path) is None


# ─── the arithmetic the surface depends on ────────────────────────────────


def _heat(ttl=3600, started=NOW, tokens=100_000):
    return CacheHeat(started_at=started, tokens=tokens, ttl_seconds=ttl,
                     model="claude-opus-5", rewrite_usd=1.0)


def test_cooling_runs_from_zero_at_the_request_to_one_at_expiry():
    h = _heat()
    assert h.cooled_fraction(NOW) == 0.0
    assert h.cooled_fraction(NOW + timedelta(minutes=30)) == pytest.approx(0.5)
    assert h.cooled_fraction(NOW + timedelta(minutes=60)) == 1.0


def test_cooling_is_clamped_past_expiry_and_before_the_request():
    h = _heat()
    assert h.cooled_fraction(NOW + timedelta(days=2)) == 1.0
    # A clock that moved backwards reads as fresh, not as a negative bar.
    assert h.cooled_fraction(NOW - timedelta(minutes=10)) == 0.0


def test_cold_is_exactly_the_end_of_the_bar():
    """One condition drives the full bar, the red name and the price. If this
    ever disagreed with `cooled_fraction`, a tab could show a full bar with a
    live name and the reader would not know which to believe."""
    h = _heat()
    for offset in (0, 30, 59, 60, 61, 600):
        moment = NOW + timedelta(minutes=offset)
        assert h.is_cold(moment) == (h.cooled_fraction(moment) >= 1.0)


def test_remaining_seconds_never_go_negative():
    h = _heat()
    assert h.seconds_remaining(NOW + timedelta(minutes=45)) == pytest.approx(900)
    assert h.seconds_remaining(NOW + timedelta(hours=5)) == 0.0


def test_a_usage_record_behind_large_records_is_still_found(tmp_path):
    """The defect the unit tests could not see, held as one.

    Measured 2026-08-27 on a live 5.7 MB transcript: the session read as
    UNMEASURED while carrying a perfectly good 489 488-token record. The records
    nearest the end were large — a screenshot's base64, a big tool result — so
    the first 64 KB chunk read backwards held only those, none with a `usage`
    block, and the reader stopped there instead of continuing.

    Every fixture above fits inside one chunk, so all nineteen of them passed
    against the broken reader. This one does not fit, on purpose: the usage
    record sits behind ~200 KB of oversized records, several of them individually
    larger than the chunk.
    """
    lines = [_record(when=NOW, read=489_000, write=488)]
    # Individually chunk-sized records, so a reader that returns the first
    # non-empty chunk gets nothing but these.
    lines += [json.dumps({"type": "user", "message": {"content": "x" * 70_000}})
              for _ in range(3)]
    path = _write(tmp_path, lines)

    assert (tmp_path / "session.jsonl").stat().st_size > 200_000
    heat = read_cache_heat(path)
    assert heat is not None, "a record behind large ones must still be found"
    assert heat.tokens == 489_488


def test_a_single_record_larger_than_a_chunk_is_read_whole(tmp_path):
    """A base64 screenshot is one line, and it can exceed the chunk on its own.

    The line has to be reassembled across reads rather than being handed back in
    pieces — a fragment does not parse as JSON, and silently skipping it would
    lose the record it belongs to.
    """
    big = _record(when=NOW, read=140_000, write=1_403)
    padded = json.dumps({"timestamp": NOW.isoformat(), "type": "user",
                         "message": {"content": "y" * 150_000}})
    path = _write(tmp_path, [big, padded])
    assert read_cache_heat(path).tokens == 141_403
