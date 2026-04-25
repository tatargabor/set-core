"""set-design-import CLI entry point (v0-only pipeline).

Supports two source modes:
  --git <url> [--ref <branch|tag|sha>]   primary: clone from git
  --source <path>                        fallback: extract from a ZIP

When neither flag is given, reads `design_source` block from
<scaffold>/scaffold.yaml.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("set-design-import")

# Exclude patterns that MUST be present in consumer tsconfig.json so the v0
# import rotation (v0-export → v0-export.bak.<ts>) does not poison tsc.
REQUIRED_TSCONFIG_EXCLUDES: tuple[str, ...] = (
    "v0-export",
    "v0-export.*",
    "*.bak",
    "*.bak.*",
)


def _patch_tsconfig_excludes(scaffold: Path) -> list[str]:
    """Ensure tsconfig.json exclude covers v0-export + backup patterns.

    Idempotent. Appends missing entries preserving pre-existing order.
    On parse failure: WARNs and returns []. On missing file: DEBUGs and returns [].
    """
    ts = scaffold / "tsconfig.json"
    if not ts.is_file():
        logger.debug("tsconfig-patch: no tsconfig.json at %s — skipping", ts)
        return []
    try:
        raw = ts.read_text()
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(
            "tsconfig-patch: could not parse %s (%s) — skipping patch; "
            "operator may need to add %s manually",
            ts, e, list(REQUIRED_TSCONFIG_EXCLUDES),
        )
        return []

    current = data.get("exclude")
    if not isinstance(current, list):
        logger.warning(
            "tsconfig-patch: %s has no list-valued 'exclude' — skipping patch",
            ts,
        )
        return []

    missing = [p for p in REQUIRED_TSCONFIG_EXCLUDES if p not in current]
    if not missing:
        logger.debug("tsconfig-patch: %s already up to date (no-op)", ts)
        return []

    data["exclude"] = list(current) + missing
    ts.write_text(json.dumps(data, indent=2) + "\n")
    logger.info("tsconfig-patch: added %s to %s", missing, ts)
    return missing


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="set-design-import",
        description="Import a v0.app design into a scaffold (v0-git primary, v0-zip fallback).",
    )
    p.add_argument("--git", help="git repo URL to clone")
    p.add_argument("--ref", default=None, help="git branch/tag/sha (default: main)")
    p.add_argument("--source", help="ZIP file fallback source")
    p.add_argument(
        "--scaffold",
        default=".",
        help="scaffold directory (default: cwd)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="remove existing v0-export/ before materializing",
    )
    p.add_argument(
        "--regenerate-manifest",
        action="store_true",
        help="regenerate design-manifest.yaml without re-importing",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="treat TypeScript type-check errors as blocking",
    )
    p.add_argument(
        "--no-build-check",
        action="store_true",
        help="skip pnpm build smoke test",
    )
    p.add_argument(
        "--ignore-navigation",
        action="store_true",
        help="do not block on broken navigation links",
    )
    p.add_argument(
        "--strict-quality",
        action="store_true",
        help="promote all quality warnings to blocking errors",
    )
    # design-binding-completeness: post-import hygiene scan
    p.add_argument(
        "--with-hygiene",
        action="store_true",
        help="run hygiene scanner after manifest regen (writes docs/design-source-hygiene-checklist.md)",
    )
    p.add_argument(
        "--ignore-critical",
        action="store_true",
        help="with --with-hygiene: do not exit non-zero on CRITICAL findings",
    )
    p.add_argument(
        "-v", "--verbose", action="store_true",
        help="verbose logging",
    )
    return p.parse_args(argv)


def _resolve_source_from_scaffold(scaffold: Path) -> dict:
    """Read scaffold.yaml's design_source block."""
    import yaml

    sf = scaffold / "scaffold.yaml"
    if not sf.is_file():
        raise SystemExit(
            f"no --git / --source flag given and scaffold.yaml not found at {sf}.\n"
            f"Either pass --git/--source OR author a design_source block in scaffold.yaml."
        )
    data = yaml.safe_load(sf.read_text()) or {}
    block = data.get("design_source")
    if not block:
        raise SystemExit(
            f"scaffold.yaml at {sf} has no design_source block.\n"
            f"Expected (v0-git):\n"
            f"  design_source:\n"
            f"    type: v0-git\n"
            f"    repo: https://github.com/owner/repo.git\n"
            f"    ref: main\n"
            f"OR pass --source <zip> on the command line."
        )
    return block


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    scaffold = Path(args.scaffold).resolve()
    if not scaffold.is_dir():
        logger.error("scaffold directory not found: %s", scaffold)
        return 2

    if args.git and args.source:
        logger.error("--git and --source are mutually exclusive")
        return 2

    from .v0_importer import V0ImportError, import_v0_git, import_v0_zip
    from .v0_manifest import generate_manifest_from_tree

    try:
        if args.regenerate_manifest and not (args.git or args.source):
            # Manifest-only refresh, no re-import.
            v0_dir = scaffold / "v0-export"
            if not v0_dir.is_dir():
                logger.error(
                    "cannot regenerate manifest — v0-export/ not present at %s. "
                    "Run a full import first (--git or --source).",
                    v0_dir,
                )
                return 2
            manifest_path = scaffold / "docs" / "design-manifest.yaml"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            generate_manifest_from_tree(v0_dir, manifest_path)
            _patch_tsconfig_excludes(scaffold)
            print(f"manifest regenerated: {manifest_path}")
            if args.with_hygiene:
                rc = _run_post_import_hygiene(scaffold, args.ignore_critical)
                return rc
            return 0

        if args.git:
            summary = import_v0_git(
                args.git, args.ref or "main", scaffold, force=args.force,
            )
        elif args.source:
            source = Path(args.source)
            if not source.is_file():
                logger.error("--source file not found: %s", source)
                return 2
            summary = import_v0_zip(source, scaffold, force=args.force)
        else:
            block = _resolve_source_from_scaffold(scaffold)
            t = block.get("type")
            if t == "v0-git":
                repo = block.get("repo") or ""
                ref = args.ref or block.get("ref") or "main"
                if not repo:
                    logger.error("scaffold.yaml design_source.repo is empty")
                    return 2
                summary = import_v0_git(repo, ref, scaffold, force=args.force)
            elif t == "v0-zip":
                zp = block.get("path") or ""
                if not zp:
                    logger.error("scaffold.yaml design_source.path is empty")
                    return 2
                source = (scaffold / zp).resolve() if not Path(zp).is_absolute() else Path(zp)
                summary = import_v0_zip(source, scaffold, force=args.force)
            else:
                logger.error(
                    "unsupported scaffold.yaml design_source.type: %r (expected 'v0-git' or 'v0-zip')", t,
                )
                return 2

        _patch_tsconfig_excludes(scaffold)

        # Quality validation (v0_validator) — run post-hoc when module is present.
        try:
            from .v0_validator import ValidatorConfig, validate_v0_export
        except ImportError:
            logger.debug("v0_validator not available; skipping quality report")
        else:
            cfg = ValidatorConfig(
                strict_tsc=args.strict,
                skip_build=args.no_build_check,
                ignore_navigation=args.ignore_navigation,
                strict_quality=args.strict_quality,
            )
            report = validate_v0_export(summary.v0_export_dir, cfg, scaffold=scaffold)
            report_path = scaffold / "docs" / "v0-import-report.md"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(report.render_markdown(summary=summary))
            print(f"v0-import-report: {report_path}")
            if report.has_blocking:
                logger.error(
                    "v0-import-report has %d BLOCKING issue(s); see %s",
                    len(report.blocking), report_path,
                )
                return 3

    except V0ImportError as e:
        logger.error("v0 import failed: %s", e)
        return 2

    print(
        f"imported: {summary.source_type} → {summary.v0_export_dir} "
        f"({'ref='+summary.resolved_ref if summary.resolved_ref else 'zip'})"
    )
    print(f"manifest: {summary.manifest_path}")
    if args.with_hygiene:
        rc = _run_post_import_hygiene(scaffold, args.ignore_critical)
        return rc
    return 0


def _run_post_import_hygiene(scaffold: Path, ignore_critical: bool) -> int:
    """Run the hygiene scanner as a post-import step.

    Writes `docs/design-source-hygiene-checklist.md` and returns exit code 1
    if any CRITICAL findings exist (unless `ignore_critical` is True).
    """
    from .v0_design_source import V0DesignSourceProvider
    from .v0_hygiene_scanner import render_checklist

    provider = V0DesignSourceProvider()
    findings = provider.scan_hygiene(scaffold)
    crit = sum(1 for f in findings if f.severity.value == "critical")
    warn = sum(1 for f in findings if f.severity.value == "warn")
    info = sum(1 for f in findings if f.severity.value == "info")

    out_path = scaffold / "docs" / "design-source-hygiene-checklist.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    md = render_checklist(findings, project_id=scaffold.name, source_dir="v0-export/")
    out_path.write_text(md)

    print(f"hygiene: {len(findings)} findings ({crit} CRITICAL, {warn} WARN, {info} INFO) → {out_path}")
    if crit > 0 and not ignore_critical:
        print(
            f"\nexit 1 due to {crit} CRITICAL finding(s). "
            f"Fix in design source repo or re-run with --ignore-critical.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
