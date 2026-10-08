"""Glob semantics shared by include/exclude and the channel rules."""

from __future__ import annotations

from set_kb.glob import glob_to_re, match_any


def one(pattern: str, rel: str) -> bool:
    return match_any([glob_to_re(pattern)], rel)


def test_star_within_segment_does_not_cross_slashes():
    assert one("client-*/mail.md", "client-alfa/mail.md")
    assert not one("client-*/mail.md", "client-alfa/deep/mail.md")


def test_dir_glob_fires_at_any_depth():
    assert one("client-*/**", "client-alfa/mail.md")
    assert one("client-*/**", "nested/client-alfa/mail.md"), "(^|/) lets the pattern fire at any depth"
    assert one("client-*/**", "client-alfa/deep/mail.md")


def test_double_star_crosses_slashes():
    assert one("**/sessions/**", "a/b/sessions/x.md")
    assert one("**/sessions/**", "sessions/x.md"), "the leading (.*/) is OPTIONAL — fires at the root too"
    assert not one("**/sessions/**", "a/b/sessionsx.md")


def test_dir_style_trailing_slash_means_tree():
    assert one("copilot/", "copilot/2026-08/x.md"), "`copilot/` ≡ `copilot/**`"
    assert one("copilot/", "copilot/x.md")


def test_leading_dot_slash_is_normalised():
    # "./" would compile to an escaped literal prefix no root-relative path
    # starts with — stripped, the pattern behaves as if "./" was never written.
    assert one("./copilot/x.md", "copilot/x.md")
    assert one("./copilot/x.md", "deep/copilot/x.md"), "same anchoring as the un-prefixed pattern"


def test_question_mark_is_single_char():
    assert one("a?c.md", "abc.md")
    assert not one("a?c.md", "ac.md")
    assert not one("a?c.md", "abbc.md")


def test_regex_metacharacters_are_literal():
    assert one("a.b.md", "a.b.md")
    assert not one("a.b.md", "axb.md")
    assert one("c++/notes.md", "c++/notes.md")


def test_anchor_is_segment_aware():
    assert one("meetings/**", "meetings/x.md")
    assert one("meetings/**", "deep/meetings/x.md")
    assert one("minutes/**", "x/minutes/x.md"), "dir patterns fire at any depth"
    assert not one("minutes/**", "x/minutes-other/x.md"), "matching is segment-aware, not a substring test"
    assert not one("**/minutes/**", "minutes-other/x.md")
