"""`set-deploy-hooks --auto-clear` (auto-clear-default-install, group 3 and the hook half of 5).

The handoff package's reload and arm hooks are merged with the package's exact strings; a
project's own mechanism is never duplicated; project hooks survive; the wiring stamp is written
only when the reload entry is added; a dry-run writes nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "bin" / "set-deploy-hooks"
RELOAD = 'node "$CLAUDE_PROJECT_DIR/.claude/hooks/handoff-reinject-clear.mjs"'
ARM = 'node "$CLAUDE_PROJECT_DIR/.claude/hooks/handoff-arm.mjs"'
STAMP = Path(".set/handoff/.reload-wired-at")

pytestmark = pytest.mark.skipif(not shutil.which("jq"), reason="set-deploy-hooks needs jq")


def state_env(state, xdg=True):
    """HOME/XDG_STATE_HOME in a sandbox: no run of the script may touch the real home."""
    env = dict(os.environ, HOME=str(state))
    if xdg:
        env["XDG_STATE_HOME"] = str(state)
    else:
        env.pop("XDG_STATE_HOME", None)
    return env


def run(tree, *flags, state=None, xdg=True):
    state = Path(state or tempfile.mkdtemp(prefix="deploy-hooks-state-"))
    r = subprocess.run(["bash", str(SCRIPT), "--auto-clear", *flags, str(tree)],
                       capture_output=True, text=True, timeout=60, env=state_env(state, xdg))
    assert r.returncode == 0, r.stderr
    return r.stdout


def backup_root(state, xdg=True):
    root = Path(state) if xdg else Path(state) / ".local" / "state"
    return root / "set-core" / "settings-backup"


def tree_key(tree):
    """The backup dir key: absolute TARGET_DIR, every / turned into -, leading - stripped."""
    return str(tree).replace("/", "-").lstrip("-")


def backup_path(out):
    [line] = [l for l in out.splitlines() if "settings backup:" in l]
    return Path(line.split("settings backup:", 1)[1].strip())


def settings(tree):
    return json.loads((tree / ".claude" / "settings.json").read_text())


def write(tree, hooks):
    (tree / ".claude").mkdir(parents=True, exist_ok=True)
    (tree / ".claude" / "settings.json").write_text(json.dumps({"hooks": hooks}, indent=2))


def commands(doc, event):
    return [h["command"] for e in doc["hooks"].get(event, []) for h in e.get("hooks", [])]


def test_empty_settings_get_both_hooks_and_the_stamp(tmp_path):
    out = run(tmp_path)
    doc = settings(tmp_path)
    [reload_entry] = doc["hooks"]["SessionStart"]
    assert reload_entry["matcher"] == "clear|compact"
    assert reload_entry["hooks"] == [{"type": "command", "command": RELOAD, "timeout": 15}]
    [arm_entry] = doc["hooks"]["PostToolUse"]
    assert arm_entry["matcher"] == "Write|Edit|MultiEdit|Bash" and arm_entry["hooks"][0]["timeout"] == 10
    stamp = (tmp_path / STAMP).read_text().strip()
    assert len(stamp) == 20 and stamp.endswith("Z") and stamp[10] == "T", stamp
    assert "reload added" in out and "arm added" in out


def test_the_package_strings_already_present_change_nothing(tmp_path):
    """AC-3, hooks half: second run — no duplicate, no rewrite, no new stamp."""
    run(tmp_path)
    before = (tmp_path / ".claude" / "settings.json").read_bytes()
    (tmp_path / STAMP).write_text("2026-01-01T00:00:00Z\n")
    out = run(tmp_path)
    assert (tmp_path / ".claude" / "settings.json").read_bytes() == before
    assert (tmp_path / STAMP).read_text() == "2026-01-01T00:00:00Z\n", "a no-op run must not move the stamp"
    assert "already wired" in out


def test_a_hand_merge_with_the_package_strings_dedups(tmp_path):
    write(tmp_path, {"SessionStart": [{"matcher": "clear|compact", "hooks": [
                        {"type": "command", "command": RELOAD, "timeout": 15}]}],
                     "PostToolUse": [{"matcher": "Write|Edit|MultiEdit|Bash", "hooks": [
                        {"type": "command", "command": ARM, "timeout": 10}]}]})
    before = (tmp_path / ".claude" / "settings.json").read_bytes()
    run(tmp_path)
    assert (tmp_path / ".claude" / "settings.json").read_bytes() == before
    assert not (tmp_path / STAMP).exists()


def test_a_projects_own_reload_script_is_not_duplicated(tmp_path):
    """AC-6"""
    write(tmp_path, {"SessionStart": [{"matcher": "startup|clear|compact", "hooks": [
                        {"type": "command", "command": "bash scripts/session-reinject.sh"}]}]})
    out = run(tmp_path)
    doc = settings(tmp_path)
    assert commands(doc, "SessionStart") == ["bash scripts/session-reinject.sh"]
    assert ARM in commands(doc, "PostToolUse"), "the arm half is independent of the reload half"
    assert "reload skipped" in out and "own reinject" in out
    assert not (tmp_path / STAMP).exists(), "this step did not wire the reload"


def test_a_reinject_for_another_source_does_not_count(tmp_path):
    """A reinject wired only for `startup` does not reload after /clear."""
    write(tmp_path, {"SessionStart": [{"matcher": "startup", "hooks": [
                        {"type": "command", "command": "bash scripts/session-reinject.sh"}]}]})
    run(tmp_path)
    assert RELOAD in commands(settings(tmp_path), "SessionStart")


def test_a_projects_own_arm_hook_is_not_duplicated(tmp_path):
    write(tmp_path, {"PostToolUse": [{"matcher": "Write", "hooks": [
                        {"type": "command", "command": "node tools/handoff-arm.mjs --mine"}]}]})
    out = run(tmp_path)
    assert commands(settings(tmp_path), "PostToolUse") == ["node tools/handoff-arm.mjs --mine"]
    assert "arm skipped" in out


def test_project_hooks_survive_in_order(tmp_path):
    own = {"SessionStart": [{"matcher": "clear|compact", "hooks": [{"type": "command", "command": "echo mine"}]},
                            {"matcher": "startup", "hooks": [{"type": "command", "command": "echo boot"}]}],
           "Stop": [{"hooks": [{"type": "command", "command": "echo stop"}]}]}
    write(tmp_path, own)
    run(tmp_path)
    doc = settings(tmp_path)
    assert commands(doc, "SessionStart") == ["echo mine", RELOAD, "echo boot"], "same matcher → same entry"
    assert commands(doc, "Stop") == ["echo stop"]


def tree_hash(root):
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        h.update(str(p.relative_to(root)).encode())
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()


@pytest.mark.parametrize("seed", [False, True])
def test_a_dry_run_writes_nothing(tmp_path, seed):
    """AC-8, hooks half: the plan is printed, the tree is byte-identical (also when empty)."""
    if seed:
        write(tmp_path, {"Stop": [{"hooks": [{"type": "command", "command": "echo stop"}]}]})
    before = tree_hash(tmp_path)
    out = run(tmp_path, "--dry-run")
    assert tree_hash(tmp_path) == before
    assert "would add reload" in out and "would add arm" in out


def test_dry_run_is_refused_outside_auto_clear(tmp_path):
    r = subprocess.run(["bash", str(SCRIPT), "--dry-run", str(tmp_path)], capture_output=True, text=True)
    assert r.returncode != 0 and not (tmp_path / ".claude").exists()


def test_a_merge_backs_up_outside_the_tree(tmp_path):
    """The pre-merge settings survive outside the tree; no settings.json.bak in it."""
    write(tmp_path, {"Stop": [{"hooks": [{"type": "command", "command": "echo stop"}]}]})
    pre = (tmp_path / ".claude" / "settings.json").read_bytes()
    state = Path(tempfile.mkdtemp(prefix="deploy-hooks-state-"))
    out = run(tmp_path, state=state)
    assert not list(tmp_path.rglob("*.bak")), "no backup may sit in the project tree"
    path = backup_path(out)
    assert path.is_file() and path.read_bytes() == pre, "the backup holds the PRE-merge content"
    assert path.parent == backup_root(state) / tree_key(tmp_path)
    assert re.fullmatch(r"settings\.json\.\d{8}T\d{6}Z", path.name), path.name


def test_a_dry_run_writes_no_backup(tmp_path):
    state = Path(tempfile.mkdtemp(prefix="deploy-hooks-state-"))
    write(tmp_path, {"Stop": [{"hooks": [{"type": "command", "command": "echo stop"}]}]})
    out = run(tmp_path, "--dry-run", state=state)
    assert not backup_root(state).exists(), "a dry-run plans, it does not back up"
    assert "backup" not in out


def test_without_xdg_state_home_the_backup_goes_under_home(tmp_path):
    """The documented default: XDG_STATE_HOME unset → $HOME/.local/state/..."""
    write(tmp_path, {"Stop": [{"hooks": [{"type": "command", "command": "echo stop"}]}]})
    state = Path(tempfile.mkdtemp(prefix="deploy-hooks-state-"))
    out = run(tmp_path, state=state, xdg=False)
    path = backup_path(out)
    assert path.parent == backup_root(state, xdg=False) / tree_key(tmp_path)
    assert path.is_file()
