"""Tests for the cost-estimation + token-attribution metrics layer.

Witnessed in micro-web-run-20260426-1704: 58.9M total tokens / 8 changes
look like a lot, but the actual financial cost is hidden behind
"input/output/cache_read/cache_create" semantics. These tests pin the
cost calculator + per-section input.md attribution + duplicate-read
detection so the dashboard surfaces real spend vs raw counts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from set_orch.cost import (
    cost_breakdown,
    estimate_cost_usd,
)
from set_orch.dispatcher import _section_size_breakdown
from set_orch.session_analysis import (
    _encode_cwd_to_session_dir,
    detect_duplicate_reads,
)


# ─── cost ────────────────────────────────────────────────────────────────


def test_opus_cost_basics():
    """1M output on Opus 4.7 → $25.

    Was asserted at $75 until 2026-08-27, when the rates were read from
    platform.claude.com and Opus 4.5/4.6/4.7 turned out to be $5/$25 —
    a third of what this table had carried for them. The $75 figure is
    real, but it belongs to the RETIRED Opus 4/4.1, which is why the
    stale row looked plausible for so long.
    """
    cost = estimate_cost_usd(
        model="claude-opus-4-7",
        input_tokens=0,
        output_tokens=1_000_000,
        cache_read_tokens=0,
        cache_create_tokens=0,
    )
    assert cost == 25.0


def test_sonnet_cheaper_than_opus():
    args = dict(
        input_tokens=1_000_000, output_tokens=0,
        cache_read_tokens=0, cache_create_tokens=0,
    )
    opus = estimate_cost_usd(model="claude-opus-4-7", **args)
    sonnet = estimate_cost_usd(model="claude-sonnet-4-6", **args)
    haiku = estimate_cost_usd(model="claude-haiku-4-5", **args)
    assert opus > sonnet > haiku


def test_cache_read_orders_of_magnitude_cheaper():
    """Cache read is a tenth of raw input, whatever the model costs.

    Asserted as a RATIO rather than against two currency figures, so a
    price change moves both sides and this test keeps measuring the
    multiplier — which is the thing that is actually stable.
    """
    raw = estimate_cost_usd(
        model="claude-opus-4-7",
        input_tokens=1_000_000, output_tokens=0,
        cache_read_tokens=0, cache_create_tokens=0,
    )
    cached = estimate_cost_usd(
        model="claude-opus-4-7",
        input_tokens=0, output_tokens=0,
        cache_read_tokens=1_000_000, cache_create_tokens=0,
    )
    assert raw == cached * 10


def test_unknown_model_falls_back_to_opus():
    cost = estimate_cost_usd(
        model="claude-some-future-model",
        input_tokens=1_000_000, output_tokens=0,
        cache_read_tokens=0, cache_create_tokens=0,
    )
    # Should still produce a non-zero cost via family fallback
    assert cost > 0


def test_breakdown_sums_to_total():
    bd = cost_breakdown(
        model="claude-opus-4-7",
        input_tokens=1_000_000,
        output_tokens=2_000_000,
        cache_read_tokens=3_000_000,
        cache_create_tokens=4_000_000,
    )
    assert bd["total"] == round(
        bd["input"] + bd["output"] + bd["cache_read"] + bd["cache_create"], 4,
    )


def test_witnessed_contact_wizard_session_cost():
    """One Implementation session of contact-wizard-form (a8091a4e):
    9,436,420 input_tokens (state semantics: raw 1,252 + cache_read
    9,435,168), 62,244 output, 377,519 cache_create on Opus 4.7.

    Expected ~$25:
    At the rates verified 2026-08-27 ($5 input / $25 output on Opus 4.7):
      raw 1,252    × $5.00/M = $0.006
      output 62K   × $25.00/M = $1.556
      cache_r 9.4M × $0.50/M = $4.718
      cache_c 377K × $6.25/M = $2.360
      total ~ $8.64

    The window was 22..30 while this module priced Opus 4.7 at $15/$75.
    """
    cost = estimate_cost_usd(
        model="claude-opus-4-7",
        input_tokens=1252 + 9435168,  # state-style: raw + cache_read
        output_tokens=62244,
        cache_read_tokens=9435168,
        cache_create_tokens=377519,
    )
    assert 7 <= cost <= 11, (
        f"Expected ~$8.6 for this session shape; got ${cost}"
    )


def test_state_semantic_input_tokens_does_not_double_count_cache():
    """Regression: the orchestrator's state stores input_tokens as
    raw+cache_read combined (loop/state.sh:307). cost.py must NOT
    bill the cache_read portion at the raw input rate.

    Witnessed bug in a consumer E2E run: state.input_tokens=36M, which
    is mostly cache_read, but the calculation billed all of it at the
    raw input rate.

    The ceiling is kept TIGHT on purpose. At the rates verified
    2026-08-27 the correct answer is ~$31.7 and the bug's answer would
    be ~$211.7 (36M × $5/M on top). The old ceiling of 110 was chosen
    against $15/M rates; left alone it would now sit between the two
    and still pass — a test that stops separating the states it was
    written to separate, while still reporting green.
    """
    cost = estimate_cost_usd(
        model="claude-opus-4-7",
        input_tokens=36_000_000,         # raw + cache_read combined
        output_tokens=235_000,
        cache_read_tokens=39_500_000,    # cache_read alone
        cache_create_tokens=970_000,
    )
    # raw_input = max(0, 36M - 39.5M) = 0, so the input rate contributes
    # nothing. Total ~ output($5.9) + cache_r($19.8) + cache_c($6.1) ~ $31.7.
    assert cost < 60, (
        f"State-semantic must not double-count cache_read; "
        f"~$212 would indicate the bug; got ${cost}"
    )


# ─── per-section input.md breakdown ──────────────────────────────────────


def test_section_breakdown_basic():
    content = (
        "preamble\n"
        "## Scope\nbody1\n"
        "## Implementation Manifest\nbody2 longer text here\n"
        "## Required Tests (MANDATORY — coverage gate will block)\ntest list\n"
    )
    bd = _section_size_breakdown(content)
    assert "Scope" in bd
    assert "Implementation Manifest" in bd
    # Trailing parenthesized note should be stripped
    assert "Required Tests" in bd
    assert "MANDATORY" not in str(bd.keys())


def test_section_breakdown_sizes_are_byte_offsets():
    """Each section's value is the byte distance to the next section."""
    content = "## A\nx\n## B\ny\n"
    bd = _section_size_breakdown(content)
    # "## A\nx\n" = 7 bytes, "## B\ny\n" = 7 bytes
    assert bd["A"] == 7
    assert bd["B"] == 7


def test_section_breakdown_empty_content():
    assert _section_size_breakdown("") == {}
    assert _section_size_breakdown("no headers here") == {}


def test_section_breakdown_ignores_h3():
    """Only ``## `` (H2) breaks sections — H3 and below stay inside their parent."""
    content = "## Top\nbody\n### Subsection\nmore\n## Next\nfoo\n"
    bd = _section_size_breakdown(content)
    assert set(bd.keys()) == {"Top", "Next"}
    # Top should include the H3 content
    assert bd["Top"] > len("## Top\nbody\n")


# ─── duplicate read detection ────────────────────────────────────────────


def test_encode_cwd_to_session_dir():
    assert _encode_cwd_to_session_dir(
        "/home/user/.local/share/foo"
    ) == "-home-user--local-share-foo"
    assert _encode_cwd_to_session_dir(
        "/home/user/code2/set-core"
    ) == "-home-user-code2-set-core"


def test_duplicate_reads_empty_when_no_sessions(tmp_path):
    """Worktree with no Claude session files → empty result."""
    wt = tmp_path / "wt"
    wt.mkdir()
    assert detect_duplicate_reads(str(wt)) == {}


def test_duplicate_reads_counts_repeats(tmp_path, monkeypatch):
    """Build a synthetic session dir + jsonl and verify counts."""
    wt = tmp_path / "wt"
    wt.mkdir()

    # Mock home so detect_duplicate_reads looks at our tmp path
    home = tmp_path / "home"
    sessions_dir = home / ".claude" / "projects" / _encode_cwd_to_session_dir(str(wt))
    sessions_dir.mkdir(parents=True)

    monkeypatch.setattr(
        "set_orch.session_analysis.Path.home",
        classmethod(lambda cls: home),
    )

    # Single session jsonl with 3 Read calls — file_a 2x, file_b 1x
    sess = sessions_dir / "abc-1.jsonl"
    sess.write_text(
        "\n".join(json.dumps(e) for e in [
            {"type": "user", "message": {"content": "init"}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/foo/file_a.tsx"}}
            ]}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/foo/file_b.tsx"}}
            ]}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/foo/file_a.tsx"}}
            ]}},
        ]) + "\n"
    )

    dups = detect_duplicate_reads(str(wt))
    assert dups == {"/foo/file_a.tsx": 2}


def test_duplicate_reads_aggregates_across_sessions(tmp_path, monkeypatch):
    """Ralph iterations spawn multiple sessions — counts should
    sum across all of them."""
    wt = tmp_path / "wt"
    wt.mkdir()
    home = tmp_path / "home"
    sessions_dir = home / ".claude" / "projects" / _encode_cwd_to_session_dir(str(wt))
    sessions_dir.mkdir(parents=True)
    monkeypatch.setattr(
        "set_orch.session_analysis.Path.home",
        classmethod(lambda cls: home),
    )

    # Session 1: file_x 1x
    (sessions_dir / "s1.jsonl").write_text(json.dumps({
        "type": "assistant",
        "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": "/foo/x.tsx"}}
        ]},
    }) + "\n")
    # Session 2: file_x 1x
    (sessions_dir / "s2.jsonl").write_text(json.dumps({
        "type": "assistant",
        "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": "/foo/x.tsx"}}
        ]},
    }) + "\n")

    dups = detect_duplicate_reads(str(wt))
    assert dups == {"/foo/x.tsx": 2}


def test_duplicate_reads_ignores_non_read_tools(tmp_path, monkeypatch):
    wt = tmp_path / "wt"
    wt.mkdir()
    home = tmp_path / "home"
    sessions_dir = home / ".claude" / "projects" / _encode_cwd_to_session_dir(str(wt))
    sessions_dir.mkdir(parents=True)
    monkeypatch.setattr(
        "set_orch.session_analysis.Path.home",
        classmethod(lambda cls: home),
    )
    (sessions_dir / "s.jsonl").write_text("\n".join(
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": tn, "input": {"file_path": "/x"}}
        ]}}) for tn in ("Bash", "Edit", "Write", "Grep")
    ) + "\n")

    assert detect_duplicate_reads(str(wt)) == {}


# ─── the priced-or-not lookup, and the dated table ────────────────────────
#
# `input_price_per_mtok` exists because `estimate_cost_usd`'s family fallback
# is wrong for a surface that offers the reader a figure to act on: it would
# have priced Opus 5 off Opus 4.1's row and been wrong by 3x. These tests hold
# the absence of that fallback, which is the whole point of the function.


def test_known_model_is_priced():
    from set_orch.cost import input_price_per_mtok

    assert input_price_per_mtok("claude-opus-5") == 5.00
    assert input_price_per_mtok("claude-sonnet-5") == 2.00
    assert input_price_per_mtok("claude-haiku-4-5") == 1.00


def test_a_dated_snapshot_resolves_to_its_base_id():
    """The transcript writes ids like `claude-opus-5[1m]`."""
    from set_orch.cost import input_price_per_mtok

    assert input_price_per_mtok("claude-opus-5[1m]") == 5.00


def test_the_longest_prefix_wins_not_the_first(monkeypatch):
    """A dated id matching two prefixes must resolve to the SPECIFIC one.

    `claude-opus-4-8-20260101` starts with both `claude-opus-4-8` ($5) and
    `claude-opus-4` (retired, $15). Taking the first match found would price it
    at three times its rate.

    The table is REORDERED here, shortest key first, and that is the point of
    the test rather than an implementation detail. Written first without the
    patch, it passed against a deliberately broken `matches[0]` lookup: the real
    table happens to list every long key before its shorter prefixes, so
    first-found and longest-found agree by accident. A test that cannot fail is
    not evidence, and the ordering it relied on is not a rule anything enforces.
    """
    from set_orch import cost

    reordered = {"claude-opus-4": cost._RATES["claude-opus-4"],
                 "claude-opus-4-8": cost._RATES["claude-opus-4-8"]}
    monkeypatch.setattr(cost, "_RATES", reordered)

    assert cost.input_price_per_mtok("claude-opus-4-8-20260101") == 5.00


def test_an_unknown_model_is_not_priced():
    """No fallback, no guess, no zero — None, so the caller can say so."""
    from set_orch.cost import input_price_per_mtok

    assert input_price_per_mtok("claude-nonesuch-9") is None
    assert input_price_per_mtok("") is None
    assert input_price_per_mtok(None) is None


def test_current_opus_is_not_priced_at_the_retired_rate():
    """The defect this pass fixed, held as a test: Opus 4.5/4.6/4.7 are $5,
    not the $15 they carried here until 2026-08-27. Only Opus 4 and 4.1,
    which are retired, are $15."""
    from set_orch.cost import input_price_per_mtok

    for current in ("claude-opus-4-5", "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8"):
        assert input_price_per_mtok(current) == 5.00, current
    for retired in ("claude-opus-4", "claude-opus-4-1"):
        assert input_price_per_mtok(retired) == 15.00, retired


def test_cache_rewrite_uses_the_ttl_it_is_given():
    """A one-hour entry costs 2x base input to rewrite; a five-minute one 1.25x.
    Verified against platform.claude.com on 2026-08-27."""
    from set_orch.cost import cache_rewrite_cost_usd

    hour = cache_rewrite_cost_usd(model="claude-opus-5", tokens=1_000_000, ttl_seconds=3600)
    five = cache_rewrite_cost_usd(model="claude-opus-5", tokens=1_000_000, ttl_seconds=300)
    assert hour == 10.00
    assert five == 6.25


def test_cache_rewrite_of_an_unpriced_model_is_none_not_zero():
    """A zero would read as 'free to rewrite', which is the opposite of
    'we do not know what this costs'."""
    from set_orch.cost import cache_rewrite_cost_usd

    assert cache_rewrite_cost_usd(model="claude-nonesuch-9", tokens=195_889, ttl_seconds=3600) is None


def test_the_table_states_when_it_was_verified():
    """A price is a measurement with a date. Prose in a docstring is not a
    date anything can check — this one is a constant on purpose."""
    import re
    from set_orch.cost import PRICES_VERIFIED_ON, PRICES_SOURCE

    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", PRICES_VERIFIED_ON)
    assert PRICES_SOURCE.startswith("https://")


def test_cache_figures_are_derived_from_the_input_price():
    """Every row's cache rates must be exact multiples of its own input price.
    A hand-typed cache rate is a second place for the same fact to drift, and
    this asserts there is no such place."""
    from set_orch.cost import (
        _RATES, CACHE_READ_MULTIPLIER, CACHE_WRITE_5M_MULTIPLIER, CACHE_WRITE_1H_MULTIPLIER,
    )

    for name, r in _RATES.items():
        assert r.cache_read == pytest.approx(r.input * CACHE_READ_MULTIPLIER), name
        assert r.cache_create == pytest.approx(r.input * CACHE_WRITE_5M_MULTIPLIER), name
        assert r.cache_write_1h == pytest.approx(r.input * CACHE_WRITE_1H_MULTIPLIER), name
