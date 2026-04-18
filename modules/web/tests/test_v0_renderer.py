"""Unit tests for v0 fixture renderer: substitution + data imports + cache."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest


def test_load_fixtures(tmp_path: Path):
    from set_project_web.v0_renderer import load_fixtures

    f = tmp_path / "content-fixtures.yaml"
    f.write_text(
        "string_replacements:\n"
        "  Sample Coffee: Ethiopia Yirgacheffe\n"
        "data_imports:\n"
        "  lib/products.ts: 'export const products = [];'\n"
        "language: hu\n"
    )
    fx = load_fixtures(f)
    assert fx.string_replacements == {"Sample Coffee": "Ethiopia Yirgacheffe"}
    assert fx.language == "hu"
    assert "products" in fx.data_imports["lib/products.ts"]


def test_load_fixtures_missing_raises(tmp_path: Path):
    from set_project_web.v0_renderer import FixturesMissingError, load_fixtures

    with pytest.raises(FixturesMissingError):
        load_fixtures(tmp_path / "does-not-exist.yaml")


def test_apply_string_replacements(tmp_path: Path):
    from set_project_web.v0_renderer import _apply_string_replacements

    (tmp_path / "a.tsx").write_text("<h1>Sample Coffee</h1>\nSample Coffee again")
    (tmp_path / "b.ts").write_text("const label = 'Lorem ipsum'")
    _apply_string_replacements(
        tmp_path, {"Sample Coffee": "Kávé", "Lorem ipsum": "Teszt"},
    )
    assert "Kávé" in (tmp_path / "a.tsx").read_text()
    assert "Sample Coffee" not in (tmp_path / "a.tsx").read_text()
    assert "Teszt" in (tmp_path / "b.ts").read_text()


def test_apply_string_replacements_zero_match_noop(tmp_path: Path):
    from set_project_web.v0_renderer import _apply_string_replacements

    (tmp_path / "x.tsx").write_text("no match here")
    # Must not raise
    _apply_string_replacements(tmp_path, {"XYZ": "ABC"})


def test_apply_data_imports_creates_missing(tmp_path: Path):
    from set_project_web.v0_renderer import _apply_data_imports

    target = "lib/mock-products.ts"
    body = "export default [{ id: 1 }]"
    _apply_data_imports(tmp_path, {target: body})
    assert (tmp_path / target).read_text() == body


def test_apply_data_imports_overwrites_existing(tmp_path: Path):
    from set_project_web.v0_renderer import _apply_data_imports

    target = "lib/thing.ts"
    (tmp_path / "lib").mkdir()
    (tmp_path / target).write_text("old content")
    _apply_data_imports(tmp_path, {target: "new content"})
    assert (tmp_path / target).read_text() == "new content"


def test_node_cache_lru_prune(tmp_path: Path, monkeypatch):
    from set_project_web import v0_renderer

    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    monkeypatch.setattr(v0_renderer, "NODE_CACHE_DIR", cache_root)
    monkeypatch.setattr(v0_renderer, "NODE_CACHE_MAX_HASHES", 2)
    for i in range(4):
        d = cache_root / f"h{i}"
        d.mkdir()
        past = time.time() - (4 - i)
        os.utime(d, (past, past))

    v0_renderer._prune_node_cache()
    remaining = sorted(p.name for p in cache_root.iterdir())
    assert remaining == ["h2", "h3"]


def test_allocate_port_returns_free_port():
    from set_project_web.v0_renderer import _allocate_port

    port = _allocate_port()
    assert 3400 <= port <= 3499
