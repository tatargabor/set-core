"""How the framework starts an agent that outlives the dashboard, per platform.

The name is systemd's — a transient *scope* is the Linux mechanism, and the
package kept the word because it is written into records and logs that predate
the split. What the package actually provides is narrower and platform-neutral:
a way to name an agent, start it so that restarting the dashboard cannot take it
down, verify that property rather than promise it, and later find, enumerate and
stop it by that name.

Two backends implement it. `_systemd` is the original module, moved here
unedited; `_darwin` is its macOS counterpart. Selection is by `sys.platform` at
import, and callers above this package do not branch on platform — see the
`agent-isolation-backend` capability.

The shared vocabulary lives in `_types` rather than here, so a backend can
import it without importing the dispatcher that imports the backend.
"""
from __future__ import annotations

import sys

from ._types import (
    SCOPE_PREFIX,
    UNIT_SUFFIX,
    Scope,
    ScopeError,
    as_unit_name,
    sanitize,
    unit_name,
)

if sys.platform == "darwin":
    from . import _darwin as _backend
else:
    from . import _systemd as _backend

#: The backend in use. Exposed so a diagnostic can report which one answered
#: rather than leaving a reader to infer it from the platform.
BACKEND = _backend.__name__.rsplit(".", 1)[-1].lstrip("_")

def __getattr__(name: str):
    """Delegate every operation to the selected backend, at ACCESS time.

    Not `get = _backend.get` at import. Binding the names here would freeze them
    to the function objects the backend had when this module was first imported,
    and the delegation would then be one-way: a caller that replaced
    `_systemd.get` — a test with a fake systemctl, a diagnostic swapping in a
    recorder — would change what the backend's own internals see and NOT what
    reaches this module, so the two halves of one call chain would disagree
    about which implementation was running. Measured while splitting the module:
    twelve tests in `test_fleet_owner.py` failed exactly that way.

    Resolving on access keeps one implementation visible from both sides, and it
    keeps the private helpers reachable for the tests that drive them — those
    belong to the backend, and a test that patches `_systemd._show` should not
    have to know whether this package re-exported it.
    """
    try:
        return getattr(_backend, name)
    except AttributeError:
        raise AttributeError(
            f"the {BACKEND} backend has no {name!r}. If this is an operation the "
            "fleet needs on every platform, it belongs in the backend contract "
            "rather than on one implementation."
        ) from None


def __dir__():
    return sorted(set(globals()) | set(dir(_backend)))


__all__ = [
    "BACKEND",
    "SCOPE_PREFIX",
    "UNIT_SUFFIX",
    "Scope",
    "ScopeError",
    "as_unit_name",
    "adopt",
    "assert_survivable",
    "child_exec",
    "await_unit",
    "get",
    "is_gone",
    "list_scopes",
    "sanitize",
    "scope_is_gone",
    "scope_of",
    "forget",
    "stop",
    "unit_name",
]
