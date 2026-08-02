"""Stream the new lines of a file the project itself pointed at.

The transport half of `set_orch.status_follow`. That module decides WHETHER a path may be
followed; this one opens it and pushes what arrives.

**Server-sent events, deliberately.** The stream is one-way, text, and line-oriented, which is
exactly what SSE is, and the browser reconnects on its own. The alternative that was actually on
the table was routing this through a tool call — request/response, so a growing file has to be
chunked into calls, and every chunk travels through a model's context for a stream the browser
can receive directly. The model has no business in this path.

**Nothing is kept.** Lines are read, sent, and dropped: no cache, no file, no log entry carrying
content. The logging here counts bytes and lines and names error classes — the same rule
`project_status.py` follows, and it matters more here than anywhere else on this surface, because
an agent's log is the densest domain material a project has.

**Silence is never the report.** Every way this stream can end — the file vanishing, being
replaced, becoming unreadable, or the caller hitting a bound — is delivered as an event before
the stream closes. A dead follow and a quiet file look identical otherwise, and the reader most
likely mistakes the first for the second.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from .helpers import _resolve_project
from ..status_follow import decide

logger = logging.getLogger(__name__)

router = APIRouter()

#: How often the file is checked for new bytes. Fast enough to read as live, slow enough that an
#: idle stream costs nothing measurable.
POLL_SECONDS = 0.4

#: Most lines one stream will deliver. A bound, not a guess about usage: an unbounded stream is a
#: denial of service the framework built for itself, and the client is TOLD when it is reached.
MAX_LINES = 5000

#: Most lines delivered per poll. Caps a burst without dropping the stream — the remainder is
#: read on the next tick rather than discarded.
MAX_LINES_PER_TICK = 200

#: Longest single line delivered. A log line is a line; anything past this is a payload someone
#: embedded, and the truncation is announced in the event rather than done quietly.
MAX_LINE_CHARS = 8000

#: How long a stream may stay open with no client interest before it closes itself.
MAX_STREAM_SECONDS = 60 * 60


def _event(kind: str, payload: dict) -> str:
    """One SSE frame. `kind` is the event name; the payload is JSON on the data line."""
    return f"event: {kind}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _still_the_same_file(handle, path: Path) -> Optional[str]:
    """`None` while the open file is still the one the name points at, else the reason it is not.

    Asked of the OPEN HANDLE, not of the path, and that distinction is the whole function.

    The obvious implementation compares `stat(path)` taken at open time with `stat(path)` taken
    now, and it is wrong in a way that is easy to miss and was measured here rather than
    predicted: **inode numbers are recycled**. Deleting a file and immediately writing a new one
    under the same name handed back the identical `(st_dev, st_ino)` — a different file, an
    identical fingerprint. That is the remembered-PID mistake in another costume: an identifier
    that can be reissued is a proxy for the thing, not the thing.

    The handle is not a proxy. `fstat` on it describes the file we are actually reading, whatever
    happened to the name, and `st_nlink == 0` says that file has been unlinked — which cannot be
    faked by a later file reusing the number. The name is then consulted only to tell the two
    endings apart: gone, or replaced by something else.
    """
    try:
        open_st = os.fstat(handle.fileno())
    except OSError:
        return "file-gone"

    if open_st.st_nlink == 0:
        # The file we hold has been unlinked. Whether a NEW file now answers to the name decides
        # which of the two stories the reader is told.
        return "file-replaced" if path.exists() else "file-gone"

    try:
        named = path.stat()
    except OSError:
        return "file-gone"

    if (named.st_dev, named.st_ino) != (open_st.st_dev, open_st.st_ino):
        # An atomic replace: the old file still has another link somewhere, so nlink stayed up.
        return "file-replaced"
    return None


async def _follow(path: Path, project: str) -> AsyncIterator[str]:
    """Yield SSE frames for lines appended to `path` after this call. Never raises."""
    started = asyncio.get_event_loop().time()
    sent = 0
    truncated = 0

    try:
        handle = open(path, "r", encoding="utf-8", errors="replace")
    except OSError as exc:
        yield _event("end", {"reason": "unreadable", "detail": type(exc).__name__})
        return

    try:
        # Start at the END. Following is about now; replaying a file that has grown to hundreds
        # of kilobytes pushes the interesting line off the screen before anyone reads it.
        handle.seek(0, os.SEEK_END)
        yield _event("open", {"from": "end"})

        pending = ""
        while True:
            if sent >= MAX_LINES:
                yield _event("end", {"reason": "line-budget", "lines": sent})
                return
            if asyncio.get_event_loop().time() - started > MAX_STREAM_SECONDS:
                yield _event("end", {"reason": "max-duration", "lines": sent})
                return

            try:
                chunk = handle.read()
            except OSError as exc:
                yield _event("end", {"reason": "unreadable", "detail": type(exc).__name__})
                return

            if chunk:
                pending += chunk

            # Drain whole lines from the buffer, capped per tick.
            #
            # The drain happens whether or not this read returned bytes, and that is the point:
            # a burst larger than the cap leaves a remainder behind, and an earlier version only
            # looked at the remainder when NEW bytes arrived. A file that went quiet right after
            # its burst therefore kept its last lines forever — the reader saw the stream stop
            # mid-thought with nothing to say it had.
            #
            # `split("\n", 1)` also removes the need to locate where the cap fell. Searching for
            # that position with `lines.index(line)` finds the FIRST equal line, and repeated
            # lines are ordinary in a log — a heartbeat, the same tool twice — so the buffer
            # would rewind and re-deliver everything between.
            delivered = 0
            while delivered < MAX_LINES_PER_TICK and "\n" in pending:
                line, pending = pending.split("\n", 1)
                if not line:
                    continue
                if len(line) > MAX_LINE_CHARS:
                    truncated += 1
                    yield _event("line", {"text": line[:MAX_LINE_CHARS], "truncated": True})
                else:
                    yield _event("line", {"text": line})
                delivered += 1
                sent += 1
                if sent >= MAX_LINES:
                    break
            if delivered:
                continue  # more may be buffered, or may have arrived while we were sending

            # Nothing to send: check the file we HOLD is still the one the name points at.
            gone = _still_the_same_file(handle, path)
            if gone is not None:
                yield _event("end", {"reason": gone, "lines": sent})
                return

            await asyncio.sleep(POLL_SECONDS)
    except asyncio.CancelledError:
        # The client went away. Not an error, and nothing to report to a socket that is closed.
        raise
    finally:
        handle.close()
        # Shape only — counts and a name. Never a line.
        logger.info(
            "status follow: stream closed for %s (%d line(s) sent, %d truncated)",
            project, sent, truncated,
        )


@router.get("/api/{project}/project-status/follow")
async def follow_declared_path(
    project: str,
    command: str = Query(..., description="the command whose answer declared the path"),
    path: str = Query(..., description="the path, exactly as the answer holds it"),
):
    """Follow a file the project's current answer names through a follow-declared field.

    The refusal is an HTTP error rather than an event stream that immediately ends: nothing was
    opened, so there is no stream to speak of, and a caller that gets 200 with a closing frame is
    one refactor away from treating a refusal as an empty log.
    """
    project_path = _resolve_project(project)
    decision = decide(project_path, command, path)

    if not decision.ok:
        status = 400 if decision.error_class in ("bad-command", "not-followable") else 404
        if decision.error_class == "outside-project":
            status = 403
        logger.info("status follow: refused for %s — %s", project, decision.error_class)
        raise HTTPException(status, {
            "error": decision.error, "errorClass": decision.error_class,
        })

    return StreamingResponse(
        _follow(decision.path, project),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",  # so a proxy in front of us does not hold the frames
        },
    )
