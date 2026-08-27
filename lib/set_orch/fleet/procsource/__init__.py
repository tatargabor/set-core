"""Where the fleet reads process state, and the only place that knows the platform.

Two backends answer the same six questions — `_linux` from `/proc`, `_darwin`
from `ps` and `lsof`. Above this package nothing tests `sys.platform` and nothing
builds a path under `/proc`; that is the point, and it is checked rather than
asked for (see the `fleet-process-source` capability).

Why it exists at all: `/proc` does not exist on macOS, so every reader that used
it answered `[]`, `False` or `None` there. Measured 2026-08-27 with two live
agent sessions on one machine — `discover_agents()` returned `[]`,
`is_agent_process(<live pid>)` returned `False`, and `purpose._pid_state(<live
pid>)` returned `(False, False)`, so every recorded run read `stale`. None of it
raised. A blind read presented as a count is the false-absence class, and it is
worse than an error because it is quotable.

**Selecting a backend — three ways, and the second one carries a subtlety.**

    procsource.live_pids("claude")                     # by platform
    procsource.live_pids("claude", root="/tmp/fake")   # the Linux reader, rooted there
    procsource.backend("darwin").live_pids("claude")   # by name, on either platform

`root` is how ~10 existing tests drive the readers against a `/proc` tree they
built under `tmp_path`, and those tests pass unedited through this change. The
subtlety is that every caller carries `proc_root="/proc"` as a DEFAULT argument
and cannot tell a default from a deliberate choice — so the literal `"/proc"` is
treated as "dispatch by platform". On Linux that resolves to the same backend it
names, so the ambiguity is unobservable; on macOS it is the difference between
reading and being blind. This is not a new rule: `live_session_ids()` already
shipped with exactly this test (`sys.platform == "darwin" and proc_root ==
"/proc"`), and this package generalises it instead of leaving it in one function.

**Delegation resolves at ACCESS time, never at import.** Binding the names here
would freeze them to the function objects the backend held when this module was
first imported, and the delegation would then be one-way: a test replacing
`_linux.cwd` would change what the backend's internals see and not what reaches
callers, so the two halves of one call chain would run different code. Measured
in the preceding platform split — twelve tests failed in exactly that way.
"""
from __future__ import annotations

import logging
import sys
from types import ModuleType
from typing import Dict, List, Optional, Sequence

from . import _darwin, _linux
from ._types import (
    BATCH_OPERATIONS,
    CONTRACT,
    DEFAULT_PROC_ROOT,
    OPERATIONS,
    ProcRow,
    ProcSourceError,
    TableRead,
)

logger = logging.getLogger(__name__)

_BACKENDS: Dict[str, ModuleType] = {"linux": _linux, "darwin": _darwin}

#: The backend this platform uses. Exposed so a diagnostic can report which one
#: answered instead of leaving a reader to infer it from the platform.
BACKEND = "darwin" if sys.platform == "darwin" else "linux"


def backend(name: Optional[str] = None) -> ModuleType:
    """A backend module by name, or this platform's when `name` is None.

    Naming one works on either platform on purpose: a Darwin backend verified
    only on a Mac is verified only where it is already the default, which leaves
    its behaviour untested everywhere it might regress.
    """
    if name is None:
        return _BACKENDS[BACKEND]
    try:
        return _BACKENDS[name]
    except KeyError:
        raise ProcSourceError(
            f"no process-source backend named {name!r}; "
            f"the backends are {sorted(_BACKENDS)}"
        ) from None


def _select(root: Optional[str], name: Optional[str]) -> ModuleType:
    if name is not None:
        return backend(name)
    if root is not None and root != DEFAULT_PROC_ROOT:
        return _linux
    return backend(None)


def _call(op: str, *args, root: Optional[str] = None, using: Optional[str] = None, **kwargs):
    """Invoke one contract operation on the selected backend.

    `getattr` runs here, per call, which is what makes a replaced backend
    function visible through this module.
    """
    module = _select(root, using)
    func = getattr(module, op)
    if module is _linux and root is not None:
        kwargs["root"] = root
    return func(*args, **kwargs)


# --------------------------------------------------------------------------- #
# the six facts
# --------------------------------------------------------------------------- #

def live_pids(
    name: str, root: Optional[str] = None, using: Optional[str] = None,
) -> Optional[List[int]]:
    """Every live pid whose executable identity is `name`.

    `None` means the process table could not be read, and it is a different
    value from `[]` on purpose — see `_types` for the caller that acts on the
    difference in the opposite direction to a listing.
    """
    return _call("live_pids", name, root=root, using=using)


def cwd(pid: int, root: Optional[str] = None, using: Optional[str] = None) -> Optional[str]:
    return _call("cwd", pid, root=root, using=using)


def cwds(
    pids: Sequence[int], root: Optional[str] = None, using: Optional[str] = None,
) -> Dict[int, Optional[str]]:
    """Working directories for many pids — one call where the platform allows it.

    Every requested pid is a key. A pid whose directory could not be read maps to
    `None`, individually, rather than failing the batch: on macOS the commonest
    reason is that the process exited between two reads, and discarding the whole
    answer for it would report a machine as unmeasurable during an ordinary pass.
    """
    return _call("cwds", pids, root=root, using=using)


def argv(
    pid: int, root: Optional[str] = None, using: Optional[str] = None,
) -> Optional[List[str]]:
    return _call("argv", pid, root=root, using=using)


def argvs(
    pids: Optional[Sequence[int]] = None,
    root: Optional[str] = None,
    using: Optional[str] = None,
) -> Optional[Dict[int, List[str]]]:
    """Arguments for the given pids, or for every live process when `pids` is None."""
    return _call("argvs", pids, root=root, using=using)


def ppid(pid: int, root: Optional[str] = None, using: Optional[str] = None) -> Optional[int]:
    return _call("ppid", pid, root=root, using=using)


def comm(pid: int, root: Optional[str] = None, using: Optional[str] = None) -> Optional[str]:
    return _call("comm", pid, root=root, using=using)


def env_value(
    pid: int, key: str, root: Optional[str] = None, using: Optional[str] = None,
) -> Optional[str]:
    """One named environment variable, or `None` when it is UNKNOWN.

    Never an empty string for an unreadable environment. The callers act on that:
    a waiter whose session cannot be read is treated as alive and is never
    offered for removal.
    """
    return _call("env_value", pid, key, root=root, using=using)


def read_table(root: Optional[str] = None, using: Optional[str] = None) -> TableRead:
    """Every live process with its identity, as one read.

    Returns a `TableRead` rather than an optional mapping so that a failure
    survives being passed around: `rows={}` with `failed=True` cannot be mistaken
    for a machine with no processes on it.
    """
    return _call("read_table", root=root, using=using)


def is_alive(pid: int, root: Optional[str] = None, using: Optional[str] = None) -> bool:
    """Whether the pid names a live process at all.

    Derived from `comm` rather than given its own backend operation, because
    "does this process exist" and "what is it" are answered by the same read on
    both platforms and a second operation would be a second thing to keep true.
    """
    return comm(pid, root=root, using=using) is not None


def __getattr__(name: str):
    """Anything not named above is resolved on the platform backend, at access.

    This is what a test reaches through when it drives a backend's private
    helper — those belong to the backend, and a test patching `_linux._read`
    should not have to know whether this package re-exported it.
    """
    try:
        return getattr(backend(None), name)
    except AttributeError:
        raise AttributeError(
            f"the {BACKEND} process-source backend has no {name!r}. If this is a "
            "fact the fleet needs on every platform, it belongs in the contract "
            f"({', '.join(CONTRACT)}) rather than on one implementation."
        ) from None


def __dir__():
    return sorted(set(globals()) | set(dir(backend(None))))


__all__ = [
    "BACKEND",
    "BATCH_OPERATIONS",
    "CONTRACT",
    "DEFAULT_PROC_ROOT",
    "OPERATIONS",
    "ProcRow",
    "ProcSourceError",
    "TableRead",
    "argv",
    "argvs",
    "backend",
    "comm",
    "cwd",
    "cwds",
    "env_value",
    "is_alive",
    "live_pids",
    "ppid",
    "read_table",
]
