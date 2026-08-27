"""The macOS reader — the same six facts, from `ps` and `lsof`.

Every command below was run on a real machine against live agent processes
before it was written here, and the numbers are from that run (632 processes):

    ps -A -o pid=,ppid=,comm=            0.01 s
    ps -p <pid> -o comm=                 0.00 s
    lsof -a -d cwd -Fpn -p 37343,33393   0.014 s   both working directories

The costs are why this module batches and the `/proc` one does not. `/proc`
answers per pid for the price of a file read; here every question is a process
spawn, so a per-pid implementation would fork once per fact per agent. One `ps`
for the whole table and one `lsof` for the matched pids answers a whole fleet
pass in three subprocesses regardless of how many agents there are.

**Two measured traps live in here, and both fail silently if you get them wrong.**

1. `lsof` exits **non-zero when any pid in the batch cannot be examined**,
   including one that has merely exited — and it does so while answering
   correctly for every other pid in the same call:

       lsof -a -d cwd -Fpn -p 37343,999999  ->  prints 37343's cwd,  rc=1
       lsof -a -d cwd -Fpn -p 999999        ->  prints nothing,      rc=1

   So the exit code cannot tell "answered nothing" from "answered some", and the
   ordinary `returncode != 0 -> failure` rule would report the whole machine as
   unmeasurable every time one process exited mid-pass. Stdout is parsed
   whatever the exit code; failure is concluded only when the command could not
   be run at all.

2. `ps` joins an argument vector with spaces, so an argument that itself
   contains a space **cannot be recovered on this platform**. That is a stated
   limitation rather than a hidden approximation — the current consumers test
   fixed positions and flag membership, neither of which a space breaks, and a
   consumer that needs exact arguments needs a different source.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Dict, List, Optional, Sequence

from ._types import ProcRow, TableRead, _basename

logger = logging.getLogger(__name__)

#: Bounded so a hung `ps` cannot hang the fleet's polling path.
TABLE_TIMEOUT = 10
PID_TIMEOUT = 5

#: Where macOS ships these, for the case where `PATH` does not say.
#:
#: **This is not belt-and-braces; it was measured breaking the whole feature.**
#: A launchd service does not inherit a login shell's `PATH`, and the dashboard's
#: does not contain `/usr/sbin`. Called as a bare name, `lsof` raised
#: `FileNotFoundError` there, every working directory came back unknown, and
#: `discover_agents()` — which skips a pid whose cwd it cannot read — returned an
#: EMPTY FLEET. From the screen that is indistinguishable from the `/proc` bug
#: this package exists to fix: 0 agents, no error, nothing to click.
#:
#: It survived the whole unit suite because tests replace `subprocess.run`, and
#: it survived the command line because an interactive shell has the directory on
#: its `PATH`. Only opening the running dashboard showed it.
FALLBACK_PATHS = {
    "lsof": ("/usr/sbin/lsof", "/usr/bin/lsof"),
    "ps": ("/bin/ps", "/usr/bin/ps"),
}


def _binary(name: str) -> str:
    """An absolute path for a reader command, or the bare name as a last resort.

    Resolved per call rather than cached: the answer depends on the environment
    the process is running in, and a cache written during a test run under one
    `PATH` would answer for a service running under another.
    """
    found = shutil.which(name)
    if found:
        return found
    for candidate in FALLBACK_PATHS.get(name, ()):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return name


def _run(argv: Sequence[str], timeout: int) -> Optional[subprocess.CompletedProcess]:
    """Run a reader command, or None when it could not be run at all.

    "Could not be run" is the only failure this reports. A non-zero exit is NOT
    one — see the module docstring for the measurement that decided it — so the
    caller receives the completed process and judges the output itself.

    The log line names the command and the status and nothing else. What these
    commands print is working directories, command lines and environments, which
    carry consumer paths and domain content this framework must not persist.
    """
    try:
        return subprocess.run(list(argv), capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("procsource: %s could not be run: %s", argv[0], type(exc).__name__)
        return None


def _ps_lines(argv: Sequence[str], timeout: int) -> Optional[List[str]]:
    """`ps` stdout as lines, or None when `ps` itself failed.

    Unlike `lsof`, a non-zero `ps` IS a failure: it has no partial-answer
    behaviour, and an empty process table is not something that happens on a
    running machine.
    """
    proc = _run(argv, timeout)
    if proc is None:
        return None
    if proc.returncode != 0:
        # A `-p <pid>` query for a process that has exited exits non-zero with
        # NOTHING on either stream — measured: `ps -p 99999 -o comm=` gives
        # rc=1, empty stdout, empty stderr. That is an answer ("no such
        # process"), not a failure, and reporting it as one would put a WARNING
        # in the log every time the fleet asked about a pid that had finished.
        # A real failure — a bad flag, a missing binary — says so on stderr.
        if not proc.stdout.strip() and not (proc.stderr or "").strip():
            logger.debug("procsource: ps matched no process for %s", argv[-1])
            return []
        logger.warning(
            "procsource: ps exited %s (%d bytes on stderr)",
            proc.returncode, len(proc.stderr or ""),
        )
        return None
    return proc.stdout.splitlines()


def _split_last_free(line: str, leading: int) -> Optional[List[str]]:
    """`leading` numeric fields, then the whole rest of the line as one value.

    Every `ps` format this module uses puts the field that may contain spaces
    LAST, and this is the parse that relies on it. Splitting the whole line on
    whitespace instead would break 19 of the 632 processes measured on one
    machine — the ones whose executable path contains a space, such as an
    application bundle under `Software Update.app`.
    """
    parts = line.split(None, leading)
    if len(parts) <= leading:
        return None
    for field in parts[:leading]:
        if not field.isdigit():
            return None
    return parts


# --------------------------------------------------------------------------- #
# the whole-table forms — one `ps` each, and never both in one command
# --------------------------------------------------------------------------- #

def _identity_table() -> Optional[Dict[int, ProcRow]]:
    """pid -> (ppid, comm), from `ps -A -o pid=,ppid=,comm=`.

    **`comm` must be the last column, and this is not a style choice.** Measured:
    with another column after it, `ps` truncates `comm` to that column's width —
    pid 94 reported `comm=/usr/libexec/log` next to `args=/usr/libexec/logd`,
    losing the final character of its identity. A truncated identity does not
    fail; it silently fails to match, which is the false-absence shape this whole
    package exists to remove. So arguments are read by a SECOND command rather
    than appended to this one.
    """
    lines = _ps_lines([_binary("ps"), "-A", "-o", "pid=,ppid=,comm="], TABLE_TIMEOUT)
    if lines is None:
        return None
    out: Dict[int, ProcRow] = {}
    for line in lines:
        parts = _split_last_free(line, 2)
        if parts is None:
            continue
        pid = int(parts[0])
        out[pid] = ProcRow(pid=pid, ppid=int(parts[1]), comm=parts[2].strip())
    return out


def _argv_table() -> Optional[Dict[int, List[str]]]:
    """pid -> arguments, from `ps -ww -A -o pid=,args=`.

    `-ww` disables the width-based truncation `ps` applies when it believes it is
    writing to a terminal; without it a long command line is cut, and a cut
    command line is a wrong answer that looks like a short one.
    """
    lines = _ps_lines([_binary("ps"), "-ww", "-A", "-o", "pid=,args="], TABLE_TIMEOUT)
    if lines is None:
        return None
    out: Dict[int, List[str]] = {}
    for line in lines:
        parts = _split_last_free(line, 1)
        if parts is None:
            continue
        out[int(parts[0])] = parts[1].split()
    return out


def read_table() -> TableRead:
    """Every live process with its identity and its parent, in one `ps` call.

    Arguments are deliberately NOT included — see `_identity_table` for the
    truncation that makes combining them wrong, and `argvs()` for the reader
    that answers them.
    """
    rows = _identity_table()
    if rows is None:
        return TableRead(failed=True)
    return TableRead(rows=rows)


# --------------------------------------------------------------------------- #
# the six facts
# --------------------------------------------------------------------------- #

def live_pids(name: str) -> Optional[List[int]]:
    """Pids whose executable identity is `name`, or None if `ps` failed.

    Identity, not substring. `ps -o comm=` prints a full executable path for
    many processes on this platform and a bare name for others, so the basename
    is compared for equality — which also means a shell whose command line
    merely contains the word does not match, and there were 31 of those on the
    machine the Linux reader was measured against.
    """
    table = read_table()
    if table.failed:
        return None
    return table.pids_with_comm(name)


def comm(pid: int) -> Optional[str]:
    """The identity of ONE pid, without reading the whole table.

    The bare name is returned rather than the path `ps` may print, so that a
    caller comparing against a name gets the same string shape both platforms
    produce.
    """
    lines = _ps_lines([_binary("ps"), "-p", str(pid), "-o", "pid=,comm="], PID_TIMEOUT)
    if not lines:
        return None
    parts = _split_last_free(lines[0], 1)
    return _basename(parts[1]) if parts else None


def cwd(pid: int) -> Optional[str]:
    return cwds([pid]).get(pid)


def cwds(pids: Sequence[int]) -> Dict[int, Optional[str]]:
    """Working directories for many pids in ONE `lsof` call.

    Every requested pid appears in the result; one that `lsof` did not answer for
    maps to None. A pid absent from the output is unknown individually — it does
    not fail the batch, because the commonest reason for it is that the process
    exited between the `ps` and this call.

    Read the module docstring before touching the exit-code handling here.
    """
    wanted = [int(p) for p in pids]
    out: Dict[int, Optional[str]] = {pid: None for pid in wanted}
    if not wanted:
        return out

    proc = _run(
        [_binary("lsof"), "-a", "-d", "cwd", "-Fpn", "-p", ",".join(str(p) for p in wanted)],
        PID_TIMEOUT,
    )
    if proc is None:
        return out

    # `-F` output is one field per line, tagged by its first character: `p<pid>`
    # opens a process block, `n<path>` is the name of the file in it. There is
    # exactly one `n` per block here because `-d cwd` restricts it to one.
    current: Optional[int] = None
    for line in proc.stdout.splitlines():
        if not line:
            continue
        tag, value = line[0], line[1:]
        if tag == "p" and value.isdigit():
            current = int(value)
        elif tag == "n" and current in out:
            out[current] = value or None
    return out


def argv(pid: int) -> Optional[List[str]]:
    """One pid's arguments, whitespace-split. See the module docstring."""
    lines = _ps_lines([_binary("ps"), "-ww", "-p", str(pid), "-o", "pid=,args="], PID_TIMEOUT)
    if not lines:
        return None
    parts = _split_last_free(lines[0], 1)
    return parts[1].split() if parts else None


def argvs(pids: Optional[Sequence[int]] = None) -> Optional[Dict[int, List[str]]]:
    """Arguments for the given pids, or for every live process when None.

    The whole-table form is one `ps`, which is what makes a waiter scan over
    several hundred processes affordable here.
    """
    table = _argv_table()
    if table is None:
        return None
    if pids is None:
        return table
    wanted = {int(p) for p in pids}
    return {pid: args for pid, args in table.items() if pid in wanted}


def ppid(pid: int) -> Optional[int]:
    lines = _ps_lines([_binary("ps"), "-p", str(pid), "-o", "pid=,ppid="], PID_TIMEOUT)
    if not lines:
        return None
    parts = _split_last_free(lines[0], 1)
    if parts is None or not parts[1].strip().isdigit():
        return None
    return int(parts[1].strip())


def env_value(pid: int, key: str) -> Optional[str]:
    """One environment variable of a process this user owns, or None.

    `ps -E` prints a process's environment after its command line, and macOS
    permits it for a process the caller owns — measured against a live agent and
    against the dashboard's own launchd job. There is no `/proc/<pid>/environ`
    here and no privileged alternative worth asking the user for.

    None means **unknown**, never "set to nothing". The callers depend on that:
    a waiter whose session cannot be read is treated as alive and is never
    offered for removal, which is the direction that cannot kill a working one.

    The command line and the environment arrive concatenated and space-joined,
    so a value containing a space cannot be recovered. Every value asked for
    here is an identity — a session uuid — which has none.
    """
    proc = _run([_binary("ps"), "-E", "-p", str(pid), "-o", "command="], PID_TIMEOUT)
    if proc is None:
        return None
    marker = key + "="
    for token in proc.stdout.split():
        if token.startswith(marker):
            return token[len(marker):] or None
    return None
