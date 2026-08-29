"""The provider configuration reader — the file, its permissions, its faults.

Every test here names the acceptance criterion it stands for, because the value
of these is that a later reader can tell WHICH stated behaviour broke, not merely
that something did.
"""

import json
import pathlib
import os
import stat

import pytest

from set_orch.providers import config as cfgmod
from set_orch.providers.errors import ConfigError


def write_config(tmp_path, data, mode=0o600):
    d = tmp_path / "set-core"
    d.mkdir(exist_ok=True)
    p = d / "providers.json"
    p.write_text(json.dumps(data))
    p.chmod(mode)
    return p


GOOD = {
    "default": {"provider": "anthropic", "model": "opus"},
    "providers": {
        "anthropic": {
            "models": ["haiku", "sonnet", "opus"],
            "requires_credential": False,
            "credential": None,
            "env": {},
            "args": [],
        },
        "glm": {
            "models": ["glm-5.3", "glm-5.3-flash"],
            "requires_credential": True,
            "credential": {"token": "t-secret", "base_url": "https://example.invalid/api"},
            "env": {"CLAUDE_CODE_MAX_CONTEXT_TOKENS": "900000"},
            "args": ["--autocompact", "700k"],
        },
    },
    "projects": {"widgets": {"model": "glm-5.3", "provider": "glm"}},
}


def test_config_dir_honours_the_override_the_rest_of_set_core_uses(tmp_path, monkeypatch):
    monkeypatch.setenv("SET_CONFIG_DIR", str(tmp_path / "elsewhere"))
    assert cfgmod.config_dir() == tmp_path / "elsewhere"


def test_a_good_file_loads_with_both_providers(tmp_path):
    p = write_config(tmp_path, GOOD)
    cfg = cfgmod.load(p)
    assert cfg.provider_names() == ["anthropic", "glm"]
    assert cfg.providers["glm"].env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] == "900000"
    assert cfg.providers["glm"].args == ("--autocompact", "700k")
    assert cfg.default_provider == "anthropic"


# AC-6 — a world-readable configuration is refused, not silently used
@pytest.mark.parametrize("mode", [0o640, 0o644, 0o604, 0o660])
def test_a_configuration_readable_by_anyone_else_is_refused(tmp_path, mode):
    p = write_config(tmp_path, GOOD, mode=mode)
    with pytest.raises(ConfigError) as e:
        cfgmod.load(p)
    assert str(p) in str(e.value)
    assert f"{mode:04o}" in str(e.value)
    # The message must be actionable, not merely correct.
    assert "chmod 600" in str(e.value)


def test_owner_only_is_accepted(tmp_path):
    p = write_config(tmp_path, GOOD, mode=0o600)
    assert cfgmod.load(p).provider_names()


# AC-13 — a missing file names itself and the command that creates it
def test_a_missing_file_names_the_path_and_the_migration_command(tmp_path):
    with pytest.raises(ConfigError) as e:
        cfgmod.load(tmp_path / "nope" / "providers.json")
    assert "providers.json" in str(e.value)
    assert "set-providers migrate" in str(e.value)


# AC-14 — malformed content is not treated as an empty configuration
def test_malformed_json_says_malformed_rather_than_yielding_nothing(tmp_path):
    d = tmp_path / "set-core"
    d.mkdir()
    p = d / "providers.json"
    p.write_text("{ not json")
    p.chmod(0o600)
    with pytest.raises(ConfigError) as e:
        cfgmod.load(p)
    assert "malformed" in str(e.value).lower()


# AC-9 — a declaration missing a required field is refused BY NAME
def test_a_declaration_without_a_credential_key_names_the_provider_and_the_field(tmp_path):
    data = json.loads(json.dumps(GOOD))
    del data["providers"]["glm"]["credential"]
    p = write_config(tmp_path, data)
    with pytest.raises(ConfigError) as e:
        cfgmod.load(p)
    assert "'glm'" in str(e.value) and "credential" in str(e.value)


def test_a_declaration_without_requires_credential_is_refused_by_name(tmp_path):
    """The flag is required precisely so its omission cannot default into fail-open."""
    data = json.loads(json.dumps(GOOD))
    del data["providers"]["glm"]["requires_credential"]
    p = write_config(tmp_path, data)
    with pytest.raises(ConfigError) as e:
        cfgmod.load(p)
    assert "'glm'" in str(e.value) and "requires_credential" in str(e.value)


def test_an_empty_model_list_is_refused(tmp_path):
    data = json.loads(json.dumps(GOOD))
    data["providers"]["glm"]["models"] = []
    p = write_config(tmp_path, data)
    with pytest.raises(ConfigError) as e:
        cfgmod.load(p)
    assert "models" in str(e.value)


# AC-29 (config half) — half a credential is refused where it is written
@pytest.mark.parametrize("drop", ["token", "base_url"])
def test_half_a_credential_is_refused_at_read_time(tmp_path, drop):
    data = json.loads(json.dumps(GOOD))
    del data["providers"]["glm"]["credential"][drop]
    p = write_config(tmp_path, data)
    with pytest.raises(ConfigError) as e:
        cfgmod.load(p)
    assert drop in str(e.value)
    assert "one unit" in str(e.value)


# AC-8 — adding a model to a catalogue is a DATA change and nothing else
def test_adding_a_model_to_the_catalogue_takes_effect_with_no_code_change(tmp_path):
    data = json.loads(json.dumps(GOOD))
    data["providers"]["glm"]["models"].append("glm-6-preview")
    p = write_config(tmp_path, data)
    assert "glm-6-preview" in cfgmod.load(p).providers["glm"].models


# A provider declared but not yet configured is a real, nameable state.
def test_a_provider_that_needs_a_credential_and_has_none_is_not_usable(tmp_path):
    data = json.loads(json.dumps(GOOD))
    data["providers"]["glm"]["credential"] = None
    p = write_config(tmp_path, data)
    cfg = cfgmod.load(p)
    assert cfg.providers["glm"].is_usable() is False
    assert cfg.providers["anthropic"].is_usable() is True


def test_no_credential_value_appears_in_any_error_message(tmp_path):
    """A diagnostic is the carrier that leaves the machine."""
    data = json.loads(json.dumps(GOOD))
    data["providers"]["glm"]["models"] = []          # provoke a failure
    p = write_config(tmp_path, data)
    with pytest.raises(ConfigError) as e:
        cfgmod.load(p)
    assert "t-secret" not in str(e.value)


# AC-7 — the deploy path never writes a provider configuration into a consumer tree
def test_no_template_or_manifest_deploys_a_provider_configuration():
    """The credential file is machine-level and inherited by being READ.

    A copy inside a project tree is removed by a `reset --hard` and republished
    by a careless `add`, which is the whole reason this file lives outside one.
    Asserted over every tree the deploy can reach, not over a remembered list.
    """
    import subprocess
    root = pathlib.Path(__file__).resolve().parents[2]
    hits = subprocess.run(
        ["grep", "-rl", "providers.json", "templates", "modules"],
        cwd=root, capture_output=True, text=True,
    ).stdout.split()
    assert hits == [], f"deployable trees mention the credential file: {hits}"


def test_the_providers_package_writes_nothing_at_all():
    """Reading a configuration must not be a write path in disguise.

    Migration is a separate, explicitly invoked act (`set-providers migrate`).
    A resolver that writes has a side effect nothing in a trace would show, and
    it fires in whichever process happens to read first.
    """
    pkg = pathlib.Path(__file__).resolve().parents[2] / "lib" / "set_orch" / "providers"
    for f in sorted(pkg.glob("*.py")):
        body = f.read_text()
        for forbidden in ("write_text(", "open(", "mkdir(", "chmod("):
            assert forbidden not in body, f"{f.name} contains {forbidden}"


# AC-15 — resolving leaves the configuration untouched
def test_resolving_does_not_create_or_modify_any_file(tmp_path):
    from set_orch.providers import resolver

    p = write_config(tmp_path, GOOD)
    before = {q: (q.stat().st_mtime_ns, q.stat().st_size) for q in p.parent.iterdir()}
    resolver.resolve(provider="glm", model="glm-5.3", config=cfgmod.load(p))
    after = {q: (q.stat().st_mtime_ns, q.stat().st_size) for q in p.parent.iterdir()}
    assert before == after
