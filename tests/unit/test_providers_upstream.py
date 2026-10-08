"""upstream-model-watch — the check that says set-core (or this machine) is behind Anthropic.

Every test injects the fetcher and points the config and cache at tmp_path: no
test touches the network or the real machine files.
"""

import json
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

from set_orch.providers import upstream as up

ROOT = Path(__file__).resolve().parents[2]

# The shape of the live page, measured 2026-09-29 — the table rows that matter,
# the link slugs that must NOT be read, and another platform's id row.
PAGE = """\
If you're unsure, start with [Claude Opus 5.5](https://platform.claude.com/docs/en/models/opus-5-5/overview).
See [prompting](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices).

| Feature | Claude Fable 5.1 | Claude Opus 5.5 | Claude Sonnet 5.5 | Claude Haiku 4.5 |
| :-- | :-- | :-- | :-- | :-- |
| Claude API ID | `claude-fable-5-1` | `claude-opus-5-5` | `claude-sonnet-5-5` | `claude-haiku-4-5-20251001` |
| [Default effort](https://x/effort) | `high` | `medium` | `medium` | `low` |
| Claude API alias | `claude-fable-5-1` | `claude-opus-5-5` | `claude-sonnet-5-5` | `claude-haiku-4-5` |
| [Amazon Bedrock ID](https://platform.claude.com/docs/en/build-with-claude/claude-in-amazon-bedrock) | `anthropic.claude-fable-5-1` | `anthropic.claude-opus-9-9` | `anthropic.claude-sonnet-5-5` | `anthropic.claude-haiku-4-5` |
"""

ALL_SHIPPED = list(up.ANTHROPIC_MODEL_NAMES)


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """A machine config dir + cache dir under tmp_path; returns a writer."""
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    monkeypatch.setenv("SET_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    def write(models=ALL_SHIPPED, anthropic=True):
        providers = {}
        if anthropic:
            providers["anthropic"] = {"models": list(models), "requires_credential": False,
                                      "default_model": None, "credential": None}
        providers["glm"] = {"models": ["glm-5.3"], "requires_credential": True,
                            "default_model": "glm-5.3", "credential": None}
        p = cfg_dir / "providers.json"
        p.write_text(json.dumps({"version": 1, "default": {"provider": "glm", "model": "glm-5.3"},
                                 "providers": providers, "projects": {}}))
        p.chmod(0o600)
        return p
    return write


def fetch_page(text=PAGE):
    calls = []

    def f(url):
        calls.append(url)
        return text
    f.calls = calls
    return f


def failing(url):
    raise urllib.error.URLError("connection refused")


# ---------------------------------------------------------------- parsing

def test_ids_come_from_the_two_id_rows_only():            # AC-1
    ids = [i for i, _ in up.parse_overview(PAGE)]
    assert ids == ["claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5-20251001"]
    assert not any("prompting" in i or "bedrock" in i for i in ids)


def test_other_platform_rows_are_ignored():               # AC-2
    only_bedrock = "\n".join(l for l in PAGE.splitlines() if "Claude API" not in l)
    assert up.parse_overview(only_bedrock) == []
    assert "anthropic.claude-opus-9-9" not in json.dumps(up.parse_overview(PAGE))


def test_aliases_pair_with_their_column():
    assert dict(up.parse_overview(PAGE))["claude-haiku-4-5-20251001"] == "claude-haiku-4-5"


# ---------------------------------------------------------------- unknown, never current

def test_network_failure_is_unknown(machine):              # AC-3
    machine()
    r = up.check(fetch=failing)
    assert r.verdict == up.UNKNOWN
    assert "connection refused" in r.error


def test_page_without_id_row_is_unknown_not_current(machine):   # AC-4
    machine()
    r = up.check(fetch=fetch_page("# Models\n\nNothing tabular here.\n"))
    assert r.verdict == up.UNKNOWN
    assert "no 'Claude API ID' row" in r.error


# ---------------------------------------------------------------- coverage

def test_a_new_sonnet_is_behind_and_names_the_shorthand(machine):   # AC-5
    machine()
    r = up.check(fetch=fetch_page())
    assert r.verdict == up.BEHIND
    assert r.not_shipped == [{"id": "claude-sonnet-5-5", "family": "sonnet",
                              "shorthand_resolves_to": up.DEFAULT_MODEL_IDS["sonnet"]}]
    text = "\n".join(up.advice(r))
    assert "claude-sonnet-5-5" in text and up.DEFAULT_MODEL_IDS["sonnet"] in text


def test_pass_through_family_is_covered():                 # AC-6
    assert "fable" in up.ANTHROPIC_MODEL_NAMES and "fable" not in up.DEFAULT_MODEL_IDS
    assert up.not_shipped([("claude-fable-5-1", "claude-fable-5-1")]) == []


def test_dated_haiku_is_covered():                          # AC-7
    assert up.not_shipped([("claude-haiku-4-5-20251001", "claude-haiku-4-5")]) == []


def test_a_new_opus_is_not_hidden_by_the_opus_shorthand():
    # `opus` exists as a name, but it is TRANSLATED, so it covers only its own id.
    assert [x["id"] for x in up.not_shipped([("claude-opus-9", None)])] == ["claude-opus-9"]


def test_every_shipped_id_is_current(machine):
    machine()
    page = ("| Claude API ID | " + " | ".join(f"`{v.split('[')[0]}`" for v in up.DEFAULT_MODEL_IDS.values())
            + " |\n")
    r = up.check(fetch=fetch_page(page))
    assert r.verdict == up.CURRENT and r.not_shipped == [] and r.not_declared == []


# ---------------------------------------------------------------- machine catalogue (B-159)

def test_machine_file_older_than_shipped_names_is_behind(machine):   # AC-8
    path = machine(models=[m for m in ALL_SHIPPED if m not in ("opus-5-5", "opus-5-5-1m")])
    r = up.check(fetch=fetch_page("| Claude API ID | `claude-opus-5-5` |\n"))
    assert r.verdict == up.BEHIND
    assert r.not_declared == ["opus-5-5", "opus-5-5-1m"]
    assert r.machine_config == str(path)


def test_no_anthropic_provider_skips_the_machine_diff_and_says_so(machine):
    machine(anthropic=False)
    r = up.check(fetch=fetch_page("| Claude API ID | `claude-opus-5-5` |\n"))
    assert r.not_declared == []
    assert "no 'anthropic' provider declared" in r.machine_note


# ---------------------------------------------------------------- cache

def test_fresh_cache_is_reused_without_fetch(machine):     # AC-9
    machine()
    first = fetch_page()
    up.check(fetch=first, now=1_000_000)
    second = fetch_page()
    r = up.check(fetch=second, now=1_000_000 + 2 * 3600)
    assert len(first.calls) == 1 and second.calls == []
    assert r.fetched_at == 1_000_000


def test_stale_cache_is_refetched(machine):
    machine()
    up.check(fetch=fetch_page(), now=1_000_000)
    again = fetch_page()
    up.check(fetch=again, now=1_000_000 + 25 * 3600)
    assert len(again.calls) == 1


def test_failed_refresh_keeps_the_last_good_list(machine):  # AC-10
    machine()
    up.check(fetch=fetch_page(), now=1_000_000)
    before = up.cache_path().read_bytes()
    r = up.check(refresh=True, fetch=failing, now=1_000_000 + 3600)
    assert r.verdict == up.UNKNOWN
    assert up.cache_path().read_bytes() == before


# ---------------------------------------------------------------- advice only

def test_behind_changes_no_config_byte(machine):            # AC-11
    path = machine(models=["opus"])
    before = path.read_bytes()
    r = up.check(fetch=fetch_page())
    assert r.verdict == up.BEHIND
    assert path.read_bytes() == before


# ---------------------------------------------------------------- CLI

def _cli(tmp_path, *args):
    """Run the real CLI with a pre-seeded cache, so no network is needed."""
    return subprocess.run([sys.executable, str(ROOT / "bin" / "set-providers"), "upstream", *args],
                          capture_output=True, text=True)


def test_cli_exit_codes(machine, tmp_path):                 # AC-12
    import time
    machine()
    cache = up.cache_path()
    cache.parent.mkdir(parents=True, exist_ok=True)

    def seed(models):
        cache.write_text(json.dumps({"fetched_at": time.time(),
                                     "models": [{"id": m, "alias": None} for m in models]}))
    seed(["claude-sonnet-99"])
    r = _cli(tmp_path)
    assert r.returncode == 1, r.stderr
    assert "claude-sonnet-99" in r.stdout and "update set-core" in r.stdout

    seed([up.DEFAULT_MODEL_IDS["opus"]])
    r = _cli(tmp_path, "--json")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["verdict"] == "current"
