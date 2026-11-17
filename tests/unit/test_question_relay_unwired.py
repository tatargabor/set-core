"""B-182: the relay names the registered projects whose sessions bypass it.

The switch said ready while one project's settings never wired the hook, so its
question stayed in a terminal nobody was looking at.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.fleet import question_relay as qr

RELAY = {"matcher": "AskUserQuestion", "hooks": [{"type": "command", "command": "set-hook-question-relay"}]}
WAIT = {"matcher": "", "hooks": [{"type": "command", "command": "set-hook-wait-detect"}]}


def _project(tmp_path, name, settings=None, local=None):
    root = tmp_path / name
    (root / ".claude").mkdir(parents=True)
    if settings is not None:
        (root / ".claude" / "settings.json").write_text(json.dumps(settings))
    if local is not None:
        (root / ".claude" / "settings.local.json").write_text(json.dumps(local))
    return {"name": name, "path": str(root)}


def test_names_the_project_without_hooks_and_only_it(tmp_path):
    wired = _project(tmp_path, "wired", {"hooks": {"PreToolUse": [RELAY], "Stop": [WAIT]}})
    bare = _project(tmp_path, "hand-authored", {"hooks": {"Stop": [{"hooks": [{"command": "own-stop.sh"}]}]}})
    out = qr.unwired_projects([wired, bare], user_settings=tmp_path / "none.json")
    assert out == [{"project": "hand-authored",
                    "missing": ["set-hook-question-relay", "set-hook-wait-detect"]}]


def test_names_which_hook_is_missing(tmp_path):
    half = _project(tmp_path, "half", {"hooks": {"PreToolUse": [RELAY]}})
    out = qr.unwired_projects([half], user_settings=tmp_path / "none.json")
    assert out == [{"project": "half", "missing": ["set-hook-wait-detect"]}]


def test_relay_hook_under_another_tool_matcher_does_not_count(tmp_path):
    wrong = {"matcher": "Bash", "hooks": RELAY["hooks"]}
    p = _project(tmp_path, "p", {"hooks": {"PreToolUse": [wrong], "Stop": [WAIT]}})
    out = qr.unwired_projects([p], user_settings=tmp_path / "none.json")
    assert out == [{"project": "p", "missing": ["set-hook-question-relay"]}]


def test_local_and_user_settings_count(tmp_path):
    split = _project(tmp_path, "split", {"hooks": {"PreToolUse": [RELAY]}}, local={"hooks": {"Stop": [WAIT]}})
    bare = _project(tmp_path, "bare", {})
    assert qr.unwired_projects([split], user_settings=tmp_path / "none.json") == []
    user = tmp_path / "user.json"
    user.write_text(json.dumps({"hooks": {"PreToolUse": [RELAY], "Stop": [WAIT]}}))
    assert qr.unwired_projects([bare], user_settings=user) == []


def test_unreadable_settings_count_as_unwired(tmp_path):
    p = _project(tmp_path, "broken")
    (tmp_path / "broken" / ".claude" / "settings.json").write_text("{ not json")
    out = qr.unwired_projects([p], user_settings=tmp_path / "none.json")
    assert out and out[0]["project"] == "broken"


def test_archived_and_missing_paths_are_skipped(tmp_path):
    gone = {"name": "gone", "path": str(tmp_path / "nope")}
    archived = dict(_project(tmp_path, "old", {}), archived=True)
    assert qr.unwired_projects([gone, archived], user_settings=tmp_path / "none.json") == []
