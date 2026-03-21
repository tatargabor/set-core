"""Backwards compatibility CLI shim for set-project-base.

Handles `python -m set_project_base.cli deploy-templates` by delegating
to set_orch.profile_deploy + profile_loader.
"""

import argparse
import sys
from pathlib import Path


def cmd_deploy_templates(args):
    """Deploy template files from a project type into a target project."""
    from set_orch.profile_deploy import deploy_templates
    from set_orch.profile_loader import load_profile, _find_project_type_class, _SET_CORE_ROOT
    import importlib

    type_name = args.type
    pt = None

    # Resolve project type using the same chain as profile_loader
    try:
        from importlib.metadata import entry_points
        eps = entry_points(group="set_tools.project_types")
    except TypeError:
        eps = entry_points().get("set_tools.project_types", [])

    for ep in eps:
        if ep.name == type_name:
            cls = ep.load()
            pt = cls()
            break

    # Direct import fallback
    if pt is None:
        try:
            mod = importlib.import_module(f"set_project_{type_name}")
            cls = _find_project_type_class(mod)
            if cls:
                pt = cls()
        except ImportError:
            pass

    # Built-in modules fallback
    if pt is None:
        modules_dir = _SET_CORE_ROOT / "modules" / type_name
        module_pkg = modules_dir / f"set_project_{type_name}"
        if module_pkg.is_dir():
            sys.path.insert(0, str(modules_dir))
            try:
                mod = importlib.import_module(f"set_project_{type_name}")
                cls = _find_project_type_class(mod)
                if cls:
                    pt = cls()
            except ImportError:
                pass

    if pt is None:
        print(f"Error: Project type '{type_name}' not found", file=sys.stderr)
        sys.exit(1)

    modules = args.modules.split(",") if args.modules else None
    messages = deploy_templates(
        pt,
        template_id=args.template,
        target_dir=Path(args.project_dir),
        modules=modules,
        force=args.force,
        dry_run=args.dry_run,
    )
    for msg in messages:
        print(msg)


def main():
    parser = argparse.ArgumentParser(prog="set-project-base")
    subparsers = parser.add_subparsers(dest="command")

    deploy = subparsers.add_parser("deploy-templates")
    deploy.add_argument("--project-dir", required=True)
    deploy.add_argument("--type", required=True)
    deploy.add_argument("--template", default=None)
    deploy.add_argument("--modules", default=None)
    deploy.add_argument("--force", action="store_true")
    deploy.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    if args.command == "deploy-templates":
        cmd_deploy_templates(args)
    else:
        print("Usage: python -m set_project_base.cli deploy-templates ...", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
