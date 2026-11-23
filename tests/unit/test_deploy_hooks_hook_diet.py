"""hook-diet: the three skill-tracking hooks are no longer deployed, and every deploy strips them.

`set-hook-skill`, `set-hook-activity` and `set-hook-stop` spawned a process on every prompt,
Skill call and Stop; the only readers of what they wrote are orchestration-era routes and the
git-bus MCP tools. Measured 2026-11-23: the fleet reads neither `.set/activity.json` nor
`.set/agents/*.skill`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DEPLOY = REPO / "bin" / "set-deploy-hooks"
RETIRED = {"set-hook-skill", "set-hook-activity", "set-hook-stop", ".claude/hooks/activity-track.sh"}

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="set-deploy-hooks requires jq")


def _commands(settings: Path) -> list[str]:
    data = json.loads(settings.read_text())
    return [h.get("command", "") for entries in data.get("hooks", {}).values()
            for e in entries for h in e.get("hooks", [])]


def _deploy(proj: Path) -> subprocess.CompletedProcess:
    return subprocess.run([str(DEPLOY), str(proj)], check=True, capture_output=True, text=True, timeout=60)


def test_a_fresh_project_gets_none_of_the_retired_hooks(tmp_path):
    _deploy(tmp_path)
    cmds = _commands(tmp_path / ".claude" / "settings.json")
    assert not RETIRED & set(cmds)
    assert "set-hook-waveboard" in cmds and "set-hook-question-relay" in cmds


def test_an_old_project_is_stripped_and_keeps_its_own_hooks(tmp_path):
    (tmp_path / ".claude").mkdir()
    settings = tmp_path / ".claude" / "settings.json"
    settings.write_text(json.dumps({"hooks": {
        "UserPromptSubmit": [{"matcher": "", "hooks": [
            {"type": "command", "command": "set-hook-skill", "timeout": 5},
            {"type": "command", "command": "own-prompt-hook"}]}],
        "PreToolUse": [
            {"matcher": "Skill", "hooks": [{"type": "command", "command": "set-hook-activity", "timeout": 5}]},
            {"matcher": "Bash", "hooks": [{"type": "command", "command": ".claude/hooks/activity-track.sh"},
                                          {"type": "command", "command": "own-firewall"}]},
            {"matcher": "AskUserQuestion", "hooks": [{"type": "command", "command": "set-hook-question-relay"}]}],
        "Stop": [{"matcher": "", "hooks": [
            {"type": "command", "command": "set-hook-stop", "timeout": 5},
            {"type": "command", "command": "set-hook-waveboard", "timeout": 15},
            {"type": "command", "command": "set-hook-wait-detect", "timeout": 60}]}],
    }}))
    out = _deploy(tmp_path)
    cmds = _commands(settings)
    assert not RETIRED & set(cmds), cmds
    assert {"own-prompt-hook", "own-firewall", "set-hook-waveboard"} <= set(cmds)
    # The Skill entry held only a retired hook, so the whole entry is gone.
    pre = json.loads(settings.read_text())["hooks"]["PreToolUse"]
    assert [e["matcher"] for e in pre] == ["Bash", "AskUserQuestion"]
    assert "retired skill-tracking" in out.stdout


def test_a_canonical_project_with_a_retired_hook_is_not_left_alone(tmp_path):
    # Every base hook present: the early "already canonical" return must not skip the strip.
    _deploy(tmp_path)
    settings = tmp_path / ".claude" / "settings.json"
    data = json.loads(settings.read_text())
    data["hooks"]["Stop"][0]["hooks"].insert(0, {"type": "command", "command": "set-hook-stop"})
    settings.write_text(json.dumps(data))
    _deploy(tmp_path)
    assert "set-hook-stop" not in _commands(settings)


def test_a_second_run_is_a_no_op(tmp_path):
    _deploy(tmp_path)
    settings = tmp_path / ".claude" / "settings.json"
    before = settings.read_text()
    _deploy(tmp_path)
    assert settings.read_text() == before
