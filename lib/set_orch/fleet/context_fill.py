"""How full a live agent's context window is, resolved from the model it RUNS.

The fleet payload already carries, per agent, the tokens of its last request and
the model that wrote it. This module turns those two into a fraction, and it is
the only place a context window size is stated.

## The window comes from the MEASURED model, never the recorded provider

Measured on the running dashboard: a live agent carried
`provider: {"recorded": false, "provider": null, "model": null}` while its
measured model was present. A provider-keyed lookup would have returned nothing
for that agent — and on a strip made of bars, nothing is read as *consumed
nothing*, which is the false-absence class rather than a visible gap.

The record is frequently absent; the measurement is not. It is also keyed on the
wrong thing: a window is a property of the MODEL, and one provider serves several
models with different windows.

## An unknown model is unmeasured, never a default

`resolve_window` returns `None` for a name it does not know, and every caller
must carry that through as an unmeasured mark. A default window would attach a
plausible wrong number to exactly the model a reader cannot check, and it would
do so silently. The fail direction is what makes the table safe: a new model
ships and reads `?` until this table learns it.

## Why the window rather than the compact threshold

The threshold is arguably the more actionable number — an agent running
`--autocompact 200k` against a 272 000 window compacts near 73 %, so a full bar
is never seen. It is still the wrong denominator here, because the threshold
lives in the provider's `args` and is reachable only through the RECORDED
provider, the source this module exists to avoid. One honest scale beats two
incomparable ones. See `design.md` of `fleet-context-fill`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "ContextFill",
    "WARNING_FRACTION",
    "CRITICAL_FRACTION",
    "band_for",
    "context_payload",
    "normalise_model",
    "resolve_window",
]

#: The bands, matching the values `usage/glm.py` already documents for its own
#: severity. No upstream states a severity for context fill, so this is
#: set-core's own opinion — and reusing the numbers means one screen teaches one
#: reading rather than two marks disagreeing about what amber means.
WARNING_FRACTION = 0.70
CRITICAL_FRACTION = 0.90

#: A gateway rewrites a model id into `anthropic-<provider-id>__<model-id>` —
#: measured against the local clodex endpoint, whose catalogue lists
#: `anthropic-openai-oauth__gpt-6-astra`. The transcript records whatever the
#: client asked for, so the prefix reaches this table and must come off before
#: any match is attempted.
_GATEWAY_PREFIX = re.compile(r"^anthropic-[a-z0-9_-]+__", re.IGNORECASE)

#: Markers for the million-token variants of an otherwise 200k model. Checked
#: BEFORE the family table, because `claude-opus-5[1m]` also matches `opus`.
_MILLION_MARKERS = ("[1m]", "-1m", "_1m", "(1m)")

#: Substring -> window. Ordered longest-first at match time so a specific entry
#: cannot be shadowed by a shorter one that happens to be a prefix of it.
#:
#: Every figure is sourced, because an unsourced constant here is a wrong
#: denominator nobody can audit:
#:   - `gpt-*` 272 000 — read from the clodex gateway's own `/v1/models`, which
#:     reports `context_window: 272000` for gpt-6-astra and its siblings.
#:   - `glm-*` 900 000 — `CLAUDE_CODE_MAX_CONTEXT_TOKENS` in this machine's
#:     `providers.json` for the glm provider.
#:   - `claude-*` 200 000 — the standard window; the 1M variants are handled
#:     above by marker rather than by a second row per model.
_WINDOWS: Dict[str, int] = {
    "gpt-6-astra": 272_000,
    "gpt-reserve": 272_000,
    "gpt-5.6": 272_000,
    "gpt-5.5": 272_000,
    "gpt-5.4": 272_000,
    "glm-": 900_000,
    "claude-": 200_000,
}

#: What a 1M-marked model resolves to.
_MILLION = 1_000_000


def normalise_model(model: Optional[str]) -> Optional[str]:
    """A model name reduced to what the table matches on.

    Lowercased and stripped of any gateway prefix. Returns `None` for a name
    that is missing or blank — an absent model is not a model called "".
    """
    if not model or not model.strip():
        return None
    return _GATEWAY_PREFIX.sub("", model.strip().lower())


def resolve_window(model: Optional[str]) -> Optional[int]:
    """The context window for a model, or `None` when it is not known.

    `None` is a legitimate answer and the ONLY safe one for an unknown name.
    Callers must render it as unmeasured; nothing here substitutes a default.
    """
    name = normalise_model(model)
    if name is None:
        return None

    if any(marker in name for marker in _MILLION_MARKERS):
        return _MILLION

    # Longest key first: `gpt-6-astra` must win over a shorter `gpt-` entry if
    # one is ever added, rather than depending on dict ordering to be lucky.
    for key in sorted(_WINDOWS, key=len, reverse=True):
        if key in name:
            return _WINDOWS[key]

    logger.debug("context window unknown for model %r (normalised %r)", model, name)
    return None


def band_for(fill: float) -> str:
    """Which band a fill falls in. One expression, so no two marks disagree."""
    if fill >= CRITICAL_FRACTION:
        return "critical"
    if fill >= WARNING_FRACTION:
        return "warning"
    return "normal"


@dataclass(frozen=True)
class ContextFill:
    """One agent's context fill, or the reason there is not one.

    `measured` is the only state carrying figures. The other states carry a
    reason instead, and never a zero: a zero window or a zero fill is a claim
    that the agent has consumed nothing, which is the most confident and least
    true thing this record could say.
    """

    state: str
    tokens: Optional[int] = None
    window: Optional[int] = None
    fill: Optional[float] = None
    model: Optional[str] = None
    band: Optional[str] = None
    reason: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        """The payload shape, with absent fields omitted rather than nulled."""
        out: Dict[str, Any] = {"state": self.state}
        for key in ("tokens", "window", "fill", "model", "band", "reason"):
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        return out


def context_payload(cache: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """`{"context": {...}}` for one agent, from its cache block.

    Always returns the key. This deliberately differs from `_cache_payload`,
    which omits itself when unmeasured: the header must COUNT the agents it
    could not measure, and a key that is absent cannot be counted. An omitted
    unmeasured agent is indistinguishable from an agent that does not exist.
    """
    if not cache:
        return {"context": ContextFill(
            state="unmeasured",
            reason="this agent has no cache record, so no token figure exists",
        ).as_dict()}

    tokens = cache.get("tokens")
    model = cache.get("model")

    if not isinstance(tokens, int) or tokens < 0:
        return {"context": ContextFill(
            state="unmeasured", model=model,
            reason="the cache record carries no usable token figure",
        ).as_dict()}

    window = resolve_window(model)
    if window is None:
        return {"context": ContextFill(
            state="unmeasured", tokens=tokens, model=model,
            reason=(f"no context window is known for model {model!r}" if model
                    else "the cache record names no model, so no window can be resolved"),
        ).as_dict()}

    # A context cannot exceed its own window, so a fill above 1.0 does not mean
    # a full agent — it means THIS WINDOW IS WRONG for this agent, and the only
    # honest answer is that it is not known.
    #
    # Measured 2026-09-08 on the live fleet: 3 of 7 agents came back above 1.0
    # (1.74, 2.14, 2.16), every one of them a million-token session whose
    # transcript records `claude-opus-5` with the `[1m]` marker dropped. The
    # marker is not recoverable — the process cmdline carries the same bare name
    # and sets no `CLAUDE_CODE_MAX_CONTEXT_TOKENS`.
    #
    # Reporting those as 214 % critical would put a red mark on nearly half the
    # fleet for a limit none of them is near, and a mark that cries wolf on its
    # first day is one nobody reads on its second. Raising the family default to
    # a million instead fails the OTHER way, which is worse: a genuine 190 000
    # token session would render as a calm 19 % in the moments before it
    # compacts. Unmeasured is the only direction that is merely uninformative.
    if tokens > window:
        return {"context": ContextFill(
            state="unmeasured", tokens=tokens, model=model,
            reason=(
                f"the token figure ({tokens:,}) exceeds the window resolved for "
                f"{model!r} ({window:,}), so that window is wrong for this agent — "
                "commonly a million-token variant whose model name does not say so"
            ),
        ).as_dict()}

    fill = tokens / window
    return {"context": ContextFill(
        state="measured", tokens=tokens, window=window,
        fill=round(fill, 4), model=model, band=band_for(fill),
    ).as_dict()}
