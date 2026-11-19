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
NOTIFY = {"matcher": "", "hooks": [{"type": "command", "command": "set-hook-notify-relay"}]}


def _project(tmp_path, name, settings=None, local=None):
    root = tmp_path / name
    (root / ".claude").mkdir(parents=True)
    if settings is not None:
        (root / ".claude" / "settings.json").write_text(json.dumps(settings))
    if local is not None:
        (root / ".claude" / "settings.local.json").write_text(json.dumps(local))
    return {"name": name, "path": str(root)}


def test_names_the_project_without_hooks_and_only_it(tmp_path):
    wired = _project(tmp_path, "wired", {"hooks": {"PreToolUse": [RELAY], "Stop": [WAIT], "Notification": [NOTIFY]}})
    bare = _project(tmp_path, "hand-authored", {"hooks": {"Stop": [{"hooks": [{"command": "own-stop.sh"}]}]}})
    out = qr.unwired_projects([wired, bare], user_settings=tmp_path / "none.json")
    assert out == [{"project": "hand-authored",
                    "missing": ["set-hook-question-relay", "set-hook-wait-detect", "set-hook-notify-relay"]}]


def test_names_which_hook_is_missing(tmp_path):
    half = _project(tmp_path, "half", {"hooks": {"PreToolUse": [RELAY]}})
    out = qr.unwired_projects([half], user_settings=tmp_path / "none.json")
    assert out == [{"project": "half", "missing": ["set-hook-wait-detect", "set-hook-notify-relay"]}]


def test_relay_hook_under_another_tool_matcher_does_not_count(tmp_path):
    wrong = {"matcher": "Bash", "hooks": RELAY["hooks"]}
    p = _project(tmp_path, "p", {"hooks": {"PreToolUse": [wrong], "Stop": [WAIT], "Notification": [NOTIFY]}})
    out = qr.unwired_projects([p], user_settings=tmp_path / "none.json")
    assert out == [{"project": "p", "missing": ["set-hook-question-relay"]}]


def test_local_and_user_settings_count(tmp_path):
    split = _project(tmp_path, "split", {"hooks": {"PreToolUse": [RELAY]}}, local={"hooks": {"Stop": [WAIT], "Notification": [NOTIFY]}})
    bare = _project(tmp_path, "bare", {})
    assert qr.unwired_projects([split], user_settings=tmp_path / "none.json") == []
    user = tmp_path / "user.json"
    user.write_text(json.dumps({"hooks": {"PreToolUse": [RELAY], "Stop": [WAIT], "Notification": [NOTIFY]}}))
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


# --------------------------------------------------------------------------- #
# wire_project — machine-local wiring, never a tracked file, never twice

import subprocess


def _git_repo(path):
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def test_wires_both_hooks_into_the_local_file_only(tmp_path):
    root = _git_repo(tmp_path / "repo")
    added = qr.wire_project(root, user_settings=tmp_path / "none.json")
    assert added == ["set-hook-question-relay", "set-hook-wait-detect", "set-hook-notify-relay"]
    assert not (root / ".claude" / "settings.json").exists()
    local = json.loads((root / ".claude" / "settings.local.json").read_text())
    assert qr._hooks_in(local) == {"set-hook-question-relay", "set-hook-wait-detect", "set-hook-notify-relay"}
    # The local file stays out of git, without touching a tracked .gitignore.
    assert not (root / ".gitignore").exists()
    ignored = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", ".claude/settings.local.json"])
    assert ignored.returncode == 0
    assert qr.unwired_projects([{"name": "repo", "path": str(root)}], user_settings=tmp_path / "none.json") == []


def test_merges_into_an_existing_local_file_and_is_idempotent(tmp_path):
    root = tmp_path / "p"
    (root / ".claude").mkdir(parents=True)
    own = {"permissions": {"allow": ["Bash(ls)"]}, "hooks": {"Stop": [{"hooks": [{"command": "own.sh"}]}]}}
    (root / ".claude" / "settings.local.json").write_text(json.dumps(own))
    qr.wire_project(root, user_settings=tmp_path / "none.json")
    assert qr.wire_project(root, user_settings=tmp_path / "none.json") == []
    data = json.loads((root / ".claude" / "settings.local.json").read_text())
    assert data["permissions"] == own["permissions"]
    stop_cmds = [h["command"] for e in data["hooks"]["Stop"] for h in e["hooks"]]
    assert stop_cmds == ["own.sh", "set-hook-wait-detect"]
    notify_cmds = [h["command"] for e in data["hooks"]["Notification"] for h in e["hooks"]]
    assert notify_cmds == ["set-hook-notify-relay"]
    relay = [e for e in data["hooks"]["PreToolUse"] if e["matcher"] == "AskUserQuestion"]
    assert len(relay) == 1


def test_never_adds_a_hook_the_project_settings_already_wire(tmp_path):
    """Two relay hooks would post every question twice."""
    p = _project(tmp_path, "half", {"hooks": {"PreToolUse": [RELAY]}})
    added = qr.wire_project(tmp_path / "half", user_settings=tmp_path / "none.json")
    assert added == ["set-hook-wait-detect", "set-hook-notify-relay"]
    local = json.loads((tmp_path / "half" / ".claude" / "settings.local.json").read_text())
    assert "PreToolUse" not in local["hooks"]


def test_refuses_to_overwrite_an_unreadable_local_file(tmp_path):
    root = tmp_path / "p"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "settings.local.json").write_text("{ broken")
    try:
        qr.wire_project(root, user_settings=tmp_path / "none.json")
        raise AssertionError("expected a refusal")
    except ValueError:
        pass
    assert (root / ".claude" / "settings.local.json").read_text() == "{ broken"


def test_adding_a_project_through_the_api_wires_it(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from set_orch import api as api_module
    from set_orch.api import helpers
    from set_orch.server import create_app

    pf = tmp_path / "projects.json"
    pf.write_text(json.dumps({"projects": {}}))
    monkeypatch.setattr(helpers, "PROJECTS_FILE", pf)
    monkeypatch.setattr(api_module, "PROJECTS_FILE", pf, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    root = _git_repo(tmp_path / "newproj")
    r = TestClient(create_app(web_dist_dir="/nonexistent")).post(
        "/api/projects", json={"name": "newproj", "path": str(root)})
    assert r.status_code == 200 and r.json()["status"] == "ok"
    local = json.loads((root / ".claude" / "settings.local.json").read_text())
    assert qr._hooks_in(local) == {"set-hook-question-relay", "set-hook-wait-detect", "set-hook-notify-relay"}
