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


def estimate_cost_usd(
    *,
    model: str | None,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_create_tokens: int,
) -> float:
    """Compute estimated USD cost from token counts.

    ``input_tokens`` here is the RAW input (uncached prefix delta),
    NOT the dashboard's "Input" column which sums input + cache_read.
    Anthropic's API returns ``input_tokens`` as the un-cached portion;
    the consumer's per-change state mirrors that semantics.

    Returns 0.0 if all token counts are zero.
    """
    rates = _resolve_rates(model)
    cost = (
        (input_tokens / 1_000_000.0) * rates.input
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
    """Return a per-component breakdown for diagnostic display."""
    rates = _resolve_rates(model)
    parts = {
        "input": round((input_tokens / 1_000_000.0) * rates.input, 4),
        "output": round((output_tokens / 1_000_000.0) * rates.output, 4),
        "cache_read": round((cache_read_tokens / 1_000_000.0) * rates.cache_read, 4),
        "cache_create": round((cache_create_tokens / 1_000_000.0) * rates.cache_create, 4),
    }
    parts["total"] = round(sum(parts.values()), 4)
    return parts
