"""Unit tests for v0 importer: ZIP extraction + validation + cache."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
import yaml


def _make_v0_zip(root: Path, with_ui: bool = True) -> Path:
    """Create a minimal valid v0 ZIP at root/v0.zip."""
    zip_path = root / "v0.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("app/page.tsx", "<h1>Home</h1>")
        zf.writestr("app/globals.css", ":root { --primary: #000; }")
        zf.writestr("app/layout.tsx", "export default function L(){return null}")
        zf.writestr("package.json", '{"name":"x"}')
        if with_ui:
            zf.writestr("components/ui/button.tsx", "export const Button = () => null")
    zip_path.write_bytes(buf.getvalue())
    return zip_path


def _make_scaffold(root: Path, ui_library: str = "shadcn") -> Path:
    scaffold = root / "scaffold"
    scaffold.mkdir()
    (scaffold / "scaffold.yaml").write_text(yaml.safe_dump({
        "project_type": "web",
        "template": "nextjs",
        "ui_library": ui_library,
    }))
    return scaffold


def test_valid_zip_import_succeeds(tmp_path: Path):
    from set_project_web.v0_importer import import_v0_zip

    scaffold = _make_scaffold(tmp_path)
    zip_path = _make_v0_zip(tmp_path)

    summary = import_v0_zip(zip_path, scaffold)
    assert summary.v0_export_dir.is_dir()
    assert (summary.v0_export_dir / "app" / "page.tsx").is_file()
    # globals.css synced
    assert (scaffold / "shadcn" / "globals.css").is_file()
    # Manifest generated
    assert summary.manifest_path.is_file()


def test_missing_app_router_fails(tmp_path: Path):
    from set_project_web.v0_importer import V0ImportError, import_v0_zip

    scaffold = _make_scaffold(tmp_path)
    # ZIP without app/
    zip_path = tmp_path / "broken.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("package.json", '{"name":"x"}')
    zip_path.write_bytes(buf.getvalue())

    with pytest.raises(V0ImportError) as exc:
        import_v0_zip(zip_path, scaffold)
    assert "app/" in str(exc.value)


def test_missing_globals_css_fails(tmp_path: Path):
    from set_project_web.v0_importer import V0ImportError, import_v0_zip

    scaffold = _make_scaffold(tmp_path)
    zip_path = tmp_path / "no-css.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("app/page.tsx", "<h1>x</h1>")
        zf.writestr("package.json", '{}')
    zip_path.write_bytes(buf.getvalue())

    with pytest.raises(V0ImportError) as exc:
        import_v0_zip(zip_path, scaffold)
    assert "globals.css" in str(exc.value)


def test_missing_ui_with_shadcn_fails(tmp_path: Path):
    from set_project_web.v0_importer import V0ImportError, import_v0_zip

    scaffold = _make_scaffold(tmp_path, ui_library="shadcn")
    zip_path = _make_v0_zip(tmp_path, with_ui=False)

    with pytest.raises(V0ImportError) as exc:
        import_v0_zip(zip_path, scaffold)
    assert "components/ui" in str(exc.value)


def test_missing_ui_without_shadcn_passes(tmp_path: Path):
    from set_project_web.v0_importer import import_v0_zip

    scaffold = _make_scaffold(tmp_path, ui_library="none")
    zip_path = _make_v0_zip(tmp_path, with_ui=False)
    summary = import_v0_zip(zip_path, scaffold)
    assert summary.v0_export_dir.is_dir()


def test_re_import_without_force_fails(tmp_path: Path):
    from set_project_web.v0_importer import V0ImportError, import_v0_zip

    scaffold = _make_scaffold(tmp_path)
    zip_path = _make_v0_zip(tmp_path)
    import_v0_zip(zip_path, scaffold)
    with pytest.raises(V0ImportError):
        import_v0_zip(zip_path, scaffold, force=False)


def test_re_import_force_replaces(tmp_path: Path):
    from set_project_web.v0_importer import import_v0_zip

    scaffold = _make_scaffold(tmp_path)
    zip_path = _make_v0_zip(tmp_path)
    s1 = import_v0_zip(zip_path, scaffold)
    stray = s1.v0_export_dir / "STRAY.txt"
    stray.write_text("should be gone")
    s2 = import_v0_zip(zip_path, scaffold, force=True)
    assert not stray.exists(), "force=True must remove previous v0-export/"
    assert s2.v0_export_dir.is_dir()


def test_flatten_single_wrapper_directory(tmp_path: Path):
    """ZIP that wraps content under a single top-level dir should be flattened."""
    from set_project_web.v0_importer import import_v0_zip

    scaffold = _make_scaffold(tmp_path)
    zip_path = tmp_path / "wrapped.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("wrapper/app/page.tsx", "<h1>x</h1>")
        zf.writestr("wrapper/app/globals.css", ":root{}")
        zf.writestr("wrapper/app/layout.tsx", "export default function L(){}")
        zf.writestr("wrapper/package.json", '{}')
        zf.writestr("wrapper/components/ui/button.tsx", "export const B = null")
    zip_path.write_bytes(buf.getvalue())

    summary = import_v0_zip(zip_path, scaffold)
    assert (summary.v0_export_dir / "app" / "page.tsx").is_file()


def test_url_mask_strips_credentials():
    from set_project_web.v0_importer import _mask_url, _url_has_embedded_credentials

    assert _mask_url("https://u:p@github.com/o/r.git") == "https://github.com/o/r.git"
    assert _mask_url("https://github.com/o/r.git") == "https://github.com/o/r.git"
    assert _url_has_embedded_credentials("https://u:p@github.com/o/r.git")
    assert not _url_has_embedded_credentials("https://github.com/o/r.git")


def test_cache_key_hashes_url(tmp_path: Path, monkeypatch):
    from set_project_web import v0_importer

    monkeypatch.setattr(v0_importer, "CLONE_CACHE_DIR", tmp_path / "cache")
    out = v0_importer._resolve_clone_cache("https://u:p@github.com/secret/repo.git")
    assert "secret" not in str(out)
    assert len(out.name) == 16  # sha256 truncated to 16 hex chars


def test_cache_lru_pruning(tmp_path: Path, monkeypatch):
    import os
    import time
    from set_project_web import v0_importer

    cache_root = tmp_path / "cache"
    monkeypatch.setattr(v0_importer, "CLONE_CACHE_DIR", cache_root)
    monkeypatch.setattr(v0_importer, "CLONE_CACHE_MAX_ENTRIES", 3)
    cache_root.mkdir()
    for i in range(5):
        d = cache_root / f"entry{i}"
        d.mkdir()
        # Stagger mtimes
        past = time.time() - (5 - i)
        os.utime(d, (past, past))

    v0_importer._prune_clone_cache()
    remaining = sorted(p.name for p in cache_root.iterdir())
    assert remaining == ["entry2", "entry3", "entry4"]
