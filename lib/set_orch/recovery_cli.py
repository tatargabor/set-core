"""CLI for set-recovery — roll back orchestration to a known-good state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _resolve_project_path(name: str) -> Path:
    """Resolve project name to its path via projects.json."""
    projects_file = Path.home() / ".config" / "set-core" / "projects.json"
    if not projects_file.exists():
        print(f"Error: projects.json not found at {projects_file}", file=sys.stderr)
        sys.exit(1)
    try:
        with open(projects_file) as f:
            data = json.load(f)
        projects = data.get("projects", {})
        if name in projects:
            return Path(projects[name]["path"])
        # Try case-insensitive match
        for pname, pinfo in projects.items():
            if pname.lower() == name.lower():
                return Path(pinfo["path"])
        print(f"Error: project '{name}' not found. Available:", file=sys.stderr)
        for pname in sorted(projects.keys()):
            print(f"  - {pname}", file=sys.stderr)
        sys.exit(1)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error reading projects.json: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Roll back orchestration to the state after a specific change was archived."
    )
    parser.add_argument("project", help="Registered project name")
    parser.add_argument("target", help="Name of the merged change to recover to")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without executing")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--json", action="store_true", help="Output plan as JSON")

    args = parser.parse_args()
    project_path = _resolve_project_path(args.project)

    if not project_path.is_dir():
        print(f"Error: project path does not exist: {project_path}", file=sys.stderr)
        sys.exit(1)

    from .recovery import recover_to_change, RecoveryError

    try:
        plan = recover_to_change(
            project_path,
            args.target,
            dry_run=args.dry_run,
            yes=args.yes,
        )
        if args.json:
            import dataclasses
            d = dataclasses.asdict(plan)
            d["archive_dirs_to_restore"] = [str(p) for p in plan.archive_dirs_to_restore]
            print(json.dumps(d, indent=2))
    except RecoveryError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(2)


if __name__ == "__main__":
    main()
