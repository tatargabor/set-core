"""The worktree porcelain parser, and the `prunable` line it used to drop.

Written for `fleet-start-agent-in-worktree`. The parser feeds two things that
must agree: what the start form offers as a location, and what the start
endpoint accepts. A prunable worktree is one whose directory git can no longer
find — nothing can run there — and before this change it parsed *identically to
a live one*, so every surface presented it as startable.

Measured in a real repository on 2026-08-23: four worktrees listed, three
prunable, all four shown as live by the dashboard and by `set-list`.
"""

from __future__ import annotations

from pathlib import Path

from set_orch.api.helpers import (
    _parse_worktree_porcelain,
    list_worktree_locations,
)


MAIN_ONLY = """\
worktree /repo
HEAD 29cec4054a0f53e87f5232043cf97499a3db7f53
branch refs/heads/main
"""

MAIN_AND_TWO = """\
worktree /repo
HEAD 29cec4054a0f53e87f5232043cf97499a3db7f53
branch refs/heads/main

worktree /repo-add-auth
HEAD a7e5b5de0bd4a74aaef105c8844ce879b603a734
branch refs/heads/change/add-auth

worktree /repo-fix-gate
HEAD ec614fcb4c6b816ad7baf2fd203e0ccc1521f298
branch refs/heads/change/fix-gate
"""

DETACHED = """\
worktree /repo
HEAD 29cec4054a0f53e87f5232043cf97499a3db7f53
branch refs/heads/main

worktree /tmp/base
HEAD 1bc30eaf518ffd29869eb130da3469c486cbb4f9
detached
"""

WITH_PRUNABLE = """\
worktree /repo
HEAD 29cec4054a0f53e87f5232043cf97499a3db7f53
branch refs/heads/main

worktree /tmp/base-e78
HEAD 1bc30eaf518ffd29869eb130da3469c486cbb4f9
detached
prunable gitdir file points to non-existent location
"""


def test_a_lone_main_checkout_parses_as_one_entry_marked_main():
    parsed = _parse_worktree_porcelain(MAIN_ONLY)
    assert len(parsed) == 1
    assert parsed[0]["path"] == "/repo"
    assert parsed[0]["branch"] == "main"
    assert parsed[0]["is_main"] is True
    assert parsed[0]["prunable"] is False


def test_two_worktrees_beside_the_main_checkout_parse_with_their_branches():
    parsed = _parse_worktree_porcelain(MAIN_AND_TWO)
    assert [wt["path"] for wt in parsed] == ["/repo", "/repo-add-auth", "/repo-fix-gate"]
    assert [wt["branch"] for wt in parsed] == ["main", "change/add-auth", "change/fix-gate"]
    # Exactly one main checkout — the form's default depends on that being unique.
    assert [wt["is_main"] for wt in parsed] == [True, False, False]


def test_a_detached_worktree_has_an_empty_branch_rather_than_a_missing_key():
    parsed = _parse_worktree_porcelain(DETACHED)
    assert parsed[1]["branch"] == ""
    assert parsed[1]["detached"] is True
    # A detached worktree is perfectly startable; only prunable is not.
    assert parsed[1]["prunable"] is False


def test_a_prunable_worktree_is_marked_prunable_and_carries_the_reason():
    """The whole point. Before this change the `prunable` line was dropped."""
    parsed = _parse_worktree_porcelain(WITH_PRUNABLE)
    assert len(parsed) == 2
    assert parsed[0]["prunable"] is False
    assert parsed[1]["prunable"] is True
    assert "non-existent" in parsed[1]["prunable_reason"]


def test_a_bare_prunable_line_with_no_reason_still_marks_the_entry():
    """git omits the reason in some versions; the flag must not depend on it."""
    parsed = _parse_worktree_porcelain(
        "worktree /repo\nHEAD abc\nbranch refs/heads/main\n\n"
        "worktree /gone\nHEAD def\ndetached\nprunable\n"
    )
    assert parsed[1]["prunable"] is True
    assert "prunable_reason" not in parsed[1]


def test_empty_output_parses_to_no_locations_rather_than_raising():
    assert _parse_worktree_porcelain("") == []


def test_locations_carry_only_identity_and_never_touch_the_filesystem(monkeypatch):
    """`list_worktree_locations` is on the start path — it must stay cheap."""
    import set_orch.api.helpers as helpers

    monkeypatch.setattr(helpers, "_worktree_porcelain", lambda path: WITH_PRUNABLE)
    locations = list_worktree_locations(Path("/repo"))
    assert locations == [
        {"path": "/repo", "branch": "main", "is_main": True, "prunable": False},
        {"path": "/tmp/base-e78", "branch": "", "is_main": False, "prunable": True},
    ]


def test_the_prunable_entry_is_carried_not_filtered(monkeypatch):
    """A filter downstream of a source looks exactly like an empty source.

    The caller decides; the source reports. The form omits prunable entries and
    the guard refuses them, but both need to be able to say *why*.
    """
    import set_orch.api.helpers as helpers

    monkeypatch.setattr(helpers, "_worktree_porcelain", lambda path: WITH_PRUNABLE)
    assert any(loc["prunable"] for loc in list_worktree_locations(Path("/repo")))


def test_git_failing_yields_no_locations_rather_than_an_exception(monkeypatch):
    import set_orch.api.helpers as helpers

    monkeypatch.setattr(helpers, "_worktree_porcelain", lambda path: "")
    assert list_worktree_locations(Path("/repo")) == []
