"""model-ids-follow-releases — a machine's copied id table follows set-core's releases (B-191).

Measured 2026-11-22: a migrated `providers.json` carried a full COPY of the shipped
id table, so moving `sonnet` to 5.5 in set-core left this machine on 4.6. These
tests drive the real refresh and check against a file under tmp_path.
"""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from set_orch.providers import migrate as mg
from set_orch.providers import upstream as up
from set_orch.providers.defaults import (
    ANTHROPIC_MODEL_NAMES, DEFAULT_MODEL_IDS, PREVIOUSLY_SHIPPED_IDS,
)

ROOT = Path(__file__).resolve().parents[2]

#: The block this machine actually carried on 2026-11-22 (ids only, no credential).
OLD_COPY = {
    "haiku": "claude-haiku-4-5-20251001", "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-5-5", "opus-1m": "claude-opus-5-5[1m]",
    "sonnet-1m": "claude-sonnet-4-6[1m]", "opus-4-6": "claude-opus-4-6",
    "opus-4-7": "claude-opus-4-7", "opus-4-8": "claude-opus-4-8", "opus-5": "claude-opus-5",
    "opus-5-5": "claude-opus-5-5", "opus-4-6-1m": "claude-opus-4-6[1m]",
    "opus-4-7-1m": "claude-opus-4-7[1m]", "opus-5-1m": "claude-opus-5[1m]",
    "opus-5-5-1m": "claude-opus-5-5[1m]",
}
OLD_MODELS = ["fable", "haiku", "sonnet", "opus", "sonnet-1m", "opus-1m", "opus-4-6", "opus-4-7",
              "opus-4-8", "opus-5", "opus-4-6-1m", "opus-4-7-1m", "opus-5-1m", "opus-5-5", "opus-5-5-1m"]


@pytest.fixture
def machine(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    monkeypatch.setenv("SET_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    def write(model_ids=OLD_COPY, models=OLD_MODELS):
        anthropic = {"models": list(models), "requires_credential": False, "credential": None,
                     "default_model": "opus", "env": {}, "args": []}
        if model_ids is not None:
            anthropic["model_ids"] = dict(model_ids)
        p = cfg_dir / "providers.json"
        p.write_text(json.dumps({"version": 1, "default": {"provider": "anthropic", "model": "opus"},
                                 "providers": {"anthropic": anthropic,
                                               "glm": {"models": ["glm-5.3"], "requires_credential": True,
                                                       "default_model": "glm-5.3",
                                                       "credential": {"token": "SECRET-TOKEN", "base_url": "https://glm.example"}}},
                                 "projects": {}}, indent=2))
        p.chmod(0o600)
        return p
    return write


def anthropic(p):
    return json.loads(p.read_text())["providers"]["anthropic"]


def launch_id(name):
    from set_orch.providers import resolver as res
    from set_orch.providers.config import load_or_legacy
    cfg, _ = load_or_legacy()
    return res.resolve(provider="anthropic", model=name, config=cfg).launch_args()[-1]


def test_history_never_holds_a_current_default():
    for name, old in PREVIOUSLY_SHIPPED_IDS.items():
        assert DEFAULT_MODEL_IDS[name] not in old, name


def test_this_machines_copy_launched_the_old_sonnet(machine):
    """The defect, held: with the copied block, the shipped bump does not reach a launch."""
    machine()
    assert launch_id("sonnet") == "claude-sonnet-4-6"


def test_a_pure_copy_is_removed_and_the_default_then_applies(machine):
    p = machine()
    changed, lines = mg.refresh(write=True, now="T")
    assert changed
    assert "model_ids" not in anthropic(p)
    assert launch_id("sonnet") == DEFAULT_MODEL_IDS["sonnet"] == "claude-sonnet-5-5"
    assert launch_id("haiku") == "claude-haiku-5-5"
    assert any("sonnet: claude-sonnet-4-6 -> claude-sonnet-5-5" in line for line in lines)
    backup = p.with_name("providers.json.bak-T")
    assert json.loads(backup.read_text())["providers"]["anthropic"]["model_ids"] == OLD_COPY
    assert stat.S_IMODE(p.stat().st_mode) == 0o600 == stat.S_IMODE(backup.stat().st_mode)
    # the credential and the other provider are untouched
    data = json.loads(p.read_text())
    assert data["providers"]["glm"]["credential"] == {"token": "SECRET-TOKEN", "base_url": "https://glm.example"}
    assert not any("SECRET" in line for line in lines)


def test_shipped_names_are_added_to_the_catalogue_never_removed(machine):
    p = machine(models=OLD_MODELS + ["my-own-name"])
    mg.refresh(write=True, now="T")
    models = anthropic(p)["models"]
    assert models[:len(OLD_MODELS) + 1] == OLD_MODELS + ["my-own-name"]
    assert set(ANTHROPIC_MODEL_NAMES) <= set(models)


def test_a_real_override_survives_and_only_stale_copies_move(machine):
    ids = dict(OLD_COPY, opus="claude-opus-9-9-experimental")
    p = machine(model_ids=ids)
    changed, lines = mg.refresh(write=True, now="T")
    block = anthropic(p)["model_ids"]
    assert block["opus"] == "claude-opus-9-9-experimental"
    assert block["sonnet"] == "claude-sonnet-5-5" and block["haiku"] == "claude-haiku-5-5"
    assert block["opus-4-6"] == "claude-opus-4-6"          # a current pin, untouched
    assert set(DEFAULT_MODEL_IDS) <= set(block)              # the lacking shipped names filled in
    assert any("kept" in line and "opus" in line for line in lines)


def test_an_older_release_pinned_on_purpose_is_not_mistaken_for_a_copy(machine):
    """`sonnet` -> an id set-core never shipped for `sonnet` is a choice, even if older."""
    p = machine(model_ids={"sonnet": "claude-sonnet-4-5"})
    mg.refresh(write=True, now="T")
    assert anthropic(p)["model_ids"]["sonnet"] == "claude-sonnet-4-5"


def test_the_dry_run_writes_nothing(machine):
    p = machine()
    before = p.read_bytes()
    changed, lines = mg.refresh(write=False)
    assert changed and p.read_bytes() == before
    assert not list(p.parent.glob("*.bak-*"))
    assert any("--write" in line for line in lines)


def test_an_up_to_date_file_is_left_alone(machine):
    p = machine(model_ids=None, models=list(ANTHROPIC_MODEL_NAMES))
    before = p.read_bytes()
    changed, lines = mg.refresh(write=True)
    assert not changed and p.read_bytes() == before
    assert not list(p.parent.glob("*.bak-*"))


def test_refresh_is_idempotent(machine):
    p = machine()
    mg.refresh(write=True, now="T1")
    after = p.read_bytes()
    changed, _ = mg.refresh(write=True, now="T2")
    assert not changed and p.read_bytes() == after


def test_a_migrated_machine_carries_no_id_table():
    data = mg.build({"GLM_TOKEN": "x", "GLM_MODEL": "glm-5.3"})
    assert "model_ids" not in data["providers"]["anthropic"]


def test_the_check_reports_a_stale_copy_as_behind(machine):
    # The catalogue is complete, so the stale pins are the ONLY reason for `behind`.
    machine(models=list(ANTHROPIC_MODEL_NAMES))
    page = ("| Claude API ID | `claude-opus-5-5` | `claude-sonnet-5-5` | `claude-haiku-5-5` |\n")
    r = up.check(fetch=lambda url: page)
    assert r.verdict == up.BEHIND
    assert {"name": "sonnet", "copied": "claude-sonnet-4-6", "current": "claude-sonnet-5-5"} in r.stale_pins
    text = "\n".join(up.advice(r))
    assert "set-providers refresh" in text and "claude-sonnet-4-6" in text


def test_the_check_is_current_after_the_refresh(machine):
    machine()
    mg.refresh(write=True, now="T")
    page = ("| Claude API ID | `claude-opus-5-5` | `claude-sonnet-5-5` | `claude-haiku-5-5` |\n")
    r = up.check(fetch=lambda url: page)
    assert r.stale_pins == [] and r.verdict == up.CURRENT


def test_cli_dry_run_exit_code(machine, tmp_path):
    machine()
    env = {**os.environ}
    res = subprocess.run([sys.executable, str(ROOT / "bin" / "set-providers"), "refresh"],
                         capture_output=True, text=True, env=env)
    assert res.returncode == 1, res.stderr
    assert "dry run" in res.stdout
