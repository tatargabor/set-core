"""How warm a session's prompt cache still is, read from the transcript.

A fleet tab reports whether an agent is running. It says nothing about what it
costs to type into it — and that swings by a factor of twenty: a live prompt
cache is read at 0.1x the base input price, an expired one is rewritten at 2x.
Measured on one machine on 2026-08-27, live sessions held between 15 044 and
195 889 tokens, so one keystroke cost between $0.008 and $1.96.

## The measurement already exists; this module only reads it

Every assistant record the runtime writes carries a `usage` block with
`cache_read_input_tokens`, `cache_creation_input_tokens` and a `cache_creation`
breakdown naming which lifetime was written. The record's own `timestamp` is the
moment its request STARTED, which is exactly the reference an expiry needs.

No hook, no wrapper, no second store. A second place for this fact would be a
place that can disagree with the transcript, go missing, or need migrating — and
it would be blind to any session that started before it was installed, which is
the session a reader is most likely to be looking at.

## The lifetime is READ, never assumed

Five minutes is the API's default; one hour is what this runtime currently
requests. Both are legal and the choice is per-request, so a constant would be
right until the day it silently was not — and the failure would be invisible,
every tab simply wrong about when it goes cold. It costs one dictionary lookup
to take it from the record instead.

## Absent is not zero

A session with no transcript, no usage record, or an unreadable file has NO
cache state — not a zero-token one. The two carry opposite meanings: a
zero-size, long-expired cache reads as "cold, cheap to restart", while the truth
is "this seat was never measured". Callers must be able to tell them apart, so
absence is `None` all the way to the surface.

## Reading backwards

Transcripts reach megabytes and this runs per agent per poll. Reading forward
would make the fleet endpoint's cost scale with total transcript size, so the
scan starts at the end of the file and stops at the first usage block it finds.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from ..cost import cache_rewrite_cost_usd

logger = logging.getLogger(__name__)

__all__ = ["CacheHeat", "read_cache_heat"]

#: Bytes read per step when walking a transcript backwards. Large enough that a
#: normal final record lands in the first chunk, small enough that a huge file
#: costs one seek rather than a full read.
_CHUNK = 64 * 1024

#: Stop after this much of the tail. A transcript whose last usage record is
#: further back than this is answered as unmeasured rather than by reading the
#: whole file: the point of the field is to be cheap, and an absence is a legal
#: answer here in a way a wrong number never is.
_MAX_TAIL = 4 * 1024 * 1024

#: What the runtime calls the two lifetimes, and how long each lasts.
_TTL_SECONDS = {
    "ephemeral_5m_input_tokens": 300,
    "ephemeral_1h_input_tokens": 3600,
}


@dataclass(frozen=True)
class CacheHeat:
    """One session's prompt-cache state, as of its last request.

    `started_at` is when that request BEGAN, which is what the entry's lifetime
    is measured from — generation time counts against it. A session mid-turn
    therefore reads slightly colder than it is, because its record is written
    when the response completes. The error is bounded by turn length and runs in
    the safe direction.
    """

    #: When the last request started (UTC).
    started_at: datetime
    #: cache_read + cache_creation of that request.
    tokens: int
    #: The lifetime that request wrote, in seconds — from the record.
    ttl_seconds: int
    #: The model that wrote it, or None if the record did not name one.
    model: Optional[str]
    #: USD to rewrite this cache once expired, or None if the model is not priced.
    rewrite_usd: Optional[float]

    def seconds_remaining(self, now: Optional[datetime] = None) -> float:
        """Seconds before the entry expires; zero once it has."""
        moment = now or datetime.now(timezone.utc)
        elapsed = (moment - self.started_at).total_seconds()
        return max(0.0, self.ttl_seconds - elapsed)

    def cooled_fraction(self, now: Optional[datetime] = None) -> float:
        """How far the cooling has run: 0.0 at the request, 1.0 at expiry.

        Clamped at both ends. A negative elapsed time — a clock that moved, a
        record from the future — reads as fresh rather than as a negative bar.
        """
        if self.ttl_seconds <= 0:
            return 1.0
        moment = now or datetime.now(timezone.utc)
        elapsed = (moment - self.started_at).total_seconds()
        return max(0.0, min(1.0, elapsed / self.ttl_seconds))

    def is_cold(self, now: Optional[datetime] = None) -> bool:
        """Whether the lifetime has elapsed.

        ONE condition, so the full bar, the red name and the price on a tab
        cannot disagree about it.
        """
        return self.cooled_fraction(now) >= 1.0


def _tail_lines(path: str) -> list[str]:
    """The file's lines, last first, without reading what comes before them."""
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        # The SHAPE, not the path: a transcript path carries the project slug,
        # and a consumer's project name must not reach a log line. Same rule
        # `db_safety.py` follows when it logs a URL's scheme and nothing else.
        logger.debug("cache heat: cannot stat transcript (%s)", type(exc).__name__)
        return []
    if size == 0:
        return []

    try:
        with open(path, "rb") as fh:
            read = 0
            buf = b""
            while read < size and read < _MAX_TAIL:
                step = min(_CHUNK, size - read)
                read += step
                fh.seek(size - read)
                buf = fh.read(step) + buf
                # Every line but the first in `buf` is whole; the first may be
                # truncated by the chunk boundary, so it is held back until the
                # next step unless we have reached the start of the file.
                lines = buf.split(b"\n")
                whole = lines if read >= size else lines[1:]
                out = [ln.decode("utf-8", "replace") for ln in reversed(whole) if ln.strip()]
                if out:
                    return out
            return []
    except OSError as exc:
        logger.debug("cache heat: cannot read transcript (%s)", type(exc).__name__)
        return []


def _heat_from_record(record: dict) -> Optional[CacheHeat]:
    """One transcript record turned into cache state, or None if it is not one."""
    usage = (record.get("message") or {}).get("usage")
    if not isinstance(usage, dict):
        return None

    read_tokens = usage.get("cache_read_input_tokens")
    write_tokens = usage.get("cache_creation_input_tokens")
    if read_tokens is None and write_tokens is None:
        return None
    tokens = int(read_tokens or 0) + int(write_tokens or 0)
    if tokens <= 0:
        # A request that neither read nor wrote a cache leaves nothing to be
        # warm about. Reporting a zero-token cache would render as "cold and
        # free", which is a claim; there is nothing here to make a claim about.
        return None

    creation = usage.get("cache_creation")
    ttl_seconds = None
    if isinstance(creation, dict):
        # Whichever bucket carries tokens names the lifetime that was written.
        # Longest first, so a request that wrote both is described by the one
        # that actually keeps the entry alive.
        for key in ("ephemeral_1h_input_tokens", "ephemeral_5m_input_tokens"):
            if creation.get(key):
                ttl_seconds = _TTL_SECONDS[key]
                break
    if ttl_seconds is None:
        # A read-only turn writes nothing, so it names no lifetime — but the
        # read refreshed an entry whose lifetime was set by an earlier write.
        # Absent that record, the API's own default is the honest floor: it is
        # the shorter of the two, so it under-states how long the cache lives
        # rather than promising warmth that may already be gone.
        ttl_seconds = _TTL_SECONDS["ephemeral_5m_input_tokens"]

    raw_time = record.get("timestamp")
    if not isinstance(raw_time, str):
        return None
    try:
        started_at = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
    except ValueError:
        # Length only. A timestamp is not domain data, but this path also fires
        # on a malformed record, and "log the shape" is cheaper to keep than to
        # re-decide each time.
        logger.debug("cache heat: unparseable timestamp (%d chars)", len(raw_time))
        return None
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)

    model = (record.get("message") or {}).get("model")
    model = model if isinstance(model, str) else None

    return CacheHeat(
        started_at=started_at,
        tokens=tokens,
        ttl_seconds=ttl_seconds,
        model=model,
        rewrite_usd=cache_rewrite_cost_usd(
            model=model, tokens=tokens, ttl_seconds=ttl_seconds,
        ),
    )


def read_cache_heat(transcript_path: Optional[str]) -> Optional[CacheHeat]:
    """This session's cache state, or None when it was not measured.

    None covers every way of not knowing — no path, no file, no usage record in
    the tail, an unreadable file, a malformed final line — because the caller's
    question is "can I show a figure for this seat", and every one of those
    answers it the same way: no.
    """
    if not transcript_path:
        return None
    for line in _tail_lines(transcript_path):
        try:
            record = json.loads(line)
        except (ValueError, TypeError):
            # A truncated final line is ordinary: the file is appended to while
            # this reads it. Skip to the record before it.
            continue
        if not isinstance(record, dict):
            continue
        heat = _heat_from_record(record)
        if heat is not None:
            return heat
    return None
