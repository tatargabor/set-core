"""`set-fleet-roster` — read the record from a terminal, and verify it after a boot.

**Why a CLI exists for something the screen already shows.** The one event this
whole feature is for cannot be arranged on demand, and when it happens the
dashboard may not be up yet — a service that failed to start, a browser not
opened, a machine reached over ssh. The evidence has to be obtainable from a
shell, before anything else is trusted.

`verify` is the check to run **after an actual reboot**. A simulation can remove
what a boot removes — and one was run, with `/proc` replaced by an empty tmpfs
and the runtime's session records hidden — but a simulation is a model of a
reboot, not a reboot. Two things only a real one answers: whether the runtime's
transcripts are still where this expects them, and whether the roster file
survived an unclean shutdown with its last write intact.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List

from . import discovery, roster


def _age(seconds: float) -> str:
    if seconds < 90:
        return f"{int(seconds)}s"
    if seconds < 5400:
        return f"{int(seconds // 60)}m"
    if seconds < 172800:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def _verify(args: argparse.Namespace) -> int:
    """What the roster holds, how much of it is resumable, and how old it is.

    Prints the live agent count beside it deliberately. After a real boot that
    number is expected to be far below the roster's — and seeing the two
    together is what tells you the roster is the thing that survived, rather
    than a second view of what is already running.
    """
    path = args.path or roster.default_roster_path()
    now = time.time()
    listed = roster.projects(path=path)

    if not os.path.exists(path):
        print(f"no roster at {path}")
        print("Nothing has been recorded yet. The first reboot this can restore from is the "
              "first one AFTER a fleet listing has run at least once.")
        return 1

    try:
        live = discovery.live_session_ids()
    except Exception:
        live = None

    rows: List[Dict[str, Any]] = []
    total = resumable = still_running = 0
    for entry in listed:
        answer = roster.read(entry["project"], path=path)
        r = sum(1 for e in answer["entries"] if e["resumable"])
        running = 0 if live is None else sum(
            1 for e in answer["entries"] if e.get("session_id") in live)
        total += len(answer["entries"])
        resumable += r
        still_running += running
        rows.append({"project": entry["project"], "entries": len(answer["entries"]),
                     "resumable": r, "running": running,
                     "age": now - entry["last_seen"]})

    if args.json:
        print(json.dumps({"path": path, "projects": rows, "total": total,
                          "resumable": resumable, "running": still_running,
                          "liveness_known": live is not None}, indent=2))
        return 0 if total else 1

    print(f"roster: {path}")
    print(f"{'project':32} {'entries':>7} {'resumable':>10} {'running':>8}  last seen")
    for row in rows:
        print(f"{row['project'][:32]:32} {row['entries']:>7} {row['resumable']:>10} "
              f"{row['running'] if live is not None else '?':>8}  {_age(row['age'])} ago")
    print(f"\n{total} entries, {resumable} resumable now, "
          f"{still_running if live is not None else 'unknown how many'} already running")
    if live is None:
        # A gap is not a zero. Saying "0 running" here would be a measurement
        # nobody took, and it is the number a reader would act on.
        print("NOTE: liveness could not be determined, so 'running' is unmeasured, not zero.")
    if resumable < total:
        print(f"NOTE: {total - resumable} entr{'y has' if total - resumable == 1 else 'ies have'} "
              "no transcript and cannot be resumed. They are kept and shown, not dropped.")
    return 0 if total else 1


def _show(args: argparse.Namespace) -> int:
    path = args.path or roster.default_roster_path()
    answer = roster.read(args.project, path=path)
    if args.json:
        print(json.dumps(answer, indent=2))
        return 0
    if not answer["record_exists"]:
        print(f"no roster file at {path}")
        return 1
    if not answer["entries"]:
        print(f"{args.project}: recorded, and holding nothing")
        return 1
    now = time.time()
    for entry in answer["entries"]:
        mark = "resumable" if entry["resumable"] else f"NOT resumable — {entry['not_resumable_reason']}"
        print(f"{entry['label'] or entry['key']:32} {_age(now - (entry['last_seen'] or now)):>8} ago  {mark}")
        print(f"{'':32} {entry['cwd']}")
    return 0


def _forget(args: argparse.Namespace) -> int:
    if roster.forget(args.project, args.key, path=args.path):
        print(f"forgot {args.key} from {args.project}")
        return 0
    print(f"no entry {args.key} recorded for {args.project}")
    return 1


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="set-fleet-roster",
        description="What the fleet has seen, kept where a reboot cannot reach it.",
    )
    parser.add_argument("--path", help="roster file (default: the per-user store)")
    sub = parser.add_subparsers(dest="command")

    v = sub.add_parser("verify", help="after a reboot: what survived, and how much is resumable")
    v.add_argument("--json", action="store_true")
    v.set_defaults(func=_verify)

    s = sub.add_parser("show", help="one project's recorded entries")
    s.add_argument("project")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=_show)

    f = sub.add_parser("forget", help="drop one recorded entry")
    f.add_argument("project")
    f.add_argument("key")
    f.set_defaults(func=_forget)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        args = parser.parse_args((argv or []) + ["verify"])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
