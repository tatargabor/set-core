"""Cross-change regression detection — Tier 2 of fix-e2e-infra-systematic.

When an integration e2e gate fails, a subset of the failing tests may belong
to features that have already been merged. In that case, the current change
has touched shared code that broke a merged feature's tests — the correct
remediation is to fix the current change's scope, NOT to modify the merged
feature. Without this signal, the agent re-inspects its own code, fails to
find a bug there, and burns retry budget "fixing" tests it doesn't own.

This module provides:

  * `resolve_owning_change(test_path, test_title, state)` — best-effort
    mapping from a failing test to the change that owns it. Three strategies
    tried in order: (a) filename convention `<change>.spec.ts`, (b) `@REQ-...`
    tag in the test title, (c) `merged_scope_files` overlap when the current
    implementation touches a file another change brought into main.

  * `detect_cross_change_regressions(...)` — classify a list of failing tests
    into "own" vs "merged-others", plus the per-merged-change breakdown.

  * `build_regression_retry_context(...)` — render the prescriptive framing
    prepended to the agent's redispatch retry_context.

All three are pure functions — unit-testable without running the engine.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Iterable

logger = logging.getLogger(__name__)


_REQ_TAG_RE = re.compile(r"@?REQ-[A-Z0-9_.-]+")
_FILE_WITH_LINE_RE = re.compile(
    r"(?P<path>[^\s:]+\.spec\.\w+)(?::\d+)?"
)


@dataclass
class RegressionReport:
    """Structured result of cross-change-regression analysis."""

    # {test_id: owning_change_name}
    regressed_tests: dict
    # {owning_change_name: [test_id, ...]} — grouped view
    by_owning_change: dict
    # Tests from the CURRENT change
    own_failing_tests: list
    # Tests with unresolved ownership
    unknown_tests: list
    # Files touched by the current change that overlap any owning change's scope
    overlapping_files: dict  # {owning_change_name: [file, ...]}

    @property
    def has_cross_change_regression(self) -> bool:
        return bool(self.regressed_tests)


def _test_id(path: str, title: str = "") -> str:
    """Canonical test identifier used in the output map."""
    if title:
        return f"{path} › {title}"
    return path


def _extract_merged_changes(state: Any) -> list:
    """Return changes in `merged`/`done` status — the universe we resolve against.

    The state object shape is flexible: we accept anything with a `.changes`
    attribute containing items with `.name`, `.status`, `.requirements`, and
    `.extras` (all optional). Missing pieces are handled gracefully.
    """
    if state is None:
        return []
    changes = getattr(state, "changes", None) or []
    merged_statuses = {"merged", "done", "archived"}
    out = []
    for c in changes:
        status = getattr(c, "status", "") or ""
        if status in merged_statuses:
            out.append(c)
    return out


def resolve_owning_change(
    test_path: str, test_title: str, state: Any,
) -> str | None:
    """Best-effort: return the merged change name that owns `test_path`/`test_title`.

    Strategy (first hit wins):
      (a) filename convention: `tests/e2e/<change-name>.spec.ts` → `<change-name>`
      (b) REQ-id tag in the test title matches a merged change's `requirements`
      (c) `merged_scope_files` overlap: the test path appears in a merged
          change's recorded scope files

    Returns None when no strategy resolves a merged change.
    """
    merged = _extract_merged_changes(state)
    if not merged:
        return None

    # (a) filename → change name
    if test_path:
        base = os.path.basename(test_path)
        stem = base.split(".spec.")[0] if ".spec." in base else os.path.splitext(base)[0]
        stem_slug = stem.lower().replace("_", "-")
        for c in merged:
            name = (getattr(c, "name", "") or "").lower()
            if name and (name == stem_slug or name in stem_slug.split("-")):
                return getattr(c, "name", "")

    # (b) REQ-id tag in title
    if test_title:
        tags = _REQ_TAG_RE.findall(test_title)
        if tags:
            for c in merged:
                reqs = getattr(c, "requirements", None) or []
                # requirements may be list[dict] or list[str]
                req_ids = set()
                for r in reqs:
                    if isinstance(r, str):
                        req_ids.add(r)
                    elif isinstance(r, dict):
                        rid = r.get("id") or r.get("req_id") or ""
                        if rid:
                            req_ids.add(rid)
                    else:
                        rid = getattr(r, "id", "") or getattr(r, "req_id", "")
                        if rid:
                            req_ids.add(rid)
                for tag in tags:
                    normalized = tag.lstrip("@")
                    if normalized in req_ids:
                        return getattr(c, "name", "")

    # (c) merged_scope_files overlap
    if test_path:
        for c in merged:
            extras = getattr(c, "extras", None) or {}
            scope = extras.get("merged_scope_files") or []
            if test_path in scope or any(test_path.endswith(s) for s in scope):
                return getattr(c, "name", "")

    return None


def detect_cross_change_regressions(
    current_change_name: str,
    failing_tests: Iterable[tuple[str, str]],  # [(path, title), ...]
    state: Any,
    current_touched_files: Iterable[str] | None = None,
) -> RegressionReport:
    """Classify failing tests into own vs merged-others, grouped by owner.

    Args:
        current_change_name: The change whose integration gate is failing.
        failing_tests: Iterable of (test_path, test_title) — e.g. from
            findings.extract_e2e_findings, or raw parsing of Playwright output.
        state: Orchestrator state (used to enumerate merged changes).
        current_touched_files: Paths in the current change's diff — used to
            build `overlapping_files` grouping. Optional.

    Returns a RegressionReport. `has_cross_change_regression` is True when at
    least one failing test resolves to an ALREADY-MERGED change different from
    the current one.
    """
    regressed: dict[str, str] = {}
    by_owner: dict[str, list] = {}
    own: list[str] = []
    unknown: list[str] = []

    for path, title in failing_tests:
        tid = _test_id(path, title)
        owner = resolve_owning_change(path, title, state)
        if owner and owner != current_change_name:
            regressed[tid] = owner
            by_owner.setdefault(owner, []).append(tid)
        elif owner == current_change_name:
            own.append(tid)
        else:
            unknown.append(tid)

    overlapping: dict[str, list[str]] = {}
    if current_touched_files:
        merged = _extract_merged_changes(state)
        touched = list(current_touched_files)
        for owner_name in by_owner.keys():
            for c in merged:
                if getattr(c, "name", "") != owner_name:
                    continue
                extras = getattr(c, "extras", None) or {}
                scope = set(extras.get("merged_scope_files") or [])
                overlap = [f for f in touched if f in scope]
                if overlap:
                    overlapping[owner_name] = overlap
                break

    return RegressionReport(
        regressed_tests=regressed,
        by_owning_change=by_owner,
        own_failing_tests=own,
        unknown_tests=unknown,
        overlapping_files=overlapping,
    )


def build_regression_retry_context(
    current_change_name: str, report: RegressionReport,
) -> str:
    """Prescriptive block to prepend to the agent's redispatch retry_context.

    The framing is deliberately blunt so the agent doesn't try to fix tests
    that are not its responsibility. Keep this short — it's prepended to an
    already-long retry_context.
    """
    if not report.has_cross_change_regression:
        return ""

    owners = sorted(report.by_owning_change.keys())
    owners_list = ", ".join(f"`{o}`" for o in owners)

    lines: list[str] = [
        "⚠ **Cross-change regression detected.**",
        "",
        f"Your change (`{current_change_name}`) broke tests belonging to "
        f"already-merged feature(s): {owners_list}.",
        "These tests pass on `main`. Do NOT modify those features' code.",
        "Fix your change so it doesn't affect the overlapping surface — "
        "revert or reshape the overlapping edits, or achieve your goal via "
        "your own scope only.",
        "",
        "## Failing tests grouped by owning change",
        "",
    ]
    for owner in owners:
        tests = report.by_owning_change[owner]
        lines.append(f"- **`{owner}`** — {len(tests)} failing test(s):")
        for t in tests[:10]:
            lines.append(f"  - {t}")
        if len(tests) > 10:
            lines.append(f"  - ... and {len(tests) - 10} more")

    if report.overlapping_files:
        lines.append("")
        lines.append("## Files in your change that overlap a merged change's scope")
        lines.append("")
        for owner, files in report.overlapping_files.items():
            lines.append(f"- **`{owner}`**: {', '.join(f'`{f}`' for f in files[:20])}")

    if report.own_failing_tests:
        lines.append("")
        lines.append(
            f"## Your own failing tests ({len(report.own_failing_tests)})"
        )
        lines.append("")
        for t in report.own_failing_tests[:10]:
            lines.append(f"  - {t}")
        if len(report.own_failing_tests) > 10:
            lines.append(f"  - ... and {len(report.own_failing_tests) - 10} more")

    lines.append("")
    lines.append(
        "### Directive\n"
        "1. Revert or reshape the files listed above so merged tests pass again.\n"
        "2. If your feature genuinely needs a breaking change on shared code, "
        "open a follow-up change for that coordination — DO NOT sneak it into "
        "this change.\n"
        "3. Fix your own failing tests (if any) within your scope only."
    )
    return "\n".join(lines) + "\n"
