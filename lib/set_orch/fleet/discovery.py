"""Who is running, and where — from process state, never from a command line.

Task 2.1/2.2/2.4 of the `fleet-view` change, plus the parts of findings CB-2 and
CB-8 that touch discovery.

The load-bearing measurement (2026-08-18, this machine): an interactive agent's
command line is the binary and one flag, and names no path at all. Only `cwd`
says which project it is in. A naive match of the binary's name against every
process command line returned **31 false positives** — all of them shell
snapshots whose path happens to contain the word — so identity is read from
`/proc/<pid>/comm`, and the project from `/proc/<pid>/cwd`.

The runtime writes one record per live session under `~/.claude/sessions/<pid>.json`
carrying `pid`, `sessionId`, `cwd`, `procStart`, `name` and `status`. Measured the
same day: **23 records, 23 live processes, one to one, nothing stale.** That record
is therefore the binding between a process and its session log — a recorded fact,
not the 4-of-9 heuristic the design had to allow for. `sources` on each agent says
which of them knew about it, so a session the record missed is visible as such
rather than absent.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)

#: The runtime's per-session records. One file per live session, named by pid.
SESSION_RECORD_DIR = Path.home() / ".claude" / "sessions"

#: Where the runtime keeps one transcript directory per project.
SESSION_LOG_ROOT = Path.home() / ".claude" / "projects"

#: `comm` is truncated to 15 characters by the kernel, so match on that basis.
AGENT_COMM = "claude"

#: Flags that mean "this is a one-shot subprocess, not a session someone is sitting at".
#: Finding CB-8: the framework itself spawns these during every orchestration run, with
#: the project as cwd — exactly what discovery enumerates — and each would otherwise get
#: a tile, reported as waiting the moment it finished its last turn.
NON_INTERACTIVE_FLAGS = ("-p", "--print")


@dataclass
class Agent:
    """One live agent session.

    `sources` is not decoration. A session can be alive and unknown to the
    runtime's own records — measured twice on 2026-08-18, from two unrelated
    causes: a session still sitting at its start-up trust prompt, and a session
    that inherited a parent's child-session marker and so writes no transcript
    at all (the default for anything the framework spawns). Both are running
    work. Reporting them with an empty source list is the point.
    """

    pid: int
    cwd: str
    #: Resolved through git, so every worktree of one repository reports one project.
    project_root: Optional[str] = None
    project_name: Optional[str] = None
    branch: Optional[str] = None
    session_id: Optional[str] = None
    session_log: Optional[str] = None
    #: The address the runtime's cross-session channel answers to.
    name: Optional[str] = None
    #: `interactive` for a session someone is sitting at; `oneshot` for a `-p` subprocess.
    kind: str = "interactive"
    #: Which sources knew about this agent: "process", "session-record", "registry".
    sources: List[str] = field(default_factory=list)
    #: True when the binding to `session_log` came from a record rather than a guess.
    binding_confirmed: bool = False

    @property
    def is_interactive(self) -> bool:
        return self.kind == "interactive"


@dataclass
class ProjectEntry:
    """A project the fleet knows about, and which sources knew it."""

    root: str
    name: str
    sources: List[str] = field(default_factory=list)
    agent_pids: List[int] = field(default_factory=list)
    archived: bool = False


# --------------------------------------------------------------------------- #
# process state
# --------------------------------------------------------------------------- #

def _read(path: str) -> Optional[str]:
    try:
        with open(path, "r", errors="replace") as fh:
            return fh.read()
    except (OSError, PermissionError):
        return None


def _proc_argv(pid: int, proc_root: str = "/proc") -> List[str]:
    raw = _read(os.path.join(proc_root, str(pid), "cmdline"))
    if not raw:
        return []
    return [part for part in raw.split("\0") if part]


def _proc_cwd(pid: int, proc_root: str = "/proc") -> Optional[str]:
    try:
        return os.readlink(os.path.join(proc_root, str(pid), "cwd"))
    except (OSError, PermissionError):
        return None


def _live_agent_pids(proc_root: str = "/proc") -> List[int]:
    """Every live process whose executable identity is the agent binary.

    Identity, not substring: `comm` is what the kernel records as the program's
    name. Matching command lines instead finds every shell that happens to have
    the word in a path — 31 of them on the machine this was measured on.
    """
    found: List[int] = []
    try:
        entries = os.listdir(proc_root)
    except OSError as exc:
        logger.warning("fleet discovery: cannot read %s: %s", proc_root, exc)
        return found
    for entry in entries:
        if not entry.isdigit():
            continue
        comm = _read(os.path.join(proc_root, entry, "comm"))
        if comm is None or comm.strip() != AGENT_COMM:
            continue
        found.append(int(entry))
    return found


def _classify_kind(pid: int, proc_root: str = "/proc") -> str:
    """Interactive session, or a one-shot subprocess the framework spawned (CB-8)."""
    argv = _proc_argv(pid, proc_root)
    for flag in NON_INTERACTIVE_FLAGS:
        if flag in argv[1:]:
            return "oneshot"
    return "interactive"


# --------------------------------------------------------------------------- #
# the runtime's session records
# --------------------------------------------------------------------------- #

def _load_session_records(record_dir: Path = SESSION_RECORD_DIR) -> Dict[int, dict]:
    """pid -> record, for records that are readable and name their own pid."""
    records: Dict[int, dict] = {}
    if not record_dir.is_dir():
        logger.debug("fleet discovery: no session record dir at %s", record_dir)
        return records
    for path in record_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            logger.warning("fleet discovery: unreadable session record %s: %s", path.name, exc)
            continue
        pid = data.get("pid")
        if not isinstance(pid, int):
            logger.warning("fleet discovery: session record %s has no pid", path.name)
            continue
        records[pid] = data
    return records


def _session_log_for(session_id: str, log_root: Path = SESSION_LOG_ROOT) -> Optional[str]:
    """The transcript for a session id, or None.

    A missing log is reported as missing. There is deliberately no fallback to
    "the newest log in this project" — measured at 4 correct of 9, and its
    failures are confident wrong answers rather than absences.
    """
    if not session_id:
        return None
    matches = sorted(log_root.glob(f"*/{session_id}.jsonl"))
    if not matches:
        return None
    return str(matches[0])


# --------------------------------------------------------------------------- #
# project resolution
# --------------------------------------------------------------------------- #

def _git_common_dir(cwd: str) -> Optional[str]:
    """The shared `.git` every worktree of one repository writes through."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=cwd, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("fleet discovery: git-common-dir failed in %s: %s", cwd, exc)
        return None
    if proc.returncode != 0:
        return None
    raw = proc.stdout.strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (Path(cwd) / path).resolve()
    return str(path)


def _git_branch(cwd: str) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def resolve_project(cwd: str) -> tuple[Optional[str], Optional[str]]:
    """(project_root, project_name) for a working directory, through git.

    Every worktree of one repository resolves to the same project, because the
    common git directory is shared. A directory that is not in a repository
    resolves to nothing rather than to itself — the caller decides what to do
    with an agent whose project is unknown.
    """
    common = _git_common_dir(cwd)
    if not common:
        return None, None
    root = os.path.dirname(common) if os.path.basename(common) == ".git" else common
    return root, os.path.basename(root.rstrip("/")) or None


# --------------------------------------------------------------------------- #
# public entry points
# --------------------------------------------------------------------------- #

def discover_agents(
    *,
    include_oneshot: bool = False,
    proc_root: str = "/proc",
    record_dir: Path = SESSION_RECORD_DIR,
    log_root: Path = SESSION_LOG_ROOT,
    registry_pids: Optional[Iterable[int]] = None,
) -> List[Agent]:
    """Every live agent session on this machine.

    `include_oneshot` defaults to False: the framework's own short-lived
    subprocesses run with a project as their cwd and are indistinguishable from
    a session by cwd alone (finding CB-8). They are classified, not guessed at —
    excluded by default and available on request.
    """
    records = _load_session_records(record_dir)
    registry = set(registry_pids or ())
    agents: List[Agent] = []

    for pid in sorted(_live_agent_pids(proc_root)):
        cwd = _proc_cwd(pid, proc_root)
        if cwd is None:
            logger.debug("fleet discovery: pid %s has no readable cwd, skipping", pid)
            continue
        kind = _classify_kind(pid, proc_root)
        if kind != "interactive" and not include_oneshot:
            continue

        sources = ["process"]
        record = records.get(pid)
        session_id = None
        name = None
        if record is not None:
            sources.append("session-record")
            session_id = record.get("sessionId")
            name = record.get("name")
        if pid in registry:
            sources.append("registry")

        root, project_name = resolve_project(cwd)
        agents.append(
            Agent(
                pid=pid,
                cwd=cwd,
                project_root=root,
                project_name=project_name,
                branch=_git_branch(cwd),
                session_id=session_id,
                session_log=_session_log_for(session_id, log_root) if session_id else None,
                name=name,
                kind=kind,
                sources=sources,
                binding_confirmed=record is not None,
            )
        )

    logger.info(
        "fleet discovery: %d agent(s), %d without a session record",
        len(agents), sum(1 for a in agents if not a.binding_confirmed),
    )
    return agents


def discover_projects(
    agents: Sequence[Agent],
    *,
    registered: Optional[Sequence[dict]] = None,
) -> List[ProjectEntry]:
    """The project list as a union of its sources, naming them per entry.

    Finding CB-3: an `archived` project is excluded by every other surface in
    this framework, so it is excluded here too — but the flag is carried rather
    than dropped, so a caller that wants them can ask.
    """
    by_root: Dict[str, ProjectEntry] = {}

    for entry in registered or ():
        root = entry.get("path") or entry.get("root")
        if not root:
            continue
        root = str(root).rstrip("/")
        by_root[root] = ProjectEntry(
            root=root,
            name=entry.get("name") or os.path.basename(root),
            sources=["registry"],
            archived=bool(entry.get("archived")),
        )

    for agent in agents:
        root = (agent.project_root or agent.cwd).rstrip("/")
        found = by_root.get(root)
        if found is None:
            found = ProjectEntry(
                root=root,
                name=agent.project_name or os.path.basename(root) or root,
                sources=[],
            )
            by_root[root] = found
        if "process" not in found.sources:
            found.sources.append("process")
        found.agent_pids.append(agent.pid)

    return sorted(by_root.values(), key=lambda p: p.name.lower())
