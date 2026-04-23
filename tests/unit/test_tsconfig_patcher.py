"""Unit tests for `_patch_tsconfig_excludes` in set-design-import CLI."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from set_project_web.design_import_cli import (
    REQUIRED_TSCONFIG_EXCLUDES,
    _patch_tsconfig_excludes,
)


def _write_tsconfig(scaffold: Path, data: dict) -> Path:
    ts = scaffold / "tsconfig.json"
    ts.write_text(json.dumps(data, indent=2) + "\n")
    return ts


def _read_tsconfig(scaffold: Path) -> dict:
    return json.loads((scaffold / "tsconfig.json").read_text())


def test_stale_exclude_gets_all_patterns_appended(tmp_path: Path) -> None:
    _write_tsconfig(tmp_path, {"compilerOptions": {}, "exclude": ["node_modules"]})

    added = _patch_tsconfig_excludes(tmp_path)

    assert set(added) == set(REQUIRED_TSCONFIG_EXCLUDES)
    excl = _read_tsconfig(tmp_path)["exclude"]
    assert "node_modules" in excl
    for p in REQUIRED_TSCONFIG_EXCLUDES:
        assert p in excl


def test_preserves_preexisting_order(tmp_path: Path) -> None:
    pre = ["node_modules", "dist", "v0-export"]
    _write_tsconfig(tmp_path, {"compilerOptions": {}, "exclude": list(pre)})

    _patch_tsconfig_excludes(tmp_path)

    excl = _read_tsconfig(tmp_path)["exclude"]
    # Original order preserved at the front
    assert excl[: len(pre)] == pre
    # New entries appended after
    for p in REQUIRED_TSCONFIG_EXCLUDES:
        assert p in excl


def test_idempotent_noop_when_all_patterns_present(tmp_path: Path) -> None:
    excl = ["node_modules", *REQUIRED_TSCONFIG_EXCLUDES]
    ts = _write_tsconfig(tmp_path, {"compilerOptions": {}, "exclude": excl})
    before = ts.read_bytes()

    added = _patch_tsconfig_excludes(tmp_path)

    assert added == []
    assert ts.read_bytes() == before


def test_partial_state_only_missing_added(tmp_path: Path) -> None:
    # Already has "v0-export", missing the other three patterns
    _write_tsconfig(tmp_path, {
        "compilerOptions": {}, "exclude": ["node_modules", "v0-export"],
    })

    added = _patch_tsconfig_excludes(tmp_path)

    assert set(added) == set(REQUIRED_TSCONFIG_EXCLUDES) - {"v0-export"}
    excl = _read_tsconfig(tmp_path)["exclude"]
    # "v0-export" not duplicated
    assert excl.count("v0-export") == 1


def test_malformed_tsconfig_warns_and_skips(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    ts = tmp_path / "tsconfig.json"
    # JSON5-style comments — not valid strict JSON
    raw = """{
      // next.js config
      "compilerOptions": {},
      "exclude": ["node_modules",],
    }
    """
    ts.write_text(raw)
    before = ts.read_bytes()

    with caplog.at_level(logging.WARNING, logger="set-design-import"):
        added = _patch_tsconfig_excludes(tmp_path)

    assert added == []
    assert ts.read_bytes() == before
    assert any(
        "could not parse" in rec.getMessage() for rec in caplog.records
    )


def test_missing_tsconfig_logs_debug_and_returns_empty(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    # No tsconfig.json at all
    with caplog.at_level(logging.DEBUG, logger="set-design-import"):
        added = _patch_tsconfig_excludes(tmp_path)

    assert added == []
    assert any(
        "no tsconfig.json" in rec.getMessage() for rec in caplog.records
    )


def test_non_list_exclude_warns_and_skips(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    # "exclude" exists but is a string, not a list
    ts = _write_tsconfig(tmp_path, {"compilerOptions": {}, "exclude": "v0-export"})
    before = ts.read_bytes()

    with caplog.at_level(logging.WARNING, logger="set-design-import"):
        added = _patch_tsconfig_excludes(tmp_path)

    assert added == []
    assert ts.read_bytes() == before
    assert any(
        "no list-valued 'exclude'" in rec.getMessage() for rec in caplog.records
    )


def test_info_log_names_added_patterns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    _write_tsconfig(tmp_path, {"compilerOptions": {}, "exclude": ["node_modules"]})

    with caplog.at_level(logging.INFO, logger="set-design-import"):
        added = _patch_tsconfig_excludes(tmp_path)

    assert set(added) == set(REQUIRED_TSCONFIG_EXCLUDES)
    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert messages, "expected an INFO log on mutation"
    joined = " ".join(messages)
    for p in REQUIRED_TSCONFIG_EXCLUDES:
        assert p in joined


def test_missing_exclude_key_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    # No "exclude" key at all
    ts = _write_tsconfig(tmp_path, {"compilerOptions": {}})
    before = ts.read_bytes()

    with caplog.at_level(logging.WARNING, logger="set-design-import"):
        added = _patch_tsconfig_excludes(tmp_path)

    # Current implementation treats missing exclude as "no list-valued exclude"
    # → warn + skip. If we later decide to auto-create exclude, update this test.
    assert added == []
    assert ts.read_bytes() == before
