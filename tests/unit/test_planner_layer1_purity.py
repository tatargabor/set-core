"""Tests for arch-cleanup-pre-model-config: Layer-1 purity in planner.py.

The planner is Layer 1 (orchestration core) and must not contain
references to web/Layer-2 specific tokens (vitest, prisma, v0-export,
mocha.config, jest.config) in production code paths. Comments and
docstrings explaining the layer rule are permitted.
"""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))


# Match the FILE / PATH / EXPORT-NAME references that prove a stack-specific
# detection is happening in Layer 1 — not the bare framework names. Bare
# "vitest"/"prisma" strings are permitted (universal backstop prefix list,
# scope-text scan keywords, etc.); the Layer rule targets concrete
# filesystem and import-path references.
_LAYER2_TOKEN_RE = re.compile(
    r"vitest\.config|prisma\.schema|prisma/schema|v0-export/|jest\.config|mocha\.config|\.mocharc"
)


def test_planner_py_has_no_layer2_tokens_in_production_code():
    """planner.py must contain zero matches of Layer-2 detection tokens
    outside of comments and docstrings.

    The check walks the file line-by-line and treats lines that:
      - start with `#` (after stripping leading whitespace)         → comment
      - are inside a triple-quoted block delimited by `\"\"\"`      → docstring
    as exempt. Any other line containing a match is a violation.
    """
    planner_path = (
        Path(__file__).resolve().parents[2] / "lib" / "set_orch" / "planner.py"
    )
    assert planner_path.is_file(), f"planner.py not found at {planner_path}"

    in_docstring = False
    violations: list[tuple[int, str]] = []

    for lineno, raw in enumerate(planner_path.read_text().splitlines(), start=1):
        line = raw.strip()
        # Track triple-quoted docstring blocks. Account for opening+closing on
        # the same line (e.g. one-liner docstrings).
        triple_count = line.count('"""') + line.count("'''")
        was_in_docstring = in_docstring
        if triple_count % 2 == 1:
            in_docstring = not in_docstring

        # Skip if comment, in-docstring at start of line, or transitioning.
        if line.startswith("#"):
            continue
        if was_in_docstring or in_docstring:
            continue

        if _LAYER2_TOKEN_RE.search(line):
            violations.append((lineno, raw))

    assert not violations, (
        "Layer-1 purity violation in lib/set_orch/planner.py — "
        "the following lines reference Layer-2 tokens "
        "(vitest|prisma|v0-export|mocha.config|jest.config) outside of "
        "comments or docstrings. Move the detection through a ProjectType "
        "hook (detect_test_framework / detect_schema_provider / "
        "get_design_globals_path).\n\n"
        + "\n".join(f"  L{ln}: {body}" for ln, body in violations)
    )
