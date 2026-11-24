"""`set-fleet-ask` — ask another project for something, in one command.

    set-fleet-ask <project> "<request>" [--subject "…"] [--question]
    set-fleet-ask --list

What it replaces: opening the other project by hand, telling that session to wait on the
bus, and then talking. What it does, in order:

1. finds this session's own bus seat;
2. asks the dashboard to resolve the project's desk — the one session that answers for the
   project — starting it when none is live, and to open an engagement;
3. sends the request on the bus **as this session**, addressed to the desk's seat, so the
   reply comes back here through the bus's own rule;
4. reports where the request is on the bus, which turns the engagement `open`.

The request text goes to the bus and nowhere else. The dashboard is told only a short
subject, and only if one is given.

Exit codes: 0 sent · 1 not sent (the reason is printed) · 2 usage · 3 this session has no
bus seat.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_API = "http://127.0.0.1:7400"
SAC = "sac"

#: Resolution may start a desk and wait for its bus seat (bounded at 60 s on the other side).
RESOLVE_TIMEOUT_SECONDS = 100
SUBJECT_MAX = 80

Http = Callable[[str, str, Optional[Dict[str, Any]], float], Tuple[int, Any]]
Run = Callable[..., Any]


def _api_base() -> str:
    return (os.environ.get("SET_WEB_URL") or DEFAULT_API).rstrip("/")


def _http(method: str, path: str, body: Optional[Dict[str, Any]], timeout: float) -> Tuple[int, Any]:
    """(status, json). Status 0 means the dashboard could not be reached at all."""
    request = urllib.request.Request(
        _api_base() + path, method=method,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read() or b"{}")
        except ValueError:
            return exc.code, {"detail": exc.reason}
    except (urllib.error.URLError, OSError) as exc:
        return 0, {"detail": f"the dashboard could not be reached at {_api_base()}: {exc}"}


def own_seat(session_id: Optional[str], *, run: Run = subprocess.run) -> Optional[str]:
    """This session's seat on the bus, from the bus's own machine-readable list."""
    if not session_id:
        return None
    try:
        done = run([SAC, "agents", "--json"], capture_output=True, text=True, timeout=20)
        data = json.loads(done.stdout or "{}") if getattr(done, "returncode", 1) == 0 else {}
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    for agent in data.get("agents") or []:
        for seat in agent.get("seats") or []:
            if seat.get("session") == session_id and seat.get("seat"):
                return str(seat["seat"])
    return None


def _detail(payload: Any) -> Dict[str, Any]:
    """A refusal's `{reason, detail, …}` whether FastAPI wrapped it in `detail` or not."""
    inner = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(inner, dict):
        return inner
    return {"reason": None, "detail": inner if isinstance(inner, str) else str(payload)}


#: What the bus says when the addressee shares several rooms with the sender.
ROOM_REQUIRED = "`room` is required"


def _dm_room(seat: str, *, run: Run) -> Optional[str]:
    """The room of two between this session and `seat` (opened if needed), or None."""
    try:
        done = run([SAC, "dm", seat], capture_output=True, text=True, timeout=30)
        if getattr(done, "returncode", 1) != 0:
            return None
        room = json.loads(done.stdout or "{}").get("room")
    except (OSError, subprocess.SubprocessError, ValueError, AttributeError) as exc:
        logger.warning("set-fleet-ask: opening a room of two raised %s", type(exc).__name__)
        return None
    return room if isinstance(room, str) and room else None


def ask(project: str, text: str, *, seat: str, kind: str = "REQUEST", subject: Optional[str] = None,
        http: Http = _http, run: Run = subprocess.run, out=None, err=None) -> int:
    """Resolve, send as the asker, report. Returns the exit code."""
    # Resolved at call time: a default bound at definition would keep the stream that
    # existed at import, which is not the one a caller (or a test) is reading.
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    body: Dict[str, Any] = {"project": project, "requested_by": seat, "kind": kind}
    if subject:
        body["subject"] = " ".join(subject.split())[:SUBJECT_MAX]
    status, payload = http("POST", "/api/fleet/desks/resolve", body, RESOLVE_TIMEOUT_SECONDS)
    if status != 200:
        refusal = _detail(payload)
        reason = refusal.get("reason")
        print(f"not sent — {reason or 'refused'}: {refusal.get('detail')}", file=err)
        for item in refusal.get("open") or []:
            print(f"  open: {item.get('id')} → {item.get('project')} "
                  f"({item.get('state')}, {int(item.get('age_seconds') or 0)} s) {item.get('subject') or ''}",
                  file=err)
        return 1

    engagement_id = payload["engagement_id"]
    desk = payload["desk"]
    try:
        done = run([SAC, "send", kind, text, "--to", desk["seat"]],
                   capture_output=True, text=True, timeout=60)
        if getattr(done, "returncode", 1) != 0 and ROOM_REQUIRED in (getattr(done, "stderr", "") or ""):
            # Asking a desk of one's OWN project (measured 2026-11-24): asker and desk share
            # every project room, so the bus cannot pick one and refuses. A room of two with
            # the desk's seat is unambiguous, and wakes exactly that seat.
            room = _dm_room(desk["seat"], run=run)
            if room:
                logger.info("set-fleet-ask: the bus needed a room; sending in a room of two")
                done = run([SAC, "send", room, kind, text, "--to", desk["seat"]],
                           capture_output=True, text=True, timeout=60)
        sent = json.loads(done.stdout or "{}") if getattr(done, "returncode", 1) == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        logger.warning("set-fleet-ask: the bus send raised %s", type(exc).__name__)
        done, sent = None, None
    if not isinstance(sent, dict) or not sent.get("room") or not sent.get("ts"):
        http("POST", f"/api/fleet/engagements/{engagement_id}/failed", {"reason": "send-failed"}, 20)
        why = (getattr(done, "stderr", "") or "").strip().splitlines()[-1:] if done is not None else []
        print(f"not sent — the bus refused the send to {desk['seat']}"
              + (f": {why[0]}" if why else ""), file=err)
        return 1

    status, _ = http("POST", f"/api/fleet/engagements/{engagement_id}/sent",
                     {"room": sent["room"], "ts": sent["ts"]}, 20)
    if status != 200:
        # The request IS on the bus; only the record is behind. Say so rather than fail.
        print(f"sent, but the engagement {engagement_id} was not recorded as open "
              f"(the dashboard answered {status})", file=err)
    how = "started for this request" if desk.get("started") else "already running"
    print(f"{engagement_id}: sent to {project}'s desk {desk['seat']} ({how}). "
          "The reply arrives on the bus, linked to your request.", file=out)
    return 0


def list_own(seat: str, *, http: Http = _http, out=None, err=None, as_json: bool = False) -> int:
    from urllib.parse import quote

    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err

    status, payload = http("GET", f"/api/fleet/engagements?asker={quote(seat, safe='')}", None, 30)
    if status != 200:
        print(f"could not list engagements: {_detail(payload).get('detail')}", file=err)
        return 1
    if as_json:
        print(json.dumps(payload), file=out)
        return 0
    rows = payload.get("engagements") or []
    if not rows:
        print("(no engagements)", file=out)
    for row in rows:
        mark = " ⚠ waiting" if row.get("waiting") else ""
        age = int(row.get("age_seconds") or 0)
        print(f"{row.get('id')}  {row.get('state'):<10} {row.get('project'):<24} {age:>6} s"
              f"{mark}  {row.get('subject') or ''}", file=out)
    if payload.get("measured") is False:
        print("(the bus could not be read: states shown as unmeasured were not checked)", file=out)
    return 0


def main(argv: Optional[List[str]] = None, *, http: Http = _http, run: Run = subprocess.run) -> int:
    parser = argparse.ArgumentParser(
        prog="set-fleet-ask",
        description="Ask another project for something: finds or starts its desk and sends your request.")
    parser.add_argument("project", nargs="?")
    parser.add_argument("request", nargs="?")
    parser.add_argument("--subject", help="a short label for the map (never the request itself)")
    parser.add_argument("--question", action="store_true", help="send a QUESTION instead of a REQUEST")
    parser.add_argument("--list", action="store_true", help="this session's engagements")
    parser.add_argument("--json", action="store_true", help="with --list: machine-readable")
    parser.add_argument("--from", dest="seat", help="this session's bus seat (default: looked up)")
    args = parser.parse_args(argv)

    seat = args.seat or own_seat(os.environ.get("CLAUDE_CODE_SESSION_ID"), run=run)
    if not seat:
        print("this session has no seat on the bus, so it cannot be answered. Enrol the project "
              "(`sac install`), or pass --from <seat>.", file=sys.stderr)
        return 3
    if args.list:
        return list_own(seat, http=http, as_json=args.json)
    if not args.project or not (args.request or "").strip():
        parser.print_usage(sys.stderr)
        return 2
    return ask(args.project, args.request, seat=seat,
               kind="QUESTION" if args.question else "REQUEST", subject=args.subject,
               http=http, run=run)


if __name__ == "__main__":
    sys.exit(main())
