"""`set-relay-wire` — wire the question relay's hooks into registered projects (B-182 follow-up).

    set-relay-wire <path> [<path> …]     wire these project directories
    set-relay-wire --registered          wire every registered project that lacks a hook
    set-relay-wire … --dry-run           say what would be added, write nothing

Writes only each project's machine-local `.claude/settings.local.json` and keeps it out of
git through `.git/info/exclude`; see `question_relay.wire_project`.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import question_relay as qr

logger = logging.getLogger(__name__)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="set-relay-wire", description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--registered", action="store_true", help="every registered project that lacks a hook")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    targets: list[tuple[str, Path]] = [(Path(p).name, Path(p).resolve()) for p in args.paths]
    if args.registered:
        from ..project_registry import load_projects
        by_name = {p.get("name"): p.get("path") for p in load_projects() if isinstance(p, dict)}
        for u in qr.unwired_projects():
            targets.append((u["project"], Path(str(by_name.get(u["project"]) or ""))))
    if not targets:
        print("nothing to wire")
        return 0

    rc = 0
    for name, root in targets:
        if not root.is_dir():
            print(f"✗ {name}: {root} is not a directory")
            rc = 1
            continue
        if args.dry_run:
            gap = qr.unwired_projects([{"name": name, "path": str(root)}])
            would = gap[0]["missing"] if gap else []
            print(f"· {name}: would add {', '.join(would) if would else 'nothing'}")
            continue
        try:
            added = qr.wire_project(root)
        except (OSError, ValueError) as exc:
            print(f"✗ {name}: not wired — {exc}")
            rc = 1
            continue
        print(f"✔ {name}: {'added ' + ', '.join(added) if added else 'already wired'}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
