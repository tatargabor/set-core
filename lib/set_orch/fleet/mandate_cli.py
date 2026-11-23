"""`set-fleet-mandate` — read a mandate, declare one, and the session-start hook.

    set-fleet-mandate hook       the framework's SessionStart hook (reads stdin, prints context)
    set-fleet-mandate show       this session's mandate, or that it has none
    set-fleet-mandate declare    give an agent a mandate after the fact (through the dashboard)

`hook` and `show` read the store directly: they run inside the agent, where the dashboard may
be restarting. `declare` goes through the dashboard, because that is the process that knows
which agent a label or a session id belongs to.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
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

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
