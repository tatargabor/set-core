"""What the engine says is runnable — asked for, and cached on what would change it.

`set_orch` may not import `set_workcycle` (engine design D10). Reading the engine's
RECORDS needs no import — `purpose.py` does that — but *what is runnable and why not*
is a different question: it needs the task file parsed, `<!-- depends: -->` resolved
and the next group selected, and all of that is the engine's. So this asks the engine,
by running its one command.

**Why not a third copy of the resolver.** The second-copy pattern is established here
(`RUN_STATE_REL`, the awaiting regex) and it works because those copies are a constant
and a regex, each held by a test that fails on divergence. A fail-closed dependency
resolver with cycle detection is not that kind of copy: two of them would disagree
exactly in the case that matters, and the disagreement would be silent.

**Why not per poll.** A process per project per poll is the cost the fleet screen
already refuses elsewhere. The cache key is what would change the answer — the change's
task file, and its run-state directory — so a start, a finish and an edit all invalidate
it without anyone having to remember to.

**Why an absent engine is an answer.** A machine with no engine installed reports
`available: False` with the reason, and the run list still renders from records. A
screen that empties itself because a command is missing has turned a missing capability
into missing data.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

__all__ = ["ENGINE_COMMAND", "PlanView", "read_plan", "clear_cache"]

#: ⚠ SECOND COPY of the name in `set_orch.api.fleet.ENGINE_COMMAND`, and the module
#: that owns the argv is that one. Kept here because importing the API module from a
#: fleet helper inverts the dependency the package is arranged around;
#: `tests/unit/test_fleet_workcycle_plan.py` fails when the two diverge.
ENGINE_COMMAND = "set-work-cycle"

#: How long to wait for the engine to answer a *read*. Generous enough for a cold
#: interpreter, short enough that a hung command cannot hold a page open.
_TIMEOUT_SECONDS = 20.0

_CACHE: Dict[Tuple[str, str], Tuple[Any, "PlanView"]] = {}


@dataclass
class PlanView:
    """The engine's answer about one change, or the recorded fact that there is none."""

    #: `False` when the engine could not be run at all. The reason says which.
    available: bool = False
    reason: str = ""
    #: The engine's own payload, carried rather than reshaped.
    payload: Dict[str, Any] = field(default_factory=dict)

    @property
    def adopted(self) -> Optional[bool]:
        """`None` where the engine could not be asked — never `False`."""
        if not self.available:
            return None
        return bool(self.payload.get("adopted"))

    @property
    def runnable(self) -> Optional[bool]:
        """`None` where nothing was measured — never `False`, which would be a claim.

        ⚠ Derived from `selected`, the key the engine actually emits. An earlier
        version of this read `payload["runnable"]` — a key the engine has never
        written — so it answered `False` for every change on the machine while
        looking exactly like a measurement. Caught by checking the engine's own
        `cmd_status` rather than by a test, which is why the derivation is named
        here: the next person to add a field should look there too.
        """
        if not self.available or not self.payload.get("adopted"):
            return None
        return self.payload.get("selected") is not None

    @property
    def selected(self) -> Optional[str]:
        """The group the engine would run next, or `None` — its own word for it."""
        return self.payload.get("selected")

    def as_dict(self) -> Dict[str, Any]:
        return {"available": self.available, "reason": self.reason,
                "runnable": self.runnable, "adopted": self.adopted, **self.payload}


def _fingerprint(tree: str, change: str, changes_dir: str) -> Any:
    """Everything whose change would change the answer, as a comparable value.

    ⚠ The task file is HASHED, not stamped. Measured while writing this module's
    own test: ticking `- [ ]` to `- [x]` leaves the size identical and lands
    inside the filesystem's timestamp granularity, so an `(mtime, size)` key did
    not change and the cache kept answering with the pre-edit plan. That is the
    mtime trap in its usual form — the file changed, the stamp did not — and its
    fail direction is the quiet one: the screen reports a plan nobody has now.

    The run-state directory is listed rather than stamped, for the same reason: a
    file appearing inside a directory need not move the directory's own mtime on
    every filesystem, and a start or a finish is exactly a file appearing.
    """
    def digest(path: str) -> Optional[str]:
        try:
            with open(path, "rb") as fh:
                return hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            # Absence is part of the fingerprint: a file appearing must invalidate.
            return None

    def listing(path: str) -> Any:
        try:
            return tuple(sorted(
                (e.name, e.stat().st_size) for e in os.scandir(path) if e.is_file()))
        except OSError:
            return None

    return (
        digest(os.path.join(tree, changes_dir, change, "tasks.md")),
        listing(os.path.join(tree, "set", "runtime", "work-cycle", change)),
    )


def read_plan(tree: str, change: str, *, changes_dir: str = "openspec/changes",
              runner=None) -> PlanView:
    """What the engine says about `change` in `tree`. Cached on the fingerprint."""
    key = (os.path.realpath(tree), change)
    fp = _fingerprint(tree, change, changes_dir)
    hit = _CACHE.get(key)
    if hit is not None and hit[0] == fp:
        return hit[1]

    # ⚠ `--json` is a TOP-LEVEL flag and must precede the subcommand. Written the
    # other way round first, and every test here injected a fake runner — so all
    # of them passed while the real command would have exited on
    # `unrecognized arguments: --json`. The mechanism was verified and the result
    # was not; `test_the_argv_this_builds_parses_with_the_engine_s_own_parser`
    # closes that by asking the engine's parser instead of a double.
    argv = [ENGINE_COMMAND, "--tree", tree, "--json"]
    if change:
        argv += ["--change", change]
    argv += ["status"]
    run = runner or _run
    try:
        code, out, err = run(argv)
    except FileNotFoundError:
        view = PlanView(available=False, reason=(
            f"{ENGINE_COMMAND} is not installed on this machine, so what is runnable "
            f"cannot be reported; recorded runs are still shown"))
        _CACHE[key] = (fp, view)
        return view
    except subprocess.TimeoutExpired:
        # NOT cached: a timeout is a fact about this moment, and caching it would
        # keep answering with it after the cause is gone.
        return PlanView(available=False,
                        reason=f"{ENGINE_COMMAND} did not answer within {_TIMEOUT_SECONDS:.0f}s")

    if code not in (0, 1):
        # The engine ran and refused. Its words, not ours.
        view = PlanView(available=False, reason=(err or out or "").strip()[:500])
        _CACHE[key] = (fp, view)
        return view

    try:
        payload = json.loads(out or "{}")
    except ValueError as exc:
        logger.warning("work-cycle plan: unparseable answer for %s: %s", change, exc)
        return PlanView(available=False, reason=f"the engine's answer could not be read: {exc}")

    view = PlanView(available=True, payload=payload if isinstance(payload, dict) else {})
    _CACHE[key] = (fp, view)
    return view


def _run(argv):
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS)
    return proc.returncode, proc.stdout, proc.stderr


def clear_cache() -> None:
    """For tests, and for a caller that knows something changed off-disk."""
    _CACHE.clear()
