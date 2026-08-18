"""Tests for the deploy provenance ledger and its use by the manifest deploy engine.

The behaviour under test decides whether `set-project init --force` preserves or
destroys a consumer's files, and whether it resurrects files the consumer deleted on
purpose. Assertions are on file content and ledger state, never on log text.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "lib"))

from set_orch.deploy_ledger import DeployLedger, sha256_file  # noqa: E402
from set_orch.profile_deploy import _deploy_single_template  # noqa: E402


# ── DeployLedger unit behaviour ──────────────────────────────────────────────


def test_decide_new_file_deploys(tmp_path):
    ledger = DeployLedger(tmp_path)
    ok, reason = ledger.decide("a.md", tmp_path / "a.md")
    assert ok is True
    assert reason == "new"


def test_decide_untouched_file_deploys(tmp_path):
    """The anti-freeze case: the project never touched it, so the update must land."""
    dst = tmp_path / "a.md"
    dst.write_text("v1")
    ledger = DeployLedger(tmp_path)
    ledger.files["a.md"] = sha256_file(dst)

    ok, reason = ledger.decide("a.md", dst)
    assert ok is True
    assert "untouched" in reason


def test_decide_modified_file_is_skipped(tmp_path):
    dst = tmp_path / "a.md"
    dst.write_text("v1")
    ledger = DeployLedger(tmp_path)
    ledger.files["a.md"] = sha256_file(dst)
    dst.write_text("EDITED BY PROJECT")

    ok, reason = ledger.decide("a.md", dst)
    assert ok is False
    assert "modified by the project" in reason


def test_decide_unknown_provenance_is_skipped(tmp_path):
    """Projects predating the ledger must not be clobbered on the first run."""
    dst = tmp_path / "a.md"
    dst.write_text("pre-existing")
    ledger = DeployLedger(tmp_path)

    ok, reason = ledger.decide("a.md", dst)
    assert ok is False
    assert "unknown provenance" in reason


def test_decide_deleted_file_is_tombstoned(tmp_path):
    ledger = DeployLedger(tmp_path)
    ledger.files["a.md"] = "deadbeef"

    ok, reason = ledger.decide("a.md", tmp_path / "a.md")
    assert ok is False
    assert "tombstone" in reason
    assert ledger.is_tombstoned("a.md")
    assert "a.md" not in ledger.files


def test_decide_tombstoned_stays_skipped(tmp_path):
    ledger = DeployLedger(tmp_path)
    ledger.tombstones.add("a.md")

    ok, reason = ledger.decide("a.md", tmp_path / "a.md")
    assert ok is False
    assert "removed by the project" in reason


def test_untombstone_restores(tmp_path):
    ledger = DeployLedger(tmp_path)
    ledger.tombstones.add("a.md")

    assert ledger.untombstone("a.md") is True
    ok, _ = ledger.decide("a.md", tmp_path / "a.md")
    assert ok is True
    assert ledger.untombstone("a.md") is False


def test_corrupt_ledger_degrades_to_conservative(tmp_path):
    """A bad ledger must never authorise an overwrite."""
    (tmp_path / "set").mkdir()
    (tmp_path / "set" / ".deploy-manifest.json").write_text("{ not json")
    dst = tmp_path / "a.md"
    dst.write_text("PROJECT")

    ledger = DeployLedger.load(tmp_path)
    ok, reason = ledger.decide("a.md", dst)
    assert ok is False
    assert "unknown provenance" in reason


def test_save_and_reload_roundtrip(tmp_path):
    src = tmp_path / "src.md"
    src.write_text("hello")
    ledger = DeployLedger(tmp_path)
    ledger.record("x/y.md", src)
    ledger.tombstone("gone.md")
    assert ledger.save() is True

    reloaded = DeployLedger.load(tmp_path)
    assert reloaded.files["x/y.md"] == sha256_file(src)
    assert reloaded.is_tombstoned("gone.md")

    data = json.loads((tmp_path / "set" / ".deploy-manifest.json").read_text())
    assert data["version"] == 2
    assert "_help" in data


def test_record_clears_a_tombstone(tmp_path):
    src = tmp_path / "src.md"
    src.write_text("hello")
    ledger = DeployLedger(tmp_path)
    ledger.tombstone("a.md")
    ledger.record("a.md", src)
    assert not ledger.is_tombstoned("a.md")


# ── manifest engine integration ──────────────────────────────────────────────


@pytest.fixture
def template(tmp_path):
    """A minimal template dir with one plain file, plus an empty target project."""
    tdir = tmp_path / "tpl"
    tdir.mkdir()
    (tdir / "manifest.yaml").write_text(
        'version: "test"\ncore:\n  - path: rules/stale.md\n    replace: true\n')
    (tdir / "rules").mkdir()
    (tdir / "rules" / "stale.md").write_text("framework rule v1")

    target = tmp_path / "proj"
    target.mkdir()
    return tdir, target


def test_manifest_engine_deploys_then_records(template):
    tdir, target = template
    _deploy_single_template(tdir, target, force=True)

    deployed = target / ".claude" / "rules" / "stale.md"
    assert deployed.read_text() == "framework rule v1"

    ledger = DeployLedger.load(target)
    assert ledger.files[".claude/rules/stale.md"] == sha256_file(deployed)


def test_manifest_engine_does_not_resurrect_deleted_file(template):
    """Deploy → project deletes → redeploy must NOT bring it back."""
    tdir, target = template
    _deploy_single_template(tdir, target, force=True)
    deployed = target / ".claude" / "rules" / "stale.md"
    deployed.unlink()

    msgs = _deploy_single_template(tdir, target, force=True)

    assert not deployed.exists(), "deleted file was resurrected"
    assert any("tombstoned" in m for m in msgs)
    assert DeployLedger.load(target).is_tombstoned(".claude/rules/stale.md")


def test_manifest_engine_keeps_tombstone_on_later_runs(template):
    tdir, target = template
    _deploy_single_template(tdir, target, force=True)
    deployed = target / ".claude" / "rules" / "stale.md"
    deployed.unlink()
    _deploy_single_template(tdir, target, force=True)

    msgs = _deploy_single_template(tdir, target, force=True)

    assert not deployed.exists()
    assert any("removed by project" in m for m in msgs)


def test_manifest_engine_dry_run_records_no_tombstone(template):
    tdir, target = template
    _deploy_single_template(tdir, target, force=True)
    (target / ".claude" / "rules" / "stale.md").unlink()

    msgs = _deploy_single_template(tdir, target, force=True, dry_run=True)

    assert any("Would skip" in m for m in msgs)
    assert not DeployLedger.load(target).tombstones, "dry run mutated the ledger"


def test_manifest_engine_restores_after_tombstone_cleared(template):
    tdir, target = template
    _deploy_single_template(tdir, target, force=True)
    deployed = target / ".claude" / "rules" / "stale.md"
    deployed.unlink()
    _deploy_single_template(tdir, target, force=True)

    ledger = DeployLedger.load(target)
    ledger.untombstone(".claude/rules/stale.md")
    ledger.save()

    _deploy_single_template(tdir, target, force=True)
    assert deployed.read_text() == "framework rule v1"
