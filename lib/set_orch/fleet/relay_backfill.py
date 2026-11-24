"""Pull in the questions already open when a relay switch turns on (fleet-relay-backfill).

The relay's carrier is a `PreToolUse` hook. While the relay switch is off, the hook returns at
once and the question opens in the terminal's own dialog; turning the switch on later changes
nothing for it, because its hook has already returned. Reported by the owner on 2026-11-24
after three questions stayed in their terminals across a switch-on.

So at switch-on (and by hand, `set-relay-backfill`) this module:

- finds every `AskUserQuestion` open in a fleet-held session with no relay waiting record,
  and hands it to the relay's outbound exactly as the hook would have (D4) — then a carrier
  process waits for the answer and types it into the terminal: Esc, one line, Enter (D3);
- for the automatic-answer switch, also starts a decide-only worker for each question the
  relay holds that no decider has seen (D5).

What is logged: short session ids, counts and reasons. Never question or answer text — the
same rule as the relay itself.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from .. import local_config
from . import question_relay as qr

logger = logging.getLogger(__name__)

Getter = Callable[..., Any]

#: The worker's decide-only switch, passed beside the relay's three variables (D5).
ENV_NO_FORWARD = "SET_RELAY_NO_FORWARD"
POLL_S = 1.0
HEADER_CHARS = 60
SESSION_RECORDS = Path.home() / ".claude" / "sessions"


# --------------------------------------------------------------------------- #
# finding open questions (task 1.1)
# --------------------------------------------------------------------------- #

def open_calls(entries: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The `AskUserQuestion` calls in a transcript tail that have no result, oldest first.

    Sidechain entries are skipped: a session's own task children never ask its operator.
    """
    opened: Dict[str, Dict[str, Any]] = {}
    closed = set()
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("isSidechain"):
            continue
        for block in qr._blocks(entry, "tool_use"):
            if block.get("name") == qr.TOOL and block.get("id") and isinstance(block.get("input"), dict):
                opened[str(block["id"])] = {"tool_use_id": str(block["id"]), "input": block["input"],
                                            "timestamp": entry.get("timestamp")}
        for block in qr._blocks(entry, "tool_result"):
            if block.get("tool_use_id"):
                closed.add(str(block["tool_use_id"]))
    return [c for k, c in opened.items() if k not in closed and qr.questions_of(c["input"])]


def call_is_open(transcript: Optional[str], tool_use_id: str,
                 read: Callable[[Any], List[Dict[str, Any]]] = qr.transcript_entries) -> bool:
    """Whether the call still has no result — the question still stands in the terminal.

    Reads for the RESULT only, never for the `tool_use`: measured on runtime 2.1.331, an open
    call whose hook did nothing is not in the transcript at all until it resolves, and then
    the `tool_use` and its result land together (measurements M3, M4).
    """
    for entry in read(transcript):
        if isinstance(entry, dict) and not entry.get("isSidechain"):
            if any(str(b.get("tool_use_id")) == tool_use_id for b in qr._blocks(entry, "tool_result")):
                return False
    return True


@dataclass
class OpenQuestion:
    session_id: str
    cwd: str
    project: str
    transcript: str
    tool_use_id: str
    tool_input: Dict[str, Any]
    label: Optional[str] = None        # the fleet terminal; None = not fleet-held

    @property
    def sid(self) -> str:
        return qr._safe_id(self.session_id)[:8]

    def report(self) -> Dict[str, Any]:
        return {"project": self.project, "session": self.sid, "questions": len(qr.questions_of(self.tool_input)),
                **({"label": self.label} if self.label else {})}


def _session_record(pid: int, records: Path) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads((records / f"{int(pid)}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _fleet_agents() -> List[Dict[str, Any]]:
    from .owner_client import OwnerClient
    return OwnerClient().list_agents()


def _other_agents() -> List[Any]:
    from . import discovery
    return discovery.discover_agents()


def _log_for(session_id: str) -> Optional[str]:
    from . import discovery
    return discovery._session_log_for(session_id)


@dataclass
class World:
    """Everything a pull-in touches that a test replaces."""
    get: Getter = local_config.get
    # Looked up at call time, not bound at class definition, so a test can replace the
    # module's reach into the machine in one place (tests/unit/conftest.py does).
    fleet_agents: Callable[[], List[Dict[str, Any]]] = lambda: _fleet_agents()
    other_agents: Callable[[], List[Any]] = lambda: _other_agents()
    log_for: Callable[[str], Optional[str]] = lambda sid: _log_for(sid)
    read: Callable[[Any], List[Dict[str, Any]]] = qr.transcript_entries
    run: Callable[..., int] = qr._run_command
    records: Path = SESSION_RECORDS
    base: Optional[Path] = None
    project_name: Callable[[str], str] = qr._project_name
    launch: Optional[Callable[[Dict[str, Any]], None]] = None
    spawn_worker: Optional[Callable[[str, Dict[str, str]], None]] = None
    wall: Callable[[], float] = time.time


def open_questions(w: World) -> List[OpenQuestion]:
    """Open questions with no relay waiting record: fleet-held first, then the rest unlabelled."""
    base = w.base or qr.state_dir()
    waiting = {r.get("session_id") for r in qr.list_waiting(base)}
    seen: set = set()
    out: List[OpenQuestion] = []

    def consider(session_id: Optional[str], cwd: str, transcript: Optional[str], label: Optional[str]) -> None:
        if not session_id or session_id in seen:
            return
        seen.add(session_id)
        if session_id in waiting or not transcript:
            return
        calls = open_calls(w.read(transcript))
        if not calls:
            return
        newest = calls[-1]          # one per session: the dialog on screen is the newest call
        out.append(OpenQuestion(session_id=session_id, cwd=cwd, project=w.project_name(cwd) if cwd else "unknown",
                                transcript=transcript, tool_use_id=newest["tool_use_id"],
                                tool_input=newest["input"], label=label))

    try:
        fleet = w.fleet_agents()
    except Exception as exc:
        logger.warning("relay backfill: the fleet's terminals could not be listed (%s)", type(exc).__name__)
        fleet = []
    try:
        others = w.other_agents()
    except Exception as exc:
        logger.warning("relay backfill: live sessions could not be discovered (%s)", type(exc).__name__)
        others = []
    # Live sessions: id → (cwd, transcript, fleet label or None).
    live: Dict[str, tuple] = {}
    for agent in fleet:
        rec = _session_record(agent.get("pid"), w.records) if agent.get("pid") else None
        sid = str((rec or {}).get("sessionId") or "")
        if sid:
            live[sid] = (str((rec or {}).get("cwd") or agent.get("cwd") or ""), w.log_for(sid),
                         str(agent.get("label") or "") or None)
    for agent in others:
        sid = str(getattr(agent, "session_id", None) or "")
        if sid and sid not in live:
            live[sid] = (str(getattr(agent, "cwd", "") or ""), getattr(agent, "session_log", None), None)

    # 1. What the hook parked: the call exactly as it was asked (M3 — the only source on a
    #    runtime that writes an open call to the transcript late).
    for rec in qr.list_parked(base):
        sid = str(rec["session_id"])
        if sid in seen:
            continue
        seen.add(sid)
        transcript = rec.get("transcript") or (live.get(sid, (None, None, None))[1])
        if sid not in live or not call_is_open(transcript, str(rec["tool_use_id"]), w.read):
            qr.unpark(sid, base)          # the session ended, or the call was answered
            continue
        if sid in waiting:
            continue
        cwd, _, label = live[sid]
        cwd = str(rec.get("cwd") or cwd)
        out.append(OpenQuestion(session_id=sid, cwd=cwd, project=w.project_name(cwd) if cwd else "unknown",
                                transcript=str(transcript or ""), tool_use_id=str(rec["tool_use_id"]),
                                tool_input=rec.get("tool_input") or {}, label=label))
    # 2. The transcript, for a session whose hook did not park (an older runtime, a call
    #    that was relayed and then released).
    for sid, (cwd, transcript, label) in live.items():
        consider(sid, cwd, transcript, label)
    return out


# --------------------------------------------------------------------------- #
# handing one over (task 1.2)
# --------------------------------------------------------------------------- #

def hand_over(q: OpenQuestion, w: World, carrier_pid: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Hand one open question to the relay's outbound, as the hook would have. The record or None."""
    base = w.base or qr.state_dir()
    state = qr.readiness(w.get)
    if not (state["enabled"] and state["ready"]) or state["target"] != "command":
        return None
    answer_dir = base / "answers"
    answer_dir.mkdir(parents=True, exist_ok=True)
    cid = qr.call_id(q.session_id, q.tool_use_id)
    envelope = qr.build_envelope(q.tool_input, cid, qr._text(w.get(qr.KEY_AUDIENCE)),
                                 f"{q.project} · {q.sid}", answer_dir)
    try:
        code = qr._hand(w.run, qr._text(w.get(qr.KEY_COMMAND)), json.dumps(envelope, ensure_ascii=False),
                        qr.relay_env(qr.KIND_ASK, q.session_id, q.cwd))
    except Exception as exc:
        logger.warning("relay backfill [%s]: outbound could not run (%s); left in the terminal", q.sid,
                       type(exc).__name__)
        return None
    if code != 0:
        logger.warning("relay backfill [%s]: outbound exited %s; left in the terminal", q.sid, code)
        return None
    record = {"session_id": q.session_id, "id": cid, "project": q.project, "cwd": q.cwd,
              "questions": len(envelope["questions"]), "target": "command", "started": w.wall(),
              "pid": carrier_pid or os.getpid(), "backfill": True, "tool_use_id": q.tool_use_id,
              "label": q.label, "transcript": q.transcript}
    qr._clear_waiting(q.session_id, base)
    qr._write_json(qr.waiting_path(q.session_id, base), record)
    logger.info("relay backfill [%s]: %d question(s) pulled in as %s; waiting", q.sid, record["questions"], cid)
    return record


# --------------------------------------------------------------------------- #
# carrying it to the answer (task 1.3)
# --------------------------------------------------------------------------- #

def answer_line(tool_input: Dict[str, Any], answers: List[str]) -> str:
    """The one line typed into the terminal: each question by its header, and its answer."""
    parts = []
    for i, (q, a) in enumerate(zip(qr.questions_of(tool_input), answers), start=1):
        head = " ".join(str(q.get("header") or "").split()) or " ".join(str(q.get("question") or "").split())
        head = head if len(head) <= HEADER_CHARS else head[:HEADER_CHARS - 1] + "…"
        parts.append(f"Q{i} “{head}”: {' '.join(a.split())}")
    many = len(parts) > 1
    return ("[fleet] Your question" + ("s were" if many else " was") + " answered on the relay channel "
            "(it was still open in this terminal when the relay came on). " + " | ".join(parts)
            + " — continue with " + ("these answers." if many else "this answer."))


def _label_live(label: str) -> bool:
    try:
        return any(a.get("label") == label for a in _fleet_agents())
    except Exception:
        return True        # the owner did not answer: not a reason to drop a question


def _type(label: str, line: str) -> None:
    from .takeover import owner_interrupt
    owner_interrupt(label, line)


def carry(record: Dict[str, Any], *, get: Getter = local_config.get, base: Optional[Path] = None,
          clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep,
          read: Callable[[Any], List[Dict[str, Any]]] = qr.transcript_entries,
          label_live: Callable[[str], bool] = _label_live,
          type_line: Callable[[str, str], None] = _type,
          tool_input: Optional[Dict[str, Any]] = None) -> str:
    """Wait for the answers to one pulled-in question and type them in. Returns the outcome."""
    base = base or qr.state_dir()
    sid = qr._safe_id(str(record.get("session_id")))[:8] or "unknown"
    cid = str(record.get("id"))
    count = int(record.get("questions") or 0)
    tool_use_id = str(record.get("tool_use_id") or "")
    transcript = record.get("transcript")
    label = str(record.get("label") or "")
    answer_dir = base / "answers"
    deadline = clock() + qr.timeout_s(get)

    def stale() -> Optional[str]:
        if not qr.record_is_own(record, base):
            return "waiting record replaced or removed"
        if qr.release_path(str(record.get("session_id")), base).exists():
            return "handed back to the terminal"
        if not qr.readiness(get)["enabled"]:
            return "switch turned off"
        if not call_is_open(transcript, tool_use_id, read):
            return "answered in the terminal"
        if label and not label_live(label):
            return "its fleet terminal is gone"
        return None

    outcome = "released"
    try:
        while True:
            reason = stale()
            if reason:
                logger.info("relay backfill [%s]: %s; nothing typed", sid, reason)
                return reason
            texts = qr.collect_answers(answer_dir, cid, count)
            if count and all(t is not None for t in texts):
                reason = stale()
                if reason:
                    logger.info("relay backfill [%s]: answer arrived but %s; nothing typed", sid, reason)
                    return reason
                for i in range(1, count + 1):
                    qr.answer_file(answer_dir, cid, f"Q{i}").unlink(missing_ok=True)
                qr.clear_own(record, base)
                ti = tool_input
                if ti is None:
                    found = [c for c in open_calls(read(transcript)) if c["tool_use_id"] == tool_use_id]
                    ti = found[0]["input"] if found else {"questions": [{}] * count}
                type_line(label, answer_line(ti, [t for t in texts if t is not None]))
                logger.info("relay backfill [%s]: answered on the channel; typed into %s", sid, label or "?")
                outcome = "typed"
                return outcome
            if clock() >= deadline:
                logger.info("relay backfill [%s]: no answer within %.0f s; left in the terminal", sid,
                            qr.timeout_s(get))
                return "timeout"
            sleep(POLL_S)
    finally:
        qr.clear_own(record, base)



# --------------------------------------------------------------------------- #
# the pull-in (tasks 1.4, 2.2)
# --------------------------------------------------------------------------- #

def _carrier_argv() -> List[str]:
    exe = Path(__file__).resolve().parents[3] / "bin" / "set-relay-backfill"
    return [str(exe), "--carry"] if exe.is_file() else [sys.executable, "-m", "set_orch.fleet.relay_backfill", "--carry"]


#: The environment a carrier must see as its caller does: where the relay's state, the machine
#: config and the decision log live.
_CARRIED_ENV = ("SET_QUESTION_RELAY_DIR", "SET_CONFIG_DIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "PATH")


def launch_carrier(job: Dict[str, Any]) -> None:
    """Start one carrier outside the caller's control group when systemd can (D2)."""
    argv = _carrier_argv()
    payload = json.dumps(job, ensure_ascii=False)
    if shutil.which("systemd-run") and os.environ.get("XDG_RUNTIME_DIR"):
        unit = f"set-relay-backfill-{qr._safe_id(str(job.get('session_id')))[:8]}-{int(time.time())}"
        # The job goes through a private file, not argv: argv is world-readable in /proc.
        jobs = qr.state_dir() / "backfill"
        jobs.mkdir(parents=True, exist_ok=True)
        path = jobs / f"{unit}.json"
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        # A transient unit starts in the USER MANAGER's environment, not the caller's, so the
        # overrides that place the relay's state and config travel explicitly. Measured
        # 2026-11-24: a test's carrier ran against the machine's real relay state because
        # SET_QUESTION_RELAY_DIR did not reach it.
        setenv = [f"--setenv={k}={os.environ[k]}" for k in _CARRIED_ENV if os.environ.get(k)]
        # KillMode=process: the decider worker the outbound starts lives in this unit's
        # cgroup, and the default (control-group) killed it when the carrier exited — the
        # same measurement: three workers died before their decision.
        proc = subprocess.run(["systemd-run", "--user", "--collect", "--quiet", f"--unit={unit}",
                               "--property=KillMode=process", *setenv, *argv, "--job", str(path)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=30)
        if proc.returncode == 0:
            return
        logger.warning("relay backfill: systemd-run refused (exit %s); starting the carrier detached",
                       proc.returncode)
        path.unlink(missing_ok=True)
    child = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             text=True, start_new_session=True, close_fds=True)
    assert child.stdin is not None
    child.stdin.write(payload)
    child.stdin.close()


def undecided_waiting(w: World) -> Dict[str, Any]:
    """Relay-held `ask` questions no decider has seen: one decide-only worker each (D5)."""
    from . import auto_answer_worker as aw
    base = w.base or qr.state_dir()
    started, skipped = [], []
    for rec in qr.list_waiting(base):
        if (rec.get("kind") or qr.KIND_ASK) != qr.KIND_ASK or rec.get("release_requested"):
            continue
        cid = str(rec.get("id") or "")
        sid = qr._safe_id(str(rec.get("session_id")))[:8]
        if not cid or aw.read_pending(base, cid) is not None:
            continue
        session_id = str(rec.get("session_id") or "")
        transcript = rec.get("transcript") or w.log_for(session_id)
        call = next((c for c in open_calls(w.read(transcript))
                     if qr.call_id(session_id, c["tool_use_id"]) == cid), None)
        if call is None:
            skipped.append({"project": rec.get("project"), "session": sid, "why": "its call is not in the transcript"})
            continue
        envelope = qr.build_envelope(call["input"], cid, qr._text(w.get(qr.KEY_AUDIENCE)),
                                     f"{rec.get('project')} · {sid}", base / "answers")
        relay_vars = {**qr.relay_env(qr.KIND_ASK, session_id, str(rec.get("cwd") or "")), ENV_NO_FORWARD: "1"}
        (w.spawn_worker or aw.spawn_worker)(json.dumps(envelope, ensure_ascii=False), relay_vars)
        started.append({"project": rec.get("project"), "session": sid})
        logger.info("relay backfill [%s]: decide-only worker started for %s", sid, cid)
    return {"decided": started, "not_decided": skipped}


def pull_in(trigger: str, w: Optional[World] = None, *, decide_waiting: bool = False) -> Dict[str, Any]:
    """Pull in what is open now. Never raises: a failure is reported, the switch stays as set."""
    w = w or World()
    launch = w.launch or (lambda job: launch_carrier(job))
    report: Dict[str, Any] = {"trigger": trigger, "pulled": [], "not_fleet_held": [], "skipped": []}
    try:
        state = qr.readiness(w.get)
        if not (state["enabled"] and state["ready"]) or state["target"] != "command":
            report["skipped"].append({"why": "the relay is off or not ready"})
            logger.info("relay backfill (%s): the relay is off or not ready; nothing pulled in", trigger)
            return report
        for q in open_questions(w):
            if not q.label:
                report["not_fleet_held"].append(q.report())
                continue
            # The carrier writes the record itself (its own pid is what keeps it alive);
            # here only the job is described.
            launch({"session_id": q.session_id, "cwd": q.cwd, "project": q.project,
                                          "transcript": q.transcript, "tool_use_id": q.tool_use_id,
                                          "tool_input": q.tool_input, "label": q.label})
            report["pulled"].append(q.report())
        if decide_waiting:
            report.update(undecided_waiting(w))
    except Exception as exc:
        logger.warning("relay backfill (%s): failed (%s)", trigger, type(exc).__name__)
        report["error"] = type(exc).__name__
    logger.info("relay backfill (%s): %d pulled in, %d not fleet-held, %d decide-only",
                trigger, len(report["pulled"]), len(report["not_fleet_held"]), len(report.get("decided", [])))
    return report


def run_job(job: Dict[str, Any], w: Optional[World] = None) -> str:
    """The carrier's body: hand over with its own pid, then carry to the answer."""
    w = w or World()
    q = OpenQuestion(session_id=str(job["session_id"]), cwd=str(job.get("cwd") or ""),
                     project=str(job.get("project") or ""), transcript=str(job.get("transcript") or ""),
                     tool_use_id=str(job["tool_use_id"]), tool_input=job.get("tool_input") or {},
                     label=job.get("label"))
    base = w.base or qr.state_dir()
    if qr.waiting_record(q.session_id, base):
        logger.info("relay backfill [%s]: the relay already holds a question here; not pulled in", q.sid)
        return "already-held"
    if not call_is_open(q.transcript, q.tool_use_id, w.read):
        logger.info("relay backfill [%s]: answered before the hand-over; not pulled in", q.sid)
        return "answered in the terminal"
    record = hand_over(q, w, carrier_pid=os.getpid())
    if record is None:
        return "not handed over"
    qr.unpark(q.session_id, base)
    return carry(record, get=w.get, base=base, read=w.read, tool_input=q.tool_input)


def main(argv: List[str]) -> int:
    qr.state_dir().mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=str(qr.state_dir() / "relay.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if "--carry" in argv:
        try:
            if "--job" in argv:
                path = Path(argv[argv.index("--job") + 1])
                job = json.loads(path.read_text(encoding="utf-8"))
                path.unlink(missing_ok=True)
            else:
                job = json.loads(sys.stdin.read())
            run_job(job)
        except Exception:
            logger.exception("relay backfill: carrier failed")
            return 1
        return 0
    report = pull_in("by-hand", decide_waiting="--decide" in argv)
    if report["skipped"] and not report["pulled"] and report["skipped"][0].get("why", "").startswith("the relay is off"):
        print("The relay is off or not ready; nothing was pulled in.")
        return 0
    print(f"Pulled in: {len(report['pulled'])}")
    for item in report["pulled"]:
        print(f"  {item['project']} · {item['session']} ({item.get('label')})")
    print(f"Not fleet-held, left in the terminal: {len(report['not_fleet_held'])}")
    for item in report["not_fleet_held"]:
        print(f"  {item['project']} · {item['session']}")
    if "decided" in report:
        print(f"Decide-only workers: {len(report['decided'])}; not decided: {len(report['not_decided'])}")
    if report.get("error"):
        print(f"Failed: {report['error']} (see the relay log)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
