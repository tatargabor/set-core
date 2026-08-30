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
    ConfigError, IncompleteCredential, MissingCredential, UnknownModel,
    UnknownProvider,
)

ANTHROPIC_MODELS = ["haiku", "sonnet", "opus", "sonnet-1m", "opus-1m",
                    "opus-4-6", "opus-4-7", "opus-4-6-1m", "opus-4-7-1m",
                    "fable"]


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
        r"|opus-4-6|opus-4-7|opus-4-6-1m|opus-4-7-1m|fable)$"
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


# --------------------------------------------------------------------------- #
# B-114 — the resolved MODEL must reach the child, not only the record
# --------------------------------------------------------------------------- #

def _bare_plan(**over):
    from set_orch.providers.resolver import LaunchPlan
    base = dict(provider="glm", model="glm-5.3-flash",
                env={"ANTHROPIC_BASE_URL": "https://gw.invalid"},
                unset=("ANTHROPIC_API_KEY",),
                args=("--autocompact", "700k"),
                provenance={})
    base.update(over)
    return LaunchPlan(**base)


def test_launch_args_delivers_the_resolved_model():
    """The model is a resolved VALUE and every caller must deliver it.

    Measured 2026-08-29 on a live agent: the owner reported `glm / glm-5.3-flash`
    while `/proc/<pid>/cmdline` read
    `claude --dangerously-skip-permissions --autocompact 700k` — no `--model` at
    all, so the agent ran the CLI's DEFAULT model against the provider's
    endpoint. The record, the API answer and the tile were all correct and the
    effect was missing, which is why a full green suite could not see it: every
    assertion checked what was RECORDED.
    """
    plan = _bare_plan()
    add = plan.launch_args()
    assert "--model" in add
    assert add[add.index("--model") + 1] == "glm-5.3-flash"
    assert "--autocompact" in add          # the declared args still come through


def test_the_caller_s_own_model_wins_and_is_not_duplicated():
    """`set-glm --model X` must keep meaning what it says."""
    plan = _bare_plan()
    add = plan.launch_args(["--model", "glm-4.6"])
    assert "--model" not in add, "the caller already chose; adding again would duplicate it"


def test_a_declared_flag_the_caller_passed_is_not_added_twice():
    plan = _bare_plan()
    add = plan.launch_args(["--autocompact", "200k"])
    assert "--autocompact" not in add
    assert "--model" in add, "skipping the declared block must not also drop the model"


def test_a_provider_declaring_no_args_still_delivers_its_model():
    """The old owner-side guard was `if plan.args:` — which skipped everything
    for a provider that declares no args, model included."""
    plan = _bare_plan(args=())
    assert plan.launch_args() == ("--model", "glm-5.3-flash")


def test_the_model_is_translated_to_a_cli_id_on_the_way_out():
    """Delivering a WRONG model would be worse than delivering none.

    The catalogue holds set-core's short names, which are exactly `_MODEL_MAP`'s
    keys; the CLI wants the full id. Caught while auditing what else besides the
    model might not be delivered — the first version of `launch_args` passed the
    catalogue name straight through, which would have sent `--model opus-1m`.
    """
    from set_orch.subprocess_utils import _MODEL_MAP

    assert _bare_plan(provider="anthropic", model="opus-1m").launch_args(
    )[-1] == "claude-opus-4-6[1m]"
    assert _bare_plan(provider="anthropic", model="opus").launch_args(
    )[-1] == "claude-opus-4-6"

    # An unmapped name passes through — for anthropic that means a name the CLI
    # resolves natively (`fable`, measured 2026-08-29: no unrecognized_model and
    # a attempted call on an unreachable endpoint, while `sonnet-1m` was refused
    # under its own name), and for a real-id catalogue no second table is needed.
    assert _bare_plan(provider="anthropic", model="fable").launch_args(
    )[-1] == "fable"
    assert _bare_plan(model="glm-5.3-flash").launch_args()[-1] == "glm-5.3-flash"


def test_the_translation_does_not_run_for_a_provider_the_map_was_not_written_for():
    """B-118 — the short-name map is an ANTHROPIC-catalogue artifact.

    A different provider whose catalogue legitimately contains a map key
    (`sonnet` as a real tier name) must receive that name untouched: translating
    it would send `claude-sonnet-4-6` at that provider's endpoint — a wrong
    value delivered silently, which the method's own docstring calls worse than
    none. `resolve()`'s catalogue check makes this unreachable for a plan it
    built (a glm catalogue never lists `sonnet`); the gate exists so the
    delivery layer cannot turn a coherent declaration into a cross-vendor pair.
    """
    assert _bare_plan(provider="glm", model="sonnet").launch_args(
    )[-1] == "sonnet"


def test_the_catalogue_and_the_translation_map_are_coherent():
    """B-118's anchor, HERMETIC — the fixture, never the machine's live config.

    The previous version of this anchor called `config.load()`: on a machine
    whose config had no anthropic provider it silently asserted nothing, and on
    THIS machine it went red the day the operator added `fable` to the live
    catalogue — real signal, but measured through the wrong instrument. The
    invariant is: every name in the FRAMEWORK's anthropic catalogue either has
    a CLI id in `_MODEL_MAP` or is resolved natively by the CLI. `fable` is the
    second kind, by measurement; anything else appearing without a mapping is
    what this assertion exists to say so about.
    """
    from set_orch.subprocess_utils import _MODEL_MAP

    cli_native = {"fable"}
    unmapped = [m for m in ANTHROPIC_MODELS
                if m not in _MODEL_MAP and m not in cli_native]
    assert not unmapped, f"catalogue names with no CLI id: {unmapped}"


# --------------------------------------------------------------------------- #
# B-116 — an alias variable the provider does NOT declare is unset, not inherited
# --------------------------------------------------------------------------- #

def test_alias_keys_a_provider_does_not_declare_are_unset_not_inherited(tmp_path):
    """A provider that declares no aliases must STRIP all four alias variables.

    Both start paths build the child's environment from the ambient one, so an
    `ANTHROPIC_DEFAULT_OPUS_MODEL` exported by an unrelated session would
    otherwise ride into a launch on a provider that never declared it, and a
    subagent would send an Anthropic id at this provider's endpoint — B-115's
    symptom through a path B-115's fix does not close.
    """
    cfg = make(tmp_path)  # fixture glm declares no model_aliases
    plan = res.resolve(provider="glm", model="glm-5.3", config=cfg)
    for key in res.MODEL_ALIASES.values():
        assert key in plan.unset


def test_an_emitted_alias_key_is_delivered_and_not_also_unset(tmp_path):
    """The other direction of the same rule: an emitted alias is env, not unset.

    If an emitted key were also unset, a caller that applies `unset` AFTER
    `env` — or set-glm's survival guard, which compares the two — would strip
    the alias the provider just declared.
    """
    from dataclasses import replace

    base = make(tmp_path)
    with_aliases = replace(base.providers["glm"],
                           model_aliases={"sonnet": "glm-5.3-flash"})
    cfg = cfgmod.ProvidersConfig(
        providers={"anthropic": base.providers["anthropic"], "glm": with_aliases},
        default_provider=base.default_provider, default_model=base.default_model,
        projects={}, source=base.source,
    )
    plan = res.resolve(provider="glm", model="glm-5.3-flash", config=cfg)
    assert plan.env["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "glm-5.3-flash"
    assert "ANTHROPIC_DEFAULT_SONNET_MODEL" not in plan.unset
    # the three NOT declared are still stripped
    for key in ("ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL",
                "ANTHROPIC_DEFAULT_FABLE_MODEL"):
        assert key in plan.unset


# ------------------------------------------------------------- the fresh install

def test_a_fresh_install_is_told_how_to_create_not_only_to_migrate(tmp_path, monkeypatch):
    """Measured 2026-08-30 on a machine that never had glm.env: the neither-exists
    refusal sent the operator to `set-providers migrate`, which answered "nothing to
    migrate" — a loop with no way in. The refusal must name the create path and
    where the JSON shape is documented."""
    d = tmp_path / "set-core"
    d.mkdir()
    monkeypatch.setenv("SET_CONFIG_DIR", str(d))
    with pytest.raises(ConfigError) as e:
        cfgmod.load_or_legacy()
    msg = str(e.value)
    assert "no provider configuration" in msg
    assert str(d / "providers.json") in msg   # both candidates named
    assert str(d / "glm.env") in msg
    assert "Provider Configuration" in msg    # where the shape is documented
    # migrate stays offered — but only for machines that actually had the old file
    assert "set-providers migrate" in msg
