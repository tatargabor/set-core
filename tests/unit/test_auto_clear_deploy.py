"""`set-project init`'s auto-clear step (auto-clear-default-install groups 1.2, 2, 4, 5).

A sandbox package checkout whose `bin/cli.mjs` behaves like the real installer (copies its
templates into `.claude/hooks/`), a sandbox HOME with a unit directory, and a fake `systemctl`
that logs every call.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from set_orch import auto_clear_deploy as acd

pytestmark = pytest.mark.skipif(not (shutil.which("node") and shutil.which("jq")),
                                reason="the package installer needs node, the hook merge needs jq")

FILES = ("clear-gate.mjs", "watch-auto-clear.sh", "handoff-arm.mjs")
CLI = """
import { mkdirSync, copyFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const src = join(dirname(fileURLToPath(import.meta.url)), "..", "templates");
mkdirSync(".claude/hooks", { recursive: true });
for (const f of readdirSync(src)) copyFileSync(join(src, f), join(".claude/hooks", f));
"""


def git(cwd, *a):
    return subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True, text=True).stdout.strip()


def commit(pkg, msg):
    git(pkg, "add", "-A")
    git(pkg, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg)


@pytest.fixture
def box(tmp_path):
    pkg = tmp_path / "pkg"
    (pkg / "bin").mkdir(parents=True)
    (pkg / "templates").mkdir()
    (pkg / "bin" / "cli.mjs").write_text(CLI)
    for f in FILES:
        (pkg / "templates" / f).write_text(f"// {f} v1\n")
    git(pkg, "init", "-q")
    commit(pkg, "v1")
    for f in FILES:
        (pkg / "templates" / f).write_text(f"// {f} v2\n")
    commit(pkg, "v2")

    tree = tmp_path / "proj"
    tree.mkdir()
    git(tree, "init", "-q")
    home = tmp_path / "home"
    (home / ".config" / "systemd" / "user").mkdir(parents=True)

    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "systemctl.log"
    (bindir / "systemctl").write_text(f'#!/bin/sh\necho "$*" >> {log}\n')
    (bindir / "systemctl").chmod(0o755)
    # HOME/XDG_STATE_HOME in the sandbox too: the hook merge backs settings up under the
    # state dir, and no test run may touch the real home. (The unit dir uses `home`
    # explicitly, not env HOME.)
    state_home = tmp_path / "statehome"
    state_home.mkdir()
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}",
               HOME=str(state_home), XDG_STATE_HOME=str(state_home))
    registry = {"set-claude-handoff": {"path": str(pkg)}, "proj": {"path": str(tree)}}

    def run(dry_run=False, reg=None):
        return acd.deploy("proj", tree, reg if reg is not None else registry, home, env, dry_run)

    return run, pkg, tree, home, log, registry


def hook(tree, name):
    return tree / ".claude" / "hooks" / name


def unit_file(home):
    return home / ".config" / "systemd" / "user" / "proj-auto-clear.service"


def calls(log):
    return log.read_text().splitlines() if log.exists() else []


def test_a_project_with_nothing_installed_gets_everything(box):
    """AC-1"""
    run, _, tree, home, log, _ = box
    out = run()
    for f in FILES:
        assert hook(tree, f).read_text() == f"// {f} v2\n"
    doc = json.loads((tree / ".claude" / "settings.json").read_text())
    assert doc["hooks"]["SessionStart"][0]["matcher"] == "clear|compact"
    text = unit_file(home).read_text()
    assert f"--dir {tree} " in text and f"{tree}/.claude/hooks/watch-auto-clear.sh" in text
    stamp = (tree / acd.STAMP).read_text().strip()
    assert f"--started-after {stamp} " in text, "until the package reads the stamp, the unit passes it"
    for flag in acd.OVERRIDING:
        assert flag + " " not in text
    assert "daemon-reload" in " ".join(calls(log))
    assert "--user enable --now proj-auto-clear.service" in calls(log)
    assert any("created and started" in l for l in out)


def test_rerunning_is_idempotent(box):
    """AC-3: no file changes, no duplicate hooks, no restart."""
    run, _, tree, home, log, _ = box
    run()
    snap = {p: p.read_bytes() for p in tree.rglob("*") if p.is_file() and ".git/" not in str(p)}
    unit_before = unit_file(home).read_bytes()
    n = len(calls(log))
    out = run()
    assert {p: p.read_bytes() for p in snap} == snap
    assert unit_file(home).read_bytes() == unit_before
    assert len(calls(log)) == n, f"no systemctl call on a re-run: {calls(log)[n:]}"
    assert any("exists, left as is" in l for l in out)


def test_an_older_shipped_version_is_upgraded(box):
    """AC-4"""
    run, _, tree, _, _, _ = box
    hook(tree, "clear-gate.mjs").parent.mkdir(parents=True)
    hook(tree, "clear-gate.mjs").write_text("// clear-gate.mjs v1\n")
    out = run()
    assert hook(tree, "clear-gate.mjs").read_text() == "// clear-gate.mjs v2\n"
    assert any("upgraded .claude/hooks/clear-gate.mjs" in l for l in out)


def test_a_hand_edited_file_survives(box):
    """AC-5"""
    run, _, tree, _, _, _ = box
    hook(tree, "watch-auto-clear.sh").parent.mkdir(parents=True)
    hook(tree, "watch-auto-clear.sh").write_text("# my own watcher\n")
    out = run()
    assert hook(tree, "watch-auto-clear.sh").read_text() == "# my own watcher\n"
    assert any("kept .claude/hooks/watch-auto-clear.sh (locally modified)" in l for l in out)


def test_a_renamed_template_keeps_its_history(box):
    """The history walk follows renames: a v1 shipped under an old path still counts."""
    run, pkg, tree, _, _, _ = box
    git(pkg, "mv", "templates/handoff-arm.mjs", "templates/handoff-arm2.mjs")
    commit(pkg, "rename")
    hook(tree, "handoff-arm2.mjs").parent.mkdir(parents=True)
    hook(tree, "handoff-arm2.mjs").write_text("// handoff-arm.mjs v1\n")
    run()
    assert hook(tree, "handoff-arm2.mjs").read_text() == "// handoff-arm.mjs v2\n"


def test_the_packages_own_deployed_copy_does_not_hide_older_shipped_versions(box):
    """The package checkout is a consumer too. Its own `.claude/hooks/` copy was deployed at v1
    and next at v3, skipping v2; at HEAD it holds the same blob as `templates/` and sorts
    first, so walking only that path's history misses v2 (`--follow` jumps to `templates/`
    at the ADD, i.e. at v1). A tree still on v2 must be upgraded, not kept as locally
    modified. Shape measured on the real package, 2026-11-24."""
    run, pkg, tree, _, _, _ = box
    own = pkg / ".claude" / "hooks" / "clear-gate.mjs"
    own.parent.mkdir(parents=True)
    own.write_text("// clear-gate.mjs v1\n")
    commit(pkg, "the package deployed into itself at v1")  # the box already has templates at v2
    (pkg / "templates" / "clear-gate.mjs").write_text("// clear-gate.mjs v3\n")
    commit(pkg, "v3")
    own.write_text("// clear-gate.mjs v3\n")
    commit(pkg, "the package deploys into itself at v3")
    hook(tree, "clear-gate.mjs").parent.mkdir(parents=True)
    hook(tree, "clear-gate.mjs").write_text("// clear-gate.mjs v2\n")
    out = run()
    assert hook(tree, "clear-gate.mjs").read_text() == "// clear-gate.mjs v3\n", out
    assert any("upgraded .claude/hooks/clear-gate.mjs" in l for l in out)


def test_an_uncommitted_template_edit_is_not_what_ships(box):
    """The installer reads the checkout's committed HEAD, not its working tree."""
    run, pkg, tree, _, _, _ = box
    (pkg / "templates" / "clear-gate.mjs").write_text("// clear-gate.mjs v3-UNCOMMITTED\n")
    assert git(pkg, "status", "--porcelain", "--", "templates"), "precondition: the edit is uncommitted"
    out = run()
    assert hook(tree, "clear-gate.mjs").read_text() == "// clear-gate.mjs v2\n", \
        "the project gets HEAD content, not the working-tree edit"
    assert any("(uncommitted changes in the checkout are not shipped)" in l for l in out)


def test_the_from_line_names_the_package_head(box):
    """The provenance line names the package and its actual HEAD short sha, first."""
    run, pkg, _, _, _, _ = box
    sha = git(pkg, "rev-parse", "--short", "HEAD")
    out = run()
    assert out[0] == f"  auto-clear templates: from set-claude-handoff {sha}", out


def test_a_no_op_run_prints_no_from_line(box):
    """Everything already current — no provenance line, nothing to attribute."""
    run, _, _, _, _, _ = box
    run()
    out = run()
    assert not any("from set-claude-handoff" in l for l in out)


@pytest.mark.parametrize("entry,why", [({"archived": True}, "archived"),
                                       ({"deploy": False}, "deploy: false"),
                                       ({"auto_clear": False}, "auto_clear: false")])
def test_archived_data_and_opted_out_projects_get_nothing(box, entry, why):
    """AC-2"""
    run, _, tree, home, log, registry = box
    out = run(reg={**registry, "proj": {"path": str(tree), **entry}})
    assert len(out) == 1 and why in out[0]
    assert not (tree / ".claude").exists() and not unit_file(home).exists() and not calls(log)


def test_no_package_checkout_is_a_line_not_a_failure(box):
    """AC-9"""
    run, _, tree, home, _, _ = box
    out = run(reg={"proj": {"path": str(tree)}})
    assert len(out) == 1 and "set-claude-handoff" in out[0] and "skipped" in out[0]
    assert not (tree / ".claude").exists()


def test_main_exits_zero_without_a_registry(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SET_CORE_REGISTRY", str(tmp_path / "missing.json"))
    assert acd.main(["--project-dir", str(tmp_path), "--name", "x"]) == 0
    assert "skipped" in capsys.readouterr().out


def test_a_hand_unit_with_an_old_threshold_is_left_and_named(box):
    """AC-7"""
    run, _, tree, home, log, _ = box
    hand = home / ".config" / "systemd" / "user" / "auto-clear-proj.service"
    hand.write_text(f"[Service]\nExecStart=/bin/bash {tree}/.claude/hooks/watch-auto-clear.sh "
                    f"--dir {tree} --compact-threshold 500000 --interval 60\n")
    before = hand.read_bytes()
    out = run()
    assert hand.read_bytes() == before and not unit_file(home).exists()
    [line] = [l for l in out if "auto-clear unit" in l]
    assert "auto-clear-proj.service" in line and "--compact-threshold 500000" in line and "remove" in line
    assert not any("enable" in c for c in calls(log))


def test_no_unit_without_a_reload_hook(box):
    """D4: a project whose own reload is not for clear and whose settings refuse the merge."""
    run, _, tree, home, _, _ = box
    (tree / ".claude").mkdir()
    (tree / ".claude" / "settings.json").write_text("not json")
    out = run()
    assert not unit_file(home).exists()
    assert any("not created" in l for l in out)


def tree_hash(*roots):
    h = hashlib.sha256()
    for root in roots:
        for p in sorted(root.rglob("*")):
            h.update(str(p).encode())
            if p.is_file():
                h.update(p.read_bytes())
    return h.hexdigest()


def test_a_dry_run_plans_and_writes_nothing(box):
    """AC-8 / 5.2"""
    run, _, tree, home, log, _ = box
    before = tree_hash(tree, home)
    out = " | ".join(run(dry_run=True))
    assert tree_hash(tree, home) == before
    assert "would write .claude/hooks/clear-gate.mjs" in out
    assert "would add reload" in out and "would create" in out
    assert all(c.startswith("--user show-environment") for c in calls(log)), calls(log)
