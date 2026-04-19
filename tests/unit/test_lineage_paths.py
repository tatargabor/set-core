"""Tests for LineagePaths and the lineage type helpers."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.paths import LineagePaths, SetRuntime
from set_orch.types import LineageId, canonicalise_spec_path, slug


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A bare git project with an isolated SetRuntime rooted under tmp_path."""
    # SET_TOOLS_DATA_DIR is module-level; patch it directly so each test runs
    # in a fresh runtime tree (env var alone is read only at import time).
    import set_orch.paths as paths_mod
    isolated_data_dir = str(tmp_path / "xdg" / "set-core")
    monkeypatch.setattr(paths_mod, "SET_TOOLS_DATA_DIR", isolated_data_dir)

    proj = tmp_path / "myproject"
    proj.mkdir()
    git_env = {**os.environ,
               "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"),
               "GIT_CONFIG_SYSTEM": "/dev/null"}
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True, env=git_env)
    (proj / "README").write_text("seed\n")
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "README"],
                   cwd=proj, check=True, env=git_env)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit",
                    "-q", "-m", "init"], cwd=proj, check=True, env=git_env)

    rt = SetRuntime(str(proj))
    rt.ensure_dirs()
    return proj, rt


def _write_state(rt, lineage_id):
    with open(rt.state_file, "w") as fh:
        json.dump({"spec_lineage_id": lineage_id}, fh)


# ---------------------------------------------------------------------------
# slug() edge cases (task 0.4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected_prefix",
    [
        ("docs/spec.md", "docs-spec.md"),
        ("docs\\spec.md", "docs-spec.md"),
        ("./docs/spec-v1.md", "docs-spec-v1.md"),
        ("docs/spec v2.md", "docs-spec_v2.md"),
        ("docs/spec\u00e9.md", "docs-spec_.md"),  # unicode collapses
        ("", "_unknown"),
        ("....", "_unknown"),
        ("/", "_unknown"),
    ],
)
def test_slug_normalisation(value, expected_prefix):
    out = slug(LineageId(value))
    assert out == expected_prefix, f"slug({value!r}) -> {out!r}"


def test_slug_truncates_long_inputs():
    long_id = "a/" * 200
    out = slug(LineageId(long_id))
    assert len(out) <= 96
    assert not out.endswith(("-", "_", "."))


def test_slug_is_idempotent():
    base = slug(LineageId("docs/spec-v1.md"))
    assert slug(LineageId(base)) == base


# ---------------------------------------------------------------------------
# canonicalise_spec_path
# ---------------------------------------------------------------------------


def test_canonicalisation_inside_project(project, tmp_path):
    proj, _ = project
    rel = canonicalise_spec_path("docs/spec.md", str(proj))
    abs_path = canonicalise_spec_path(str(proj / "docs" / "spec.md"), str(proj))
    assert rel == abs_path == "docs/spec.md"


def test_canonicalisation_outside_project_keeps_absolute(project):
    proj, _ = project
    parent = proj.parent / "external" / "spec.md"
    parent.parent.mkdir(parents=True, exist_ok=True)
    parent.write_text("x")
    out = canonicalise_spec_path(str(parent), str(proj))
    assert out.startswith("/")  # absolute, not project-relative


def test_canonicalisation_rejects_empty():
    with pytest.raises(ValueError):
        canonicalise_spec_path("", "/tmp")


# ---------------------------------------------------------------------------
# LineagePaths — live lineage (task 0.6.a)
# ---------------------------------------------------------------------------


def test_live_lineage_returns_unsuffixed_paths(project):
    proj, rt = project
    _write_state(rt, "docs/spec-v1.md")

    lp = LineagePaths(str(proj), lineage_id=LineageId("docs/spec-v1.md"))
    assert lp.is_live is True
    assert lp.plan_file.endswith("/orchestration-plan.json")
    assert lp.plan_domains_file.endswith("/orchestration-plan-domains.json")
    assert lp.digest_dir.endswith("/digest")
    assert lp.state_archive.endswith("/state-archive.jsonl")
    assert lp.state_file == rt.state_file


def test_no_lineage_id_is_treated_as_live(project):
    proj, rt = project
    _write_state(rt, "docs/spec-v1.md")
    lp = LineagePaths(str(proj))
    assert lp.is_live is True
    assert lp.plan_file.endswith("/orchestration-plan.json")


# ---------------------------------------------------------------------------
# LineagePaths — non-live lineage with rotated copy present (task 0.6.b)
# ---------------------------------------------------------------------------


def test_non_live_lineage_with_rotated_copy(project):
    proj, rt = project
    _write_state(rt, "docs/spec-v2.md")

    v1_slug = slug(LineageId("docs/spec-v1.md"))
    rotated_plan = os.path.join(rt.orchestration_dir, f"orchestration-plan-{v1_slug}.json")
    # Per the codebase contract digest_dir lives under the project tree
    # (`<project>/set/orchestration/digest`), not the runtime tree.
    rotated_digest = os.path.join(
        str(proj), "set", "orchestration", f"digest-{v1_slug}",
    )
    with open(rotated_plan, "w") as fh:
        json.dump({"plan_version": 1}, fh)
    os.makedirs(rotated_digest, exist_ok=True)

    lp = LineagePaths(str(proj), lineage_id=LineageId("docs/spec-v1.md"))
    assert lp.is_live is False
    assert lp.plan_file == rotated_plan
    assert lp.digest_dir == rotated_digest
    assert lp.lineage_specific_exists("plan_file") is True
    assert lp.lineage_specific_exists("digest_dir") is True


# ---------------------------------------------------------------------------
# LineagePaths — non-live lineage with NO rotated copy → fallback (task 0.6.c)
# ---------------------------------------------------------------------------


def test_non_live_lineage_falls_back_with_debug_log(project, caplog):
    proj, rt = project
    _write_state(rt, "docs/spec-v2.md")

    lp = LineagePaths(str(proj), lineage_id=LineageId("docs/spec-v1.md"))
    with caplog.at_level(logging.DEBUG, logger="set_orch.paths"):
        result = lp.plan_file

    assert result.endswith("/orchestration-plan.json")  # fell back to live
    assert any("LineagePaths fallback" in rec.message for rec in caplog.records)
    assert lp.lineage_specific_exists("plan_file") is False


def test_non_live_digest_falls_back_when_dir_missing(project, caplog):
    proj, rt = project
    _write_state(rt, "docs/spec-v2.md")
    lp = LineagePaths(str(proj), lineage_id=LineageId("docs/spec-v1.md"))
    with caplog.at_level(logging.DEBUG, logger="set_orch.paths"):
        result = lp.digest_dir
    assert result.endswith("/digest")
    assert any("digest" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# LineagePaths — rotated event file enumeration
# ---------------------------------------------------------------------------


def test_rotated_event_files_are_sorted_by_cycle(project):
    proj, rt = project
    cycles = [3, 1, 2, 10]
    for n in cycles:
        path = os.path.join(rt.orchestration_dir, f"orchestration-events-cycle{n}.jsonl")
        with open(path, "w") as fh:
            fh.write(f"cycle={n}\n")
    lp = LineagePaths(str(proj))
    files = lp.rotated_event_files
    cycle_order = [int(os.path.basename(p).split("cycle")[1].split(".")[0]) for p in files]
    assert cycle_order == sorted(cycles)


# ---------------------------------------------------------------------------
# LineagePaths — project-relative properties never depend on lineage
# ---------------------------------------------------------------------------


def test_project_relative_paths(project):
    proj, _ = project
    lp = LineagePaths(str(proj), lineage_id=LineageId("docs/spec-v1.md"))
    assert lp.directives_file == os.path.join(str(proj), "set", "orchestration", "directives.json")
    assert lp.config_yaml == os.path.join(str(proj), "set", "orchestration", "config.yaml")
    assert lp.review_learnings.endswith("review-learnings.jsonl")
    assert lp.review_findings.endswith("review-findings.jsonl")
    assert lp.coverage_report.endswith("spec-coverage-report.md")
    assert lp.coverage_history.endswith("spec-coverage-history.jsonl")
    assert lp.e2e_manifest_history.endswith("e2e-manifest-history.jsonl")
    assert lp.worktrees_history.endswith("worktrees-history.json")
    assert lp.specs_archive_dir.endswith(os.path.join("openspec", "changes", "archive"))


def test_per_worktree_helpers():
    wt = "/tmp/some-worktree"
    assert LineagePaths.e2e_manifest_for_worktree(wt) == "/tmp/some-worktree/e2e-manifest.json"
    assert LineagePaths.reflection_for_worktree(wt) == "/tmp/some-worktree/.set/reflection.md"


def test_artifacts_dir_for_change(project):
    proj, _ = project
    lp = LineagePaths(str(proj))
    assert lp.artifacts_dir_for_change("foundation-setup").endswith(
        os.path.join("openspec", "changes", "foundation-setup")
    )


# ---------------------------------------------------------------------------
# from_project() migration shim (task 0.8)
# ---------------------------------------------------------------------------


def test_from_project_resolves_live_lineage_and_logs_warning(project, caplog):
    proj, rt = project
    _write_state(rt, "docs/spec-v1.md")

    with caplog.at_level(logging.WARNING, logger="set_orch.paths"):
        lp = LineagePaths.from_project(str(proj))

    assert lp.lineage_id == "docs/spec-v1.md"
    assert lp.is_live is True
    assert any("from_project" in rec.message for rec in caplog.records)


def test_from_project_handles_missing_state(project, caplog):
    proj, _ = project
    with caplog.at_level(logging.WARNING, logger="set_orch.paths"):
        lp = LineagePaths.from_project(str(proj))
    assert lp.lineage_id is None


# ---------------------------------------------------------------------------
# Public API re-export (task 0.9)
# ---------------------------------------------------------------------------


def test_public_reexports():
    import set_orch

    assert set_orch.LineagePaths is LineagePaths
    assert set_orch.LineageId is LineageId
    assert callable(set_orch.slug)
    assert callable(set_orch.canonicalise_spec_path)
