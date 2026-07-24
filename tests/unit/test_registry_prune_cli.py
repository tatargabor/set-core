"""The CLI's confirmation gate — the last thing between an operator and a write.

The gate matters more than the code it guards: a prune that acts before the
operator has read the plan removes the one step where a wrong classification is
still catchable by a human.
"""
from __future__ import annotations

import builtins
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch import project_registry  # noqa: E402
from set_orch import registry_prune as rp  # noqa: E402


@pytest.fixture
def registry(tmp_path, monkeypatch):
    reg = tmp_path / "projects.json"
    reg.write_text(json.dumps({"projects": {
        "gone": {"path": str(tmp_path / "gone")},
    }}, indent=2))
    monkeypatch.setattr(project_registry, "PROJECTS_FILE", reg)
    return reg


def _answer(monkeypatch, text):
    monkeypatch.setattr(builtins, "input", lambda *a, **kw: text)


def test_declining_the_confirmation_writes_nothing(registry, monkeypatch, capsys):
    """AC-18."""
    before = registry.read_bytes()
    _answer(monkeypatch, "n")
    assert rp.main([]) == 1
    assert registry.read_bytes() == before
    assert list(registry.parent.glob("*.bak-*")) == []
    assert "Aborted" in capsys.readouterr().out


def test_an_empty_answer_is_a_refusal(registry, monkeypatch):
    """The prompt reads `[y/N]`; Enter must mean no. A default-yes prompt is a
    prompt that only looks like a gate."""
    before = registry.read_bytes()
    _answer(monkeypatch, "")
    assert rp.main([]) == 1
    assert registry.read_bytes() == before


def test_an_interrupted_prompt_writes_nothing(registry, monkeypatch):
    def interrupt(*a, **kw):
        raise KeyboardInterrupt

    monkeypatch.setattr(builtins, "input", interrupt)
    before = registry.read_bytes()
    assert rp.main([]) == 1
    assert registry.read_bytes() == before


def test_assume_yes_skips_the_prompt(registry, monkeypatch):
    """AC-19."""
    def must_not_prompt(*a, **kw):
        raise AssertionError("prompted despite --yes")

    monkeypatch.setattr(builtins, "input", must_not_prompt)
    assert rp.main(["--yes"]) == 0
    assert json.loads(registry.read_text())["projects"] == {}


def test_dry_run_never_prompts_and_never_writes(registry, monkeypatch, capsys):
    """A preview asking for confirmation would train the operator to confirm
    without reading."""
    def must_not_prompt(*a, **kw):
        raise AssertionError("dry-run prompted")

    monkeypatch.setattr(builtins, "input", must_not_prompt)
    before = registry.read_bytes()
    assert rp.main(["--dry-run"]) == 0
    assert registry.read_bytes() == before
    assert "Would deregister" in capsys.readouterr().out


def test_a_bad_threshold_exits_before_doing_anything(registry, monkeypatch, capsys):
    def must_not_prompt(*a, **kw):
        raise AssertionError("prompted on a bad threshold")

    monkeypatch.setattr(builtins, "input", must_not_prompt)
    before = registry.read_bytes()
    assert rp.main(["--archive-e2e-older-than", "soon"]) == 2
    assert registry.read_bytes() == before
    assert "error" in capsys.readouterr().out


def test_nothing_to_do_reports_and_exits_clean(tmp_path, monkeypatch, capsys):
    reg = tmp_path / "projects.json"
    live = tmp_path / "live"
    live.mkdir()
    reg.write_text(json.dumps({"projects": {"live": {"path": str(live)}}}))
    monkeypatch.setattr(project_registry, "PROJECTS_FILE", reg)

    def must_not_prompt(*a, **kw):
        raise AssertionError("prompted with nothing to do")

    monkeypatch.setattr(builtins, "input", must_not_prompt)
    assert rp.main([]) == 0
    assert "No registry entry has a missing directory" in capsys.readouterr().out


def test_the_plan_names_kept_unreachable_entries_separately(tmp_path, monkeypatch, capsys):
    """An unreachable entry silently kept is indistinguishable from one that was
    never examined. It has to appear in the plan under its own heading."""
    reg = tmp_path / "projects.json"
    reg.write_text(json.dumps({"projects": {
        "nas": {"path": str(tmp_path / "no-mount" / "proj")},
    }}))
    monkeypatch.setattr(project_registry, "PROJECTS_FILE", reg)

    assert rp.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "unreachable" in out
    assert "nas" in out
