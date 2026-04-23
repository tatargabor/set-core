"""Test that classname-rewritten findings no longer block merge.

Craftbrew-run-20260421-0025 produced 47 classname-rewritten violations
across 3 changes, ~90% false-positive (agent used shadcn prefabs, split
into _components/, legitimately extended layouts). The design is a
guideline, not a literal template — byte-for-byte fidelity would mean
shipping v0's output unchanged. So we keep the check as informational
context for the agent but stop failing the gate on it.

Hard fail (blocks merge) remains for:
  - hardcoded-color (token_guard)
  - missing-route / missing-shared-file / decomposition-collapsed (skeleton)
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from set_project_web.v0_fidelity_gate import (
    GateOutcome,
    SkeletonViolation,
    _run_gate,
)


def _fake_manifest():
    return SimpleNamespace(
        routes=[SimpleNamespace(path="/admin", fidelity_threshold=None,
                                component_deps=[])],
        shared=[],
        shared_aliases={},
        deferred_design_routes=[],
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Scaffold a minimal consumer project so _run_gate can find v0-export / manifest."""
    proj = tmp_path / "project"
    (proj / "docs").mkdir(parents=True)
    (proj / "docs" / "design-manifest.yaml").write_text("routes: []\nshared: []\n")
    (proj / "v0-export").mkdir()
    return proj


@pytest.fixture
def wt(tmp_path: Path) -> Path:
    wt_dir = tmp_path / "wt"
    wt_dir.mkdir()
    return wt_dir


def _run_with_stubs(wt_path, project_path, *, skel=None, token=None, classname=None):
    """Invoke _run_gate with all the heavy pipeline steps stubbed."""
    with (
        patch("set_project_web.v0_manifest.load_manifest",
              return_value=_fake_manifest()),
        patch("set_project_web.v0_fidelity_gate.run_skeleton_check",
              return_value=skel or []),
        patch("set_project_web.v0_fidelity_gate.run_token_guard_check",
              return_value=token or []),
        patch("set_project_web.v0_fidelity_gate.run_classname_preservation_check",
              return_value=classname or []),
        patch("set_orch.verifier._get_merge_base", return_value="deadbeef"),
        patch("set_project_web.v0_fidelity_gate._read_pixel_diff_flag",
              return_value=False),
    ):
        return _run_gate(
            change_name="foo", wt_path=str(wt_path),
            project_path=project_path,
            change=SimpleNamespace(scope=""),
        )


def test_classname_only_violations_do_not_block(wt, project):
    """Sole classname-rewritten findings → gate still passes."""
    classname_finds = [
        SkeletonViolation(
            "classname-rewritten",
            "route /admin: only 3% of v0 className tokens preserved (v0=71 agent=9)",
        ),
    ]
    outcome = _run_with_stubs(wt, project, classname=classname_finds)
    assert outcome.status == "pass"
    # But the findings survive in the outcome for forensic visibility
    assert any(v.status == "classname-rewritten" for v in outcome.skeleton_violations)


def test_token_violation_still_blocks(wt, project):
    """hardcoded-color is real drift — keeps blocking."""
    outcome = _run_with_stubs(
        wt, project,
        token=[SkeletonViolation("hardcoded-color", "src/app/page.tsx:42 #ff0000")],
    )
    assert outcome.status == "fail"
    assert outcome.message == "design-drift"
    assert any(v.status == "hardcoded-color" for v in outcome.skeleton_violations)


def test_token_and_classname_together_blocks_with_both_in_context(wt, project):
    """When token fails, classname findings attach as context."""
    outcome = _run_with_stubs(
        wt, project,
        token=[SkeletonViolation("hardcoded-color", "src/app/page.tsx:42 #ff0000")],
        classname=[SkeletonViolation("classname-rewritten", "route /admin: 3%")],
    )
    assert outcome.status == "fail"
    statuses = {v.status for v in outcome.skeleton_violations}
    assert "hardcoded-color" in statuses
    assert "classname-rewritten" in statuses


def test_missing_route_blocks(wt, project):
    """Skeleton blocking violations take priority over classname."""
    outcome = _run_with_stubs(
        wt, project,
        skel=[SkeletonViolation("missing-route", "/admin missing")],
        classname=[SkeletonViolation("classname-rewritten", "route /admin: 3%")],
    )
    assert outcome.status == "fail"
    # Skeleton-blocking path returns early — classname not in output
    assert outcome.message == "skeleton-mismatch"


def test_no_violations_passes(wt, project):
    outcome = _run_with_stubs(wt, project)
    assert outcome.status == "pass"
    assert outcome.skeleton_violations == []


def test_classname_noop_branch_logs_info(
    wt, project, caplog: pytest.LogCaptureFixture,
):
    """Informational logging fires when only classname findings exist."""
    import logging
    with caplog.at_level(logging.INFO, logger="set_project_web.v0_fidelity_gate"):
        _run_with_stubs(
            wt, project,
            classname=[
                SkeletonViolation("classname-rewritten", "route /admin: 3%"),
                SkeletonViolation("classname-rewritten", "components/ui/input.tsx: 44%"),
            ],
        )
    info_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert any("classname-preservation finding(s) recorded" in m for m in info_msgs)
    assert any("not blocking merge" in m for m in info_msgs)
