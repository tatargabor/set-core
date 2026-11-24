"""The decider's outbound and its worker — `set-auto-answer` (fleet-auto-answer, group 3).

The relay runs `set-auto-answer` as its outbound. With the switch off it is a pipe to
the operator's real outbound (`auto_answer.forward_command`), byte for byte. With the
switch on it hands the envelope to a DETACHED worker and returns at once (D2): the relay
records its waiting state only after its outbound exits, so a model call inside that
exit would hide the waiting agent from the fleet.

The worker decides (bounded), writes a pending record, forwards the question WITH the
proposal (D4), and — only for an allowed answer — writes it after the window unless a
human answer arrived first or the proposal was cancelled (D7: an exclusive create, never
an overwrite). It keeps watching until the question ends, so the decision log records the
operator's own answer next to the proposal: that pair is the live accuracy (D14).

What is stored, and where (D9): the pending record beside the relay's answer store, and
one decision-log record per question under `~/.local/share/set-core/auto-answer/`, mode
600. Both hold question text; neither is ever written into a repository, and the log
lines of this module carry ids, counts, tiers and outcomes only.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .. import local_config
from . import auto_answer as aa
from . import question_relay as qr

logger = logging.getLogger(__name__)

Getter = Callable[..., Any]

POLL_S = 1.0
PENDING_RETENTION_S = qr.ANSWER_RETENTION_S
RECORD_WAIT_S = 15.0          # how long to wait for the relay's waiting record to appear
EXCERPT_CHARS = 140

OUT_WRITTEN = "written"
OUT_EXCLUDED = aa.OUTCOME_EXCLUDED
OUT_BELOW_BAR = aa.OUTCOME_BELOW_BAR
OUT_CANCELLED = "cancelled"
OUT_OVERTAKEN = "overtaken"
OUT_NO_DECISION = "no-decision"
OUT_RELEASED = "released"         # the question ended with no answer this worker saw
OUT_FORWARD_FAILED = "forward-failed"
OUT_CLOSED = "closed"             # a finished turn with nothing worth doing: left idle, not posted
OUT_HELD = "held"                 # allowed, but another question of the same call is not


# --------------------------------------------------------------------------- #
# where things live
# --------------------------------------------------------------------------- #

def log_path() -> Path:
    root = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(root) / "set-core" / "auto-answer" / "decisions.jsonl"


def pending_dir(base: Path) -> Path:
    return base / "auto-answer"


def pending_path(base: Path, cid: str) -> Path:
    return pending_dir(base) / f"{qr._safe_id(cid)}.json"


def _private_write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=1)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def read_pending(base: Path, cid: str) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(pending_path(base, cid).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def list_pending(base: Optional[Path] = None) -> List[Dict[str, Any]]:
    folder = pending_dir(base or qr.state_dir())
    out = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


def cancel(cid: str, base: Optional[Path] = None) -> bool:
    """Mark a pending proposal cancelled. The worker re-reads it before writing (D7)."""
    base = base or qr.state_dir()
    record = read_pending(base, cid)
    if record is None or record.get("state") != "proposed":
        return False
    record["cancelled"] = True
    record["cancelled_at"] = time.time()
    _private_write(pending_path(base, cid), record)
    logger.info("auto answer [%s]: cancelled from the fleet", qr._safe_id(cid)[-12:])
    return True


def prune_pending(base: Path, now: float) -> int:
    folder = pending_dir(base)
    removed = 0
    for path in folder.glob("*.json") if folder.is_dir() else []:
        try:
            if now - path.stat().st_mtime > PENDING_RETENTION_S:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def append_log(records: List[Dict[str, Any]], *, get: Getter = local_config.get,
               path: Optional[Path] = None, now: Optional[float] = None) -> None:
    """Append, then drop records older than `auto_answer.log_days`. Owner-only, always."""
    path = path or log_path()
    now = time.time() if now is None else now
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as handle:
        for r in records:
            handle.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.chmod(path, 0o600)
    horizon = now - aa.log_days(get) * 86400
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    kept = []
    for line in lines:
        try:
            ts = float(json.loads(line).get("ts", now))
        except (ValueError, AttributeError, TypeError):
            continue
        if ts >= horizon:
            kept.append(line)
    if len(kept) != len(lines):
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("".join(l + "\n" for l in kept))
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        logger.info("auto answer: pruned %d decision-log record(s)", len(lines) - len(kept))


def read_log(limit: int = 50, path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """The newest records first. Read on request, never cached (D13)."""
    path = path or log_path()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in reversed(lines):
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
        if len(out) >= limit:
            break
    return out


# --------------------------------------------------------------------------- #
# what the fleet reads (task 4.1)
# --------------------------------------------------------------------------- #

def set_enabled(enabled: bool) -> None:
    local_config.set_value(aa.KEY_ENABLED, bool(enabled))
    logger.info("auto answer: switch %s", "on" if enabled else "off")


def wired(get: Getter = local_config.get) -> bool:
    """Whether the relay's outbound IS this decider — without it the switch does nothing."""
    command = aa._text(get(qr.KEY_COMMAND))
    first = command.split()[0] if command else ""
    return os.path.basename(first) == "set-auto-answer"


def pending_view(now: float, base: Optional[Path] = None) -> List[Dict[str, Any]]:
    """The live proposals: what will be written, when, from which checked sources."""
    out = []
    for rec in list_pending(base):
        if rec.get("state") != "proposed" or rec.get("cancelled"):
            continue
        write_at = rec.get("write_at")
        for q in rec.get("questions") or []:
            if q.get("outcome") != aa.OUTCOME_ALLOWED:
                continue
            out.append({
                "id": rec.get("id"), "key": q.get("key"), "session_id": rec.get("session_id"),
                "agent": rec.get("source"), "project": rec.get("project"), "kind": rec.get("kind"),
                "question": q.get("question"), "choice": q.get("choice"), "tier": q.get("tier"),
                "confidence": q.get("confidence"),
                # Shown as the channel shows them: relative to the tree, never a home path
                # (seen on the running screen: the fork had cited an absolute path).
                "references": [{**r, **({"path": _shown_path(str(r["path"]), str(rec.get("cwd") or ""))}
                                        if r.get("path") else {})}
                               for r in q.get("references") or [] if r.get("checked")],
                "seconds_left": max(0.0, write_at - now) if isinstance(write_at, (int, float)) else None,
            })
    return out


def send_proposal(call_id: str, base: Optional[Path] = None) -> Optional[str]:
    """Send the decider's proposal as the OPERATOR's answer, now. None on success, else why not.

    Asked for by the owner (2026-11-24): an excluded or below-bar proposal is often right, and
    the one-click way to say so was missing. This is the person answering — through the same
    answer file the chat bridge and the fleet's own answer box write — so the exclusion, the
    bar and the window do not apply: they govern what the DECIDER may write on its own. The
    worker sees the answer like any human one and logs it as the operator's (`overtaken`).
    """
    base = base or qr.state_dir()
    rec = read_pending(base, call_id)
    if rec is None:
        return "no proposal is recorded for that question"
    if rec.get("state") == "done":
        return "the proposal was already written"
    questions = rec.get("questions") or []
    if len(questions) != 1:
        return "the agent asked several questions at once; answer them in its terminal"
    choice = questions[0].get("choice")
    if not isinstance(choice, str) or not choice.strip():
        return "the decider made no proposal for this question"
    session_id = str(rec.get("session_id") or "")
    record = qr.waiting_record(session_id, base)
    if not record or record.get("id") != call_id:
        return "the question is no longer waiting on the relay"
    why = qr.deliver_answer(session_id, choice, base)
    if why is None:
        logger.info("auto answer [%s]: the operator sent the proposal from the fleet", qr._safe_id(call_id)[-12:])
    return why


def verdict_view(now: float, base: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """The decider's verdict per relayed call, for the relay's waiting list.

    Asked for by the owner (2026-11-24): four questions sat on the relay panel with no sign
    that the decider had looked at them — it had (two excluded, one abstained), and nothing
    on the screen said so. One entry per call id: the first question's outcome, the proposal,
    and the countdown only while an allowed proposal is still due to be written.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for rec in list_pending(base):
        qs = rec.get("questions") or []
        if not qs or not rec.get("id"):
            continue
        q = next((x for x in qs if x.get("outcome") == aa.OUTCOME_ALLOWED), qs[0])
        write_at = rec.get("write_at")
        due = (rec.get("state") == "proposed" and not rec.get("cancelled")
               and q.get("outcome") == aa.OUTCOME_ALLOWED and isinstance(write_at, (int, float)))
        out[str(rec["id"])] = {
            "state": "cancelled" if rec.get("cancelled") else rec.get("state"),
            "outcome": q.get("outcome"), "reason": q.get("reason") or "",
            "choice": q.get("choice"), "tier": q.get("tier"),
            "seconds_left": max(0.0, write_at - now) if due else None,
        }
    return out


def status(get: Getter = local_config.get, base: Optional[Path] = None,
           now: Optional[float] = None) -> Dict[str, Any]:
    now = time.time() if now is None else now
    pending = pending_view(now, base)
    return {"enabled": aa.enabled(get), "wired": wired(get), "forward": bool(aa.forward_command(get)),
            "window_s": aa.window_s(get), "likely_min": aa.likely_min(get),
            "pending": pending, "pending_count": len(pending)}


# --------------------------------------------------------------------------- #
# the proposal, as the operator reads it
# --------------------------------------------------------------------------- #

def _shown_path(path: str, cwd: str) -> str:
    """A source path as it may appear in a channel: relative to the tree, never a home path."""
    p = os.path.expanduser(path)
    if cwd and os.path.isabs(p) and (p == cwd or p.startswith(cwd.rstrip("/") + "/")):
        return os.path.relpath(p, cwd)
    if os.path.isabs(p):
        home = str(Path.home())
        return "~/" + os.path.relpath(p, home) if p.startswith(home + "/") else os.path.basename(p)
    return path


def source_line(answer: aa.Answer, cwd: str) -> str:
    checked = [r for r in answer.references if r.checked]
    if not checked:
        return "no checked source"
    r = checked[0]
    quote = aa.normalise(r.quote)
    quote = quote if len(quote) <= EXCERPT_CHARS else quote[:EXCERPT_CHARS - 1] + "…"
    where = "your words" if r.kind == "operator" else _shown_path(r.path, cwd)
    more = f" (+{len(checked) - 1} more)" if len(checked) > 1 else ""
    return f"{where}: “{quote}”{more}"


def proposal_text(answer: aa.Answer, cwd: str, *, write_at: Optional[float], reason: str = "") -> str:
    tier = answer.tier if answer.tier != aa.TIER_LIKELY else f"likely {answer.confidence:.2f}"
    src = source_line(answer, cwd)
    if write_at is not None:
        when = datetime.fromtimestamp(write_at).strftime("%H:%M:%S")
        return (f"\n\n🤖 Auto-answer: «{answer.choice}» — {tier}; {src}. "
                f"Written at {when} unless you answer first.")
    return f"\n\n🤖 Recommendation (not written automatically — {reason}): «{answer.choice}» — {tier}; {src}."


# --------------------------------------------------------------------------- #
# the outbound entry point (task 3.1)
# --------------------------------------------------------------------------- #

Runner = Callable[..., int]


def outbound(payload: str, *, get: Getter = local_config.get, environ: Optional[Dict[str, str]] = None,
             run: Runner = qr._run_command, spawn: Optional[Callable[[str, Dict[str, str]], None]] = None) -> int:
    """What `set-auto-answer` does with one envelope. Returns its exit code."""
    environ = dict(os.environ if environ is None else environ)
    forward = aa.forward_command(get)
    relay_vars = {k: environ.get(k, "") for k in (qr.ENV_KIND, qr.ENV_SESSION, qr.ENV_CWD)}
    if not aa.enabled(get):
        if not forward:
            logger.warning("auto answer: off and %s is not set; nothing to forward to", aa.KEY_FORWARD)
            return 1
        code = run(forward, payload, env={k: v for k, v in relay_vars.items() if v})
        logger.info("auto answer: off — forwarded unchanged (exit %s)", code)
        return code
    try:
        envelope = json.loads(payload)
        ok = isinstance(envelope, dict) and bool(aa.questions_of(envelope))
    except ValueError:
        ok = False
    if not ok:
        logger.warning("auto answer: the envelope carries no question; forwarded unchanged")
        return run(forward, payload, env={k: v for k, v in relay_vars.items() if v}) if forward else 1
    (spawn or spawn_worker)(payload, relay_vars)
    logger.info("auto answer: worker started for kind %s", relay_vars.get(qr.ENV_KIND) or "?")
    return 0


def spawn_worker(payload: str, relay_vars: Dict[str, str]) -> None:
    """A detached worker: its own session, the envelope on stdin, nothing tied to the relay."""
    exe = Path(__file__).resolve().parents[3] / "bin" / "set-auto-answer"
    argv = [str(exe), "--worker"] if exe.is_file() else [sys.executable, "-m", "set_orch.fleet.auto_answer_worker", "--worker"]
    env = {**os.environ, **relay_vars}
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            env=env, text=True, start_new_session=True, close_fds=True)
    assert proc.stdin is not None
    proc.stdin.write(payload)
    proc.stdin.close()


# --------------------------------------------------------------------------- #
# the worker (tasks 3.2, 3.3, 3.4)
# --------------------------------------------------------------------------- #

@dataclass
class World:
    """Everything the worker touches that a test replaces."""
    get: Getter = local_config.get
    decide: Callable[..., aa.Decision] = aa.decide
    run: Runner = qr._run_command
    wall: Callable[[], float] = time.time
    sleep: Callable[[float], None] = time.sleep
    log: Optional[Path] = None


def _write_answer(answer_dir: Path, cid: str, key: str, text: str) -> bool:
    """Create the answer file only if none exists: a link, never a rename over it (D7)."""
    target = qr.answer_file(answer_dir, cid, key)
    answer_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(answer_dir), prefix=".auto-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"valasz": text}, handle, ensure_ascii=False)
        os.link(tmp, target)
        return True
    except FileExistsError:
        return False
    finally:
        Path(tmp).unlink(missing_ok=True)


def _read_one(path: Path) -> Optional[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get("valasz") if isinstance(data, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def _record_live(base: Path, session_id: str, cid: str) -> bool:
    record = qr.waiting_record(session_id, base)
    return bool(record and record.get("id") == cid and not record.get("release_requested")
                and not qr.release_path(session_id, base).exists())


def work(payload: str, relay_vars: Dict[str, str], world: Optional[World] = None) -> Dict[str, str]:
    """Decide, forward, wait, write. Returns the outcome per question key."""
    w = world or World()
    envelope = json.loads(payload)
    questions = aa.questions_of(envelope)
    first = (envelope.get("questions") or [{}])[0]
    cid = str(first.get("id") or "")
    answer_dir = Path(str(first.get("valasz_tar") or (qr.state_dir() / "answers")))
    base = answer_dir.parent
    kind = relay_vars.get(qr.ENV_KIND) or aa.KIND_ASK
    session_id = relay_vars.get(qr.ENV_SESSION) or ""
    cwd = relay_vars.get(qr.ENV_CWD) or ""
    label = qr._safe_id(cid)[-12:] or "?"
    asked_at = w.wall()
    prune_pending(base, asked_at)

    t0 = time.monotonic()
    decision = w.decide(envelope, kind=kind, session_id=session_id, cwd=cwd, asked_at=asked_at, get=w.get)
    latency = round(time.monotonic() - t0, 1)

    never = aa.never_patterns(w.get)
    bar = aa.likely_min(w.get)
    outcome: Dict[str, str] = {}
    reasons: Dict[str, str] = {}
    for q in questions:
        a = decision.answers.get(q.key)
        if a is None:
            outcome[q.key], reasons[q.key] = OUT_NO_DECISION, decision.refused.get(q.key, "no decision")
            continue
        excl = aa.exclusion(kind, q, a.choice, a.outward, never, aa.allow_families(w.get))
        outcome[q.key] = aa.allow(a.tier, a.confidence, excl, bar)
        reasons[q.key] = excl or ("" if outcome[q.key] == aa.OUTCOME_ALLOWED else
                                  f"likely {a.confidence:.2f} below {bar:.2f}")
    allowed = [q.key for q in questions if outcome[q.key] == aa.OUTCOME_ALLOWED]
    if allowed and len(allowed) < len(questions):
        # All or nothing (measured live 2026-11-24): a two-question call had Q1 written and
        # Q2 abstained. The relay waits for EVERY key, so the agent stayed blocked for 27 min,
        # and the written Q1 would have pre-empted the operator's own Q1 answer. One call is
        # answered by one party: the decider only when it may answer all of it.
        for key in allowed:
            outcome[key], reasons[key] = OUT_HELD, "another question in the same call needs you"
        logger.info("auto answer [%s]: %d of %d questions allowed — none written, all forwarded",
                    qr._safe_id(cid)[-12:], len(allowed), len(questions))
        allowed = []

    forwarded_at = w.wall()
    write_at = forwarded_at + aa.window_s(w.get) if allowed else None
    pending = {
        "id": cid, "session_id": session_id, "kind": kind, "source": str(first.get("source") or ""),
        "project": os.path.basename(cwd.rstrip("/")) if cwd else "", "cwd": cwd, "created": forwarded_at,
        "write_at": write_at, "state": "proposed" if allowed else "forwarded", "cancelled": False,
        "method": decision.method,
        "questions": [{
            "key": q.key, "question": q.text, "options": q.options, "outcome": outcome[q.key],
            "reason": reasons[q.key],
            **({"choice": decision.answers[q.key].choice, "tier": decision.answers[q.key].tier,
                "confidence": decision.answers[q.key].confidence,
                "references": [r.as_record() for r in decision.answers[q.key].references]}
               if q.key in decision.answers else {}),
        } for q in questions],
    }
    _private_write(pending_path(base, cid), pending)

    # Forward the question, with the proposal or the recommendation attached (D4).
    shown = json.loads(payload)
    for entry in shown.get("questions") or []:
        a = decision.answers.get(str(entry.get("key")))
        if a is None:
            continue
        key = str(entry.get("key"))
        entry["question"] = str(entry.get("question") or "") + proposal_text(
            a, cwd, write_at=write_at if key in allowed else None, reason=reasons.get(key, ""))
    if kind == aa.KIND_CONTINUATION and questions and all(
            reasons.get(q.key, "").startswith(aa.DONE_PREFIX) for q in questions):
        # Nothing worth doing: close quietly — no post on the channel, no wake, no tokens.
        for q in questions:
            outcome[q.key] = OUT_CLOSED
        logger.info("auto answer [%s]: finished turn, nothing worth doing; left idle, not posted", label)
        _wait_for_record(base, session_id, cid, w)
        qr.request_release(session_id, base)
        return _close(w, pending, decision, outcome, reasons, {}, latency, base, cid)
    forward = aa.forward_command(w.get)
    if forward:
        try:
            code = w.run(forward, json.dumps(shown, ensure_ascii=False),
                         env={k: v for k, v in relay_vars.items() if v})
        except Exception as exc:
            logger.warning("auto answer [%s]: forward could not run (%s)", label, type(exc).__name__)
            code = -1
        if code != 0:
            # The operator cannot see the proposal, so nothing may act on it: hand back.
            logger.warning("auto answer [%s]: forward exited %s; released to the terminal, nothing written", label, code)
            for key in list(outcome):
                if outcome[key] == aa.OUTCOME_ALLOWED:
                    outcome[key] = OUT_FORWARD_FAILED
            allowed, write_at = [], None
            _wait_for_record(base, session_id, cid, w)
            qr.request_release(session_id, base)
            return _close(w, pending, decision, outcome, reasons, {}, latency, base, cid)
    elif not allowed:
        logger.info("auto answer [%s]: no forward command and no automatic answer; released", label)
        _wait_for_record(base, session_id, cid, w)
        qr.request_release(session_id, base)
        return _close(w, pending, decision, outcome, reasons, {}, latency, base, cid)
    logger.info("auto answer [%s]: %s via %s — %s", label, kind, decision.method,
                ", ".join(f"{k}={v}" for k, v in outcome.items()))

    # Watch: until the window ends (allowed keys), then until the question ends (the log).
    human: Dict[str, str] = {}
    written: Dict[str, str] = {}
    if not _wait_for_record(base, session_id, cid, w):
        logger.warning("auto answer [%s]: the relay recorded no waiting state; nothing written", label)
        for key in allowed:
            outcome[key] = OUT_RELEASED
        return _close(w, pending, decision, outcome, reasons, human, latency, base, cid)
    deadline = qr.timeout_s(w.get) + forwarded_at + 60
    while True:
        for q in questions:
            if q.key not in human and q.key not in written:
                text = _read_one(qr.answer_file(answer_dir, cid, q.key))
                if text is not None:
                    human[q.key] = text
        current = read_pending(base, cid)
        if allowed and (current is None or current.get("cancelled")):
            for key in allowed:
                if key not in human:
                    outcome[key] = OUT_CANCELLED
            logger.info("auto answer [%s]: cancelled before the write", label)
            allowed, write_at = [], None
            pending["state"] = "cancelled"
            if current is not None:
                _private_write(pending_path(base, cid), {**current, "state": "cancelled"})
        for key in list(allowed):
            if key in human:
                outcome[key] = OUT_OVERTAKEN
                allowed.remove(key)
        if allowed and not _record_live(base, session_id, cid):
            # The question ended elsewhere (typed prompt, terminal answer, the hook gone): stop
            # now, so the panel and the tile do not count down to a write that cannot happen.
            for key in allowed:
                outcome[key] = OUT_RELEASED
            logger.info("auto answer [%s]: the question ended before the window — nothing written", label)
            allowed = []
        if allowed and write_at is not None and w.wall() >= write_at:
            if not _record_live(base, session_id, cid):
                for key in allowed:
                    outcome[key] = OUT_RELEASED
            else:
                for key in allowed:
                    choice = decision.answers[key].choice
                    if _write_answer(answer_dir, cid, key, choice):
                        written[key], outcome[key] = choice, OUT_WRITTEN
                    else:
                        human.setdefault(key, _read_one(qr.answer_file(answer_dir, cid, key)) or "")
                        outcome[key] = OUT_OVERTAKEN
                logger.info("auto answer [%s]: window over — %d written", label, len(written))
            allowed = []
            _private_write(pending_path(base, cid), {**(read_pending(base, cid) or pending), "state": "done"})
        everyone = all(q.key in human or q.key in written for q in questions)
        if not allowed and (everyone or not _record_live(base, session_id, cid) or w.wall() > deadline):
            break
        w.sleep(POLL_S)
    return _close(w, pending, decision, outcome, reasons, human, latency, base, cid)


def _wait_for_record(base: Path, session_id: str, cid: str, w: World) -> bool:
    """The relay writes its waiting record just after this outbound exits; give it a moment."""
    start = w.wall()
    while True:
        record = qr.waiting_record(session_id, base)
        if record and record.get("id") == cid:
            return True
        if w.wall() - start >= RECORD_WAIT_S:
            return False
        w.sleep(0.25)


def _close(w: World, pending: Dict[str, Any], decision: aa.Decision, outcome: Dict[str, str],
           reasons: Dict[str, str], human: Dict[str, str], latency: float, base: Path, cid: str) -> Dict[str, str]:
    now = w.wall()
    records = []
    for q in pending["questions"]:
        key = q["key"]
        a = decision.answers.get(key)
        records.append({
            "ts": now, "id": cid, "key": key, "session": pending["session_id"], "kind": pending["kind"],
            "project": pending["project"], "agent": pending["source"],
            "question": q["question"], "options": q["options"],
            "choice": a.choice if a else None, "tier": a.tier if a else None,
            "claimed_tier": a.claimed_tier if a else None, "confidence": a.confidence if a else None,
            "references": [r.as_record() for r in a.references] if a else [],
            "outcome": outcome.get(key), "reason": reasons.get(key, ""),
            "human_answer": human.get(key), "method": decision.method, "notes": decision.notes,
            "launch": decision.launch, "usage": decision.usage, "latency_s": latency,
        })
    try:
        append_log(records, get=w.get, path=w.log)
    except OSError as exc:
        logger.warning("auto answer [%s]: decision log not written (%s)", qr._safe_id(cid)[-12:], type(exc).__name__)
    try:
        pending_path(base, cid).unlink(missing_ok=True)
    except OSError:
        pass
    return outcome


def main(argv: List[str]) -> int:
    # Logs go to a file beside the relay's, never to stderr: the relay discards the
    # outbound's output, and the worker has no terminal at all.
    qr.state_dir().mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=str(qr.state_dir() / "auto-answer.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    payload = sys.stdin.read()
    if "--worker" in argv:
        relay_vars = {k: os.environ.get(k, "") for k in (qr.ENV_KIND, qr.ENV_SESSION, qr.ENV_CWD)}
        try:
            work(payload, relay_vars)
        except Exception:
            logger.exception("auto answer: worker failed")
            return 1
        return 0
    try:
        return outbound(payload)
    except Exception:
        logger.exception("auto answer: outbound failed")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
