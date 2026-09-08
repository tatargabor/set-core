"""Tests for lib/set_orch/local_config.py — the uncommitted home for values
that are machine- or project-specific.

The layer exists so the leak gate's block message can point somewhere
legitimate. Every test here pins one half of the promise: values resolve in
one documented order, they never land inside a repository, and a listing
never prints one.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SET_CONFIG = Path(__file__).resolve().parents[2] / "bin" / "set-config"
SETCORE_LIB = Path(__file__).resolve().parents[2] / "lib"

from set_orch import local_config as lc


@pytest.fixture
def cfgdir(tmp_path, monkeypatch):
    d = tmp_path / "cfg"
    monkeypatch.setenv("SET_CONFIG_DIR", str(d))
    return d


class TestOneResolutionChain:
    def test_unset_reads_as_unset_and_returns_the_default(self, cfgdir):
        assert lc.get("no_such_key") is None
        assert lc.get("no_such_key", default="fallback") == "fallback"

    def test_the_environment_overrides_the_files(self, cfgdir, monkeypatch):
        lc.set_value("tools_dir", "/from/file", project="p")
        monkeypatch.setenv("SETCORE_TOOLS_DIR", "/from/env")
        assert lc.get("tools_dir", project="p") == "/from/env"

    def test_project_scope_wins_over_machine_scope(self, cfgdir):
        lc.set_value("endpoint", "machine-value")
        lc.set_value("endpoint", "project-value", project="p")
        assert lc.get("endpoint", project="p") == "project-value"
        assert lc.get("endpoint") == "machine-value"

    def test_the_env_key_folds_non_alphanumerics(self):
        assert lc.env_key("db.host-1") == "SETCORE_DB_HOST_1"


class TestValuesLiveOutsideEveryRepository:
    def test_a_project_write_lands_in_the_config_dir_merged_not_replaced(
            self, cfgdir):
        lc.set_value("first", "1", project="p")
        path = lc.set_value("second", "2", project="p")
        assert path == cfgdir / "projects" / "p.json"
        data = json.loads(path.read_text())
        assert data == {"first": "1", "second": "2"}

    def test_files_and_directories_are_owner_only(self, cfgdir):
        path = lc.set_value("secret_shape", "value", project="p")
        assert (path.stat().st_mode & 0o777) == 0o600
        assert (path.parent.stat().st_mode & 0o777) == 0o700
        assert (lc.set_value("k", "v").stat().st_mode & 0o777) == 0o600

    def test_another_project_does_not_see_the_value(self, cfgdir):
        lc.set_value("endpoint", "only-p", project="p")
        assert lc.get("endpoint", project="q") is None

    def test_a_corrupt_file_reads_as_unset_and_is_rebuilt(self, cfgdir):
        machine = cfgdir / "config.json"
        machine.parent.mkdir(parents=True, exist_ok=True)
        machine.write_text("{not json")
        assert lc.get("k") is None
        lc.set_value("k", "v")
        assert json.loads(machine.read_text())["k"] == "v"


class TestTheListingMasks:
    def test_entries_never_carry_the_value_itself(self, cfgdir):
        secret = "super-secret-token-value"
        lc.set_value("token", secret, project="p")
        rows = lc.entries(project="p")
        shapes = [shape for _, shape, _ in rows]
        keys = [key for key, _, _ in rows]
        assert keys == ["token"]
        assert shapes == ["str(24)"]
        assert secret not in str(rows), "the value leaked through the mask"

    def test_the_project_source_shadows_the_machine_source(self, cfgdir):
        lc.set_value("k", "machine")
        lc.set_value("k", "project", project="p")
        rows = lc.entries(project="p")
        assert len(rows) == 1
        assert rows[0][2] == cfgdir / "projects" / "p.json"


class TestTheCLIRoundTripsThroughTheSameLayer:
    def _run(self, cfgdir, *args):
        # set-config is a BASH script — running it under sys.executable parses
        # it as Python and dies on the arrows in its usage text.
        return subprocess.run(
            ["bash", str(SET_CONFIG), *args],
            capture_output=True, text=True,
            env=dict(os.environ, SET_CONFIG_DIR=str(cfgdir),
                     PYTHONPATH=str(SETCORE_LIB)))

    def test_set_then_get_prints_the_value(self, cfgdir):
        assert self._run(cfgdir, "set", "db_host", "localhost",
                         "--project", "p").returncode == 0
        r = self._run(cfgdir, "get", "db_host", "--project", "p")
        assert r.returncode == 0
        assert r.stdout.strip() == "localhost"

    def test_list_masks_every_value(self, cfgdir):
        self._run(cfgdir, "set", "token", "very-secret-123")
        r = self._run(cfgdir, "list")
        assert r.returncode == 0
        assert "token" in r.stdout
        assert "very-secret-123" not in r.stdout

    def test_get_of_a_missing_key_exits_nonzero_without_a_value(
            self, cfgdir):
        r = self._run(cfgdir, "get", "missing_key")
        assert r.returncode != 0
        assert "missing_key" in r.stderr
