"""Test that retry budgets were raised to give agents more chances before giving up.

Context from craftbrew: verify_retry_count exhausted in 4 attempts, redispatch
max_iter=3 was too tight for non-trivial fixes (i18n key additions across 50
files in one round). Raising budgets so one bad LLM response doesn't doom a
change.
"""

from __future__ import annotations

from set_orch.engine import Directives


def test_max_verify_retries_default_raised():
    d = Directives()
    # Craftbrew post-fix: 4 → 6 so 5 consecutive bad verifies still get a shot
    assert d.max_verify_retries >= 6


def test_resume_retry_max_iter_values():
    # Read the code directly to assert the constants — these are inline
    # literals in resume_change, not dataclass fields.
    from pathlib import Path
    import re
    src = Path(__file__).resolve().parents[2] / "lib" / "set_orch" / "dispatcher.py"
    text = src.read_text()
    # Find the resume_change retry-context branch
    retry_block = re.search(
        r"if is_merge_retry:\s*\n\s*done_criteria = \"merge\"\s*\n\s*max_iter = (\d+)\s*\n\s*elif is_review_retry:\s*\n\s*done_criteria = \"test\"\s*\n\s*max_iter = (\d+)",
        text,
    )
    assert retry_block, "retry_ctx branch not found in dispatcher.py"
    merge_retries = int(retry_block.group(1))
    review_retries = int(retry_block.group(2))
    # Pre-fix values were 5/5/3. Post-fix: 7/7/5 minimum.
    assert merge_retries >= 7, f"merge retry budget too tight: {merge_retries}"
    assert review_retries >= 7, f"review retry budget too tight: {review_retries}"
