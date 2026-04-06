"""E2E test skeleton generator — deterministic test structure from test-plan.json.

Reads TestPlanEntry objects, groups by REQ-ID, and calls the profile's
render_test_skeleton() to produce a .spec.ts file with all test blocks
pre-filled with // TODO: implement markers.

The agent's job reduces from "write tests" to "fill test bodies".
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .test_coverage import TestPlanEntry

logger = logging.getLogger(__name__)


def generate_skeleton(
    test_plan_entries: list[TestPlanEntry],
    change_name: str,
    worktree_path: str,
    profile,
) -> tuple[str, int]:
    """Generate a test skeleton file in the worktree.

    Args:
        test_plan_entries: Filtered entries for this change's requirements.
        change_name: kebab-case change name (used for file naming).
        worktree_path: Absolute path to the worktree.
        profile: ProjectType instance with render_test_skeleton().

    Returns:
        (spec_file_path, test_count) — path to generated file and number of test blocks.
        Returns ("", 0) if nothing was generated.
    """
    if not test_plan_entries:
        logger.debug("generate_skeleton: no test plan entries for %s — skipping", change_name)
        return ("", 0)

    if not hasattr(profile, "render_test_skeleton"):
        logger.debug("generate_skeleton: profile %s has no render_test_skeleton — skipping", type(profile).__name__)
        return ("", 0)

    # Determine output path
    spec_dir = Path(worktree_path) / "tests" / "e2e"
    spec_file = spec_dir / f"{change_name}.spec.ts"

    # Don't overwrite existing spec file (redispatch safety)
    if spec_file.exists():
        logger.info(
            "generate_skeleton: %s already exists — preserving agent work (redispatch)",
            spec_file,
        )
        return (str(spec_file), 0)

    # Group entries by REQ-ID
    grouped = group_entries_by_req(test_plan_entries)

    # Render via profile
    content = profile.render_test_skeleton(test_plan_entries, change_name)
    if not content:
        logger.warning("generate_skeleton: profile returned empty skeleton for %s", change_name)
        return ("", 0)

    # Count test blocks
    test_count = content.count("// TODO: implement")

    # Write file
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec_file.write_text(content, encoding="utf-8")

    logger.info(
        "Generated test skeleton: %s (%d test blocks, %d REQs)",
        spec_file, test_count, len(grouped),
    )

    return (str(spec_file), test_count)


def group_entries_by_req(
    entries: list[TestPlanEntry],
) -> dict[str, list[TestPlanEntry]]:
    """Group test plan entries by req_id, sorted alphabetically."""
    grouped: dict[str, list[TestPlanEntry]] = defaultdict(list)
    for entry in entries:
        grouped[entry.req_id].append(entry)
    return dict(sorted(grouped.items()))
