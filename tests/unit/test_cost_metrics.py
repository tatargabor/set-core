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
    """1M output on Opus → $75 (the canonical rate)."""
    cost = estimate_cost_usd(
        model="claude-opus-4-7",
        input_tokens=0,
        output_tokens=1_000_000,
        cache_read_tokens=0,
        cache_create_tokens=0,
    )
    assert cost == 75.0


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
    """Cache_read at 1.50/M vs raw input at 15/M (Opus): 10× cheaper."""
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
    9.8M input including 9.4M cache_read, 62K output, 377K cache_create
    on Opus 4.7 → ~$50."""
    cost = estimate_cost_usd(
        model="claude-opus-4-7",
        input_tokens=1252,
        output_tokens=62244,
        cache_read_tokens=9435168,
        cache_create_tokens=377519,
    )
    assert 20 <= cost <= 30, (
        f"Expected ~$25 for this session shape; got ${cost}"
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
        "/home/tg/.local/share/foo"
    ) == "-home-tg--local-share-foo"
    assert _encode_cwd_to_session_dir(
        "/home/tg/code2/set-core"
    ) == "-home-tg-code2-set-core"


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
