"""USD cost estimation for Anthropic API token usage.

Rates per model (USD per million tokens, Anthropic pricing as of
2026-Q1). Cache rates assume the default 5-minute TTL — if a project
opts into 1-hour cache, multiply create by ~1.6x.

Cost helps surface the actual financial impact of agent runs in the
dashboard, where raw token counts hide the order-of-magnitude
differences between input / output / cache-read / cache-create.

Witnessed in micro-web-run-20260426-1704 contact-wizard-form: 9.8M
"input" looks like a lot, but 95% of that was cache_read at $1.50/M
— the actual cost was dominated by 240K output × $75/M (Opus) plus
377K cache_create × $18.75/M.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class _Rates:
    """USD per million tokens."""
    input: float
    output: float
    cache_read: float
    cache_create: float


# Rate table. Default fallback is conservative-Opus.
_RATES: dict[str, _Rates] = {
    # Opus 4.x
    "claude-opus-4-7": _Rates(input=15.00, output=75.00, cache_read=1.50, cache_create=18.75),
    "claude-opus-4-6": _Rates(input=15.00, output=75.00, cache_read=1.50, cache_create=18.75),
    "claude-opus-4-5": _Rates(input=15.00, output=75.00, cache_read=1.50, cache_create=18.75),
    "claude-opus-4": _Rates(input=15.00, output=75.00, cache_read=1.50, cache_create=18.75),
    # Sonnet 4.x
    "claude-sonnet-4-6": _Rates(input=3.00, output=15.00, cache_read=0.30, cache_create=3.75),
    "claude-sonnet-4-5": _Rates(input=3.00, output=15.00, cache_read=0.30, cache_create=3.75),
    "claude-sonnet-4": _Rates(input=3.00, output=15.00, cache_read=0.30, cache_create=3.75),
    # Haiku 4.x
    "claude-haiku-4-5-20251001": _Rates(input=1.00, output=5.00, cache_read=0.10, cache_create=1.25),
    "claude-haiku-4-5": _Rates(input=1.00, output=5.00, cache_read=0.10, cache_create=1.25),
    "claude-haiku-4": _Rates(input=1.00, output=5.00, cache_read=0.10, cache_create=1.25),
    # Bare alias fallbacks
    "opus": _Rates(input=15.00, output=75.00, cache_read=1.50, cache_create=18.75),
    "sonnet": _Rates(input=3.00, output=15.00, cache_read=0.30, cache_create=3.75),
    "haiku": _Rates(input=1.00, output=5.00, cache_read=0.10, cache_create=1.25),
}

_DEFAULT_RATES = _RATES["claude-opus-4-7"]


def _resolve_rates(model: str | None) -> _Rates:
    """Look up rates by model id, with prefix-match fallback."""
    if not model:
        return _DEFAULT_RATES
    m = model.lower().strip()
    if m in _RATES:
        return _RATES[m]
    # Prefix match (e.g., "claude-opus-4-7-20251101" → "claude-opus-4-7")
    for key, rates in _RATES.items():
        if m.startswith(key):
            return rates
    # Family fallback
    for family in ("opus", "sonnet", "haiku"):
        if family in m:
            return _RATES[family]
    return _DEFAULT_RATES


def _raw_input(input_tokens: int, cache_read_tokens: int) -> int:
    """Subtract cache reads from total input to get the un-cached
    portion that gets billed at the full input rate.

    The orchestrator's loop state stores ``input_tokens`` as the
    dashboard's "Input" column — i.e. RAW + cache_read combined (see
    ``lib/loop/state.sh:307``: ``input_tokens: ((.input_tokens // 0)
    + (.cache_read_tokens // 0))``). Subtracting cache_read recovers
    the actual raw-input portion. Clamped to zero — defensive against
    edge cases where the two counters drift (e.g. cache_read >
    aggregated input due to ordering).
    """
    return max(0, input_tokens - cache_read_tokens)


def estimate_cost_usd(
    *,
    model: str | None,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_create_tokens: int,
) -> float:
    """Compute estimated USD cost from token counts.

    ``input_tokens`` is treated as the dashboard "Input" column:
    raw + cache_read combined. We subtract cache_read internally so
    the input rate ($15/M Opus) is only applied to actually-uncached
    tokens. Without this subtraction, the cost was inflated 10-100×
    on cache-heavy sessions because cache_read got billed at the
    raw rate.

    Returns 0.0 if all token counts are zero.
    """
    rates = _resolve_rates(model)
    raw_input = _raw_input(input_tokens, cache_read_tokens)
    cost = (
        (raw_input / 1_000_000.0) * rates.input
        + (output_tokens / 1_000_000.0) * rates.output
        + (cache_read_tokens / 1_000_000.0) * rates.cache_read
        + (cache_create_tokens / 1_000_000.0) * rates.cache_create
    )
    return round(cost, 4)


def cost_breakdown(
    *,
    model: str | None,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_create_tokens: int,
) -> dict:
    """Return a per-component breakdown for diagnostic display.

    ``input`` reflects only the raw (uncached) portion of input —
    see ``estimate_cost_usd`` docstring for the input_tokens semantics.
    """
    rates = _resolve_rates(model)
    raw_input = _raw_input(input_tokens, cache_read_tokens)
    parts = {
        "input": round((raw_input / 1_000_000.0) * rates.input, 4),
        "output": round((output_tokens / 1_000_000.0) * rates.output, 4),
        "cache_read": round((cache_read_tokens / 1_000_000.0) * rates.cache_read, 4),
        "cache_create": round((cache_create_tokens / 1_000_000.0) * rates.cache_create, 4),
    }
    parts["total"] = round(sum(parts.values()), 4)
    return parts
