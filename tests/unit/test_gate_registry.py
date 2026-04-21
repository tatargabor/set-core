"""Unit tests for the content-aware gate selector (section 7 of
fix-replan-stuck-gate-and-decomposer).

Tests cover:
- `classify_content` exact-match and glob-match semantics
- `tags_to_gates` union of tag→gate sets
- `augment_gate_config_with_content` additive behavior + gate_hints
  (require/skip) overrides
- CoreProfile-level `content_tag_to_gates` defaults
- WebProjectType's `content_classifier_rules` + end-to-end additive
  augmentation on a foundation-style change with UI scope
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.gate_registry import (  # noqa: E402
    augment_gate_config_with_content,
    classify_content,
    redetect,
    tags_to_gates,
)
from set_orch.gate_profiles import GateConfig, resolve_gate_config  # noqa: E402
from set_orch.state import Change  # noqa: E402


def test_classify_content_empty_inputs():
    assert classify_content([], {"ui": ["src/**"]}) == set()
    assert classify_content(["src/x.ts"], {}) == set()


def test_classify_content_glob_match():
    rules = {
        "ui": ["src/app/**/*.tsx", "src/components/**/*.tsx"],
        "server": ["src/server/**"],
    }
    assert classify_content(["src/app/cart/page.tsx"], rules) == {"ui"}
    assert classify_content(["src/server/orders.ts"], rules) == {"server"}
    assert classify_content(
        ["src/app/cart/page.tsx", "src/server/orders.ts"],
        rules,
    ) == {"ui", "server"}


def test_tags_to_gates_union():
    mapping = {
        "ui": {"design-fidelity", "i18n_check"},
        "e2e_ui": {"e2e"},
    }
    assert tags_to_gates(["ui"], mapping) == {"design-fidelity", "i18n_check"}
    assert tags_to_gates(["ui", "e2e_ui"], mapping) == {
        "design-fidelity", "i18n_check", "e2e",
    }
    assert tags_to_gates([], mapping) == set()


class _FakeProfile:
    def content_classifier_rules(self):
        return {
            "ui": ["src/app/**/*.tsx"],
            "server": ["src/server/**"],
        }

    def content_tag_to_gates(self):
        return {
            "ui": {"design-fidelity", "i18n_check"},
            "server": {"test"},
        }


def test_augment_gate_config_adds_ui_gates():
    gc = GateConfig(gates={
        "build": "run", "test": "run", "design-fidelity": "skip",
        "i18n_check": "skip",
    })
    change = Change(
        name="c1", change_type="infrastructure",
        touched_file_globs=["src/app/cart/page.tsx"],
    )
    added = augment_gate_config_with_content(gc, change, _FakeProfile())
    assert "design-fidelity" in added
    assert "i18n_check" in added
    assert gc.should_run("design-fidelity")
    assert gc.should_run("i18n_check")


def test_augment_preserves_existing_runs():
    gc = GateConfig(gates={"test": "run"})
    change = Change(
        name="c1", touched_file_globs=["src/server/foo.ts"],
    )
    augment_gate_config_with_content(gc, change, _FakeProfile())
    # "test" was already run — no change
    assert gc.get("test") == "run"


def test_gate_hints_skip_overrides_content(tmp_path):
    gc = GateConfig(gates={
        "design-fidelity": "skip", "i18n_check": "skip",
    })
    change = Change(
        name="c1",
        touched_file_globs=["src/app/x.tsx"],
        gate_hints={"design-fidelity": "skip"},
    )
    added = augment_gate_config_with_content(gc, change, _FakeProfile())
    assert "design-fidelity" not in added
    assert gc.get("design-fidelity") == "skip"
    # i18n_check still added (no hint override)
    assert "i18n_check" in added


def test_gate_hints_require_forces_inclusion():
    gc = GateConfig(gates={"e2e": "skip"})
    change = Change(
        name="c1",
        touched_file_globs=[],  # no content classification → no tags
        gate_hints={"e2e": "require"},
    )
    added = augment_gate_config_with_content(gc, change, _FakeProfile())
    assert "e2e" in added
    assert gc.should_run("e2e")


def test_empty_touched_globs_is_noop():
    gc = GateConfig(gates={"test": "skip"})
    change = Change(name="c1", touched_file_globs=[])
    added = augment_gate_config_with_content(gc, change, _FakeProfile())
    assert added == set()
    assert gc.get("test") == "skip"


def test_null_profile_is_noop():
    gc = GateConfig(gates={})
    change = Change(name="c1", touched_file_globs=["src/app/x.tsx"])
    assert augment_gate_config_with_content(gc, change, None) == set()


def test_redetect_unions_committed_files_into_touched_globs():
    change = Change(
        name="c1", touched_file_globs=["src/app/cart/page.tsx"],
    )
    added = redetect(
        change, ["src/server/orders.ts"], _FakeProfile(),
    )
    assert "test" in added
    assert "src/server/orders.ts" in change.touched_file_globs
    assert "src/app/cart/page.tsx" in change.touched_file_globs


def test_foundation_change_with_ui_gets_design_gates_via_resolve():
    """Integration: resolve_gate_config on a change_type=infrastructure
    change with UI globs ends up with design-fidelity + i18n_check in
    the gate set via the new content-aware step.
    """
    change = Change(
        name="foundation-setup",
        change_type="infrastructure",
        touched_file_globs=["src/app/cart/page.tsx"],
    )
    gc = resolve_gate_config(change, profile=_FakeProfile())
    assert gc.should_run("design-fidelity")
    assert gc.should_run("i18n_check")


def test_core_profile_default_tag_map_present():
    """Spec check: CoreProfile.content_tag_to_gates() carries the core
    defaults from the spec (ui, e2e_ui, server, schema, config,
    i18n_catalog). Projects without a plugin still get sane behavior.
    """
    from set_orch.profile_loader import CoreProfile

    m = CoreProfile().content_tag_to_gates()
    assert "design-fidelity" in m.get("ui", set())
    assert "e2e" in m.get("e2e_ui", set())
    assert "test" in m.get("server", set())
    assert "build" in m.get("schema", set())
    assert "i18n_check" in m.get("i18n_catalog", set())


def test_server_only_change_does_not_add_design_fidelity():
    """AC-18: server-only globs → unit test gate in set, design-fidelity
    stays skipped. Content scan must not sweep in UI gates when the
    diff contains zero src/app/**/*.tsx files.
    """
    gc = GateConfig(gates={
        "test": "skip",  # will be added
        "design-fidelity": "skip",  # must stay skipped
        "i18n_check": "skip",  # must stay skipped
    })
    change = Change(
        name="c_srv",
        change_type="feature",
        touched_file_globs=["src/server/orders.ts", "src/server/auth.ts"],
    )
    added = augment_gate_config_with_content(gc, change, _FakeProfile())
    assert "test" in added
    assert "design-fidelity" not in added
    assert "i18n_check" not in added
    assert gc.get("design-fidelity") == "skip"
    assert gc.get("i18n_check") == "skip"


def test_first_commit_redetect_sets_flag_and_emits_event(tmp_path):
    """AC-20 + AC-21: on the first monitor poll that sees commits AND
    `gate_recheck_done=False`, engine runs `redetect()`, sets the flag
    True, and emits `GATE_SET_EXPANDED` with `added_gates` when the
    content scan produces any new gate.
    """
    import json
    import subprocess
    from set_orch.engine import _first_commit_gate_redetect
    from set_orch.state import save_state, OrchestratorState

    # Minimal git worktree with one commit whose diff touches a UI file.
    wt = tmp_path / "wt"
    wt.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(wt)], check=True)
    subprocess.run(["git", "-C", str(wt), "config", "user.email", "x@y.z"], check=True)
    subprocess.run(["git", "-C", str(wt), "config", "user.name", "x"], check=True)
    # Baseline empty commit on main so `main..HEAD` is meaningful.
    subprocess.run(
        ["git", "-C", str(wt), "commit", "--allow-empty", "-q", "-m", "base"],
        check=True,
    )
    # Agent works on a feature branch so `main..HEAD` shows the new files.
    subprocess.run(
        ["git", "-C", str(wt), "checkout", "-q", "-b", "change/feature"], check=True,
    )
    (wt / "src" / "app" / "cart").mkdir(parents=True)
    (wt / "src" / "app" / "cart" / "page.tsx").write_text("export default () => null;\n")
    subprocess.run(["git", "-C", str(wt), "add", "."], check=True)
    subprocess.run(["git", "-C", str(wt), "commit", "-q", "-m", "agent: cart ui"], check=True)

    change = Change(
        name="c_redetect",
        scope="x",
        worktree_path=str(wt),
        change_type="feature",
        touched_file_globs=[],  # original scope had no UI globs
        gate_recheck_done=False,
    )
    state = OrchestratorState(changes=[change])
    state_file = str(tmp_path / "state.json")
    save_state(state, state_file)

    events: list[tuple[str, dict]] = []

    class _Bus:
        def emit(self, ev: str, change: str = "", data=None, **_):
            events.append((ev, {"change": change, "data": data or {}}))

    # Monkey-patch load_profile so redetect() has rules to classify against —
    # tmp_path is not a project dir, so the real loader returns NullProfile.
    # The engine imports load_profile lazily inside the function, so we patch
    # the source module.
    import set_orch.profile_loader as _pl
    _orig_loader = _pl.load_profile
    _pl.load_profile = lambda *a, **k: _FakeProfile()
    try:
        _first_commit_gate_redetect(state_file, change, _Bus())
    finally:
        _pl.load_profile = _orig_loader

    # Flag persisted.
    updated = json.loads(open(state_file).read())
    assert updated["changes"][0]["gate_recheck_done"] is True
    # touched_file_globs grew to include the UI file path.
    assert any(
        "src/app/cart/page.tsx" in g
        for g in updated["changes"][0].get("touched_file_globs", [])
    )
    # GATE_SET_EXPANDED emitted with added_gates non-empty.
    expanded = [e for e in events if e[0] == "GATE_SET_EXPANDED"]
    assert len(expanded) == 1
    assert expanded[0][1]["data"]["added_gates"]


def test_redetect_is_one_shot_when_flag_already_true(tmp_path):
    """AC-20 guard: `gate_recheck_done=True` makes the function a no-op
    even if new commits appeared since the prior redetect.
    """
    import subprocess
    from set_orch.engine import _first_commit_gate_redetect
    from set_orch.state import save_state, OrchestratorState

    wt = tmp_path / "wt"
    wt.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(wt)], check=True)
    subprocess.run(["git", "-C", str(wt), "config", "user.email", "x@y.z"], check=True)
    subprocess.run(["git", "-C", str(wt), "config", "user.name", "x"], check=True)
    subprocess.run(
        ["git", "-C", str(wt), "commit", "--allow-empty", "-q", "-m", "base"],
        check=True,
    )

    change = Change(
        name="c_guard", scope="x",
        worktree_path=str(wt),
        gate_recheck_done=True,  # already done
    )
    state = OrchestratorState(changes=[change])
    state_file = str(tmp_path / "state.json")
    save_state(state, state_file)

    events: list[tuple[str, dict]] = []

    class _Bus:
        def emit(self, ev: str, **kw):
            events.append((ev, kw))

    _first_commit_gate_redetect(state_file, change, _Bus())
    # No events — function returned early on the flag guard.
    assert events == []
