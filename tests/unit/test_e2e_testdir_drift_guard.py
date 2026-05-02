"""Tests for e2e-testdir-drift-guard helpers."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "modules", "web"))

from set_project_web.gates import (
    _CANONICAL_TESTDIR_PREFERENCE,
    _classify_unparseable_failure,
    _extract_testdir_drift,
    _read_declared_testdir,
    _resolve_canonical_testdir,
    _resync_playwright_config_testdir,
    _scan_spec_files,
)
from set_orch.verifier import _lint_playwright_testdir_consistency


# ─── Fixtures ──────────────────────────────────────────────────────


def _write_playwright_config(root, testdir, global_setup="./tests/e2e/global-setup.ts"):
    cfg = (
        "import { defineConfig } from '@playwright/test';\n"
        "export default defineConfig({\n"
        f'  testDir: "{testdir}",\n'
        f'  globalSetup: "{global_setup}",\n'
        "  fullyParallel: false,\n"
        "});\n"
    )
    (root / "playwright.config.ts").write_text(cfg)


def _make_spec(root, rel_path, body="test('x', () => { /* ok */ });\n"):
    p = root / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    return p


# ─── _scan_spec_files ─────────────────────────────────────────────


def test_scan_spec_files_finds_specs(tmp_path):
    _make_spec(tmp_path, "tests/e2e/foo.spec.ts")
    _make_spec(tmp_path, "tests/e2e/bar.spec.ts")
    found = _scan_spec_files(str(tmp_path))
    assert sorted(found) == ["tests/e2e/bar.spec.ts", "tests/e2e/foo.spec.ts"]


def test_scan_spec_files_skips_node_modules(tmp_path):
    _make_spec(tmp_path, "tests/e2e/foo.spec.ts")
    _make_spec(tmp_path, "node_modules/playwright/test.spec.ts")
    found = _scan_spec_files(str(tmp_path))
    assert found == ["tests/e2e/foo.spec.ts"]


# ─── _read_declared_testdir ────────────────────────────────────────


def test_read_declared_testdir_from_config(tmp_path):
    _write_playwright_config(tmp_path, "./tests/e2e")
    assert _read_declared_testdir(str(tmp_path)) == "tests/e2e"


def test_read_declared_testdir_no_config(tmp_path):
    assert _read_declared_testdir(str(tmp_path)) is None


# ─── _extract_testdir_drift ────────────────────────────────────────


def test_extract_testdir_drift_positive(tmp_path):
    _write_playwright_config(tmp_path, "./e2e")  # stale: points at e2e/
    _make_spec(tmp_path, "tests/e2e/foo.spec.ts")  # but specs are at tests/e2e/
    output = "Running 0 tests using 0 workers\n\nError: No tests found.\n"
    assert _extract_testdir_drift(output, str(tmp_path)) is True


def test_extract_testdir_drift_no_signature(tmp_path):
    _write_playwright_config(tmp_path, "./e2e")
    _make_spec(tmp_path, "tests/e2e/foo.spec.ts")
    assert _extract_testdir_drift("normal failure", str(tmp_path)) is False


def test_extract_testdir_drift_no_specs(tmp_path):
    _write_playwright_config(tmp_path, "./e2e")
    output = "Error: No tests found.\n"
    # No spec files anywhere → drift cannot be confirmed
    assert _extract_testdir_drift(output, str(tmp_path)) is False


def test_extract_testdir_drift_specs_already_in_testdir(tmp_path):
    _write_playwright_config(tmp_path, "./tests/e2e")
    _make_spec(tmp_path, "tests/e2e/foo.spec.ts")
    output = "Error: No tests found.\n"
    # Specs ARE under declared testDir — likely a CLI typo, not config drift
    assert _extract_testdir_drift(output, str(tmp_path)) is False


# ─── _resolve_canonical_testdir ────────────────────────────────────


def test_resolve_canonical_single_dir(tmp_path):
    _make_spec(tmp_path, "tests/e2e/a.spec.ts")
    _make_spec(tmp_path, "tests/e2e/b.spec.ts")
    assert _resolve_canonical_testdir(str(tmp_path)) == "tests/e2e"


def test_resolve_canonical_prefers_canonical_on_tie(tmp_path):
    _make_spec(tmp_path, "tests/e2e/a.spec.ts")
    _make_spec(tmp_path, "e2e/b.spec.ts")
    # 1 each → tiebreaker prefers tests/e2e
    assert _resolve_canonical_testdir(str(tmp_path)) == _CANONICAL_TESTDIR_PREFERENCE


def test_resolve_canonical_count_wins_over_preference(tmp_path):
    _make_spec(tmp_path, "tests/e2e/a.spec.ts")
    _make_spec(tmp_path, "weird/dir/b.spec.ts")
    _make_spec(tmp_path, "weird/dir/c.spec.ts")
    _make_spec(tmp_path, "weird/dir/d.spec.ts")
    # weird/dir has 3 vs tests/e2e has 1 — count wins
    assert _resolve_canonical_testdir(str(tmp_path)) == "weird/dir"


def test_resolve_canonical_no_specs(tmp_path):
    assert _resolve_canonical_testdir(str(tmp_path)) is None


# ─── _resync_playwright_config_testdir ─────────────────────────────


def test_resync_rewrites_testdir_and_global_setup(tmp_path):
    _write_playwright_config(tmp_path, "./e2e", global_setup="./e2e/global-setup.ts")
    _make_spec(tmp_path, "tests/e2e/foo.spec.ts")
    assert _resync_playwright_config_testdir(str(tmp_path), "tests/e2e") is True
    new_text = (tmp_path / "playwright.config.ts").read_text()
    assert 'testDir: "./tests/e2e"' in new_text
    assert 'globalSetup: "./tests/e2e/global-setup.ts"' in new_text


def test_resync_returns_false_when_regex_does_not_match(tmp_path):
    (tmp_path / "playwright.config.ts").write_text("// no testDir field at all\n")
    assert _resync_playwright_config_testdir(str(tmp_path), "tests/e2e") is False


def test_resync_migrates_global_setup_when_canonical_absent(tmp_path):
    _write_playwright_config(tmp_path, "./e2e", global_setup="./e2e/global-setup.ts")
    (tmp_path / "e2e").mkdir()
    (tmp_path / "e2e" / "global-setup.ts").write_text("export default async () => { /* setup */ };\n")
    _make_spec(tmp_path, "tests/e2e/foo.spec.ts")
    assert _resync_playwright_config_testdir(str(tmp_path), "tests/e2e") is True
    canonical_gs = tmp_path / "tests" / "e2e" / "global-setup.ts"
    assert canonical_gs.is_file()
    assert "setup" in canonical_gs.read_text()
    # source not deleted
    assert (tmp_path / "e2e" / "global-setup.ts").is_file()


def test_resync_does_not_overwrite_existing_canonical_global_setup(tmp_path):
    _write_playwright_config(tmp_path, "./e2e", global_setup="./e2e/global-setup.ts")
    (tmp_path / "e2e").mkdir()
    (tmp_path / "e2e" / "global-setup.ts").write_text("STALE SETUP\n")
    _make_spec(tmp_path, "tests/e2e/foo.spec.ts")
    canonical_gs = tmp_path / "tests" / "e2e" / "global-setup.ts"
    canonical_gs.parent.mkdir(parents=True, exist_ok=True)
    canonical_gs.write_text("CANONICAL SETUP\n")
    assert _resync_playwright_config_testdir(str(tmp_path), "tests/e2e") is True
    assert canonical_gs.read_text() == "CANONICAL SETUP\n"


# ─── _classify_unparseable_failure ──────────────────────────────────


def test_classify_testdir_drift(tmp_path):
    _write_playwright_config(tmp_path, "./e2e")
    _make_spec(tmp_path, "tests/e2e/foo.spec.ts")
    msg = _classify_unparseable_failure("Error: No tests found.\n", str(tmp_path))
    assert "testDir vs spec file path mismatch" in msg
    assert "tests/e2e" in msg


def test_classify_falls_back_to_legacy_message(tmp_path):
    msg = _classify_unparseable_failure("normal crash output", str(tmp_path))
    assert "[no parseable failure list" in msg


# ─── verify-gate canary ────────────────────────────────────────────


def test_canary_warns_on_empty_testdir_with_specs_elsewhere(tmp_path):
    _write_playwright_config(tmp_path, "./e2e")  # 0 specs there
    for n in range(3):
        _make_spec(tmp_path, f"tests/e2e/s{n}.spec.ts")
    finding = _lint_playwright_testdir_consistency(str(tmp_path))
    assert finding is not None
    assert finding["declared_testdir"] == "e2e"
    assert finding["canonical_candidate"] == "tests/e2e"
    assert finding["declared_count"] == 0
    assert finding["canonical_count"] == 3


def test_canary_passes_when_testdir_matches_densest(tmp_path):
    _write_playwright_config(tmp_path, "./tests/e2e")
    for n in range(3):
        _make_spec(tmp_path, f"tests/e2e/s{n}.spec.ts")
    assert _lint_playwright_testdir_consistency(str(tmp_path)) is None


def test_canary_passes_with_no_config(tmp_path):
    _make_spec(tmp_path, "tests/e2e/foo.spec.ts")
    assert _lint_playwright_testdir_consistency(str(tmp_path)) is None


def test_canary_passes_with_no_specs(tmp_path):
    _write_playwright_config(tmp_path, "./tests/e2e")
    assert _lint_playwright_testdir_consistency(str(tmp_path)) is None


def test_canary_passes_under_3x_threshold(tmp_path):
    _write_playwright_config(tmp_path, "./tests/e2e")
    # declared has 2, sibling has 5 (2.5x — under 3x threshold) → pass
    _make_spec(tmp_path, "tests/e2e/a.spec.ts")
    _make_spec(tmp_path, "tests/e2e/b.spec.ts")
    for n in range(5):
        _make_spec(tmp_path, f"other/o{n}.spec.ts")
    assert _lint_playwright_testdir_consistency(str(tmp_path)) is None


def test_canary_warns_at_3x_threshold(tmp_path):
    _write_playwright_config(tmp_path, "./tests/e2e")
    # declared has 2, sibling has 6 (3x) → warn
    _make_spec(tmp_path, "tests/e2e/a.spec.ts")
    _make_spec(tmp_path, "tests/e2e/b.spec.ts")
    for n in range(6):
        _make_spec(tmp_path, f"other/o{n}.spec.ts")
    finding = _lint_playwright_testdir_consistency(str(tmp_path))
    assert finding is not None
    assert finding["canonical_candidate"] == "other"
