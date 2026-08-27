"""USD cost estimation for Anthropic API token usage.

Cost helps surface the actual financial impact of agent runs in the
dashboard, where raw token counts hide the order-of-magnitude
differences between input / output / cache-read / cache-create.

Witnessed in a consumer E2E run: 9.8M "input" looks like a lot, but
95% of that was cache_read at a tenth of the input rate — the actual
cost was dominated by 240K output plus 377K cache_create.

## The table is a MEASUREMENT WITH A DATE, and it has already been wrong

Every figure below was read from platform.claude.com on the date in
``PRICES_VERIFIED_ON``. Before that pass this module priced Opus 4.5,
4.6 and 4.7 at $15/$75 — **three times their actual price** — because
those were the rates when it was written and nothing here recorded
when that was. Three call sites displayed the inflated number.

So: the multipliers and the per-model prices live here and only here,
the verification date is a constant rather than prose, and the cache
figures are DERIVED from the input price rather than typed in beside
it — a hand-typed cache rate is a second place for the same fact to
drift.

## Two lookups, deliberately different

``estimate_cost_usd`` and ``cost_breakdown`` keep their conservative
fallback: they exist to put a rough number on a finished run, and a
run that produced tokens did cost something, so a family guess beats
a blank.

``input_price_per_mtok`` has NO fallback and returns ``None`` for a
model it does not know. It backs surfaces that offer the reader a
figure to act on, where a guess derived from a different model's price
is worse than an honest absence — see the fleet tab's cache mark,
which shows tokens when this returns ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass


#: The date every figure below was read from platform.claude.com.
#: Bump it only when the prices are actually re-read, never on an edit.
PRICES_VERIFIED_ON = "2026-08-27"
PRICES_SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"

#: Prompt-cache pricing, as multipliers of a model's base input price.
#: Verified on PRICES_VERIFIED_ON against the source above.
CACHE_READ_MULTIPLIER = 0.1
CACHE_WRITE_5M_MULTIPLIER = 1.25
CACHE_WRITE_1H_MULTIPLIER = 2.0


@dataclass(frozen=True)
class _Rates:
    """USD per million tokens."""
    input: float
    output: float
    cache_read: float
    #: The FIVE-MINUTE cache write. The one-hour write is a different
    #: multiplier; ask for it with `cache_write_1h`.
    cache_create: float

    @property
    def cache_write_1h(self) -> float:
        return self.input * CACHE_WRITE_1H_MULTIPLIER


def _rates(*, input: float, output: float) -> _Rates:
    """Build a rate row, DERIVING the cache figures from the input price.

    Typing the cache rates in by hand is how a table gains a row whose
    cache price does not match its own input price. They are a fixed
    multiple; make them one.
    """
    return _Rates(
        input=input,
        output=output,
        cache_read=input * CACHE_READ_MULTIPLIER,
        cache_create=input * CACHE_WRITE_5M_MULTIPLIER,
    )


# Rate table. Verified on PRICES_VERIFIED_ON.
_RATES: dict[str, _Rates] = {
    # Fable / Mythos 5
    "claude-fable-5": _rates(input=10.00, output=50.00),
    "claude-mythos-5": _rates(input=10.00, output=50.00),
    # Opus 5 and the current 4.x line — all $5/$25, NOT the $15/$75 this
    # table carried for them until 2026-08-27.
    "claude-opus-5": _rates(input=5.00, output=25.00),
    "claude-opus-4-8": _rates(input=5.00, output=25.00),
    "claude-opus-4-7": _rates(input=5.00, output=25.00),
    "claude-opus-4-6": _rates(input=5.00, output=25.00),
    "claude-opus-4-5": _rates(input=5.00, output=25.00),
    # Retired Opus — these really are $15/$75, which is why the stale
    # figures above looked plausible for so long.
    "claude-opus-4-1": _rates(input=15.00, output=75.00),
    "claude-opus-4": _rates(input=15.00, output=75.00),
    # Sonnet
    "claude-sonnet-5": _rates(input=2.00, output=10.00),
    "claude-sonnet-4-6": _rates(input=3.00, output=15.00),
    "claude-sonnet-4-5": _rates(input=3.00, output=15.00),
    "claude-sonnet-4": _rates(input=3.00, output=15.00),
    # Haiku
    "claude-haiku-4-5-20251001": _rates(input=1.00, output=5.00),
    "claude-haiku-4-5": _rates(input=1.00, output=5.00),
    "claude-haiku-4": _rates(input=1.00, output=5.00),
    "claude-haiku-3-5": _rates(input=0.80, output=4.00),
    # Bare alias fallbacks — the CURRENT member of each family, because a
    # bare "opus" in a log is far more likely to be today's model than a
    # retired one.
    "opus": _rates(input=5.00, output=25.00),
    "sonnet": _rates(input=2.00, output=10.00),
    "haiku": _rates(input=1.00, output=5.00),
}

_DEFAULT_RATES = _RATES["claude-opus-5"]


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


def input_price_per_mtok(model: str | None) -> float | None:
    """The model's base input price, or ``None`` if the table does not know it.

    Deliberately without the family fallback ``_resolve_rates`` applies.
    A caller that shows the reader a figure to act on — the fleet tab's
    cache mark is the first — must be able to say "not priced" rather
    than quote a number derived from a different model. Getting Opus 5's
    cost from Opus 4.1's row would have been wrong by 3x.

    Matches an exact id first, then the longest prefix, so a dated
    snapshot resolves to its base id. A bare family alias is a table
    entry like any other and does resolve; an unknown id does not.
    """
    if not model:
        return None
    m = model.lower().strip()
    if m in _RATES:
        return _RATES[m].input
    matches = [k for k in _RATES if m.startswith(k)]
    if matches:
        return _RATES[max(matches, key=len)].input
    return None


def cache_rewrite_cost_usd(*, model: str | None, tokens: int, ttl_seconds: int) -> float | None:
    """What rewriting ``tokens`` of expired cache costs on this model.

    ``None`` when the model is not priced — the caller shows the token
    count instead. The TTL selects the multiplier: an entry written for
    an hour costs twice base input to rewrite, a five-minute one 1.25x.
    """
    price = input_price_per_mtok(model)
    if price is None:
        return None
    multiplier = CACHE_WRITE_1H_MULTIPLIER if ttl_seconds > 300 else CACHE_WRITE_5M_MULTIPLIER
    return round((tokens / 1_000_000.0) * price * multiplier, 4)
