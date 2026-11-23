"""B-200: the registry module honours SET_CONFIG_DIR / SET_CORE_REGISTRY like every other reader."""

from __future__ import annotations

import json

from set_orch import project_registry as R


def test_set_config_dir_redirects_load_and_save(tmp_path, monkeypatch):
    monkeypatch.delenv("SET_CORE_REGISTRY", raising=False)
    monkeypatch.setenv("SET_CONFIG_DIR", str(tmp_path))
    (tmp_path / "projects.json").write_text(json.dumps({"projects": {"x": {"path": "/tmp/x"}}}))
    names = [p.get("name") for p in R.load_projects()]
    assert "x" in names
    assert R.default_registry_file() == tmp_path / "projects.json"


def test_set_core_registry_wins(tmp_path, monkeypatch):
    reg = tmp_path / "elsewhere.json"
    monkeypatch.setenv("SET_CONFIG_DIR", str(tmp_path / "unused"))
    monkeypatch.setenv("SET_CORE_REGISTRY", str(reg))
    assert R.default_registry_file() == reg


def test_a_repointed_projects_file_still_wins(tmp_path, monkeypatch):
    # The existing prune/archive tests sandbox by patching PROJECTS_FILE; the environment
    # must not send them to the real registry.
    monkeypatch.setenv("SET_CONFIG_DIR", str(tmp_path / "env"))
    pinned = tmp_path / "pinned.json"
    monkeypatch.setattr(R, "PROJECTS_FILE", pinned)
    assert R.default_registry_file() == pinned
