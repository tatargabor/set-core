"""A terminal for a FOREIGN agent that happens to run inside tmux.

The fleet can attach a terminal only to a pty its owner holds, and a pty master
cannot be reacquired from outside (`owner.py`, measured 2026-08-17). So an agent
some other session started — a parent agent launching a child with
`tmux new-session -d …` is the ordinary case — is `foreign`, and stays foreign.

tmux changes one thing about that, and only one: it is itself a terminal
multiplexer, so the pty the agent writes to belongs to the tmux SERVER, which
accepts any number of clients. The owner can therefore start a *viewer* — a
plain `tmux attach-session` — under a pty it holds, and the surface opens that
pty like any other held terminal. The agent is not adopted, not resumed, not
moved: closing or stopping the viewer detaches one tmux client and nothing else.

## What is measured, and what is not trusted

The agent's environment says `TMUX=<socket>,<server pid>,<session index>` and
`TMUX_PANE=%<n>`. An environment is INHERITED, so on its own it is a claim, not
a fact: a process started from a tmux shell that then escaped to another pty
would still carry it. The claim is accepted only when the named server pid is
an ANCESTOR of the agent — a process cannot leave the tree it was forked into,
so that walk is the measurement the variable stands in for.

The binary used for the viewer is the server's own (`/proc/<server>/exe`), not
whatever `tmux` is first on some PATH: a client must speak its server's
protocol version, and the dashboard's PATH and the owner's are not the shell's.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

#: Every viewer label starts with this, so the listing can tell a viewer from an
#: agent without asking the owner for argv it does not report.
VIEWER_PREFIX = "tmux-"

_PANE_RE = re.compile(r"^%\d+$")


@dataclass(frozen=True)
class TmuxPane:
    """Where a foreign agent's pty lives — the server, and the pane on it."""

    socket: str
    server_pid: int
    pane: str


def _read_environ(pid: int) -> Dict[str, str]:
    try:
        with open(f"/proc/{pid}/environ", "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        logger.debug("tmux view: cannot read the environment of pid %s: %s", pid, exc)
        return {}
    env: Dict[str, str] = {}
    for item in raw.split(b"\0"):
        key, sep, value = item.partition(b"=")
        if sep:
            env[key.decode("utf-8", "replace")] = value.decode("utf-8", "replace")
    return env


def _parent_of(pid: int) -> Optional[int]:
    try:
        with open(f"/proc/{pid}/stat", "r", encoding="utf-8", errors="replace") as fh:
            stat = fh.read()
    except OSError:
        return None
    # The command name is in parentheses and may itself contain ") ", so the
    # fields are counted from the LAST closing parenthesis.
    rest = stat.rsplit(")", 1)[-1].split()
    try:
        return int(rest[1])
    except (IndexError, ValueError):
        return None


def _is_ancestor(ancestor: int, pid: int, *, limit: int = 64) -> bool:
    current: Optional[int] = pid
    for _ in range(limit):
        if current is None or current <= 1:
            return False
        if current == ancestor:
            return True
        current = _parent_of(current)
    return False


def pane_of(pid: int) -> Optional[TmuxPane]:
    """The tmux pane this process runs in, or None when it does not run in one.

    None covers "no tmux in its environment", "the environment names a server
    that is not its ancestor" and "unreadable" alike — every one of them means
    no viewer can be offered, and the surface keeps saying `foreign`.
    """
    env = _read_environ(pid)
    tmux = env.get("TMUX", "")
    pane = env.get("TMUX_PANE", "")
    if not tmux or not _PANE_RE.match(pane):
        return None
    parts = tmux.split(",")
    if len(parts) < 2:
        logger.debug("tmux view: pid %s has an unparseable TMUX value", pid)
        return None
    socket = parts[0]
    try:
        server_pid = int(parts[1])
    except ValueError:
        return None
    if not _is_ancestor(server_pid, pid):
        # The inherited-environment case. Logged, because it is exactly the
        # claim this module refuses to take on trust.
        logger.debug(
            "tmux view: pid %s names tmux server %s, which is not its ancestor — ignored",
            pid, server_pid,
        )
        return None
    return TmuxPane(socket=socket, server_pid=server_pid, pane=pane)


def tmux_binary(pane: TmuxPane) -> Optional[str]:
    """The server's own executable — see the module docstring for why."""
    try:
        exe = os.readlink(f"/proc/{pane.server_pid}/exe")
    except OSError as exc:
        logger.warning("tmux view: cannot resolve the binary of tmux server %s: %s",
                       pane.server_pid, exc)
        return None
    # A binary replaced on disk since the server started reads as "<path> (deleted)".
    return exe if os.path.isfile(exe) else None


def session_of(pane: TmuxPane) -> Optional[str]:
    """The name of the session that holds the pane NOW (sessions can be renamed)."""
    binary = tmux_binary(pane)
    if binary is None:
        return None
    try:
        out = subprocess.run(
            [binary, "-S", pane.socket, "display-message", "-p", "-t", pane.pane,
             "#{session_name}"],
            capture_output=True, text=True, timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("tmux view: could not ask server %s about %s: %s",
                       pane.server_pid, pane.pane, exc)
        return None
    if out.returncode != 0:
        logger.info("tmux view: server %s does not know pane %s: %s",
                    pane.server_pid, pane.pane, out.stderr.strip())
        return None
    name = out.stdout.strip()
    return name or None


def viewer_label(session: str) -> str:
    return f"{VIEWER_PREFIX}{session}"


def viewer_argv(pane: TmuxPane) -> Optional[List[str]]:
    """`tmux attach-session` to the pane's session — or None when it cannot run.

    Targeted by PANE id, not by session name: the id is what was measured, and a
    renamed session would otherwise send the viewer to whatever now carries the
    old name.
    """
    binary = tmux_binary(pane)
    if binary is None:
        return None
    return [binary, "-S", pane.socket, "attach-session", "-t", pane.pane]
