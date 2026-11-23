"""`set-fleet-mandate` — read a mandate, declare one, and the session-start hook.

    set-fleet-mandate hook       the framework's SessionStart hook (reads stdin, prints context)
    set-fleet-mandate show       this session's mandate, or that it has none
    set-fleet-mandate declare    give an agent a mandate after the fact (through the dashboard)
    set-fleet-mandate done       end THIS agent's work mandate: tell the requester, end, stop

`hook` and `show` read the store directly: they run inside the agent, where the dashboard may
be restarting. `declare` goes through the dashboard, because that is the process that knows
which agent a label or a session id belongs to.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.error
import urllib.request
from typing import List, Optional

from . import mandate, mandate_delivery

logger = logging.getLogger(__name__)

DEFAULT_API = "http://127.0.0.1:7400"


def _api_base() -> str:
    return (os.environ.get("SET_WEB_URL") or DEFAULT_API).rstrip("/")


def _hook(_args: argparse.Namespace) -> int:
    """Always exit 0. A session start must not depend on this command succeeding."""
    try:
        text = sys.stdin.read() if not sys.stdin.isatty() else ""
        out = mandate_delivery.hook_output(os.environ, text)
        if out:
            sys.stdout.write(out)
    except Exception as exc:  # noqa: BLE001 — never fail a session start
        logger.warning("set-fleet-mandate hook: %s", type(exc).__name__)
    return 0


def _show(args: argparse.Namespace) -> int:
    mandate_id = (args.id or os.environ.get(mandate.ENV_MANDATE) or "").strip()
    record = None
    if mandate_id:
        try:
            record = mandate.MandateStore().get(mandate_id)
        except mandate.MandateStoreUnreadable as exc:
            print(f"the mandate store could not be read ({exc})", file=sys.stderr)
            return 2
    if args.json:
        print(json.dumps({"mandate": mandate.public(record),
                          "absent": None if record else {"reason": "none-recorded"}}))
        return 0
    if record is None:
        print("This session has no mandate."
              + ("" if mandate_id else " (It was not started by the fleet, or the fleet gave it no id.)"))
        return 0
    print(mandate_delivery.render_context(record))
    return 0


def _declare(args: argparse.Namespace) -> int:
    body = {"goal": args.goal, "kind": "work"}
    if args.label:
        body["label"] = args.label
    if args.session:
        body["session_id"] = args.session
    if not args.label and not args.session:
        own = os.environ.get("CLAUDE_CODE_SESSION_ID")
        if not own:
            print("name the agent: --label <label> or --session <session id>", file=sys.stderr)
            return 2
        body["session_id"] = own
    if args.done_when:
        body["done_when"] = args.done_when
    if args.path:
        body["scope"] = {"paths": list(args.path)}
    request = urllib.request.Request(
        _api_base() + "/api/fleet/mandates", method="POST",
        data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            answer = json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read() or b"{}").get("detail")
        except ValueError:
            detail = None
        print(f"refused ({exc.code}): {detail or exc.reason}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError) as exc:
        print(f"the dashboard could not be reached at {_api_base()}: {exc}", file=sys.stderr)
        return 1
    told = "the agent will be told at its next session start" if answer.get("carrier") \
        else "recorded for the screen only — this agent has no carrier and has NOT been told"
    print(f"mandate {answer.get('id')} declared; {told}")
    return 0


def _sac_bin() -> Optional[str]:
    found = shutil.which("sac")
    if found:
        return found
    fallback = os.path.expanduser("~/.local/bin/sac")
    return fallback if os.access(fallback, os.X_OK) else None


def _post_to_requester(requester: str, text: str) -> Optional[str]:
    """Send the done line to the requester seat. Returns None on success, else the reason."""
    sac = _sac_bin()
    if sac is None:
        return "the bus client (sac) is not installed"
    try:
        proc = subprocess.run([sac, "send", "FACT", text, "--to", requester],
                              capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"the bus client did not run: {exc}"
    if proc.returncode != 0:
        return (proc.stderr or proc.stdout or f"exit {proc.returncode}").strip()
    return None


def _stop_label(label: str) -> Optional[str]:
    """Stop a label through the dashboard's stop route. Returns None on success, else the reason."""
    request = urllib.request.Request(
        _api_base() + "/api/fleet/agents/" + urllib.parse.quote(label, safe="") + "/stop",
        method="POST", data=b"", headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60):
            return None
    except urllib.error.HTTPError as exc:
        return f"the stop route refused ({exc.code})"
    except (urllib.error.URLError, OSError) as exc:
        return f"the dashboard could not be reached at {_api_base()}: {exc}"


def _done(args: argparse.Namespace) -> int:
    """fleet-work-agent-done: tell the requester, end the mandate, stop this agent.

    The ORDER is the contract. The post comes first, so a bus that cannot be reached leaves
    everything as it was (nothing ended, nothing stopped). The end comes before the stop:
    the stop ends the caller, and a listing that sees the agent vanish first would end the
    mandate as `ended` and lose the agent's own `agent-done` (measured by the session that
    owns the record: `_settle_mandates` runs on every listing).
    """
    line = (args.line or "").strip()
    if not line:
        print("say in one line what was done: set-fleet-mandate done \"<line>\"", file=sys.stderr)
        return 2
    mandate_id = (os.environ.get(mandate.ENV_MANDATE) or "").strip()
    if not mandate_id:
        print("refused: this session carries no mandate id — it was not started by the fleet "
              "with a mandate, so there is nothing to end", file=sys.stderr)
        return 2
    store = mandate.MandateStore()
    try:
        record = store.get(mandate_id)
    except mandate.MandateStoreUnreadable as exc:
        print(f"refused: the mandate store could not be read ({exc})", file=sys.stderr)
        return 2
    if record is None:
        print(f"refused: mandate {mandate_id} is not in the store", file=sys.stderr)
        return 2
    if record.get("ended"):
        print(f"refused: mandate {mandate_id} already ended ({record['ended'].get('reason')})",
              file=sys.stderr)
        return 2
    if record.get("kind") != "work":
        print(f"refused: mandate {mandate_id} is a {record.get('kind')} mandate — only a work "
              "mandate ends with a done step (a desk closes when it is quiet)", file=sys.stderr)
        return 2
    requester = record.get("requested_by")
    if not requester:
        print(f"refused: mandate {mandate_id} names no requester — the operator started this "
              "agent, and closing it is the operator's call", file=sys.stderr)
        return 2
    label = record.get("label") or os.environ.get(mandate.ENV_LABEL)
    if not label:
        print(f"refused: mandate {mandate_id} names no label, so this agent cannot be stopped "
              "through the fleet", file=sys.stderr)
        return 2

    why_not = _post_to_requester(requester, f"[done] {label} (mandate {mandate_id}): {line}")
    if why_not:
        print(f"not done: the line did not reach {requester} ({why_not}). Nothing was ended "
              "or stopped.", file=sys.stderr)
        return 1
    store.end(mandate_id, "agent-done")
    logger.info("set-fleet-mandate done: %s ended agent-done, stopping %s", mandate_id, label)
    print(f"told {requester}; mandate {mandate_id} ended (agent-done); stopping {label}")
    sys.stdout.flush()
    why_not = _stop_label(label)
    if why_not:
        print(f"the mandate is ended but this agent was NOT stopped: {why_not}. Close this "
              "session by hand; the idle-close work bound will also close it.", file=sys.stderr)
        return 1
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="set-fleet-mandate", description="Why an agent was started: read it, declare it.")
    sub = parser.add_subparsers(dest="command")

    h = sub.add_parser("hook", help="the framework's SessionStart hook")
    h.set_defaults(func=_hook)

    s = sub.add_parser("show", help="this session's mandate")
    s.add_argument("--id", help="a mandate id (default: the one in this session's environment)")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=_show)

    d = sub.add_parser("declare", help="give an agent a mandate after the fact")
    d.add_argument("goal")
    d.add_argument("--label", help="the agent's fleet label")
    d.add_argument("--session", help="the agent's session id (default: this session)")
    d.add_argument("--done-when", dest="done_when")
    d.add_argument("--path", action="append", help="a path in scope (repeatable)")
    d.set_defaults(func=_declare)

    f = sub.add_parser("done", help="end this agent's work mandate: tell the requester, end, stop")
    f.add_argument("line", help="one line: what was done")
    f.set_defaults(func=_done)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
