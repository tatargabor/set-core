"""Test-only path helpers that mirror the production `LineagePaths` resolver.

Production code uses ``LineagePaths(project).state_file`` etc., which resolves
paths under the XDG runtime location.  Most unit-test fixtures build a
disposable directory tree under ``tmp_path`` and prefer the legacy
project-root layout (state.json next to plan.json next to state-archive.jsonl).

These helpers return the project-root paths while naming the lineage concept
explicitly so the audit gate (and human readers) can grep for them.

Usage::

    from tests.lib.test_paths import state_file, state_archive
    state_path = state_file(project_dir)
    archive_path = state_archive(project_dir)

Section 15b.15 — keep all hardcoded orchestration filenames centralised in
this module so a future relocation only needs to edit here.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union

PathLike = Union[str, os.PathLike]


def _join(project: PathLike, name: str):
    """Return ``project / name`` as a ``Path`` when given a ``Path``, else ``str``.

    Tests call these helpers with both ``str`` and ``pathlib.Path`` and rely on
    type-preserving behaviour (``.write_text`` / ``.exists`` on Path inputs).
    """
    if isinstance(project, Path):
        return project / name
    return os.path.join(str(project), name)


def state_file(project: PathLike):           return _join(project, "orchestration-state.json")
def state_archive(project: PathLike):        return _join(project, "state-archive.jsonl")
def plan_file(project: PathLike):            return _join(project, "orchestration-plan.json")
def plan_domains_file(project: PathLike):    return _join(project, "orchestration-plan-domains.json")
def events_file(project: PathLike):          return _join(project, "orchestration-events.jsonl")
def state_events_file(project: PathLike):    return _join(project, "orchestration-state-events.jsonl")
def coverage_history(project: PathLike):     return _join(project, "spec-coverage-history.jsonl")
def e2e_manifest_history(project: PathLike): return _join(project, "e2e-manifest-history.jsonl")
def worktrees_history(project: PathLike):    return _join(project, "worktrees-history.json")
def directives_file(project: PathLike):      return _join(project, "orchestration-directives.yaml")
def coverage_report(project: PathLike):      return _join(project, "spec-coverage-report.json")
def review_learnings(project: PathLike):     return _join(project, "review-learnings.jsonl")
def review_findings(project: PathLike):      return _join(project, "review-findings.jsonl")
