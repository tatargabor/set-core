"""The `/proc` reader — the original implementation, moved rather than rewritten.

Every body here came from `fleet/discovery.py`, `fleet/instruct.py` or
`fleet/purpose.py` and is kept as it was, including the parses that were arrived
at by measurement:

- identity is read from `comm`, never matched against a command line, because
  matching command lines found 31 false positives — all shell snapshots whose
  path contains the word;
- `ppid` is parsed starting after the LAST `)` in `/proc/<pid>/stat`, because
  field 2 is a `comm` in parentheses and a `comm` may itself contain spaces and
  parentheses, so splitting the line on whitespace gets the wrong field for any
  process with an unusual name.

This module is the one thing in the change that must NOT change behaviour: it is
what the existing `/proc`-fixture suites drive, and those suites pass unedited as
the evidence that the abstraction moved nothing.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Sequence

from ._types import DEFAULT_PROC_ROOT, ProcRow, TableRead, _basename

logger = logging.getLogger(__name__)


def _read(path: str) -> Optional[str]:
    try:
        with open(path, "r", errors="replace") as fh:
            return fh.read()
    except (OSError, PermissionError):
        return None


def _read_bytes(path: str) -> Optional[bytes]:
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except (OSError, PermissionError):
        return None


def _pid_entries(root: str) -> Optional[List[int]]:
    """The numeric entries of a `/proc` root, or None when it cannot be read."""
    try:
        entries = os.listdir(root)
    except OSError as exc:
        logger.warning("procsource: cannot read %s: %s", root, exc)
        return None
    return sorted(int(e) for e in entries if e.isdigit())


# --------------------------------------------------------------------------- #
# the six facts
# --------------------------------------------------------------------------- #

def live_pids(name: str, root: str = DEFAULT_PROC_ROOT) -> Optional[List[int]]:
    """Pids whose executable identity is `name`, or None if `/proc` is unreadable.

    Only `comm` is read per pid — deliberately not `cmdline` or `stat`, which
    would turn a cheap walk into three file reads for every process on the
    machine when the caller wanted one field.
    """
    pids = _pid_entries(root)
    if pids is None:
        return None
    found: List[int] = []
    for pid in pids:
        got = comm(pid, root)
        if got is not None and _basename(got) == name:
            found.append(pid)
    return found


def comm(pid: int, root: str = DEFAULT_PROC_ROOT) -> Optional[str]:
    raw = _read(os.path.join(root, str(pid), "comm"))
    return raw.strip() if raw is not None else None


def cwd(pid: int, root: str = DEFAULT_PROC_ROOT) -> Optional[str]:
    try:
        return os.readlink(os.path.join(root, str(pid), "cwd"))
    except (OSError, PermissionError):
        return None


def cwds(pids: Sequence[int], root: str = DEFAULT_PROC_ROOT) -> Dict[int, Optional[str]]:
    """The batch form. On `/proc` there is nothing to batch — a readlink each."""
    return {pid: cwd(pid, root) for pid in pids}


def argv(pid: int, root: str = DEFAULT_PROC_ROOT) -> Optional[List[str]]:
    """The argument vector, NUL-separated and therefore exact on this platform.

    An empty `cmdline` is a kernel thread, and the empty list it produces is a
    real answer rather than a failure — which is why an unreadable file returns
    None and this does not.
    """
    raw = _read_bytes(os.path.join(root, str(pid), "cmdline"))
    if raw is None:
        return None
    return [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]


def argvs(
    pids: Optional[Sequence[int]] = None, root: str = DEFAULT_PROC_ROOT,
) -> Optional[Dict[int, List[str]]]:
    """Argument vectors for the given pids, or for every live pid when None.

    None for the whole-table form means the root could not be read at all; a pid
    whose own `cmdline` is unreadable is simply absent from the mapping, which is
    the same distinction one level down.
    """
    if pids is None:
        listed = _pid_entries(root)
        if listed is None:
            return None
        pids = listed
    out: Dict[int, List[str]] = {}
    for pid in pids:
        got = argv(pid, root)
        if got is not None:
            out[pid] = got
    return out


def ppid(pid: int, root: str = DEFAULT_PROC_ROOT) -> Optional[int]:
    """The parent pid, parsed the only way that is safe.

    `/proc/<pid>/stat` puts `comm` in parentheses in field 2, and a comm may
    contain spaces and parentheses — so splitting the line on whitespace gets the
    wrong field for any process whose name is unusual. The parse starts after the
    LAST `)`, which is where the fixed-width fields begin.
    """
    raw = _read(os.path.join(root, str(pid), "stat"))
    if raw is None:
        return None
    tail = raw[raw.rfind(")") + 2:].split()
    if len(tail) < 2 or not tail[1].isdigit():
        return None
    return int(tail[1])


def env_value(pid: int, key: str, root: str = DEFAULT_PROC_ROOT) -> Optional[str]:
    """One environment variable, or None when it is unknown.

    None covers both "the file could not be read" and "the variable is not set",
    and the callers treat them the same way — an undeterminable value is not
    acted on. An empty assignment is returned as None too, because every current
    caller wants an identity and an empty identity is not one.
    """
    raw = _read_bytes(os.path.join(root, str(pid), "environ"))
    if raw is None:
        return None
    marker = key.encode() + b"="
    for item in raw.split(b"\0"):
        if item.startswith(marker):
            return item.split(b"=", 1)[1].decode("utf-8", "replace") or None
    return None


# --------------------------------------------------------------------------- #
# the whole-table form
# --------------------------------------------------------------------------- #

def read_table(root: str = DEFAULT_PROC_ROOT) -> TableRead:
    """Every live process with its identity. Lazy about everything else.

    `comm` only — `ppid` and `argv` are left `None` rather than read for all of
    them, because on `/proc` those are two more file opens per process and the
    callers that want them want them for a handful of matched pids. Reading them
    here would make this platform pay for the other one's batching.
    """
    pids = _pid_entries(root)
    if pids is None:
        return TableRead(failed=True)
    return TableRead(rows={pid: ProcRow(pid=pid, comm=comm(pid, root)) for pid in pids})
