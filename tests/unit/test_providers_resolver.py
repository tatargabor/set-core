"""The resolver: precedence, provenance, and every refusal.

The refusals matter more than the successes here. Each one exists because the
alternative fails SILENTLY — a launch on the wrong provider looks exactly like a
launch on the right one, and the difference only shows up on a bill.
"""

import json

import pytest

from set_orch.providers import config as cfgmod
from set_orch.providers import resolver as res
from set_orch.providers.errors import (
    IncompleteCredential, MissingCredential, UnknownModel, UnknownProvider,
)

ANTHROPIC_MODELS = ["haiku", "sonnet", "opus", "sonnet-1m", "opus-1m",
                    "opus-4-6", "opus-4-7", "opus-4-6-1m", "opus-4-7-1m"]


def make(tmp_path, **over):
    data = {
        "default": {"provider": "anthropic", "model": "opus"},
        "providers": {
            "anthropic": {
                "models": ANTHROPIC_MODELS,
                "requires_credential": False,
                "default_model": "opus",
                "credential": None, "env": {}, "args": [],
            },
            "glm": {
                "models": ["glm-5.3", "glm-5.3-flash"],
                "requires_credential": True,
                "default_model": "glm-5.3-flash",
                "credential": {"token": "machine-token",
                               "base_url": "https://machine.invalid/api"},
                "env": {"CLAUDE_CODE_MAX_CONTEXT_TOKENS": "900000"},
                "args": ["--autocompact", "700k"],
            },
        },
        "projects": {},
    }
    for k, v in over.items():
        data[k] = v
    d = tmp_path / "set-core"
    d.mkdir(exist_ok=True)
    p = d / "providers.json"
    p.write_text(json.dumps(data))
    p.chmod(0o600)
    return cfgmod.load(p)


# ---------------------------------------------------------------- precedence

# AC-30 — the request outranks both stored levels
def test_the_request_outranks_the_project_and_the_machine_default(tmp_path):
    cfg = make(tmp_path, projects={"w": {"provider": "anthropic", "model": "sonnet"}})
    plan = res.resolve(project="w", provider="glm", model="glm-5.3", config=cfg)
    assert (plan.provider, plan.model) == ("glm", "glm-5.3")
    assert plan.provenance["provider"] == res.LEVEL_REQUEST
    assert plan.provenance["model"] == res.LEVEL_REQUEST


# AC-28 — a project overriding only the model inherits the machine credential,
#         and the credential/endpoint pair comes from ONE level
def test_a_project_overriding_only_the_model_keeps_the_machine_credential(tmp_path):
    cfg = make(tmp_path, projects={"w": {"provider": "glm", "model": "glm-5.3"}})
    plan = res.resolve(project="w", config=cfg)
    assert plan.model == "glm-5.3"
    assert plan.provenance["model"] == res.LEVEL_PROJECT
    assert plan.env["ANTHROPIC_AUTH_TOKEN"] == "machine-token"
    assert plan.env["ANTHROPIC_BASE_URL"] == "https://machine.invalid/api"
    assert plan.provenance["credential"] == res.LEVEL_DEFAULT
    assert plan.uses_default_credential() is True


# AC-11 — a project may spend against its own credential
# AC-32
def test_a_project_may_carry_its_own_credential_and_it_is_visible_as_such(tmp_path):
    cfg = make(tmp_path, projects={"w": {
        "provider": "glm",
        "credential": {"token": "project-token", "base_url": "https://project.invalid/api"},
    }})
    plan = res.resolve(project="w", model="glm-5.3", config=cfg)
    assert plan.env["ANTHROPIC_AUTH_TOKEN"] == "project-token"
    assert plan.env["ANTHROPIC_BASE_URL"] == "https://project.invalid/api"
    assert plan.provenance["credential"] == res.LEVEL_PROJECT
    # The screen needs this answerable WITHOUT the credential itself.
    assert plan.uses_default_credential() is False

    other = res.resolve(project="unlisted", provider="glm", model="glm-5.3", config=cfg)
    assert other.env["ANTHROPIC_AUTH_TOKEN"] == "machine-token"


# AC-29 — a credential is never carried to a provider it was not written for
def test_a_project_credential_is_not_carried_to_another_provider(tmp_path):
    cfg = make(tmp_path, projects={"w": {
        "provider": "glm",
        "credential": {"token": "project-token", "base_url": "https://project.invalid/api"},
    }})
    with pytest.raises(IncompleteCredential) as e:
        res.resolve(project="w", provider="anthropic", model="opus", config=cfg)
    assert "not carried to another provider" in str(e.value)


# ---------------------------------------------------------------- provenance

# AC-31 — the launch reports the level that decided each field
def test_describe_names_the_endpoint_and_every_level_but_never_the_token(tmp_path):
    cfg = make(tmp_path)
    line = res.resolve(provider="glm", model="glm-5.3-flash", config=cfg).describe()
    assert "glm-5.3-flash" in line
    assert "https://machine.invalid/api" in line
    assert res.LEVEL_REQUEST in line
    assert "machine-token" not in line


# ------------------------------------------------------------------ catalogue

# AC-53 / AC-54 — names and a usable flag, no credential, nothing omitted
def test_the_catalogue_carries_names_and_usability_and_no_credential(tmp_path):
    cfg = make(tmp_path)
    cat = res.catalogue(cfg)
    blob = json.dumps(cat)
    assert "machine-token" not in blob
    names = [p["name"] for p in cat["providers"]]
    assert names == ["anthropic", "glm"]
    assert all(p["usable"] for p in cat["providers"])


def test_an_unconfigured_provider_is_listed_as_unusable_rather_than_omitted(tmp_path):
    cfg = make(tmp_path)
    cfg.providers["glm"] = cfg.providers["glm"].__class__(
        name="glm", models=cfg.providers["glm"].models,
        requires_credential=True, default_model=None, credential=None, env={}, args=(),
    )
    cat = res.catalogue(cfg)
    glm = [p for p in cat["providers"] if p["name"] == "glm"][0]
    assert glm["usable"] is False
    assert glm["reason"]                      # a person must be able to see WHY


# -------------------------------------------------------------------- models

# AC-33 / AC-35 — a provider's own models are accepted, and nothing regressed
@pytest.mark.parametrize("name", ANTHROPIC_MODELS)
def test_every_model_name_valid_before_this_change_is_still_valid(tmp_path, name):
    cfg = make(tmp_path)
    assert res.resolve(provider="anthropic", model=name, config=cfg).model == name


# AC-34 — a model from another provider's catalogue is refused, naming both
def test_a_model_from_another_catalogue_is_refused_naming_the_catalogue(tmp_path):
    cfg = make(tmp_path)
    with pytest.raises(UnknownModel) as e:
        res.resolve(provider="anthropic", model="glm-5.3", config=cfg)
    assert "glm-5.3" in str(e.value) and "'anthropic'" in str(e.value)
    assert "haiku" in str(e.value)            # the catalogue that WAS searched


# AC-37 — the gateway prefix is caught before anything is created
def test_a_gateway_prefixed_name_is_refused_and_the_bare_form_is_named(tmp_path):
    cfg = make(tmp_path)
    with pytest.raises(UnknownModel) as e:
        res.resolve(provider="glm", model="zai/glm-5.3-flash", config=cfg)
    assert "gateway prefix" in str(e.value)
    assert "'glm-5.3-flash'" in str(e.value)
    assert "1214" in str(e.value)             # the measured response


# ------------------------------------------------------------------ refusals

# AC-36 — a missing credential stops the launch and says where to put one
def test_a_provider_requiring_a_credential_with_none_is_refused(tmp_path):
    cfg = make(tmp_path)
    cfg.providers["glm"] = cfg.providers["glm"].__class__(
        name="glm", models=("glm-5.3",), requires_credential=True,
        default_model=None, credential=None, env={}, args=(),
    )
    with pytest.raises(MissingCredential) as e:
        res.resolve(provider="glm", model="glm-5.3", config=cfg)
    assert "providers.glm.credential" in str(e.value)
    assert "does NOT continue on another provider" in str(e.value)


def test_an_undeclared_provider_is_refused_and_the_declared_ones_are_named(tmp_path):
    cfg = make(tmp_path)
    with pytest.raises(UnknownProvider) as e:
        res.resolve(provider="mistral", model="whatever", config=cfg)
    assert "'mistral'" in str(e.value) and "anthropic" in str(e.value)


# AC-38 — a refusal is NEVER a fallback
@pytest.mark.parametrize("kwargs", [
    {"provider": "mistral", "model": "x"},
    {"provider": "glm", "model": "opus"},
    {"provider": "glm", "model": "zai/glm-5.3"},
])
def test_no_refusal_ever_yields_a_plan_on_a_different_provider(tmp_path, kwargs):
    cfg = make(tmp_path)
    with pytest.raises((UnknownProvider, UnknownModel, MissingCredential)):
        res.resolve(config=cfg, **kwargs)


# ------------------------------------------------- foreign credential removal

# AC-40 / AC-41 — the removal is unconditional, the default provider included
@pytest.mark.parametrize("provider,model", [("glm", "glm-5.3"), ("anthropic", "opus")])
def test_every_plan_removes_credentials_belonging_to_another_provider(tmp_path, provider, model):
    cfg = make(tmp_path)
    plan = res.resolve(provider=provider, model=model, config=cfg)
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"):
        assert key in plan.unset


def test_the_default_provider_sets_no_endpoint_so_the_cli_login_is_used(tmp_path):
    cfg = make(tmp_path)
    plan = res.resolve(provider="anthropic", model="opus", config=cfg)
    assert "ANTHROPIC_BASE_URL" not in plan.env
    assert "ANTHROPIC_AUTH_TOKEN" not in plan.env


# AC-27 — a launch parameter is stated once, as data
# AC-5 / AC-10 / AC-27
def test_the_measured_launch_parameters_come_from_the_configuration(tmp_path):
    cfg = make(tmp_path)
    plan = res.resolve(provider="glm", model="glm-5.3", config=cfg)
    assert plan.env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] == "900000"
    assert plan.args == ("--autocompact", "700k")


def test_the_resolver_reads_nothing_from_the_ambient_environment(tmp_path, monkeypatch):
    """What a launch gets is decided by the configuration, not by the calling shell."""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://hijack.invalid")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "inherited")
    monkeypatch.setenv("GLM_MODEL", "glm-5.3")
    cfg = make(tmp_path)
    plan = res.resolve(provider="glm", model="glm-5.3-flash", config=cfg)
    assert plan.env["ANTHROPIC_BASE_URL"] == "https://machine.invalid/api"
    assert plan.env["ANTHROPIC_AUTH_TOKEN"] == "machine-token"


# ------------------------------------------- the Anthropic catalogue's source

def test_the_derived_regex_is_byte_identical_to_the_literal_it_replaced():
    """`MODEL_NAME_RE` is now built from a tuple. Nothing downstream may notice.

    The whole point of deriving it is that the model list becomes readable by the
    provider layer WITHOUT changing what the engine's own chain accepts. If this
    string ever differs, some caller's validation has quietly moved.
    """
    from set_orch.config import MODEL_NAME_RE
    assert MODEL_NAME_RE == (
        r"^(haiku|sonnet|opus|sonnet-1m|opus-1m"
        r"|opus-4-6|opus-4-7|opus-4-6-1m|opus-4-7-1m)$"
    )


def test_the_test_s_own_model_list_is_the_frameworks_not_a_second_copy():
    """A hand-copied list in a test is a second source that drifts silently."""
    from set_orch.config import ANTHROPIC_MODEL_NAMES
    assert list(ANTHROPIC_MODEL_NAMES) == ANTHROPIC_MODELS


# AC-35 — every name the framework accepted before is still accepted
def test_every_name_the_old_validator_accepted_still_validates(tmp_path):
    import re
    from set_orch.config import ANTHROPIC_MODEL_NAMES, MODEL_NAME_RE
    cfg = make(tmp_path)
    for name in ANTHROPIC_MODEL_NAMES:
        assert re.match(MODEL_NAME_RE, name), name
        assert res.resolve(provider="anthropic", model=name, config=cfg).model == name


def test_an_alternative_providers_name_still_fails_the_anthropic_validator(tmp_path):
    """The measurement that made this change necessary, held as a test.

    Deriving the regex must NOT have widened it — a pattern that now admits every
    provider's names would stop rejecting typos for all of them at once.
    """
    import re
    from set_orch.config import MODEL_NAME_RE
    for name in ("glm-5.3", "glm-5.3-flash"):
        assert re.match(MODEL_NAME_RE, name) is None


# A provider's own default is NOT the machine default, and must not claim to be.
def test_a_providers_own_default_model_is_reported_as_the_providers_level(tmp_path):
    """Provenance that names the wrong level is a false value.

    It is the same defect class the whole result type exists to prevent, showing
    up inside the mechanism meant to prevent it: the reader is told a level
    decided something it never named.
    """
    cfg = make(tmp_path)                       # machine default is anthropic/opus
    plan = res.resolve(provider="glm", config=cfg)
    assert plan.model == "glm-5.3-flash"
    assert plan.provenance["model"] == res.LEVEL_PROVIDER
    assert plan.provenance["model"] != res.LEVEL_DEFAULT


def test_the_machine_default_model_is_used_only_for_the_machine_default_provider(tmp_path):
    cfg = make(tmp_path)
    same = res.resolve(provider="anthropic", config=cfg)
    assert (same.model, same.provenance["model"]) == ("opus", res.LEVEL_DEFAULT)


def test_a_provider_with_no_default_of_its_own_refuses_rather_than_borrowing_one(tmp_path):
    """The refusal must explain WHY the machine default was not used.

    "unknown model 'opus'" would be true and useless: it names the symptom of a
    fallback the reader never asked for.
    """
    cfg = make(tmp_path)
    cfg.providers["glm"] = cfg.providers["glm"].__class__(
        name="glm", models=("glm-5.3",), requires_credential=True,
        default_model=None,
        credential=cfg.providers["glm"].credential, env={}, args=(),
    )
    with pytest.raises(UnknownModel) as e:
        res.resolve(provider="glm", config=cfg)
    assert "belongs to provider 'anthropic'" in str(e.value)
    assert "glm-5.3" in str(e.value)


# AC-26 — the CLI runner and the fleet's owner obtain the SAME plan
def test_the_command_line_runner_and_a_library_caller_resolve_identically(tmp_path):
    """One resolver, two carriers. Asserted through the CLI, not by inspection.

    `set-glm --print-env` is the command-line carrier; `resolve()` is the one the
    owner uses. If these ever differ, a measured value has grown a second home.
    """
    import json as _json
    import os as _os
    import pathlib as _pathlib
    import subprocess as _subprocess

    root = _pathlib.Path(__file__).resolve().parents[2]
    cfgdir = tmp_path / "set-core"
    cfgdir.mkdir(exist_ok=True)
    raw = {
        "default": {"provider": "glm", "model": "glm-5.3-flash"},
        "providers": {
            "glm": {
                "models": ["glm-5.3", "glm-5.3-flash"],
                "requires_credential": True,
                "default_model": "glm-5.3-flash",
                "credential": {"token": "shared-token", "base_url": "https://z.invalid/api"},
                "env": {"CLAUDE_CODE_MAX_CONTEXT_TOKENS": "900000"},
                "args": ["--autocompact", "700k"],
            },
        },
        "projects": {},
    }
    p = cfgdir / "providers.json"
    p.write_text(_json.dumps(raw))
    p.chmod(0o600)

    library = res.resolve(provider="glm", model="glm-5.3", config=cfgmod.load(p))

    out = _subprocess.run(
        [str(root / "bin" / "set-glm"), "--model", "glm-5.3", "--print-env"],
        capture_output=True, text=True,
        env=dict(_os.environ, SET_CONFIG_DIR=str(cfgdir)), cwd=str(root),
    ).stdout

    assert f"ANTHROPIC_BASE_URL={library.env['ANTHROPIC_BASE_URL']}" in out
    assert "CLAUDE_CODE_MAX_CONTEXT_TOKENS=900000" in out
    assert f"# args:  {' '.join(library.args)}" in out
    assert f"# unset: {', '.join(library.unset)}" in out
    assert library.model == "glm-5.3"
    assert "shared-token" not in out          # and still never the credential
