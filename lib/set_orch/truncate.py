"""Smart truncation utilities for LLM-bound text.

Never silently drops content. All truncation is visible via markers that
tell the LLM exactly what was omitted and how much.

Three strategies:
- smart_truncate: head + tail with "[truncated N lines]" marker
- smart_truncate_structured: same + preserves error/warning lines from middle
- truncate_with_budget: for named items (rules), returns omitted names
"""

from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)

# Default patterns that indicate important lines worth preserving
_DEFAULT_KEEP_PATTERNS = re.compile(
    r"(?i)\b(?:error|FAIL|CRITICAL|WARNING|panic|Traceback|AssertionError|TypeError|"
    r"ReferenceError|SyntaxError|ModuleNotFoundError|ImportError|ENOENT|EACCES|"
    r"Cannot find module|failed to compile|Build failed)\b"
)


def smart_truncate(
    text: str,
    max_chars: int,
    *,
    head_ratio: float = 0.3,
) -> str:
    """Truncate text preserving head + tail with a visible marker.

    Args:
        text: Input text.
        max_chars: Maximum output length (approximate — marker adds ~80 chars).
        head_ratio: Fraction of budget for the head (0.0-1.0). Default 0.3
            keeps 30% head, 70% tail — because error summaries are usually
            at the end but root causes are at the start.

    Returns:
        Original text if within budget, otherwise head + marker + tail.
    """
    if not text or len(text) <= max_chars:
        return text

    head_budget = int(max_chars * head_ratio)
    tail_budget = max_chars - head_budget

    head = text[:head_budget]
    tail = text[-tail_budget:]
    middle = text[head_budget:-tail_budget] if tail_budget else text[head_budget:]

    # Count omitted lines for the marker
    omitted_lines = middle.count("\n")
    omitted_chars = len(middle)

    marker = (
        f"\n\n... [truncated {omitted_lines} lines — {omitted_chars} chars omitted] ...\n\n"
    )

    return head + marker + tail


def smart_truncate_structured(
    text: str,
    max_chars: int,
    *,
    head_ratio: float = 0.3,
    keep_patterns: re.Pattern | None = None,
    max_kept_ratio: float = 0.2,
) -> str:
    """Truncate text preserving head + tail + important lines from the middle.

    Like smart_truncate, but scans the truncated middle section for lines
    matching error/warning patterns and preserves them.

    Args:
        text: Input text.
        max_chars: Maximum output length.
        head_ratio: Fraction of budget for the head.
        keep_patterns: Compiled regex for important lines. None uses defaults
            (error, FAIL, CRITICAL, WARNING, panic, Traceback, etc.).
        max_kept_ratio: Maximum fraction of budget for preserved middle lines.

    Returns:
        Original text if within budget, otherwise head + preserved lines + tail.
    """
    if not text or len(text) <= max_chars:
        return text

    if keep_patterns is None:
        keep_patterns = _DEFAULT_KEEP_PATTERNS

    head_budget = int(max_chars * head_ratio)
    tail_budget = max_chars - head_budget

    head = text[:head_budget]
    tail = text[-tail_budget:]
    middle = text[head_budget:-tail_budget] if tail_budget else text[head_budget:]

    # Find important lines in the middle
    kept_lines = []
    max_kept_chars = int(max_chars * max_kept_ratio)
    kept_chars = 0

    # Track approximate line number offset (head contains some lines)
    head_line_count = head.count("\n")

    for i, line in enumerate(middle.split("\n")):
        if keep_patterns.search(line):
            line_num = head_line_count + i + 1
            formatted = f"  > line {line_num}: {line.strip()}"
            if kept_chars + len(formatted) > max_kept_chars:
                break
            kept_lines.append(formatted)
            kept_chars += len(formatted) + 1  # +1 for newline

    omitted_lines = middle.count("\n")
    omitted_chars = len(middle)

    if kept_lines:
        kept_section = "\n".join(kept_lines)
        marker = (
            f"\n\n... [truncated {omitted_lines} lines — {omitted_chars} chars omitted"
            f", {len(kept_lines)} important line(s) preserved below] ...\n\n"
            f"{kept_section}\n\n"
        )
    else:
        marker = (
            f"\n\n... [truncated {omitted_lines} lines — {omitted_chars} chars omitted] ...\n\n"
        )

    return head + marker + tail


def truncate_with_budget(
    items: list[tuple[str, str]],
    max_chars: int,
) -> tuple[list[tuple[str, str]], list[str]]:
    """Select items that fit within a character budget.

    For budget-based truncation of named items (security rules, planning rules).
    Unlike blind `if total > N: break`, returns the names of omitted items
    so the caller can add an explicit marker.

    Args:
        items: List of (name, content) pairs.
        max_chars: Total character budget.

    Returns:
        (included_items, omitted_names) — included items that fit within
        budget, and names of items that didn't fit.
    """
    included: list[tuple[str, str]] = []
    omitted: list[str] = []
    total = 0

    budget_exceeded = False
    for name, content in items:
        if budget_exceeded or (total + len(content) > max_chars and included):
            budget_exceeded = True
            omitted.append(name)
        else:
            included.append((name, content))
            total += len(content)

    return included, omitted
