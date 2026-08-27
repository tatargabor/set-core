from __future__ import annotations

"""Handing ONE path to the desktop's default application.

This is the third module in this package that guards a path, and the three guard
three different things — which is exactly why they are three files:

- `files.py` confines every path INTO a known project root,
- `paste.py` confines every path AWAY from one,
- and this one confines nothing by location at all. It steps outside every root
  on purpose, and what it guards instead is the *act*: a path may be OPENED, and
  must never be RUN.

A single function meaning all three would sit in the most safety-relevant place
in this repository and mean whichever one its last reader assumed.

## Why the act is the thing to guard

The paths that reach here come from a fleet terminal, where every character was
written by whatever an agent ran. A person's activation is what starts a
request — nothing here fires on its own — but the TEXT that person activated is
still data, not an instruction. `xdg-open` does not distinguish: handed a JPEG it
shows a picture, handed an executable or a `.desktop` entry it starts a program.
So the refusals below are about that difference and nothing else, and they fail
in the direction of not starting anything.

## What this module must never become

- **A reader.** It never opens the file it hands over. No content, no preview, no
  size, no sniffing — the desktop reads it, this only names it.
- **An oracle.** There is no probe endpoint and there must not be one: a "does
  this path exist" route would answer for any path on the machine, one polite
  request at a time, which is the hole `files.py:_DENIED` exists to refuse. The
  only existence answer here is the outcome of an open somebody asked for.
- **A record.** The log carries the path and the outcome — never file content.
"""

import logging
import os
import shutil
import subprocess
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

#: The program that knows the desktop's file associations. Linux's answer, and
#: the only one wired up: on a platform without it the endpoint refuses rather
#: than guessing at `open` or `start`, because a wrong guess would be a silent
#: no-op and this endpoint's whole contract is that every outcome is reported.
_OPENER = "xdg-open"

#: Suffixes that are launchers whatever their permission bits say. A `.desktop`
#: entry carries its own `Exec=` line, so the executable-bit check below would
#: wave through a file whose entire purpose is to run a command.
_LAUNCHER_SUFFIXES = (".desktop",)

#: Suffixes whose desktop association RUNS the file, whatever its permissions.
#:
#: Measured 2026-08-27 on a running desktop, with 644 files and no executable bit
#: anywhere: `harmless.jar` passed `refusal()` and its handler was
#: `openjdk-7-java.desktop`, which executes it. A `.jar` is data by permission and
#: a program by association, and the permission bit — the thing this module used
#: to test — is a proxy for the wrong question.
#:
#: The control in that same measurement is worth keeping in view: `harmless.py`
#: also passed, and its handler was an EDITOR. So the class is not "a file some
#: program understands"; it is "a file whose handler runs it", and `.py` is
#: correctly absent from this list.
_ASSOCIATION_RUNS = (
    # a runtime executes the file itself
    ".jar", ".appimage", ".run", ".jnlp", ".msi", ".apk",
    ".exe", ".com", ".bat", ".cmd", ".scr", ".ps1", ".vbs", ".vbe",
    ".wsf", ".wsh", ".hta",
    # an installer package — opening one is starting an install
    ".deb", ".rpm", ".pkg", ".snap", ".flatpak", ".flatpakref",
    # macro-ENABLED office formats. The `m` suffixes are the ones that exist to
    # carry code; the ordinary `.docx`/`.xlsx` cannot, and are not refused.
    ".docm", ".dotm", ".xlsm", ".xltm", ".xlam", ".xlsb",
    ".pptm", ".potm", ".ppam", ".ppsm", ".sldm",
)

#: Suffixes whose association INTERPRETS the file at a `file://` origin.
#:
#: A milder severity and the same class: `harmless.html` reached
#: `google-chrome.desktop` in the same measurement. Nothing is executed, but a
#: local page can read this machine's files, and the text that named it was
#: written by whatever an agent ran.
#:
#: `.svg` is deliberately NOT here even though it is XML a browser interprets.
#: An image that opened before this change must still open — the widening is a
#: widening of refusals, not a place to add ones nobody measured.
_ASSOCIATION_INTERPRETS = (".html", ".htm", ".xhtml", ".xht", ".shtml", ".mhtml")


class OpenRequest(BaseModel):
    """One absolute path, and nothing else.

    No "application" field, no arguments, no working directory. Every one of
    those would turn a path into a command line, which is the thing this module
    exists not to be.
    """

    path: str


def refusal(path: str) -> str | None:
    """Why this path must not be handed to the desktop, or `None` if it may be.

    Kept as a function of its own, and returning a REASON rather than a boolean,
    for two reasons that have both cost something in this repository before: a
    caller who is told *no* without being told *which rule* reports "it didn't
    work" to the reader, and a guard that is one expression inside a route
    handler cannot be tested without a web server.

    ## The rule is stated by the ACT, not by the permission bit

    What RUNS a file is the desktop association, and the permission bit is only
    one way to reach it. Measured 2026-08-27 (`B-89`): a 644 `.jar` with no
    executable bit anywhere passed this function and reached a JVM. That the
    `.desktop` suffix was already refused by name shows the class was understood
    — the list was simply one item long.

    The list is a FLOOR and never proof of completeness. Associations are
    per-machine and per-user, so this cannot enumerate what a given desktop will
    do, and it does not try: it refuses a fixed set from the path alone, which is
    why the same input gives the same verdict on every machine and in every test.
    **Nothing here asks the local desktop anything.** A guard that did would give
    a different answer on every machine and could not be tested at all.

    The order is fixed and the resolution comes first:

        absolute → realpath → exists → file or directory → launcher suffix
                 → association runs it → association interprets it
                 → executable bit (REGULAR FILES ONLY)

    Three of those steps are the ones that would be got wrong:

    - **`realpath` before judging.** A symlink is precisely how a harmless-looking
      name reaches an executable, so the suffix and mode checks run on the
      resolved target and never on the request string. Same reasoning as
      `files.py:_confine`, applied to a different question.
    - **The executable bit is a rule about FILES.** Every traversable directory
      has its execute bits set, so a uniform check would refuse *every* directory
      while looking perfectly correct in review — and while passing any test
      written only against files.
    - **The suffix rules come BEFORE the bit**, so the reason names the stronger
      fact. *"Executable files are not opened"*, said about a file with no
      executable bit, sends the reader to inspect permissions that are not the
      cause — which is the whole reason a reason is returned at all.
    """
    if not path or not path.startswith("/"):
        return "path must be absolute"

    target = os.path.realpath(path)

    if not os.path.exists(target):
        return "no such file or directory"

    is_dir = os.path.isdir(target)
    if not is_dir and not os.path.isfile(target):
        return "not a regular file or directory"

    lowered = target.lower()
    if lowered.endswith(_LAUNCHER_SUFFIXES):
        return "desktop entries are launchers, not documents"

    for suffix in _ASSOCIATION_RUNS:
        if lowered.endswith(suffix):
            return (f"a {suffix} file is RUN by whatever the desktop associates with it, "
                    "whatever its permissions say")

    for suffix in _ASSOCIATION_INTERPRETS:
        if lowered.endswith(suffix):
            return (f"a {suffix} file opens as a local page that can read this "
                    "machine's files")

    if not is_dir and os.access(target, os.X_OK):
        return "this file carries an executable bit, and executables are not opened"

    return None


@router.post("/api/desktop/open")
def desktop_open(req: OpenRequest) -> Dict[str, Any]:
    """Ask the desktop to open one path with its default application.

    The answer is about the HAND-OVER and says no more than that. The handler is
    started detached, so this cannot know whether a window appeared, and claiming
    otherwise would be a false success — the failure class where a check reports
    on the mechanism and is silent about the result.

    Detached deliberately, rather than waited on: some handlers do not return
    until their window closes, so waiting would report a successful open as a
    timeout. That is the fail direction that teaches readers to ignore the
    message.
    """
    path = (req.path or "").strip()

    why = refusal(path)
    if why:
        logger.info("desktop_open: refused path=%s reason=%s", path, why)
        raise HTTPException(status_code=400, detail=why)

    opener = shutil.which(_OPENER)
    if not opener:
        logger.warning("desktop_open: no %s on PATH", _OPENER)
        raise HTTPException(
            status_code=501,
            detail=f"no desktop handler available ({_OPENER} not found)",
        )

    try:
        subprocess.Popen(
            [opener, path],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        logger.error("desktop_open: could not start %s for %s — %s", _OPENER, path, exc)
        raise HTTPException(status_code=500, detail=f"could not start {_OPENER}: {exc}")

    logger.info("desktop_open: handed over path=%s", path)
    # `opened` means ASKED. The message is what reaches the reader, so it is
    # worded as the weaker claim the endpoint can actually stand behind.
    return {"opened": True, "path": path, "message": "handed to the desktop"}
