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
still data, not an instruction. The desktop's opener does not distinguish: handed a JPEG it
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
import sys
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

#: The program that knows the desktop's file associations, per platform: macOS
#: answers `open`, everything else `xdg-open`. Measured 2026-09-25 on a Mac mini,
#: where the endpoint refused every request because this was the Linux constant.
#:
#: A FUNCTION rather than a constant, for a reason that is about the tests and not
#: about style: a value computed at import is invisible to a test that wants the
#: other platform's branch, so each machine would only ever exercise its own half
#: and a green suite would say nothing about the other one.
#:
#: There is deliberately NO fallback from one to the other. On a platform without
#: its own opener the endpoint refuses, because a stray program of the other name
#: would be handed an agent-written path, and this endpoint's whole contract is
#: that every outcome is reported rather than guessed at.
def _opener_name() -> str:
    return "open" if sys.platform == "darwin" else "xdg-open"

#: What a program needs to put a window on the screen the reader is looking at.
#:
#: Measured 2026-10-23: the server had been started without `DISPLAY` (a user
#: service started before the session exported it), so `xdg-open` still found the
#: GNOME session over D-Bus and `gio open` started mpv — with no screen to draw
#: on. The reader saw a busy cursor, mpv burned ~150 % CPU for ten seconds,
#: exited, and nothing appeared, while this endpoint had answered "handed to the
#: desktop". The user manager DOES carry the session's variables
#: (`systemctl --user show-environment`), so they are read from there at the
#: moment of the open, not at server start, which is exactly when they were absent.
_SESSION_VARS = (
    "DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY",
    "XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP", "DBUS_SESSION_BUS_ADDRESS",
)


def _user_manager_environment() -> Dict[str, str]:
    """The graphical-session variables the systemd user manager holds, or `{}`."""
    systemctl = shutil.which("systemctl")
    if not systemctl:
        return {}
    try:
        out = subprocess.run(
            [systemctl, "--user", "show-environment"],
            capture_output=True, text=True, timeout=2, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("desktop_open: could not read the user manager environment — %s", exc)
        return {}
    if out.returncode != 0:
        logger.warning("desktop_open: systemctl --user show-environment exited %s", out.returncode)
        return {}
    env: Dict[str, str] = {}
    for line in out.stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep and key in _SESSION_VARS:
            env[key] = value
    return env


def _opener_env() -> Dict[str, str] | None:
    """The environment the opener starts in, or `None` when no screen is reachable.

    `None` is a refusal, not a fallback: started without a display, the handler
    runs headless and the reader is told it opened. Only the Linux opener needs
    this — macOS `open` talks to LaunchServices, not to a display variable.
    """
    env = dict(os.environ)
    if _opener_name() != "xdg-open" or env.get("DISPLAY") or env.get("WAYLAND_DISPLAY"):
        return env
    session = _user_manager_environment()
    if not (session.get("DISPLAY") or session.get("WAYLAND_DISPLAY")):
        return None
    for key, value in session.items():
        env.setdefault(key, value)
    logger.info(
        "desktop_open: server has no display; borrowed %s from the user manager",
        ", ".join(f"{k}={session[k]}" for k in ("DISPLAY", "WAYLAND_DISPLAY") if k in session),
    )
    return env

#: Suffixes that are launchers whatever their permission bits say. A `.desktop`
#: entry carries its own `Exec=` line, so the executable-bit check below would
#: wave through a file whose entire purpose is to run a command.
#:
#: `.app` is here and not with the executable bit because a macOS bundle is a
#: DIRECTORY (measured 2026-09-25: `mdls -name kMDItemContentType` on
#: `Calculator.app` gives `com.apple.application-bundle`). The bit check below
#: exempts directories deliberately — every traversable directory carries the bit —
#: so a bundle is the one launcher class a correct Linux-shaped guard waves through.
_LAUNCHER_SUFFIXES = (".desktop", ".app")

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
    # macOS, measured 2026-09-25 with `mdls -name kMDItemContentType`:
    #   .command  -> com.apple.terminal.shell-script  (Terminal executes it)
    #   .terminal -> com.apple.terminal.settings      (a profile that can carry a command)
    #   .dmg      -> com.apple.disk-image-udif        (opening one MOUNTS it — the
    #                                                  installer act `.pkg` is here for)
    # `.workflow` was measured in the same pass and is deliberately ABSENT: it came
    # back a dynamic UTI (nothing registered), and this list is widened by
    # measurement, never by a name that sounds executable.
    ".command", ".terminal", ".dmg",
    # macro-ENABLED office formats. The `m` suffixes are the ones that exist to
    # carry code; the ordinary `.docx`/`.xlsx` cannot, and are not refused.
    ".docm", ".dotm", ".xlsm", ".xltm", ".xlam", ".xlsb",
    ".pptm", ".potm", ".ppam", ".ppsm", ".sldm",
)

#: A LOCAL PAGE (`.html`, `.svg`, …) was refused here as its own class until
#: 2026-10-23: a page is not executed but is interpreted at a `file://` origin.
#: Retired by the owner's decision that day, after a generated report outside
#: every project could not be opened from anywhere in the dashboard: a person's
#: activation opens it in the browser, from the terminal too. The `viewed` request
#: field existed only to lift that class and went with it.

#: Suffixes for which the executable bit says nothing, so it is not consulted.
#:
#: Reported 2026-10-19: every video on an exFAT drive was refused. exFAT stores
#: no Unix permissions — 844 of 844 files on that drive read as 755 — so the bit
#: refused every file there and told the reader nothing about any of them.
#:
#: Measured that day on Linux, per suffix: a copy of an ELF binary and a
#: `#!/bin/sh` script, each given the suffix and mode 755. Both `xdg-mime query
#: filetype` and `gio info` typed every one as the MEDIA type (never an
#: executable or a script), and every `xdg-mime query default` handler was a
#: player, viewer or editor. So for these the desktop chooses by suffix, and the
#: bit is not the path to a program starting.
#:
#: `.ts` measured `video/mpeg` and is deliberately ABSENT: in a code project it
#: is TypeScript. The browser's `MEDIA_SUFFIXES` (`web/src/lib/fleetFiles.ts`)
#: routes the same list to the desktop; a test holds the two equal.
_MEDIA_SUFFIXES = (
    # video
    ".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".mpg", ".mpeg",
    ".ogv", ".3gp", ".flv",
    # audio
    ".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".oga", ".opus", ".wma",
    # raster image
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".avif", ".tif", ".tiff",
    ".heic", ".ico",
    # document
    ".pdf",
    # office document, e-book, archive — measured 2026-10-23, same method: typed by
    # suffix with an ELF or a script inside, handler an office suite or an archive
    # manager. No view in the editor, so the browser routes these to the desktop
    # from inside a checkout too. Legacy `.doc/.xls/.ppt` are absent: those formats
    # can carry macros, and nothing measured what the office suite does with one.
    ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp", ".rtf", ".epub",
    ".zip", ".tar", ".gz", ".7z",
)

#: Text formats the desktop ALSO types by suffix (measured 2026-10-23, same
#: method), so the bit is not consulted for them either. They are not routed past
#: the file view: inside a checkout the editor shows them.
#:
#: Absent ON PURPOSE, and the measurement is why: `.jsonl`, `.toml`, `.ini` and a
#: name with no suffix were typed by CONTENT — `application/x-executable` when they
#: held a binary — so for them the bit is the only thing saying "program". Scripts
#: (`.sh .py .js` …) are absent too: on an ordinary filesystem their bit is real.
_TEXT_SUFFIXES = (
    ".html", ".htm", ".xhtml", ".xml", ".json", ".svg",
    ".txt", ".md", ".csv", ".tsv", ".log", ".srt", ".vtt", ".yaml", ".yml",
)


def _bit_is_meaningless(lowered_target: str) -> bool:
    """Whether the executable bit is not consulted for this resolved target.

    Only where the measurement above was made: the opener is `xdg-open`. On
    macOS the bit still refuses, because nothing was measured there and an entry
    here rests on a measurement, never on plausibility.
    """
    return _opener_name() == "xdg-open" and lowered_target.endswith(_MEDIA_SUFFIXES + _TEXT_SUFFIXES)


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
                 → association runs it
                 → executable bit (REGULAR FILES ONLY; not for a measured
                   media, document or text suffix on Linux — see
                   `_MEDIA_SUFFIXES` and `_TEXT_SUFFIXES`)

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
    for suffix in _LAUNCHER_SUFFIXES:
        if lowered.endswith(suffix):
            # Named per suffix rather than one sentence for both: "desktop entries
            # are launchers" said about a `.app` sends the reader looking for a
            # file that is not there, which is the whole reason a REASON is
            # returned instead of a boolean.
            what = "a .desktop entry" if suffix == ".desktop" else f"a {suffix} bundle"
            return f"{what} is a launcher, not a document"

    for suffix in _ASSOCIATION_RUNS:
        if lowered.endswith(suffix):
            return (f"a {suffix} file is RUN by whatever the desktop associates with it, "
                    "whatever its permissions say")

    # Judged on the RESOLVED name, like the suffix rules above: a link named
    # `clip.mp4` that points at a program keeps the program's name here.
    if not is_dir and os.access(target, os.X_OK):
        if _bit_is_meaningless(lowered):
            logger.debug("desktop refusal: executable bit not consulted for media file %s", target)
        else:
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

    wanted = _opener_name()
    opener = shutil.which(wanted)
    if not opener:
        logger.warning("desktop_open: no %s on PATH", wanted)
        raise HTTPException(
            status_code=501,
            detail=f"no desktop handler available ({wanted} not found)",
        )

    env = _opener_env()
    if env is None:
        logger.warning("desktop_open: no graphical session reachable, nothing started for %s", path)
        raise HTTPException(
            status_code=503,
            detail="no graphical session is visible to the server (no DISPLAY or "
                   "WAYLAND_DISPLAY), so nothing was started",
        )

    try:
        subprocess.Popen(
            [opener, path],
            env=env,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        logger.error("desktop_open: could not start %s for %s — %s", wanted, path, exc)
        raise HTTPException(status_code=500, detail=f"could not start {wanted}: {exc}")

    logger.info("desktop_open: handed over path=%s", path)
    # `opened` means ASKED. The message is what reaches the reader, so it is
    # worded as the weaker claim the endpoint can actually stand behind.
    return {"opened": True, "path": path, "message": "handed to the desktop"}
