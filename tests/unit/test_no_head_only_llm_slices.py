"""Source-level audit: forbid new head-only `[:N]` slices on LLM-bound output.

See OpenSpec change: fix-retry-context-signal-loss.

Head-only truncation like `e2e_output[:2000]` drops the tail of subprocess
output, where assertion errors and stack traces live. When such truncated
text is passed into an LLM prompt (retry_context, replan_context, verify
prompt, etc.), the model receives only setup noise and cannot produce a
meaningful fix. Use `smart_truncate_structured` from lib/set_orch/truncate.py
instead — it preserves head + tail + error-matching lines.

This test fails if a new head-only slice of a stdout/stderr/output-bound
variable is added to one of the gate/dispatcher/verifier/merger files.
Cosmetic sites (CLI echo, memory recall fallback, planner debug file) are
explicitly allowlisted below.
"""

import os
import re
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]

# Files to audit. These are the files where LLM-bound output flows.
_AUDITED_FILES = [
    _ROOT / "lib/set_orch/verifier.py",
    _ROOT / "lib/set_orch/merger.py",
    _ROOT / "lib/set_orch/engine.py",
    _ROOT / "lib/set_orch/dispatcher.py",
    _ROOT / "modules/web/set_project_web/gates.py",
]

# Pattern: variable name ending in output/stdout/stderr/tail/text followed by
# [:N] slice (head-only truncation).
_HEAD_SLICE_RE = re.compile(
    r"\b(\w*(?:output|stdout|stderr|tail|text))\[:(\d+)\]",
    re.IGNORECASE,
)

# Allowlist: specific (file, line_contains) tuples where a head-only slice is
# intentional (cosmetic logging, not LLM-bound). Each entry must include a
# substring from the line so renames/reformats surface a review request.
_ALLOWLIST = [
    # merger.py: stderr snippet for error log — cosmetic logging, not LLM-bound
    ("merger.py", "merge_result.stderr[:300]"),
    ("merger.py", "merge_result.stdout[:500]"),
    ("merger.py", "merge_result.stderr[:500]"),
    ("merger.py", "result.stderr[:300]"),
    # merger.py: hash computation on truncated output — not LLM-bound
    ("merger.py", "hashlib.sha256(output[:2000]"),
    # engine.py: worktree remove error log
    ("engine.py", "rm_r.stderr[:200]"),
    # verifier.py: integration merge error log
    ("verifier.py", "merge_result.stderr[:300]"),
    # gates.py: e2e PASS path — no new failures, appended to a "no regressions"
    # message for human operators. Head-only is fine; the impl agent is not
    # invoked on the PASS path.
    ("gates.py", "+ e2e_output[:3000],"),
]


def _audit_file(path: Path) -> list[tuple[int, str, str, int]]:
    """Return list of (line_no, variable_name, slice_size, line_text) for
    head-only slices found in `path` that are NOT in the allowlist.
    """
    if not path.exists():
        return []
    offenders: list[tuple[int, str, str, int]] = []
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        for m in _HEAD_SLICE_RE.finditer(line):
            var = m.group(1)
            size = int(m.group(2))
            # Skip comments (common in docstrings / examples)
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'"):
                continue
            # Allowlist check
            file_name = path.name
            if any(
                file_name == f and snip in line for f, snip in _ALLOWLIST
            ):
                continue
            offenders.append((lineno, var, size, line.strip()))
    return offenders


def test_no_head_only_slices_on_llm_bound_output():
    """Fail if a head-only `[:N]` slice appears on an output/stdout/stderr
    variable in an audited file without being explicitly allowlisted.
    """
    all_offenders: list[str] = []
    for path in _AUDITED_FILES:
        offenders = _audit_file(path)
        for lineno, var, size, text in offenders:
            all_offenders.append(
                f"  {path.relative_to(_ROOT)}:{lineno} — `{var}[:{size}]`\n"
                f"    {text}"
            )

    assert not all_offenders, (
        "Head-only truncation on LLM-bound output detected. Use "
        "`smart_truncate_structured(var, N)` from lib/set_orch/truncate.py "
        "instead — it preserves head + tail + error-matching lines.\n\n"
        "If this is intentional (cosmetic logging, not LLM-bound), add the "
        "site to _ALLOWLIST in tests/unit/test_no_head_only_llm_slices.py.\n\n"
        "Offenders:\n" + "\n".join(all_offenders)
    )
