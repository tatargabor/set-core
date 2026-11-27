"""The doctor's per-project auto-clear check (auto-clear-default-install, group 6).

Everything is a sandbox: a fake package checkout (a git repo holding the templates), a project
tree, a HOME with settings.json and a user unit directory, and a fake `systemctl` on PATH.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from set_doctor import auto_clear as ac

RELOAD = 'node "$CLAUDE_PROJECT_DIR/.claude/hooks/handoff-reinject-clear.mjs"'
ARM = 'node "$CLAUDE_PROJECT_DIR/.claude/hooks/handoff-arm.mjs"'


def git(cwd, *a):
    return subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def box(tmp_path):
    pkg = tmp_path / "pkg"
    for name, src in ac.HOOK_FILES.items():
        f = pkg / src
        f.parent.mkdir(parents=True, exist_ok=True)
        body = f"// {name} v1\n"
        if name == "clear-gate.mjs":
            body += "export const DEFAULT_THRESHOLD = 400_000;\n"
        f.write_text(body)
    git(pkg, "init", "-q")
    git(pkg, "add", "-A")
    git(pkg, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "v1")

    tree = tmp_path / "proj"
    (tree / ".claude" / "hooks").mkdir(parents=True)
    git(tree, "init", "-q")
    for name, src in ac.HOOK_FILES.items():
        shutil.copy(pkg / src, tree / ".claude" / "hooks" / name)
    settings(tree, {"SessionStart": [{"matcher": "clear|compact", "hooks": [{"command": RELOAD}]}],
                    "PostToolUse": [{"matcher": "Write|Edit|MultiEdit|Bash", "hooks": [{"command": ARM}]}]})

    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(json.dumps({
        "model": "opus", "autoCompactWindow": 600000,
        "modelSettings": {"claude-opus-5-5": {"autoCompactWindow": 550000}}}))
    (home / ".config" / "systemd" / "user").mkdir(parents=True)
    unit(home, "proj-auto-clear.service", tree, "")

    bindir = tmp_path / "bin"
    bindir.mkdir()
    state = tmp_path / "active"
    state.write_text("active\n")
    fake = bindir / "systemctl"
    fake.write_text(f"#!/bin/sh\ncat {state}\n")
    fake.chmod(0o755)
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}")
    registry = {"set-claude-handoff": {"path": str(pkg)}}
    run = lambda entry=None: ac.check("proj", entry or {}, str(tree), registry, str(home), env)  # noqa: E731
    return run, pkg, tree, home, state


def settings(tree, hooks):
    (tree / ".claude" / "settings.json").write_text(json.dumps({"hooks": hooks}))


def unit(home, name, tree, extra):
    (home / ".config" / "systemd" / "user" / name).write_text(
        "[Service]\nExecStart=" + f"{tree}/.claude/hooks/watch-auto-clear.sh --dir {tree} --interval 60 {extra}\n")


def test_a_complete_install_is_ok(box):
    """AC-13"""
    run, *_ = box
    c = run()
    assert c.status == "ok", c.detail
    assert c.name == "auto-clear" and "proj-auto-clear.service" in c.detail


def test_an_opted_out_project_is_skipped(box):
    run, *_ = box
    c = run({"auto_clear": False})
    assert c.status == "skip" and "auto_clear: false" in c.detail


def test_a_project_without_a_unit_warns_with_init(box):
    """AC-10"""
    run, _, _, home, _ = box
    (home / ".config" / "systemd" / "user" / "proj-auto-clear.service").unlink()
    c = run()
    assert c.status == "warn" and "no watcher unit" in c.detail
    assert c.fix == "set-project init --project proj"


def test_a_differently_named_hand_unit_counts(box):
    """D3: a hand unit is recognised by its ExecStart, whatever its name."""
    run, _, tree, home, _ = box
    (home / ".config" / "systemd" / "user" / "proj-auto-clear.service").unlink()
    unit(home, "auto-clear-proj.service", tree, "")
    assert run().status == "ok"


def test_a_unit_written_with_the_real_path_counts_for_a_symlinked_registry_path(box, tmp_path):
    """B-218: the registry holds a symlink, the unit names the real directory. Same tree."""
    _, pkg, tree, home, _ = box
    link = tmp_path / "proj-link"
    link.symlink_to(tree)
    assert [u for u, _ in ac.watcher_units(str(home), str(link))] == ["proj-auto-clear.service"]
    (home / ".config" / "systemd" / "user" / "proj-auto-clear.service").unlink()
    unit(home, "proj-auto-clear.service", link, "")
    assert [u for u, _ in ac.watcher_units(str(home), str(tree))] == ["proj-auto-clear.service"]


def test_another_trees_unit_does_not_count(box, tmp_path):
    run, _, _, home, _ = box
    (home / ".config" / "systemd" / "user" / "proj-auto-clear.service").unlink()
    unit(home, "other-auto-clear.service", tmp_path / "proj-other", "")
    assert "no watcher unit" in run().detail


def test_an_inactive_unit_warns_with_start(box):
    """AC-11"""
    run, _, _, _, state = box
    state.write_text("inactive\n")
    c = run()
    assert c.status == "warn" and "not active" in c.detail
    assert c.fix == "systemctl --user start proj-auto-clear.service"


def test_a_pinned_threshold_in_the_unit_is_named(box):
    """AC-12, unit side: names the flag, the unit, and why."""
    run, _, tree, home, _ = box
    unit(home, "proj-auto-clear.service", tree, "--compact-threshold 500000")
    c = run()
    assert c.status == "warn"
    assert "proj-auto-clear.service passes --compact-threshold 500000" in c.detail
    assert "above the package default 400000" in c.detail
    assert "native compaction trigger ~495000" in c.detail, "opus resolves to claude-opus-5-5: 0.9 x 550000"
    assert "--compact-threshold 500000" in c.fix and "proj-auto-clear.service" in c.fix


def test_a_threshold_at_the_default_is_not_flagged(box):
    run, _, tree, home, _ = box
    unit(home, "proj-auto-clear.service", tree, "--threshold 400000")
    assert run().status == "ok"


def test_a_keep_going_threshold_is_named_once(box):
    """AC-12, settings side: post and stop carrying the same value give ONE line."""
    run, _, tree, _, _ = box
    kg = 'node "$CLAUDE_PROJECT_DIR/.claude/hooks/keep-going.mjs" --threshold 500000'
    settings(tree, {"SessionStart": [{"matcher": "clear|compact", "hooks": [{"command": RELOAD}]}],
                    "PostToolUse": [{"matcher": "Bash", "hooks": [{"command": ARM}, {"command": kg}]}],
                    "Stop": [{"hooks": [{"command": kg}]}]})
    c = run()
    assert c.status == "warn" and c.detail.count("keep-going hook") == 1
    assert "--threshold 500000" in c.detail


def test_missing_and_stale_templates_are_told_apart(box):
    run, pkg, tree, _, _ = box
    (tree / ".claude" / "hooks" / "presence.mjs").unlink()
    (pkg / "templates" / "turn-state.mjs").write_text("// turn-state v2\n")
    git(pkg, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "v2")
    c = run()
    assert "templates missing: presence.mjs" in c.detail
    assert "templates not current: turn-state.mjs" in c.detail
    assert c.fix == "set-project init --project proj"


def test_a_projects_own_reload_script_counts(box):
    """D2: a project-owned reinject for the clear source is a wired reload."""
    run, _, tree, _, _ = box
    settings(tree, {"SessionStart": [{"matcher": "startup|clear|compact",
                                      "hooks": [{"command": "bash scripts/session-reinject.sh"}]}],
                    "PostToolUse": [{"matcher": "Write", "hooks": [{"command": ARM}]}]})
    assert run().status == "ok"


def test_unwired_hooks_warn(box):
    run, _, tree, _, _ = box
    settings(tree, {})
    c = run()
    assert "no SessionStart clear reload hook" in c.detail and "no PostToolUse handoff-arm hook" in c.detail


def test_a_missing_package_checkout_warns_not_fails(box, tmp_path):
    run, _, tree, home, _ = box
    c = ac.check("proj", {}, str(tree), {}, str(home), {})
    assert c.status == "warn" and "set-claude-handoff" in c.detail


def test_the_native_trigger_prefers_the_per_model_key(tmp_path):
    """D5: the top-level key read 600000 while the per-model key was the one that applied."""
    (tmp_path / ".claude").mkdir()
    s = tmp_path / ".claude" / "settings.json"
    s.write_text(json.dumps({"model": "claude-opus-4-8", "autoCompactWindow": 600000,
                             "modelSettings": {"claude-opus-4-8": {"autoCompactWindow": 400000}}}))
    assert ac.native_trigger(str(tmp_path)) == 360000
    s.write_text(json.dumps({"model": "fable", "autoCompactWindow": 600000,
                             "modelSettings": {"claude-fable-5-2": {}}}))
    assert ac.native_trigger(str(tmp_path)) == 540000
    s.write_text("{}")
    assert ac.native_trigger(str(tmp_path)) is None


# ── B-253: the package route ────────────────────────────────────────────────


PLUGIN_RELOAD = 'H="$(command -v set-claude-handoff)"; "$H" hook reinject --from-plugin'
PLUGIN_ARM = 'H="$(command -v set-claude-handoff)"; "$H" hook arm --from-plugin'


def package_route(tree, home, tmp_path, *, plugin_enabled=True, unit_cmd=None):
    """A tree wired the way a plugin-installed project is: no hook copies, no hooks in its
    settings, the reload and arm hooks in an enabled plugin's hooks.json, and a unit running
    the package's own watcher for the tree."""
    shutil.rmtree(tree / ".claude" / "hooks")
    (tree / ".claude" / "settings.json").write_text(json.dumps(
        {"enabledPlugins": {"kit@kit": plugin_enabled}}))
    install = tmp_path / "plugins" / "kit" / "1.0.0"
    (install / "hooks").mkdir(parents=True)
    (install / "hooks" / "hooks.json").write_text(json.dumps({"hooks": {
        "SessionStart": [{"matcher": "clear|compact", "hooks": [{"command": PLUGIN_RELOAD}]}],
        "PostToolUse": [{"matcher": "Write|Edit|MultiEdit|Bash", "hooks": [{"command": PLUGIN_ARM}]}]}}))
    (home / ".claude" / "plugins").mkdir(parents=True, exist_ok=True)
    (home / ".claude" / "plugins" / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {
        "kit@kit": [{"scope": "local", "projectPath": str(tree), "installPath": str(install)}]}}))
    (home / ".config" / "systemd" / "user" / "proj-auto-clear.service").write_text(
        "[Service]\nExecStart=" + (unit_cmd or f"/usr/bin/env set-claude-handoff watch --dir {tree} --interval 60") + "\n")


def test_a_package_route_install_is_ok_b253(box, tmp_path):
    """B-253: plugin-wired hooks + the package's watcher is a complete install, not 'missing all'."""
    run, _, tree, home, _ = box
    package_route(tree, home, tmp_path)
    c = run()
    assert c.status == "ok", c.detail
    assert "package route" in c.detail and "proj-auto-clear.service" in c.detail
    assert c.fix is None


def test_the_package_template_watcher_counts_as_the_package_route_b253(box, tmp_path):
    run, pkg, tree, home, _ = box
    package_route(tree, home, tmp_path, unit_cmd=(
        f"bash {pkg}/templates/watch-auto-clear.sh --gate {pkg}/templates/clear-gate.mjs --dir {tree}"))
    assert run().status == "ok"


def test_unused_stale_copies_do_not_count_on_the_package_route_but_called_ones_do_b253(box, tmp_path):
    """Leftover copies the package watcher never runs are not a finding; a copy the tree's own
    settings still call is."""
    run, pkg, tree, home, _ = box
    package_route(tree, home, tmp_path)
    (tree / ".claude" / "hooks").mkdir()
    (tree / ".claude" / "hooks" / "clear-gate.mjs").write_text("// clear-gate v0\n")
    assert run().status == "ok"
    (tree / ".claude" / "hooks" / "handoff-arm.mjs").write_text("// handoff-arm v0\n")
    (tree / ".claude" / "settings.json").write_text(json.dumps({
        "enabledPlugins": {"kit@kit": True},
        "hooks": {"PostToolUse": [{"matcher": "Bash", "hooks": [{"command": ARM}]}]}}))
    c = run()
    assert c.status == "warn" and "templates not current: handoff-arm.mjs" in c.detail
    assert "clear-gate.mjs" not in c.detail


def test_a_disabled_plugin_wires_nothing_b253(box, tmp_path):
    run, _, tree, home, _ = box
    package_route(tree, home, tmp_path, plugin_enabled=False)
    c = run()
    assert "no SessionStart clear reload hook" in c.detail and "no PostToolUse handoff-arm hook" in c.detail


def test_another_trees_package_watcher_does_not_count_b253(box, tmp_path):
    run, _, tree, home, _ = box
    package_route(tree, home, tmp_path,
                  unit_cmd=f"/usr/bin/env set-claude-handoff watch --dir {tmp_path / 'proj-other'}")
    c = run()
    assert "no watcher unit" in c.detail
