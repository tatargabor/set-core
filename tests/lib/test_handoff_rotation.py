"""Handoff rotation helpers (set-claude-handoff specs/auto-clear, fleet -p plane)."""

import asyncio

from set_orch.handoff_rotation import (
    marker_path,
    read_handoff_from_marker,
    session8,
    usage_total,
    wait_for_marker,
)


def test_usage_total_is_the_documented_identity():
    # input + cache_creation + cache_read; cache_read is the dominant term and must
    # never be dropped (a measured 334 900 of 338 009 lived there on the consumer side).
    usage = {
        "input_tokens": 10,
        "cache_creation_input_tokens": 20,
        "cache_read_input_tokens": 500_000,
    }
    assert usage_total(usage) == 500_030


def test_usage_total_tolerates_missing_and_empty():
    assert usage_total({}) == 0
    assert usage_total({"input_tokens": None}) == 0


def test_session8_strips_and_truncates():
    assert session8("a1b2c3d4e5f6-xxxx") == "a1b2c3d4e5f6"[:8]
    assert session8(None) == "ismeretlen"
    assert session8("!!!") == "ismeretlen"


def test_marker_roundtrip(tmp_path):
    p = marker_path(tmp_path, "abcd1234")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("2026-09-12T19:18:38.748Z 0912-a16a--kritikusok-prd0032-devbuild.md\n")
    assert read_handoff_from_marker(p) == "0912-a16a--kritikusok-prd0032-devbuild.md"
    assert read_handoff_from_marker(tmp_path / "missing") is None


def test_wait_for_marker_true_when_present(tmp_path):
    p = tmp_path / ".written-abcd1234"
    p.write_text("now\n")
    assert asyncio.run(wait_for_marker(p, timeout_s=1, poll_s=0.1)) is True


def test_wait_for_marker_times_out_without_rotating(tmp_path):
    # The no-silent-rotation rule: False is the caller's signal to KEEP the lineage
    # and log loudly — a rotation without a fresh handoff is the loss this prevents.
    p = tmp_path / ".written-abcd1234"
    assert asyncio.run(wait_for_marker(p, timeout_s=0.3, poll_s=0.1)) is False


def test_wait_for_marker_arrives_mid_wait(tmp_path):
    p = tmp_path / ".written-abcd1234"

    def drop():
        p.write_text("late\n")

    import threading

    t = threading.Timer(0.25, drop)
    t.start()
    try:
        assert asyncio.run(wait_for_marker(p, timeout_s=2, poll_s=0.1)) is True
    finally:
        t.cancel()
