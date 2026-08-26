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

from .fleet import _known_roots, _start_location_verdict

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
    """The checkout a request may read, or the refusal.

    The same verdict as `fleet_start_agent`, from the same function: a directory
    this screen may start an agent in and one it may open a file in are the same
    set, and two checks meant to agree drift.

    ⚠ **They HAD drifted, and it took a live report to notice.** This used to ask
    `_known_roots()` while the start path asked `_start_location_verdict()`, which
    is wider by exactly one case: a non-prunable WORKTREE of a known project. So
    the screen would start an agent in a worktree and then refuse to open any of
    the files that agent was working on — measured 2026-08-26 as
    `could not open <project>/openspec/changes/<name>: no such file or directory`,
    where the framework had resolved a worktree agent's relative path against the
    main checkout.

    The docstring above claimed the two agreed while they did not, which is why
    the claim is now made by CALLING the other function rather than by copying
    what it does. A prefix test would be the wrong repair in both directions —
    see `_start_location_verdict` for why.
    """
    root = os.path.realpath(os.path.expanduser(raw or ""))
    if not os.path.isdir(root):
        raise HTTPException(status_code=400, detail=f"no such directory: {raw}")
    allowed, _reason = _start_location_verdict(root)
    if not allowed:
        raise HTTPException(
            status_code=400,
            detail=f"{root} is not a project this screen knows, nor a worktree of one; "
                   "register it first",
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


def _skipped(rel: str) -> bool:
    """Whether a path lies inside one of the heavy directories nobody wants listed.

    The SAME `_SKIP_DIRS` the non-repository walk refuses to enter, applied to the
    directory components of a path. Reused rather than written twice on purpose:
    two lists meant to agree drift, and this module has already paid for exactly
    that — see `_known_root`, whose docstring claimed an agreement the code did
    not have until a live report found it.

    Only used when the ignore rules have been lifted. With them in place the
    project's own `.gitignore` is doing this job, better.
    """
    return any(part in _SKIP_DIRS for part in rel.split("/")[:-1])


def _git_lines(root: Path, args: List[str]) -> Optional[List[str]]:
    """A NUL-separated git answer, split, or `None` if the command did not work.

    ⚠ **`-z` is not an optimisation — it is the difference between a path and a
    RENDERING of one.** Without it git renders any name containing a byte outside
    the portable set as a quoted C-string: `"docs/…\\303\\263….md"`. Measured
    2026-08-26 on a consumer checkout — 11 of 1794 paths — and the damage
    compounds: the tree builder reads the leading quote as part of the first
    segment, so a directory named `"docs` appears that nobody made, the eleven
    real files sit unreachable under it, and the path sent back names no file, so
    opening one is refused. A phantom folder and eleven broken files, from a
    quoting rule.

    `-z` also removes the newline-in-a-filename ambiguity that was always latent
    in splitting on `\\n` and had simply never been hit.
    """
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=str(root), capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("files: git %s failed in %s: %s", args[0], root, exc)
        return None
    if out.returncode != 0:
        logger.warning("files: git %s exited %s in %s", args[0], out.returncode, root)
        return None
    return [field for field in out.stdout.split("\0") if field]


def _git_files(root: Path, include_ignored: bool = False) -> Optional[List[str]]:
    """The project's own list of its files, or `None` if this is not a repo.

    `--cached --others --exclude-standard`: what git tracks, plus what exists but
    is not tracked yet, minus what the project's ignore rules exclude. The middle
    term is the one that matters on this screen — a file an agent wrote a minute
    ago is exactly the file a reader wants to open, and it is not committed.

    ## `include_ignored`, and why it is not simply the third term dropped

    Dropping `--exclude-standard` outright is the obvious widening and it is
    wrong. Measured 2026-08-26 on a consumer checkout: **36 149** paths against a
    cap of 20 000, so the answer would come back TRUNCATED — one silent absence
    traded for another — and what filled it was `node_modules` and build output.

    So the widened listing re-applies `_SKIP_DIRS`. Measured on the same tree:
    **2005** paths against 1794 with the flag off, and the 211 difference is the
    framework directories the reader was looking for.

    The bound is real and stated: a file under `node_modules` is not listable
    either way. The flag's answer is *the ignored files this view will carry*,
    never *all of them* — which is why the caller marks them rather than merging
    them into the rest.
    """
    if not (root / ".git").exists():
        return None
    args = ["ls-files", "-z", "--cached", "--others"]
    if not include_ignored:
        args.append("--exclude-standard")
    found = _git_lines(root, args)
    if found is None:
        return None
    return [rel for rel in found if not _skipped(rel)] if include_ignored else found


def _git_status(root: Path) -> Optional[Dict[str, str]]:
    """Each non-clean path's status code, or `None` when there is nothing to ask.

    ## The absence of this map is a VALUE

    `None` and `{}` are different answers and the caller must be able to tell them
    apart: `{}` says *I asked, and everything is clean*; `None` says *there was
    nothing to ask* — no repository, or a read that failed. A panel handed `{}`
    for a directory that is not a repository would render a tree of unmarked rows
    and imply a cleanliness it never measured, which is this repository's
    "a gap is not a zero" rule arriving at the wire.

    ## Two details that are easy to get plausibly wrong

    - **`-uall`.** The default collapses an untracked directory into one `dir/`
      entry, while the listing carries its files individually — so every file in a
      newly created directory would come back unmarked. That is the reassuring
      direction, which is the one to distrust.
    - **A rename's second field.** Under `-z` the porcelain-v1 record is
      `XY<space><path>\\0`, but a rename or copy is `XY<space><to>\\0<from>\\0`.
      The `<from>` is NOT a new record. A parser that treats it as one invents a
      status entry out of the origin path — and the malformed-record guard below
      catches that only by luck: it fires when the origin's third character is
      not a space, which for `src/app.ts` it is not and for `my file.ts` it is.
      So the phantom appears for some filenames and not others, marked with a
      code git never emitted. Measured while mutation-testing this parser: the
      first test written for it renamed `src/app.ts` and passed with this
      consume removed.

    A failure here does not fail the listing: files with no marks are useful, an
    error instead of the files is not.
    """
    if not (root / ".git").exists():
        return None
    fields = _git_lines(root, ["status", "--porcelain", "-z", "-uall"])
    if fields is None:
        return None
    status: Dict[str, str] = {}
    i = 0
    while i < len(fields):
        field = fields[i]
        i += 1
        # `XY path` — the code is the first two characters, then one space.
        if len(field) < 4 or field[2] != " ":
            logger.debug("files: unparsable status record %r in %s", field[:16], root)
            continue
        code, path = field[:2], field[3:]
        status[path] = code
        # A rename or a copy carries its ORIGIN as the next NUL field. Consume it
        # here or it becomes a phantom record and shifts everything after it.
        if "R" in code or "C" in code:
            i += 1
    return status


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
def list_files(root: str, ignored: bool = False) -> Dict[str, Any]:
    """Every file of one project, and whether the answer is complete.

    `truncated`, `cap` and `total` are returned together on purpose. A list cut
    to its cap and served as a plain array reads as the whole project — the
    false-absence shape: the reader concludes a file is not there when the answer
    simply stopped. So the answer states its own limit.

    `source` says which of the two producers ran. "no files" from a directory
    that is not a repository and "no files" from an empty repository are
    different facts, and a caller that cannot tell them apart will debug the
    wrong one.

    ## `ignored`, and why it defaults to off

    The project's ignore rules are the project's own statement of what is noise,
    and a listing that overrode them by default would bury the source tree. But
    the framework directory a project deliberately ignores is exactly what a
    reader of THIS screen comes looking for — measured 2026-08-26: `.set/` is
    ignored on a consumer checkout, so **0 of its 156 files** were listable, and
    nothing on the screen distinguished that from a project without it.

    So it is asked for. Entries present ONLY because it was asked for are marked
    `!!` in `status`, git's own code for an ignored path, so a caller can render
    the difference rather than merge it — the whole point being that a control
    which changes the answer must be visible in the answer.

    ## `status`

    A map of the paths that are NOT clean, to git's two-character code. Absent
    from the map means clean; a `null` map means there was nothing to ask. See
    `_git_status` — the two are deliberately different values.
    """
    project_root = _known_root(root)
    tracked = _git_files(project_root, include_ignored=ignored)
    source = "git"
    status: Optional[Dict[str, str]] = None
    if tracked is None:
        source = "walk"
        tracked = _walked_files(project_root, MAX_FILES)
    else:
        status = _git_status(project_root)
        # Which entries are here only because the rules were lifted — a set
        # difference against the unwidened answer, rather than a second guess at
        # what "ignored" means. `git check-ignore` per path would be one process
        # per file; `ls-files --ignored` is a third listing whose own exclusions
        # would then have to be kept in step with these.
        #
        # Merged only into a map that EXISTS. Building one out of the `!!` marks
        # alone would answer "everything else is clean" on the strength of a
        # status read that failed — the reassuring direction, and the whole
        # reason `None` is a distinct value here.
        if ignored and status is not None:
            plain = _git_files(project_root, include_ignored=False)
            if plain is not None:
                for rel in set(tracked) - set(plain):
                    status[rel] = "!!"
    total = len(tracked)
    truncated = total > MAX_FILES
    return {
        "root": str(project_root),
        "source": source,
        "files": sorted(tracked[:MAX_FILES]),
        "total": total,
        "cap": MAX_FILES,
        "truncated": truncated,
        "ignored": ignored,
        "status": status,
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
