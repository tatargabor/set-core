"""The status contract reader: what it accepts, and what it refuses to guess.

The rule under test throughout is the same one the consumer side states as its own iron
rule — the abstraction may define the SHAPE, never the VALUE. Every failure path here
must produce a visible gap. A dashboard that shows 0 open bugs because a script crashed
is worse than one showing an error, because only one of the two ever gets fixed.
"""

import json
import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from set_orch.project_status import (  # noqa: E402
    CONFIG_KEY,
    StatusConfig,
    gather,
    load_status_config,
    parse_envelope,
    query,
)


def _envelope(**over):
    payload = {
        "contractVersion": 1,
        "generatedAt": "2026-07-24T10:00:00Z",
        "command": "bugs",
        "ok": True,
        "data": {"total": 67},
    }
    payload.update(over)
    return json.dumps(payload)


def _script(tmp_path: Path, body: str, name: str = "api.sh") -> Path:
    path = tmp_path / name
    path.write_text("#!/usr/bin/env bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def _project(tmp_path: Path, command: str, **extra) -> Path:
    proj = tmp_path / "proj"
    (proj / "set" / "orchestration").mkdir(parents=True, exist_ok=True)
    block = {"command": command}
    block.update(extra)
    import yaml
    (proj / "set" / "orchestration" / "config.yaml").write_text(
        yaml.safe_dump({"max_parallel": 2, CONFIG_KEY: block})
    )
    return proj


# ── envelope validation ────────────────────────────────────────────────────

def test_a_valid_envelope_yields_its_data():
    result = parse_envelope("bugs", _envelope())
    assert result.ok and result.data == {"total": 67}
    assert result.contract_version == 1
    assert result.generated_at == "2026-07-24T10:00:00Z"


def test_an_unknown_contract_version_is_refused_not_parsed():
    """A later version may have MOVED a field, which this code would read as absent."""
    result = parse_envelope("bugs", _envelope(contractVersion=2))
    assert not result.ok
    assert result.error_class == "unsupported-version"
    assert "2" in result.error


def test_a_missing_version_is_refused():
    payload = json.loads(_envelope())
    del payload["contractVersion"]
    result = parse_envelope("bugs", json.dumps(payload))
    assert not result.ok and result.error_class == "missing-version"


def test_non_json_output_is_a_gap_not_a_crash():
    result = parse_envelope("bugs", "Traceback (most recent call last):\n  ...")
    assert not result.ok and result.error_class == "invalid-json"


def test_ok_false_carries_the_projects_own_reason_through():
    """The project's explanation is better than any we could substitute."""
    result = parse_envelope("environments", _envelope(ok=False, error="health check unreachable"))
    assert not result.ok
    assert result.error == "health check unreachable"
    assert result.error_class == "project-reported-failure"


def test_ok_true_without_data_is_refused():
    payload = json.loads(_envelope())
    del payload["data"]
    result = parse_envelope("bugs", json.dumps(payload))
    assert not result.ok and result.error_class == "missing-data"


def test_no_failure_path_ever_invents_a_value():
    """The property that matters more than any single case."""
    broken = [
        "not json", "[]", "null",
        json.dumps({"ok": True, "data": {}}),
        _envelope(contractVersion=99),
    ]
    for raw in broken:
        result = parse_envelope("bugs", raw)
        assert not result.ok, raw
        assert result.data is None, f"a failed read produced data: {result.data!r}"
        assert result.error, "a failure with no explanation is not actionable"


# ── config ────────────────────────────────────────────────────────────────

def test_a_project_without_a_contract_is_not_an_error(tmp_path):
    proj = tmp_path / "bare"
    (proj / "set" / "orchestration").mkdir(parents=True)
    (proj / "set" / "orchestration" / "config.yaml").write_text("max_parallel: 2\n")
    assert load_status_config(proj) is None


def test_config_is_read_with_its_timeout(tmp_path):
    proj = _project(tmp_path, "node scripts/api.mjs", timeout=90)
    cfg = load_status_config(proj)
    assert cfg.command == "node scripts/api.mjs"
    assert cfg.timeout == 90
    assert cfg.argv_prefix == ["node", "scripts/api.mjs"]


def test_a_nonsense_timeout_falls_back_to_the_default(tmp_path):
    cfg = load_status_config(_project(tmp_path, "x", timeout=-5))
    assert cfg.timeout > 0


def test_a_block_without_a_command_is_treated_as_absent(tmp_path):
    proj = _project(tmp_path, "   ")
    assert load_status_config(proj) is None


# ── invocation ────────────────────────────────────────────────────────────

def test_query_runs_the_command_and_returns_its_data(tmp_path):
    script = _script(tmp_path, f"echo '{_envelope()}'")
    proj = _project(tmp_path, str(script))
    result = query(proj, "bugs")
    assert result.ok and result.data == {"total": 67}


def test_the_command_receives_the_command_name_and_args(tmp_path):
    script = _script(tmp_path, 'printf \'{"contractVersion":1,"ok":true,"data":"%s"}\' "$*"')
    proj = _project(tmp_path, str(script))
    result = query(proj, "bugs", ["--status", "open"])
    assert result.data == "bugs --status open"


def test_a_missing_command_is_a_named_gap(tmp_path):
    proj = _project(tmp_path, str(tmp_path / "does-not-exist"))
    result = query(proj, "bugs")
    assert not result.ok and result.error_class == "command-not-found"


def test_a_nonzero_exit_is_a_gap_and_does_not_leak_stderr(tmp_path):
    """stderr is the project's and may quote its domain — report that, not what."""
    secret = "partner Ács & Társa order 88213"
    script = _script(tmp_path, f'echo "{secret}" >&2; exit 3')
    proj = _project(tmp_path, str(script))
    result = query(proj, "bugs")
    assert not result.ok and result.error_class == "nonzero-exit"
    assert secret not in (result.error or "")


def test_a_hanging_command_times_out_rather_than_blocking(tmp_path):
    script = _script(tmp_path, "sleep 30")
    proj = _project(tmp_path, str(script), timeout=1)
    result = query(proj, "bugs")
    assert not result.ok and result.error_class == "timeout"


def test_an_unconfigured_project_says_so_plainly(tmp_path):
    proj = tmp_path / "bare"
    proj.mkdir()
    result = query(proj, "bugs")
    assert not result.ok and result.error_class == "not-configured"


def test_the_command_runs_in_the_project_directory(tmp_path):
    script = _script(tmp_path, 'printf \'{"contractVersion":1,"ok":true,"data":"%s"}\' "$PWD"')
    proj = _project(tmp_path, str(script))
    result = query(proj, "where")
    assert result.data == str(proj)


# ── gathering several answers ─────────────────────────────────────────────

def test_one_broken_command_does_not_blank_the_others(tmp_path):
    """A project with a broken release script still has bugs worth showing."""
    script = _script(tmp_path, f"""
case "$1" in
  bugs) echo '{_envelope()}' ;;
  releases) echo "boom" >&2; exit 1 ;;
esac
""")
    proj = _project(tmp_path, str(script))
    snap = gather(proj, ["bugs", "releases"])

    assert snap.results["bugs"].ok
    assert snap.results["bugs"].data == {"total": 67}
    assert not snap.results["releases"].ok
    assert not snap.ok, "the snapshot as a whole is not ok while one answer is missing"


def test_the_snapshot_names_its_gaps_so_a_surface_can_render_them(tmp_path):
    script = _script(tmp_path, 'echo "no" >&2; exit 1')
    proj = _project(tmp_path, str(script))
    snap = gather(proj, ["bugs"])
    assert "bugs" in snap.gaps and snap.gaps["bugs"]


def test_serialised_snapshot_never_carries_data_for_a_failed_answer(tmp_path):
    script = _script(tmp_path, 'echo "not json"')
    proj = _project(tmp_path, str(script))
    payload = gather(proj, ["bugs"]).to_dict()
    assert payload["commands"]["bugs"]["data"] is None
    assert payload["commands"]["bugs"]["errorClass"] == "invalid-json"
    assert payload["ok"] is False


def test_config_is_loaded_once_for_a_whole_snapshot(tmp_path, monkeypatch):
    """Re-reading the yaml per command would be a per-request file read for nothing."""
    proj = _project(tmp_path, str(_script(tmp_path, f"echo '{_envelope()}'")))
    calls = []
    import set_orch.project_status as ps
    real = ps.load_status_config
    monkeypatch.setattr(ps, "load_status_config", lambda p: (calls.append(p), real(p))[1])

    ps.gather(proj, ["bugs", "releases", "changes"])
    assert len(calls) == 1
