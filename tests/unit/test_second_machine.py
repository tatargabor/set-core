"""set-core on a second developer's machine — nothing of the first machine baked in.

Each test holds one place that used to assume the machine it was written on: a unit PATH with
one machine's node directory, a project search limited to one directory layout, a bus registry
path that ignored XDG_DATA_HOME.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
UNITS = [REPO / "templates" / "systemd" / "set-web.service",
         REPO / "templates" / "systemd" / "set-agent-owner.service"]


def test_unit_templates_carry_no_fixed_path():
    for unit in UNITS:
        text = unit.read_text()
        assert "Environment=PATH=__SERVICE_PATH__" in text, unit.name
        assert "/home/" not in text and "linuxbrew" not in text, unit.name


def test_every_installer_fills_the_path_placeholder():
    """Whoever fills __SET_TOOLS_ROOT__ in a systemd unit must fill __SERVICE_PATH__ too —
    an unfilled placeholder is a unit whose PATH is a literal word."""
    for script in (REPO / "install.sh", REPO / "bin" / "set-web-install"):
        text = script.read_text()
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if "__SET_TOOLS_ROOT__" in line and ("service_src" in line or "owner_src" in line
                                                 or "SERVICE_FILE" in line or (
                                                     i + 1 < len(lines) and "_src" in lines[i + 1])):
                window = "\n".join(lines[i:i + 3])
                if "plist" in window or "__PYTHON__" in window:
                    continue  # the macOS launchd plists set no PATH
                assert "__SERVICE_PATH__" in window, f"{script.name}:{i + 1}"


def test_service_path_follows_the_installing_shell(tmp_path):
    tools = tmp_path / "somewhere" / "bin"
    tools.mkdir(parents=True)
    for name in ("node", "claude"):
        f = tools / name
        f.write_text("#!/bin/sh\n")
        f.chmod(0o755)
    env = {"HOME": str(tmp_path / "home"), "PATH": f"{tools}:/usr/bin:/bin"}
    r = subprocess.run(["bash", "-c", f'source "{REPO}/bin/set-common.sh" >/dev/null 2>&1; service_path'],
                       capture_output=True, text=True, env=env, timeout=30)
    parts = r.stdout.strip().split(":")
    assert parts[0] == f"{tmp_path}/home/.local/bin"
    assert str(tools) in parts and parts.count(str(tools)) == 1
    assert {"/usr/local/bin", "/usr/bin", "/bin"} <= set(parts) and len(parts) == len(set(parts))
    assert not any("linuxbrew" in p for p in parts)


def test_the_bus_registry_follows_xdg_data_home(tmp_path, monkeypatch):
    from set_orch.fleet.discovery import messaging_registry_path
    monkeypatch.delenv("SET_AGENT_COMM_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert messaging_registry_path() == str(tmp_path / "data" / "set-agent-comm" / "registry.json")
    monkeypatch.setenv("SET_AGENT_COMM_DIR", str(tmp_path / "bus"))
    assert messaging_registry_path() == str(tmp_path / "bus" / "registry.json")


def test_context_report_finds_a_project_through_the_registry(tmp_path):
    """A project outside ~/code2 is found by its registry name."""
    proj = tmp_path / "src" / "elsewhere"
    (proj).mkdir(parents=True)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "projects.json").write_text(json.dumps({"projects": {"demo": {"path": str(proj)}}}))
    env = {**os.environ, "HOME": str(tmp_path / "home"), "SET_CONFIG_DIR": str(cfg)}
    r = subprocess.run([str(REPO / "bin" / "set-context-report"), "--project", "demo"],
                       capture_output=True, text=True, env=env, timeout=60)
    assert "not found" not in r.stderr, r.stderr
    assert f"Path: {proj}" in r.stdout
