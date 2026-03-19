"""CLI entry point for set-memoryd.

Usage:
    python -m set_memoryd start [--project NAME] [--storage PATH]
    python -m set_memoryd stop  [--project NAME]
    python -m set_memoryd status [--project NAME]
    python -m set_memoryd run   [--project NAME] [--storage PATH]  (foreground)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from . import lifecycle


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="set-memoryd",
        description="Per-project memory daemon for shodh-memory",
    )
    sub = parser.add_subparsers(dest="command")

    # start
    p_start = sub.add_parser("start", help="Start daemon (background)")
    p_start.add_argument("--project", default="")
    p_start.add_argument("--storage", default="")

    # stop
    p_stop = sub.add_parser("stop", help="Stop daemon")
    p_stop.add_argument("--project", default="")

    # status
    p_status = sub.add_parser("status", help="Show daemon status")
    p_status.add_argument("--project", default="")
    p_status.add_argument("--json", action="store_true", dest="as_json")

    # run (foreground)
    p_run = sub.add_parser("run", help="Run daemon in foreground")
    p_run.add_argument("--project", default="")
    p_run.add_argument("--storage", default="")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    project = args.project or lifecycle.resolve_project()

    if args.command == "start":
        storage = args.storage or lifecycle.storage_path_for(project)
        pid = lifecycle.start(project, storage_path=storage)
        if pid:
            print(f"set-memoryd started: project={project} pid={pid}")
        else:
            print(f"set-memoryd failed to start for {project}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "stop":
        if lifecycle.stop(project):
            print(f"set-memoryd stopped: project={project}")
        else:
            print(f"set-memoryd failed to stop for {project}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "status":
        info = lifecycle.status(project)
        if hasattr(args, "as_json") and args.as_json:
            print(json.dumps(info))
        else:
            state = "running" if info["running"] else "stopped"
            pid_str = f" pid={info['pid']}" if info["pid"] else ""
            print(f"set-memoryd {state}: project={project}{pid_str}")

    elif args.command == "run":
        # Foreground mode — configure logging to stderr
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
            stream=sys.stderr,
        )
        storage = args.storage or lifecycle.storage_path_for(project)
        lifecycle.start(project, storage_path=storage, foreground=True)


if __name__ == "__main__":
    main()
