"""The migration and the deprecation window.

The behaviours worth holding here are the refusals and the silences: a migration
that overwrites, that deletes its source, that widens permissions, or that prints
a secret is one somebody cannot check afterwards.
"""

import json
import pathlib
import stat

import pytest

from set_orch.providers import config as cfgmod
from set_orch.providers import legacy, migrate as mig
from set_orch.providers.errors import ConfigError

GLM_ENV = 'GLM_TOKEN="t-secret-value"\nGLM_MODEL=glm-5.3-flash\nGLM_BASE_URL=https://z.invalid/api\n'


@pytest.fixture
def home(tmp_path, monkeypatch):
    d = tmp_path / "set-core"
    d.mkdir()
    monkeypatch.setenv("SET_CONFIG_DIR", str(d))
    return d


def write_legacy(home, text=GLM_ENV, mode=0o600):
    p = home / "glm.env"
    p.write_text(text)
    p.chmod(mode)
    return p


# ------------------------------------------------------------------ migration

# AC-16 — the command performs the conversion
def test_migrate_writes_a_configuration_carrying_the_old_values(home):
    write_legacy(home)
    dst, _ = mig.migrate()
    data = json.loads(dst.read_text())
    glm = data["providers"]["glm"]
    assert glm["credential"]["token"] == "t-secret-value"
    assert glm["credential"]["base_url"] == "https://z.invalid/api"
    assert glm["models"] == ["glm-5.3-flash"]
    assert data["default"] == {"provider": "glm", "model": "glm-5.3-flash"}


def test_the_migrated_file_loads_and_resolves(home):
    from set_orch.providers import resolver
    write_legacy(home)
    mig.migrate()
    cfg, notice = cfgmod.load_or_legacy()
    assert notice is None                      # a migrated setup goes quiet
    plan = resolver.resolve(config=cfg)
    assert plan.env["ANTHROPIC_AUTH_TOKEN"] == "t-secret-value"


def test_the_migration_also_writes_the_default_provider_so_switching_back_is_possible(home):
    write_legacy(home)
    dst, _ = mig.migrate()
    data = json.loads(dst.read_text())
    assert "anthropic" in data["providers"]
    assert data["providers"]["anthropic"]["requires_credential"] is False
    from set_orch.config import ANTHROPIC_MODEL_NAMES
    assert data["providers"]["anthropic"]["models"] == list(ANTHROPIC_MODEL_NAMES)


# AC-24 — the written configuration is owner-only
def test_the_written_configuration_is_owner_only(home):
    write_legacy(home)
    dst, _ = mig.migrate()
    assert stat.S_IMODE(dst.stat().st_mode) == 0o600


def test_an_existing_world_readable_target_is_narrowed_not_left_alone(home):
    write_legacy(home)
    (home / "providers.json").write_text("{}")
    (home / "providers.json").chmod(0o644)
    dst, _ = mig.migrate(overwrite=True)
    assert stat.S_IMODE(dst.stat().st_mode) == 0o600


# AC-25 — the source survives
def test_the_source_file_still_exists_afterwards(home):
    src = write_legacy(home)
    mig.migrate()
    assert src.exists()


# AC-17 — an existing configuration is not overwritten silently
def test_an_existing_configuration_is_not_replaced_without_being_told(home):
    write_legacy(home)
    target = home / "providers.json"
    target.write_text('{"keep": "me"}')
    target.chmod(0o600)
    with pytest.raises(ConfigError) as e:
        mig.migrate()
    assert "already exists" in str(e.value)
    assert "--overwrite" in str(e.value)
    assert json.loads(target.read_text()) == {"keep": "me"}
    # It must still say WHAT it would have done, or the refusal is unhelpful.
    assert "GLM_MODEL" in str(e.value)


def test_overwrite_replaces_it_when_asked(home):
    write_legacy(home)
    target = home / "providers.json"
    target.write_text('{"keep": "me"}')
    target.chmod(0o600)
    mig.migrate(overwrite=True)
    assert "providers" in json.loads(target.read_text())


# AC-23 — the report names fields, never secrets
def test_the_report_names_every_field_and_no_secret_value(home):
    write_legacy(home)
    _, report = mig.migrate()
    blob = "\n".join(report)
    assert "GLM_TOKEN" in blob and "GLM_MODEL" in blob and "GLM_BASE_URL" in blob
    assert "t-secret-value" not in blob
    assert "withheld" in blob


def test_a_refusal_message_carries_no_secret_either(home):
    write_legacy(home)
    (home / "providers.json").write_text("{}")
    (home / "providers.json").chmod(0o600)
    with pytest.raises(ConfigError) as e:
        mig.migrate()
    assert "t-secret-value" not in str(e.value)


def test_migrating_with_no_source_says_so(home):
    with pytest.raises(ConfigError) as e:
        mig.migrate()
    assert "nothing to migrate" in str(e.value)


@pytest.mark.parametrize("missing", ["GLM_TOKEN", "GLM_MODEL"])
def test_an_incomplete_source_is_refused_naming_the_field(home, missing):
    text = "\n".join(l for l in GLM_ENV.splitlines() if not l.startswith(missing))
    write_legacy(home, text + "\n")
    with pytest.raises(ConfigError) as e:
        mig.migrate()
    assert missing in str(e.value)


# ---------------------------------------------------------- the legacy reader

def test_only_glm_prefixed_keys_are_read_from_the_old_file(home):
    """Sourcing the whole file would import the key that redirects the call."""
    write_legacy(home, GLM_ENV + 'ANTHROPIC_API_KEY=sk-ant-should-never-be-read\n')
    values = legacy.read_legacy(home / "glm.env")
    assert set(values) == {"GLM_TOKEN", "GLM_MODEL", "GLM_BASE_URL"}
    assert not any("sk-ant" in v for v in values.values())


# ------------------------------------------------------ the deprecation window

# AC-18 — the old file still works and says it is going away
def test_the_old_file_still_resolves_and_warns_during_the_window(home, monkeypatch):
    monkeypatch.setattr(legacy, "WINDOW_OPEN", True)
    write_legacy(home)
    cfg, notice = cfgmod.load_or_legacy()
    assert cfg.providers["glm"].credential.token == "t-secret-value"
    assert notice and "glm.env" in notice and "set-providers migrate" in notice


# AC-19 — a migrated setup stops warning
def test_the_new_file_wins_and_silences_the_notice(home):
    write_legacy(home)
    mig.migrate()
    _, notice = cfgmod.load_or_legacy()
    assert notice is None


# AC-20 — after the window, the failure names the command and does NOT say "none"
def test_after_the_window_the_failure_names_the_command_not_an_absence(home, monkeypatch):
    monkeypatch.setattr(legacy, "WINDOW_OPEN", False)
    write_legacy(home)
    with pytest.raises(ConfigError) as e:
        cfgmod.load_or_legacy()
    msg = str(e.value)
    assert "set-providers migrate" in msg
    assert "no longer read" in msg
    # The sentence an operator must NOT be given: they DO have a configuration.
    assert "your provider is configured" in msg.lower()


def test_with_neither_file_the_error_names_both_paths(home):
    with pytest.raises(ConfigError) as e:
        cfgmod.load_or_legacy()
    assert "providers.json" in str(e.value) and "glm.env" in str(e.value)


def test_a_world_readable_legacy_file_is_refused_too(home):
    write_legacy(home, mode=0o644)
    with pytest.raises(ConfigError) as e:
        cfgmod.load_or_legacy()
    assert "owner-only" in str(e.value)


def test_closing_the_window_is_one_edit():
    """The switch must be a single named flag, not a condition spread around."""
    src = pathlib.Path(legacy.__file__).read_text()
    assert src.count("WINDOW_OPEN = ") == 1
    cfg_src = pathlib.Path(cfgmod.__file__).read_text()
    assert cfg_src.count("legacy.WINDOW_OPEN") == 1


def test_the_file_is_CREATED_owner_only_not_merely_narrowed_afterwards():
    """A structural test, and it says so — the behaviour it guards is unobservable.

    Measured by mutation 2026-08-29: removing the owner-only mode from the
    `os.open` call breaks NO test, because the `chmod` immediately after repairs
    it. Removing the `chmod` DOES break one. So the suite's behavioural
    assertions rest entirely on the chmod, and the create mode looks redundant.

    It is not. Between `open` and `chmod` the file exists, and if it is created
    0644 it is world-readable for that instant — with a credential in it. A test
    cannot see an interval that short without racing, so the guarantee is held
    structurally instead of pretended into a behavioural one.

    This is why the mutation result is recorded rather than resolved by deleting
    a "redundant" line: two mechanisms covering one effect hide each other from a
    mutation, and the one that survives the mutation is not always the one that
    matters.
    """
    src = pathlib.Path(mig.__file__).read_text()
    assert "os.open(" in src
    open_call = src.split("os.open(", 1)[1].split("\n", 1)[0]
    assert "stat.S_IRUSR | stat.S_IWUSR" in open_call, (
        "the configuration must be CREATED owner-only; a later chmod leaves a "
        "window in which a credential file is world-readable"
    )
