"""CLI command for scaffolding web project knowledge files."""

import argparse
import json
import shutil
import sys
from pathlib import Path

from set_project_web.project_type import WebProjectType


def _prompt_design_setup(target_dir: Path) -> None:
    """Interactively set up design tool integration (Figma MCP + orchestration.yaml)."""
    try:
        answer = input("\nDo you have a Figma design file? (y/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if answer not in ("y", "yes"):
        return

    try:
        figma_url = input("Figma file URL: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if not figma_url:
        print("  skip: no URL provided")
        return

    # Register Figma MCP server via Claude CLI
    _register_figma_mcp(target_dir)

    # Write design_file to orchestration.yaml
    _write_design_file_ref(target_dir, figma_url)


def _register_figma_mcp(target_dir: Path) -> None:
    """Register Figma MCP server in .claude/settings.json."""
    settings_path = target_dir / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    settings = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    mcp_servers = settings.setdefault("mcpServers", {})
    mcp_servers["figma"] = {
        "type": "http",
        "url": "https://mcp.figma.com/mcp",
    }

    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    action = "update" if settings_path.exists() else "create"
    print(f"  {action}: .claude/settings.json (figma MCP)")


def _write_design_file_ref(target_dir: Path, figma_url: str) -> None:
    """Write design_file reference to .claude/orchestration.yaml."""
    orch_path = target_dir / ".claude" / "orchestration.yaml"
    orch_path.parent.mkdir(parents=True, exist_ok=True)

    design_line = f"design_file: \"{figma_url}\"\n"

    if orch_path.exists():
        content = orch_path.read_text()
        # Replace existing design_file line or append
        lines = content.splitlines(keepends=True)
        replaced = False
        for i, line in enumerate(lines):
            if line.startswith("design_file:"):
                lines[i] = design_line
                replaced = True
                break
        if not replaced:
            if content and not content.endswith("\n"):
                lines.append("\n")
            lines.append(design_line)
        orch_path.write_text("".join(lines))
        action = "update" if replaced else "append"
        print(f"  {action}: .claude/orchestration.yaml (design_file)")
    else:
        orch_path.write_text(design_line)
        print("  create: .claude/orchestration.yaml (design_file)")


def init_project(
    target_dir: Path, template_id: str, force: bool = False, no_design: bool = False
) -> None:
    """Scaffold project knowledge files from a template into the target directory."""
    project_type = WebProjectType()
    template_dir = project_type.get_template_dir(template_id)

    if template_dir is None:
        available = [t.id for t in project_type.get_templates()]
        print(f"Error: Unknown template '{template_id}'. Available: {', '.join(available)}")
        sys.exit(1)

    if not template_dir.exists():
        print(f"Error: Template directory not found: {template_dir}")
        sys.exit(1)

    copied = 0
    skipped = 0

    for src_file in sorted(template_dir.rglob("*")):
        if src_file.is_dir():
            continue

        rel_path = src_file.relative_to(template_dir)
        dest_file = target_dir / rel_path

        if dest_file.exists() and not force:
            print(f"  skip: {rel_path} (already exists, use --force to overwrite)")
            skipped += 1
            continue

        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest_file)
        print(f"  create: {rel_path}")
        copied += 1

    # Design tool setup (interactive)
    if not no_design:
        _prompt_design_setup(target_dir)

    print(f"\nDone: {copied} files created, {skipped} skipped")


def main() -> None:
    """Entry point for wt-project init command."""
    parser = argparse.ArgumentParser(
        prog="set-project-web",
        description="Scaffold web project knowledge files",
    )
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Initialize project knowledge files")
    init_parser.add_argument(
        "--type",
        required=True,
        dest="template_type",
        help="Template type (e.g., nextjs, spa)",
    )
    init_parser.add_argument(
        "--target",
        default=".",
        help="Target project directory (default: current directory)",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files",
    )
    init_parser.add_argument(
        "--no-design",
        action="store_true",
        help="Skip interactive design tool setup",
    )

    list_parser = subparsers.add_parser("list", help="List available templates")

    args = parser.parse_args()

    if args.command == "init":
        target = Path(args.target).resolve()
        print(f"Initializing web project knowledge ({args.template_type}) in {target}")
        init_project(target, args.template_type, args.force, args.no_design)
    elif args.command == "list":
        project_type = WebProjectType()
        print("Available templates:")
        for tmpl in project_type.get_templates():
            print(f"  {tmpl.id:12s} — {tmpl.description}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
