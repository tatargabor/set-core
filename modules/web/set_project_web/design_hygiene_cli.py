"""set-design-hygiene CLI entry point.

Scans the design source for quality issues and writes a markdown checklist.
Operator runs this before each orchestration to catch design-source bugs
that would otherwise propagate into agent runs (broken routes, mock data,
header inconsistency, hardcoded strings, etc.).

Usage:
    set-design-hygiene                          # cwd
    set-design-hygiene /path/to/project
    set-design-hygiene --output docs/custom-checklist.md
    set-design-hygiene --ignore-critical        # don't exit non-zero on CRITICAL
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("set-design-hygiene")


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="set-design-hygiene",
        description="Scan the design source for quality issues; generate per-project checklist.",
    )
    p.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Project root (default: cwd). Must contain v0-export/ or claude-design-export/.",
    )
    p.add_argument(
        "--output",
        type=Path,
        help="Output markdown file. Default: <project>/docs/design-source-hygiene-checklist.md",
    )
    p.add_argument(
        "--ignore-critical",
        action="store_true",
        help="Do not exit non-zero on CRITICAL findings (write checklist and exit 0).",
    )
    p.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase log verbosity (repeat for more detail).",
    )
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)

    log_level = logging.DEBUG if args.verbose >= 2 else (
        logging.INFO if args.verbose == 1 else logging.WARNING
    )
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    project = Path(args.project_path).resolve()
    if not project.is_dir():
        logger.error("project path is not a directory: %s", project)
        return 2

    # Resolve the profile to find the design source.
    try:
        from set_orch.profile_loader import load_profile
        profile = load_profile(str(project))
    except Exception as exc:
        logger.error("could not load profile for %s: %s", project, exc)
        return 2

    source = profile.detect_design_source(project)
    if source == "none":
        logger.error(
            "no design source detected at %s — looking for v0-export/. "
            "Run `set-design-import` first.",
            project,
        )
        return 2

    logger.info("scanning %s design source at %s", source, project)

    findings = profile.scan_design_hygiene(project)
    if not findings:
        logger.info("0 findings — design source is clean")
        out_path = args.output or (project / "docs" / "design-source-hygiene-checklist.md")
        # Still write empty checklist for visibility
        from .v0_hygiene_scanner import render_checklist
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render_checklist(
            [],
            project_id=project.name,
            source_dir=f"{source}-export/" if source != "v0" else "v0-export/",
        ))
        print(f"hygiene: 0 findings — {out_path}")
        return 0

    # Severity counts
    crit = sum(1 for f in findings if f.severity.value == "critical")
    warn = sum(1 for f in findings if f.severity.value == "warn")
    info = sum(1 for f in findings if f.severity.value == "info")

    out_path = args.output or (project / "docs" / "design-source-hygiene-checklist.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Render markdown — re-import inside web module since we know it's web.
    from .v0_hygiene_scanner import render_checklist
    md = render_checklist(
        findings,
        project_id=project.name,
        source_dir=f"{source}-export/" if source != "v0" else "v0-export/",
    )
    out_path.write_text(md)

    print(
        f"hygiene: {len(findings)} findings ({crit} CRITICAL, {warn} WARN, {info} INFO) "
        f"→ {out_path}",
    )

    if crit > 0 and not args.ignore_critical:
        print(
            f"\nexit 1 due to {crit} CRITICAL finding(s). "
            f"Fix in design source repo or re-run with --ignore-critical.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
