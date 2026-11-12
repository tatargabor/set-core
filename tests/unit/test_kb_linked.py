"""Linked projects (change kb-linked-projects): a project's kb.json names other
registered projects, and a search also runs in each of THEIR own indexes with
their own configuration and the link's scope. One level only; a link that
cannot be searched is shown, never skipped silently; `get --project` reaches
only a linked name."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest_kb import make_repo, write

BIN = Path(__file__).resolve().parents[2] / "bin" / "set-kb"
BODY = "\n\n" + "word " * 30 + "\n"
CONFIG = "set/knowledge/kb.json"


def run(args, cwd, registry: Path):
    env = {**os.environ, "SET_CORE_REGISTRY": str(registry)}
    return subprocess.run([sys.executable, str(BIN), *args], cwd=str(cwd), env=env, capture_output=True, text=True, timeout=120)


def page(r) -> dict:
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture
def world(tmp_path):
    """An app project linked to a corpus project; the corpus carries two client
    scopes and links back to a third project that must NOT be followed."""
    app = make_repo(tmp_path, "app")
    write(app / "docs" / "own.md", "# Own page\n\nappword sharedword" + BODY)

    corpus = make_repo(tmp_path, "corpus")
    write(corpus / "wiki" / "alfa" / "limits.md", "# Rate limit\n\nsharedword ratelimitword for alfa" + BODY)
    write(corpus / "wiki" / "beta" / "limits.md", "# Rate limit beta\n\nsharedword ratelimitword for beta" + BODY)
    write(corpus / CONFIG, json.dumps({
        "scopes": [{"name": "client", "pattern": "wiki/{scope}/**"}],
        "linked": [{"project": "third"}],
    }))

    third = make_repo(tmp_path, "third")
    write(third / "x.md", "# Third\n\nsharedword ratelimitword thirdonly" + BODY)

    registry = tmp_path / "projects.json"
    registry.write_text(json.dumps({"projects": {
        "app": {"path": str(app)}, "corpus": {"path": str(corpus)}, "third": {"path": str(third)},
    }}))
    return app, corpus, registry


def link(app: Path, *entries: dict) -> None:
    write(app / CONFIG, json.dumps({"linked": list(entries)}))


def test_a_linked_hit_carries_its_project_and_its_own_path(world):
    app, corpus, reg = world
    link(app, {"project": "corpus", "about": "the shared wiki"})
    d = page(run(["search", "ratelimitword", "--json"], app, reg))
    assert d["hits"] == [], "the app itself has no such page"
    [ln] = d["linked"]
    assert ln["project"] == "corpus" and ln["searched"] is True and ln["about"] == "the shared wiki"
    paths = {h["path"] for h in ln["hits"]}
    assert paths == {"wiki/alfa/limits.md", "wiki/beta/limits.md"}, "relative to the CORPUS root"
    assert all(h["project"] == "corpus" for h in ln["hits"])


def test_the_link_scope_is_applied_in_the_linked_index(world):
    app, corpus, reg = world
    link(app, {"project": "corpus", "scope": "client=alfa"})
    [ln] = page(run(["search", "ratelimitword", "--json"], app, reg))["linked"]
    assert {h["path"] for h in ln["hits"]} == {"wiki/alfa/limits.md"}
    assert ln["scope"] == "client=alfa"


def test_links_are_followed_one_level_only(world):
    app, corpus, reg = world
    link(app, {"project": "corpus"})
    d = page(run(["search", "thirdonly", "--json"], app, reg))
    assert [ln["project"] for ln in d["linked"]] == ["corpus"]
    assert d["linked"][0]["hits"] == [], "the corpus's own link to `third` is not searched"


def test_an_unsearchable_link_is_shown_not_skipped(world):
    app, corpus, reg = world
    link(app, {"project": "corpus"}, {"project": "gone"})
    r = run(["search", "ratelimitword", "--json"], app, reg)
    d = page(r)
    by = {ln["project"]: ln for ln in d["linked"]}
    assert by["corpus"]["searched"] is True and by["corpus"]["hits"], "one broken link does not cost the others"
    assert by["gone"]["searched"] is False and "not in the registry" in by["gone"]["error"]
    text = run(["search", "ratelimitword"], app, reg)
    assert text.returncode == 0 and "NOT SEARCHED" in text.stdout and "gone" in text.stdout


def test_no_linked_searches_only_this_project(world):
    app, corpus, reg = world
    link(app, {"project": "corpus"})
    d = page(run(["search", "sharedword", "--json", "--no-linked"], app, reg))
    assert d["linked"] == [] and [h["path"] for h in d["hits"]] == ["docs/own.md"]


def test_the_text_page_names_the_linked_project_and_how_to_open_a_hit(world):
    app, corpus, reg = world
    link(app, {"project": "corpus"})
    r = run(["search", "ratelimitword"], app, reg)
    assert r.returncode == 0, r.stderr
    assert "linked: corpus" in r.stdout and "wiki/alfa/limits.md" in r.stdout
    assert "set-kb get <path> --project corpus" in r.stdout


def test_get_project_fetches_from_a_linked_project(world):
    app, corpus, reg = world
    link(app, {"project": "corpus"})
    page(run(["search", "ratelimitword", "--json"], app, reg))  # builds the linked index
    r = run(["get", "wiki/alfa/limits.md", "--project", "corpus", "--json"], app, reg)
    d = page(r)
    assert "ratelimitword for alfa" in json.dumps(d)


def test_get_project_refuses_a_name_that_is_not_linked(world):
    app, corpus, reg = world
    link(app, {"project": "corpus"})
    r = run(["get", "x.md", "--project", "third"], app, reg)
    assert r.returncode != 0 and "not a linked project" in r.stderr, "the link is the permission"


def test_a_project_linking_itself_is_refused(world):
    app, corpus, reg = world
    link(app, {"project": "app"})
    [ln] = page(run(["search", "appword", "--json"], app, reg))["linked"]
    assert ln["searched"] is False and "this project itself" in ln["error"]


@pytest.mark.parametrize(
    "linked, message",
    [
        ([{"scope": "client=alfa"}], r"linked\[0\]\.project"),
        ([{"project": "corpus"}, {"project": "corpus"}], r"linked twice"),
        ([{"project": "corpus", "scope": "alfa"}], r"linked\[0\]\.scope"),
        ([{"project": "corpus", "about": 3}], r"linked\[0\]\.about"),
        (["corpus"], r"linked\[0\]: expected an object"),
    ],
)
def test_config_validation(tmp_path, linked, message):
    from set_kb.config import ConfigError, load_config

    root = make_repo(tmp_path)
    write(root / CONFIG, json.dumps({"linked": linked}))
    with pytest.raises(ConfigError, match=message):
        load_config(root, machine_path="/nonexistent/kb-machine.json")


def test_linked_is_out_of_the_corpus_hash(tmp_path):
    from set_kb.config import corpus_config_hash, load_config

    a, b = make_repo(tmp_path, "a"), make_repo(tmp_path, "b")
    write(b / CONFIG, json.dumps({"linked": [{"project": "corpus"}]}))
    m = "/nonexistent/kb-machine.json"
    assert corpus_config_hash(load_config(a, machine_path=m)) == corpus_config_hash(load_config(b, machine_path=m))


def test_the_mcp_tools_carry_linked_and_project(world, monkeypatch):
    from test_kb_mcp import load_server

    app, corpus, reg = world
    link(app, {"project": "corpus"})
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(app))
    monkeypatch.setenv("SET_CORE_REGISTRY", str(reg))
    mod = load_server()
    d = json.loads(mod.kb_search("ratelimitword"))
    assert d["linked"][0]["project"] == "corpus" and d["linked"][0]["hits"]
    assert json.loads(mod.kb_search("ratelimitword", linked=False))["linked"] == []
    got = mod.kb_get("wiki/alfa/limits.md", project="corpus")
    assert "ratelimitword for alfa" in got
