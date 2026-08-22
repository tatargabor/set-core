from __future__ import annotations

"""Reading and writing ONE file of a project the fleet screen knows.

Three endpoints and one guard, and the guard is the reason this module exists as
its own file rather than as three more functions in `fleet.py`: it is the only
place in this repository that writes into a project tree at a person's request,
and a guard that is easy to find is a guard somebody can check.

## Why the ROOT and not the project name

`_resolve_project(name)` reads the registry (`~/.config/set-core/projects.json`).
The fleet screen does not: it is built from process discovery, the messaging
registry AND the registry, so it shows projects the registry has never heard of.
Measured 2026-08-22 — of four projects on the screen, two were absent from the
registry. Resolving by registry name would therefore refuse a project the reader
is looking at, which is the divergence `fleet.py:_known_roots` already warns
about in its own words: *the rule is what the screen shows*.

So these endpoints take a root, `realpath` it, and require it to be one of the
roots the screen itself is built from — the same two refusals, from the same
function, as starting an agent.

## What this module must never become

- **A cache.** Every request goes to disk. A consumer's source is the consumer's
  domain: set-core may display it and persists none of it (`CLAUDE.md`, External
  Project Confidentiality). Nothing here writes content anywhere but back into
  the file the person edited.
- **A file manager.** No create, no delete, no rename, no mkdir. One file, read
  or written, and nothing else.
- **A merge tool.** A file that changed underneath the caller is REFUSED. On this
  screen the other writer is an agent running flat out, and a merge that goes
  wrong destroys its work silently.
"""

import hashlib
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .fleet import _known_roots

logger = logging.getLogger(__name__)

router = APIRouter()

# ─── Limits, stated in one place because they are stated to callers ──────────

#: How many paths a listing may carry. A tree larger than this is answered
#: truncated AND says so — see `list_files`.
MAX_FILES = 20_000

#: The largest file this will serve or accept. Beyond it the answer is a refusal
#: naming the size, never a truncated prefix: a prefix looks like a whole file.
MAX_BYTES = 2 * 1024 * 1024

#: Directories the non-git fallback never walks into. Kept short and boring —
#: it is a fallback, not a second ignore-rule engine.
_SKIP_DIRS = {
    ".git", "node_modules", ".next", "dist", "build", "__pycache__",
    ".venv", "venv", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "target", ".turbo", ".cache", "coverage", ".playwright",
}

#: The one refusal used for everything outside a known root.
#:
#: Deliberately identical for a path that exists and one that does not. A message
#: that distinguished them would turn this endpoint into a way of asking whether
#: an arbitrary file exists on the machine — and it would do it politely, one
#: request at a time, which is exactly how such a hole stays unnoticed.
_DENIED = "access denied"


def _known_root(raw: str) -> Path:
    """The project root for a request, or the refusal.

    The same two refusals as `fleet_start_agent`, reusing the same
    `_known_roots()` rather than a second check: a directory this screen may
    start an agent in and one it may open a file in are the same set, and two
    checks meant to agree drift.
    """
    root = os.path.realpath(os.path.expanduser(raw or ""))
    if not os.path.isdir(root):
        raise HTTPException(status_code=400, detail=f"no such directory: {raw}")
    if root not in _known_roots():
        raise HTTPException(
            status_code=400,
            detail=f"{root} is not a project this screen knows; register it first",
        )
    return Path(root)


def _confine(root: Path, rel: str) -> Path:
    """Resolve `rel` under `root` and refuse anything that lands outside it.

    Two things make this correct rather than merely careful, and both are
    failures this repository has already met in other forms:

    - **The check is on the RESOLVED path.** A symbolic link is exactly how a
      confined-looking path reaches an unconfined place, so `..`-scanning the
      request string (the `server.py:159` shape) passes a link straight through.
      `Path.resolve()` follows links; the comparison happens after.
    - **The refusal says nothing.** Same status, same text, whether the target
      exists, is a directory, or was never there — see `_DENIED`.

    The root itself is resolved too: a project whose root is reached through a
    link would otherwise fail its own containment check.
    """
    if not rel or rel.startswith("/"):
        raise HTTPException(status_code=403, detail=_DENIED)
    resolved_root = root.resolve()
    try:
        candidate = (resolved_root / rel).resolve()
    except (OSError, RuntimeError):
        # A resolution that cannot complete — a symlink loop, a path too long —
        # is refused with the same answer as one that escapes. It is not an
        # invitation to try a variation.
        raise HTTPException(status_code=403, detail=_DENIED) from None
    if not candidate.is_relative_to(resolved_root):
        raise HTTPException(status_code=403, detail=_DENIED)
    return candidate


def _identity(data: bytes) -> str:
    """The identity of exactly these bytes — what a later write is checked against.

    A hash and not an mtime: two writes inside one second are indistinguishable
    by mtime, and the other writer here is an agent running flat out.
    """
    return hashlib.sha256(data).hexdigest()


def _git_files(root: Path) -> Optional[List[str]]:
    """The project's own list of its files, or `None` if this is not a repo.

    `--cached --others --exclude-standard`: what git tracks, plus what exists but
    is not tracked yet, minus what the project's ignore rules exclude. The middle
    term is the one that matters on this screen — a file an agent wrote a minute
    ago is exactly the file a reader wants to open, and it is not committed.
    """
    if not (root / ".git").exists():
        return None
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=str(root), capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("files: git ls-files failed in %s: %s", root, exc)
        return None
    if out.returncode != 0:
        logger.warning("files: git ls-files exited %s in %s", out.returncode, root)
        return None
    return [line for line in out.stdout.splitlines() if line]


def _walked_files(root: Path, cap: int) -> List[str]:
    """The fallback for a project that is not a git repository.

    A bounded walk that skips the usual heavy directories. It is deliberately
    dumber than git: this is the case where the project has no ignore rules to
    honour, so guessing at more of them would only hide files.
    """
    found: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), root)
            found.append(rel)
            if len(found) > cap:
                return found
    return found


@router.get("/api/fleet/files")
def list_files(root: str) -> Dict[str, Any]:
    """Every file of one project, and whether the answer is complete.

    `truncated`, `cap` and `total` are returned together on purpose. A list cut
    to its cap and served as a plain array reads as the whole project — the
    false-absence shape: the reader concludes a file is not there when the answer
    simply stopped. So the answer states its own limit.

    `source` says which of the two producers ran. "no files" from a directory
    that is not a repository and "no files" from an empty repository are
    different facts, and a caller that cannot tell them apart will debug the
    wrong one.
    """
    project_root = _known_root(root)
    tracked = _git_files(project_root)
    source = "git"
    if tracked is None:
        source = "walk"
        tracked = _walked_files(project_root, MAX_FILES)
    total = len(tracked)
    truncated = total > MAX_FILES
    return {
        "root": str(project_root),
        "source": source,
        "files": sorted(tracked[:MAX_FILES]),
        "total": total,
        "cap": MAX_FILES,
        "truncated": truncated,
    }


@router.get("/api/fleet/files/content")
def read_file(root: str, path: str) -> Dict[str, Any]:
    """One file's text, with the identity of the bytes actually served."""
    project_root = _known_root(root)
    target = _confine(project_root, path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="no such file")
    size = target.stat().st_size
    if size > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"file is {size} bytes; this view serves at most {MAX_BYTES}",
        )
    data = target.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        # No partial content, and no lossy decode. A file half-rendered as
        # mojibake looks like a file, and somebody will eventually save it back.
        raise HTTPException(status_code=415, detail="not a text file") from None
    return {
        "path": path,
        "content": text,
        "identity": _identity(data),
        "bytes": size,
    }


class WriteBody(BaseModel):
    root: str
    path: str
    content: str
    #: The identity the caller last read. Required — a write with no idea what it
    #: is replacing is exactly the write this endpoint exists to refuse.
    identity: str


@router.put("/api/fleet/files/content")
def write_file(body: WriteBody) -> Dict[str, Any]:
    """Write one file back, but only if nobody else changed it meanwhile.

    The order is the whole guarantee: confine, then read what is on disk NOW,
    then compare, then replace atomically. Comparing against anything the caller
    supplied about the old content — a length, a timestamp — would be trusting
    the party that is about to overwrite.
    """
    project_root = _known_root(body.root)
    target = _confine(project_root, body.path)
    if not target.is_file():
        # Not re-created. A deletion is an act by somebody — an agent, a merge, a
        # person — and writing the file back would undo it silently.
        raise HTTPException(status_code=404, detail="no such file")

    current = target.read_bytes()
    if _identity(current) != body.identity:
        raise HTTPException(
            status_code=409,
            detail="the file changed on disk since it was read; nothing was written",
        )

    data = body.content.encode("utf-8")
    # A temp file in the SAME directory, then replace: an interrupted write must
    # not be able to leave the project holding half a file. Same directory
    # because `os.replace` is only atomic within one filesystem.
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".set-file-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, target)
    except BaseException:
        # Clean up the temp file on any failure — including a cancellation.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    # The SHAPE, never the content: project, path and size. A log line carrying
    # a consumer's source is the confidentiality breach this file is careful
    # about everywhere else.
    logger.info("files: wrote %s bytes to %s (%s)", len(data), body.path, project_root)
    return {"path": body.path, "identity": _identity(data), "bytes": len(data)}
