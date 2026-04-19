"""Test: check_config_drift detects stale directives.json vs config.yaml.

See OpenSpec change: fix-e2e-infra-systematic (T1.7.3).

The orchestrator parses `directives.json` once at startup. If the user edits
`config.yaml` later but doesn't restart, gate behavior diverges from what the
user believes is configured — silently. `check_config_drift()` surfaces this
explicitly in events + WARNING logs.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "lib"))

from tests.lib import test_paths as tp


@pytest.fixture
def fake_project(tmp_path: Path):
    state_dir = tmp_path / "proj"
    cfg_dir = state_dir / "set" / "orchestration"
    cfg_dir.mkdir(parents=True)
    state_file = tp.state_file(state_dir)
    state_file.write_text(json.dumps({"status": "running", "changes": []}))
    return state_file, cfg_dir


def test_config_drift_detected_when_yaml_newer(fake_project, caplog):
    from set_orch.engine import check_config_drift

    state_file, cfg_dir = fake_project
    directives_json = cfg_dir / "directives.json"
    directives_json.write_text(json.dumps({"time_limit_secs": 0}))
    old = time.time() - 3600
    os.utime(directives_json, (old, old))

    config_yaml = cfg_dir / "config.yaml"
    config_yaml.write_text("e2e_command: npx playwright test\n")
    # config.yaml mtime is "now" (3600s after directives) → drift.

    caplog.set_level(logging.WARNING)
    bus = MagicMock()
    drifted = check_config_drift(str(state_file), str(directives_json), event_bus=bus)

    assert drifted is True
    msgs = " ".join(r.getMessage() for r in caplog.records)
    assert "CONFIG_DRIFT" in msgs, msgs

    # Event emitted with the expected payload
    emits = [c for c in bus.emit.call_args_list if c.args and c.args[0] == "CONFIG_DRIFT"]
    assert len(emits) == 1
    data = emits[0].kwargs.get("data") or {}
    assert data["delta_seconds"] >= 3000
    assert data["config_yaml"].endswith("config.yaml")
    assert data["directives_json"].endswith("directives.json")


def test_no_drift_when_directives_newer(fake_project, caplog):
    from set_orch.engine import check_config_drift

    state_file, cfg_dir = fake_project
    config_yaml = cfg_dir / "config.yaml"
    config_yaml.write_text("e2e_command: npx playwright test\n")
    old = time.time() - 3600
    os.utime(config_yaml, (old, old))

    directives_json = cfg_dir / "directives.json"
    directives_json.write_text(json.dumps({"time_limit_secs": 0}))

    caplog.set_level(logging.WARNING)
    bus = MagicMock()
    drifted = check_config_drift(str(state_file), str(directives_json), event_bus=bus)

    assert drifted is False
    msgs = " ".join(r.getMessage() for r in caplog.records)
    assert "CONFIG_DRIFT" not in msgs
    drifts = [c for c in bus.emit.call_args_list if c.args and c.args[0] == "CONFIG_DRIFT"]
    assert not drifts


def test_no_drift_when_config_missing(fake_project, caplog):
    from set_orch.engine import check_config_drift

    state_file, cfg_dir = fake_project
    directives_json = cfg_dir / "directives.json"
    directives_json.write_text(json.dumps({"time_limit_secs": 0}))
    # No config.yaml on disk.
    caplog.set_level(logging.WARNING)
    bus = MagicMock()
    drifted = check_config_drift(str(state_file), str(directives_json), event_bus=bus)
    assert drifted is False
    assert not [c for c in bus.emit.call_args_list if c.args and c.args[0] == "CONFIG_DRIFT"]


def test_touch_triggers_drift(fake_project):
    """Simulate a user `touch`-ing config.yaml — even with no content change,
    mtime bump must be enough to trigger the warning."""
    from set_orch.engine import check_config_drift

    state_file, cfg_dir = fake_project
    directives_json = cfg_dir / "directives.json"
    directives_json.write_text(json.dumps({"time_limit_secs": 0}))
    config_yaml = cfg_dir / "config.yaml"
    config_yaml.write_text("unchanged\n")

    # Both same mtime — no drift
    same = time.time() - 1000
    os.utime(directives_json, (same, same))
    os.utime(config_yaml, (same, same))
    assert check_config_drift(str(state_file), str(directives_json)) is False

    # Touch config.yaml forward
    os.utime(config_yaml, (same + 10, same + 10))
    assert check_config_drift(str(state_file), str(directives_json)) is True
