"""Tests for Part 7: ralph iteration input.md refresh."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch import dispatcher as dispatcher_mod
from set_orch.dispatcher import (
    _LEARNINGS_SECTION_END,
    _LEARNINGS_SECTION_MARKER,
    _learnings_file_path,
    _maybe_refresh_input_md,
    _render_learnings_section,
    _replace_learnings_section,
)


def _setup_wt(tmp_path: Path, change_name: str, input_content: str) -> tuple[Path, Path]:
    project = tmp_path / "proj"
    project.mkdir()
    wt = tmp_path / f"wt-{change_name}"
    (wt / "openspec" / "changes" / change_name).mkdir(parents=True)
    input_md = wt / "openspec" / "changes" / change_name / "input.md"
    input_md.write_text(input_content)
    # Touch the learnings file location
    (project / "set" / "orchestration").mkdir(parents=True)
    learnings = project / "set" / "orchestration" / "review-learnings.jsonl"
    learnings.write_text('{"pattern":"placeholder","severity":"CRITICAL","seen":3}\n')
    return project, wt


@pytest.fixture(autouse=True)
def fake_checklist(monkeypatch):
    """Stub the profile loader so learnings return a deterministic string."""
    class FakeProfile:
        def review_learnings_checklist(self, project_path, content_categories=None):
            return (
                "- Pattern A [auth, seen 3x]\n"
                "- Pattern B [frontend, seen 5x]\n"
            )

    monkeypatch.setattr(
        dispatcher_mod, "load_profile", lambda: FakeProfile(), raising=False
    )

    # Render helper imports the loader lazily — also stub via the same path
    import set_orch.profile_loader as profile_loader_mod

    monkeypatch.setattr(
        profile_loader_mod, "load_profile", lambda: FakeProfile(), raising=False
    )


class TestReplaceLearningsSection:
    def test_append_when_no_prior_block(self):
        content = "# Input\n\n## Scope\nhello\n"
        new_section = (
            f"\n\n{_LEARNINGS_SECTION_MARKER}\n"
            "## Current Review Learnings\n- foo\n"
            f"{_LEARNINGS_SECTION_END}\n"
        )
        updated = _replace_learnings_section(content, new_section)
        assert _LEARNINGS_SECTION_MARKER in updated
        assert "## Scope" in updated
        assert updated.count(_LEARNINGS_SECTION_MARKER) == 1

    def test_replace_existing_block_no_duplication(self):
        content = (
            "# Input\n\n"
            f"{_LEARNINGS_SECTION_MARKER}\n"
            "## Current Review Learnings\n- old\n"
            f"{_LEARNINGS_SECTION_END}\n"
        )
        new_section = (
            f"\n\n{_LEARNINGS_SECTION_MARKER}\n"
            "## Current Review Learnings\n- new\n"
            f"{_LEARNINGS_SECTION_END}\n"
        )
        updated = _replace_learnings_section(content, new_section)
        assert updated.count(_LEARNINGS_SECTION_MARKER) == 1
        assert "- new" in updated
        assert "- old" not in updated


class TestMaybeRefreshInputMd:
    def test_refreshes_when_learnings_newer(self, tmp_path):
        project, wt = _setup_wt(tmp_path, "foo", "# Input\n\n## Scope\nhello\n")
        input_md = wt / "openspec" / "changes" / "foo" / "input.md"

        # Age the input.md so learnings is clearly newer
        old_mtime = time.time() - 3600
        os.utime(input_md, (old_mtime, old_mtime))

        refreshed = _maybe_refresh_input_md("foo", str(wt), str(project))
        assert refreshed is True
        content = input_md.read_text()
        assert _LEARNINGS_SECTION_MARKER in content
        assert "Pattern A" in content

    def test_no_refresh_when_learnings_older(self, tmp_path):
        project, wt = _setup_wt(tmp_path, "foo", "# Input\n")
        input_md = wt / "openspec" / "changes" / "foo" / "input.md"
        learnings = project / "set" / "orchestration" / "review-learnings.jsonl"

        # Make learnings older
        old = time.time() - 3600
        os.utime(learnings, (old, old))

        refreshed = _maybe_refresh_input_md("foo", str(wt), str(project))
        assert refreshed is False
        assert _LEARNINGS_SECTION_MARKER not in input_md.read_text()

    def test_no_refresh_when_learnings_missing(self, tmp_path):
        project, wt = _setup_wt(tmp_path, "foo", "# Input\n")
        learnings = project / "set" / "orchestration" / "review-learnings.jsonl"
        learnings.unlink()

        refreshed = _maybe_refresh_input_md("foo", str(wt), str(project))
        assert refreshed is False

    def test_no_refresh_when_input_md_missing(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        (project / "set" / "orchestration").mkdir(parents=True)
        (project / "set" / "orchestration" / "review-learnings.jsonl").write_text("{}")
        wt = tmp_path / "wt"
        wt.mkdir()
        # No input.md created
        refreshed = _maybe_refresh_input_md("foo", str(wt), str(project))
        assert refreshed is False

    def test_second_refresh_with_no_change_is_noop(self, tmp_path):
        project, wt = _setup_wt(tmp_path, "foo", "# Input\n")
        input_md = wt / "openspec" / "changes" / "foo" / "input.md"

        old_mtime = time.time() - 3600
        os.utime(input_md, (old_mtime, old_mtime))

        first = _maybe_refresh_input_md("foo", str(wt), str(project))
        assert first is True

        # Age the input.md again so mtime comparison triggers a second pass,
        # but the section content is unchanged → function returns False.
        os.utime(input_md, (old_mtime - 100, old_mtime - 100))
        second = _maybe_refresh_input_md("foo", str(wt), str(project))
        assert second is False

    def test_directive_disabled_no_refresh(self, tmp_path):
        """AC-59: operator disables feature via refresh_input_on_learnings_update."""
        import json as _json

        project, wt = _setup_wt(tmp_path, "foo", "# Input\n")
        input_md = wt / "openspec" / "changes" / "foo" / "input.md"
        old_mtime = time.time() - 3600
        os.utime(input_md, (old_mtime, old_mtime))

        directives = project / "set" / "orchestration" / "directives.json"
        directives.parent.mkdir(parents=True, exist_ok=True)
        directives.write_text(_json.dumps({"refresh_input_on_learnings_update": False}))

        refreshed = _maybe_refresh_input_md("foo", str(wt), str(project))
        assert refreshed is False
        # Section must NOT have been injected
        assert _LEARNINGS_SECTION_MARKER not in input_md.read_text()
