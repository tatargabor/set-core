"""The `kb_search` / `kb_get` MCP tools.

The MCP server runs under `uv` with fastmcp, which the unit venv does not
carry — so the server module is imported HERE with a stub fastmcp whose
`@mcp.tool` decorator passes functions through. The tool bodies then run for
real: they shell out to `bin/set-kb --json` with `cwd = CLAUDE_PROJECT_DIR`,
and the tests hold them to the contract — hits from the project's own index,
and the engine's error text returned verbatim instead of an empty result."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from pathlib import Path

from conftest_kb import make_repo, write

SERVER = Path(__file__).resolve().parents[2] / "mcp-server" / "set_mcp_server.py"

BODY = "\n\n" + "word " * 30 + "\n"


def load_server():
    """Import the server module with fastmcp stubbed — the decorator must not
    wrap the function, so the tests call the real body."""
    stub = types.ModuleType("fastmcp")

    class _FakeMCP:
        def __init__(self, name=None):
            self.name = name

        def tool(self, fn=None, **kwargs):
            def deco(f):
                return f

            return deco(fn) if fn is not None else deco

        def resource(self, *args, **kwargs):
            def deco(f):
                return f

            return deco

    stub.FastMCP = _FakeMCP
    saved = sys.modules.get("fastmcp")
    sys.modules["fastmcp"] = stub
    try:
        spec = importlib.util.spec_from_file_location("set_mcp_server_under_test", SERVER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        if saved is not None:
            sys.modules["fastmcp"] = saved
        else:
            del sys.modules["fastmcp"]
    return mod


def indexed_project(tmp_path) -> str:
    from test_kb_cli import run_cli

    root = make_repo(tmp_path, "mcpproj")
    write(root / "notes" / "team.md", "# Team note\n\nmcpword content" + BODY)
    r = run_cli(["search", "mcpword"], cwd=root)  # build the index
    assert r.returncode == 0
    return str(root)


def test_kb_search_returns_hits_from_the_project_index(tmp_path, monkeypatch):
    """AC: WHEN an agent in an initialized project calls kb_search THEN it
    receives the hits from that project's own index, as the JSON contract."""
    root = indexed_project(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", root)
    mod = load_server()
    out = mod.kb_search("mcpword")
    d = json.loads(out)
    assert d["version"] == 1
    assert d["hits"] and d["hits"][0]["path"] == "notes/team.md"


def test_kb_search_error_surfaces_verbatim(tmp_path, monkeypatch):
    """AC: WHEN set-kb fails THEN kb_search returns the error text, not an
    empty hit list."""
    root = make_repo(tmp_path, "broken")
    write(root / "set" / "knowledge" / "kb.json", json.dumps({"language": "xx"}))  # unknown pack
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", root)
    mod = load_server()
    out = mod.kb_search("anything")
    assert "not valid JSON" not in out
    assert "config.language" in out and "available packs" in out, "the engine's own words come through"


def test_kb_search_missing_project_is_not_an_empty_hit_list(tmp_path, monkeypatch):
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(plain))
    mod = load_server()
    out = mod.kb_search("anything")
    assert "no project" in out and '"hits"' not in out


def test_kb_get_accepts_a_hit_path_unchanged(tmp_path, monkeypatch):
    root = indexed_project(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", root)
    mod = load_server()
    hits = json.loads(mod.kb_search("mcpword"))["hits"]
    out = mod.kb_get(hits[0]["path"], section=hits[0]["headingPath"])
    d = json.loads(out)
    assert d["found"] is True and "mcpword content" in d["body"]


def test_kb_get_error_surfaces(tmp_path, monkeypatch):
    root = indexed_project(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", root)
    mod = load_server()
    out = mod.kb_get("notes/absent.md")
    assert "not in the index" in out
