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
    StatusSnapshot,
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


# ── discovery: the repo-root manifest ─────────────────────────────────────
#
# A project announces its own entry point so set-core does not have to be configured
# once per project. `command` is a list, and nothing assumes an interpreter — the next
# project to publish a contract may be Python, Go, or a compiled binary.

def _manifest(proj: Path, **over):
    from set_orch.project_status import MANIFEST_FILENAME
    payload = {"contractVersion": 1, "command": ["echo", "hi"], "cwd": "."}
    payload.update(over)
    proj.mkdir(parents=True, exist_ok=True)
    (proj / MANIFEST_FILENAME).write_text(json.dumps(payload))
    return proj


def test_a_manifest_is_discovered_without_any_configuration(tmp_path):
    from set_orch.project_status import resolve_status_config
    script = _script(tmp_path, f"echo '{_envelope()}'")
    proj = _manifest(tmp_path / "p", command=[str(script)])

    cfg = resolve_status_config(proj)
    assert cfg is not None and cfg.source == "manifest"
    assert query(proj, "bugs", config=cfg).data == {"total": 67}


def test_manifest_command_is_a_list_so_a_path_with_a_space_survives(tmp_path):
    """The reason it is a list: splitting a string is where this silently breaks."""
    from set_orch.project_status import resolve_status_config
    spaced = tmp_path / "my tools"
    spaced.mkdir()
    script = _script(spaced, f"echo '{_envelope()}'", name="api.sh")
    proj = _manifest(tmp_path / "p", command=[str(script)])

    result = query(proj, "bugs", config=resolve_status_config(proj))
    assert result.ok, result.error


def test_an_operator_override_beats_the_manifest(tmp_path):
    """Whoever is running set-core must be able to redirect it without editing a repo."""
    from set_orch.project_status import resolve_status_config
    good = _script(tmp_path, f"echo '{_envelope()}'", name="good.sh")
    proj = _project(tmp_path, str(good))
    _manifest(proj, command=[str(tmp_path / "never-run")])

    cfg = resolve_status_config(proj)
    assert cfg.source == "config"
    assert query(proj, "bugs", config=cfg).ok


def test_a_manifest_declaring_an_unsupported_version_is_not_even_called(tmp_path):
    from set_orch.project_status import resolve_status_config
    marker = tmp_path / "was-called"
    script = _script(tmp_path, f"touch '{marker}'; echo '{_envelope()}'")
    proj = _manifest(tmp_path / "p", contractVersion=99, command=[str(script)])

    assert resolve_status_config(proj) is None
    assert query(proj, "bugs").error_class == "not-configured"
    assert not marker.exists(), "a version we cannot read must not be executed"


def test_a_corrupt_manifest_is_ignored_rather_than_fatal(tmp_path):
    from set_orch.project_status import MANIFEST_FILENAME, resolve_status_config
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / MANIFEST_FILENAME).write_text("{ not json")
    assert resolve_status_config(proj) is None


def test_manifest_cwd_is_resolved_relative_to_the_project(tmp_path):
    from set_orch.project_status import resolve_status_config
    proj = tmp_path / "p"
    (proj / "sub").mkdir(parents=True)
    script = _script(tmp_path, 'printf \'{"contractVersion":1,"ok":true,"data":"%s"}\' "$PWD"')
    _manifest(proj, command=[str(script)], cwd="sub")

    result = query(proj, "where", config=resolve_status_config(proj))
    assert result.data == str((proj / "sub").resolve())


def test_the_not_configured_message_names_both_places_to_look(tmp_path):
    proj = tmp_path / "bare"
    proj.mkdir()
    err = query(proj, "bugs").error
    assert "config.yaml" in err and ".set-endpoint.json" in err


# ─── deprecated fields: the project's call, never the framework's ─────────────

def test_the_envelope_carries_which_fields_the_project_no_longer_stands_behind():
    """A replaced field usually keeps being emitted, because removing it breaks someone.

    A renderer that shows everything then puts the stale value next to its replacement,
    contradicting it — found on a live screen. The project is the only side that knows
    which of its fields those are, so it says so and set-core reads it.
    """
    raw = json.dumps({
        "contractVersion": 1, "ok": True,
        "deprecated": ["oldCount"],
        "data": {"oldCount": 1, "newCount": 2},
    })

    result = parse_envelope("releases", raw)

    assert result.deprecated == ("oldCount",)
    assert result.data == {"oldCount": 1, "newCount": 2}, \
        "the value is still delivered — hiding it is a rendering decision, not a read one"


def test_no_declaration_means_no_deprecated_fields_not_a_guess():
    result = parse_envelope("releases", json.dumps({
        "contractVersion": 1, "ok": True, "data": {"a": 1},
    }))

    assert result.deprecated == ()


def test_a_malformed_deprecation_list_is_ignored_rather_than_crashing_the_read():
    """A status panel must not go dark over a badly typed advisory field."""
    result = parse_envelope("releases", json.dumps({
        "contractVersion": 1, "ok": True, "deprecated": "oldCount", "data": {"a": 1},
    }))

    assert result.deprecated == ()
    assert result.ok is True


def test_duplicates_and_blanks_are_dropped():
    result = parse_envelope("releases", json.dumps({
        "contractVersion": 1, "ok": True,
        "deprecated": ["a", "a", "  ", "b"], "data": {},
    }))

    assert result.deprecated == ("a", "b")


def test_the_snapshot_carries_the_deprecations_to_the_surface():
    snapshot = StatusSnapshot()
    snapshot.results["releases"] = parse_envelope("releases", json.dumps({
        "contractVersion": 1, "ok": True, "deprecated": ["x"], "data": {"x": 1},
    }))

    assert snapshot.to_dict()["commands"]["releases"]["deprecated"] == ["x"]


# ── which answer opens the surface ────────────────────────────────────────
#
# Without a declared preference the surface opens whatever the project listed first,
# which is an ordering decision nobody made. Only the project knows which of its answers
# is "where do we stand"; set-core must never infer that from a command's name.
#
# Every way of getting it wrong resolves to None rather than to an error: the cost of
# ignoring a preference is one extra click, and the cost of honouring a bad one is a
# surface that opens on something it cannot show — or worse, on a mutation.

def test_a_declared_primary_is_carried_from_the_manifest(tmp_path):
    from set_orch.project_status import load_manifest
    proj = _manifest(tmp_path / "p", commands=["bugs", "readiness"], primary="readiness")

    assert load_manifest(proj).primary == "readiness"


def test_a_primary_naming_an_undeclared_command_is_ignored(tmp_path):
    """Including a stale one left behind after the command was renamed."""
    from set_orch.project_status import load_manifest
    proj = _manifest(tmp_path / "p", commands=["bugs"], primary="renamed-away")

    assert load_manifest(proj).primary is None


def test_a_primary_naming_a_WRITE_command_is_refused(tmp_path):
    """Opening the page would land the reader on a mutation nobody asked for."""
    from set_orch.project_status import load_manifest
    proj = _manifest(
        tmp_path / "p", commands=["bugs"], writeCommands=["ack"], primary="ack",
    )

    assert load_manifest(proj).primary is None


def test_a_primary_that_is_not_a_command_name_never_reaches_the_config(tmp_path):
    from set_orch.project_status import load_manifest
    proj = _manifest(tmp_path / "p", commands=["bugs"], primary="--eval")

    assert load_manifest(proj).primary is None


def test_no_primary_is_None_not_the_first_command(tmp_path):
    """Absence must stay absence: the surface decides the fallback, not the loader."""
    from set_orch.project_status import load_manifest
    proj = _manifest(tmp_path / "p", commands=["bugs", "releases"])

    assert load_manifest(proj).primary is None


def test_the_operator_config_can_declare_a_primary_too(tmp_path):
    proj = _project(
        tmp_path, "node api.mjs", commands=["bugs", "readiness"], primary="readiness",
    )

    assert load_status_config(proj).primary == "readiness"


# ── answers too expensive to ask on a page load ──────────────────────────
#
# "Is the live system up" is exactly what a status screen exists for, and on a real
# project probing it took minutes. The alternative to marking it is the project dropping
# the command entirely, which trades a slow answer for NO answer — the wrong direction.

def test_a_declared_on_demand_command_is_kept(tmp_path):
    from set_orch.project_status import load_manifest
    proj = _manifest(
        tmp_path / "p", commands=["bugs", "environments"], onDemand=["environments"],
    )

    assert load_manifest(proj).on_demand == ("environments",)


def test_an_on_demand_name_that_is_not_declared_is_dropped(tmp_path):
    """Honouring it would silently stop asking a question the project believes it
    publishes — a gap indistinguishable from a project with nothing to say."""
    from set_orch.project_status import load_manifest
    proj = _manifest(tmp_path / "p", commands=["bugs"], onDemand=["typo"])

    assert load_manifest(proj).on_demand == ()


def test_on_demand_is_empty_by_default_so_nothing_stops_being_asked(tmp_path):
    from set_orch.project_status import load_manifest
    proj = _manifest(tmp_path / "p", commands=["bugs", "environments"])

    assert load_manifest(proj).on_demand == ()


def test_the_operator_config_can_mark_a_command_on_demand_too(tmp_path):
    proj = _project(
        tmp_path, "node api.mjs", commands=["bugs", "probe"], on_demand=["probe"],
    )

    assert load_status_config(proj).on_demand == ("probe",)
