from __future__ import annotations

"""The store for binary content a reader pasted into an agent's terminal.

One endpoint, and a store with three bounds. It is its own module rather than
three more functions in `files.py` because the two guard OPPOSITE things:
`files.py` confines every path INTO a known project root, and this must confine
every path AWAY from one. A single function serving both policies would sit in
the most safety-relevant place in this repository and mean two things.

## What this module must never become

- **A project writer.** Nothing here may create a path inside a project tree or a
  worktree. Writing into a consumer's tree is the operation class the framework's
  safety work closed; a paste feature has no reason to reopen it, and a
  destination the caller can influence reopens it through a different door.
- **Something the browser can read back.** There is no GET. The agent reads these
  files from disk; nothing serves them over HTTP, so no path here can become a
  way to read one project's bytes from another's screen.
- **A record.** A pasted image is a consumer's content. The framework holds it
  long enough for an agent to open it and keeps no note of what it was: the log
  carries the SHAPE of the operation — type, size, outcome — and never the bytes,
  the caller's file name, or the stored name.
- **A file manager.** No list, no delete, no rename. One write, and a sweep that
  is nobody's request.
"""

import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple

from fastapi import APIRouter, HTTPException, Request

from ..paths import SET_TOOLS_DATA_DIR

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# The bounds, in ONE place. A second copy of any of these would drift the moment
# it was written — the same reason the baseline check asserts the thing rather
# than a hand-maintained list of paths.
# ---------------------------------------------------------------------------

MAX_ITEM_BYTES = 8 * 1024 * 1024
MAX_STORE_BYTES = 256 * 1024 * 1024
MAX_AGE_SECONDS = 7 * 24 * 60 * 60

# Sniffed from the leading bytes, never from the caller's declared type. A
# declared type is a claim about the REQUEST; this needs a statement about what
# landed on disk.
_MAGIC: Tuple[Tuple[bytes, str, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"GIF87a", "image/gif", ".gif"),
    (b"GIF89a", "image/gif", ".gif"),
)

ACCEPTED_TYPES = ("image/png", "image/jpeg", "image/gif", "image/webp")


def sniff_image_type(data: bytes) -> Optional[Tuple[str, str]]:
    """The (mime, extension) the BYTES are, or None if they are not an image.

    WebP needs both halves of its container header checked: `RIFF....WEBP`. A
    check on `RIFF` alone would accept a WAV file, which is the shape of every
    magic-number bug — a prefix that is shared by a family, treated as if it
    identified one member.
    """
    for magic, mime, ext in _MAGIC:
        if data.startswith(magic):
            return mime, ext
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


def store_root() -> Path:
    """Where pasted content lives — the framework's own per-user data root.

    Resolved through `paths.SET_TOOLS_DATA_DIR` rather than spelled out here, so
    that a machine using the XDG override or the legacy directory gets one
    answer, not two.
    """
    return Path(SET_TOOLS_DATA_DIR) / "paste"


def _entries(root: Path) -> list[Tuple[float, int, Path]]:
    out: list[Tuple[float, int, Path]] = []
    for p in root.iterdir():
        if not p.is_file():
            continue
        try:
            st = p.stat()
        except FileNotFoundError:
            continue
        out.append((st.st_mtime, st.st_size, p))
    return out


def sweep(root: Path, incoming: int = 0, now: Optional[float] = None) -> int:
    """Apply both bounds, computed from DISK, and return the bytes still stored.

    On use, not on a timer. A cleanup that only runs while a process is alive
    leaves entries behind precisely when the process died, which is when nobody
    is looking — and this repository has already paid for the general form of
    that: a long-lived service holds the code it started with.
    """
    now = time.time() if now is None else now
    if not root.is_dir():
        return 0
    kept: list[Tuple[float, int, Path]] = []
    for mtime, size, p in _entries(root):
        if now - mtime > MAX_AGE_SECONDS:
            _unlink(p, "expired")
            continue
        kept.append((mtime, size, p))
    total = sum(size for _, size, _ in kept)
    if total + incoming <= MAX_STORE_BYTES:
        return total
    for mtime, size, p in sorted(kept):
        _unlink(p, "ceiling")
        total -= size
        if total + incoming <= MAX_STORE_BYTES:
            break
    return total


def _unlink(p: Path, why: str) -> None:
    try:
        p.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        # Never silent: a store that cannot prune is a store that will fill.
        logger.warning("paste store could not remove an entry (%s): %s", why, exc.errno)
        return
    logger.info("paste store removed an entry: reason=%s", why)


@router.post("/api/fleet/paste")
async def store_paste(request: Request) -> dict:
    """Store one pasted image and answer with the path an agent can open.

    The body is the raw bytes. There is deliberately no field for a file name and
    no field for a destination: the name is derived from the content and the
    destination is decided here. A request cannot influence either, which is what
    keeps this from becoming a way to write into a project tree.
    """
    data = await request.body()
    size = len(data)

    if size > MAX_ITEM_BYTES:
        logger.info(
            "paste refused: rule=size bytes=%d limit=%d", size, MAX_ITEM_BYTES
        )
        raise HTTPException(
            status_code=413,
            detail=(
                f"the image is {size} bytes and the limit is {MAX_ITEM_BYTES} bytes"
            ),
        )

    sniffed = sniff_image_type(data)
    if sniffed is None:
        declared = request.headers.get("content-type", "")
        logger.info("paste refused: rule=type declared=%s bytes=%d", declared[:40], size)
        raise HTTPException(
            status_code=415,
            detail="only PNG, JPEG, GIF and WebP images are accepted",
        )
    mime, ext = sniffed

    root = store_root()
    root.mkdir(parents=True, exist_ok=True)
    total = sweep(root, incoming=size)
    if total + size > MAX_STORE_BYTES:
        logger.info(
            "paste refused: rule=ceiling bytes=%d ceiling=%d", size, MAX_STORE_BYTES
        )
        raise HTTPException(
            status_code=507,
            detail=(
                f"the paste store is full — its ceiling is {MAX_STORE_BYTES} bytes"
            ),
        )

    name = hashlib.sha256(data).hexdigest() + ext
    path = root / name
    if not path.exists():
        # Write beside, then rename: a reader's agent must never see a half file.
        tmp = root / (name + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, path)
    else:
        os.utime(path, None)

    logger.info("paste stored: type=%s bytes=%d outcome=ok", mime, size)
    return {"path": str(path), "bytes": size, "type": mime}
