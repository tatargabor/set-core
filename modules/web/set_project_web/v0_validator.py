"""v0 template quality validator.

Runs a suite of checks against a v0 export to catch bugs before they reach
an agent. Blocking checks fail the import; warnings show up in the report
but do not block (unless --strict / --strict-quality promote them).

Checks:
  - TypeScript type-check (npx tsc --noEmit)
  - pnpm build smoke test
  - Component naming consistency (similarity heuristic)
  - Navigation link integrity (Link href + router.push validated)
  - Variant coverage (flag when shared components use variants inconsistently)
  - shadcn primitive usage consistency (raw <button> in some pages vs Button
    in others)
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidatorConfig:
    strict_tsc: bool = False  # --strict
    skip_build: bool = False  # --no-build-check
    ignore_navigation: bool = False  # --ignore-navigation
    strict_quality: bool = False  # --strict-quality → promotes all warnings to blocking


@dataclass
class Finding:
    severity: str  # "BLOCKING" | "ERROR" | "WARNING" | "INFO"
    section: str
    message: str
    file: Optional[str] = None


@dataclass
class ValidationReport:
    findings: list[Finding] = field(default_factory=list)

    @property
    def blocking(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "BLOCKING"]

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "ERROR"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "WARNING"]

    @property
    def has_blocking(self) -> bool:
        return bool(self.blocking)

    def add(self, severity: str, section: str, message: str, file: str = None):
        self.findings.append(Finding(severity, section, message, file))

    def render_markdown(self, summary=None) -> str:
        from datetime import datetime

        lines = ["# v0 Import Report", ""]
        if summary is not None:
            lines.append(f"- source: `{summary.source_type}` ({summary.source_spec})")
            if summary.resolved_ref:
                lines.append(f"- ref: `{summary.resolved_ref}`")
            lines.append(f"- v0-export: `{summary.v0_export_dir}`")
        lines.append(f"- generated: {datetime.utcnow().isoformat()}Z")
        lines.append("")
        lines.append(
            f"- Blocking: {len(self.blocking)} | "
            f"Errors: {len(self.errors)} | "
            f"Warnings: {len(self.warnings)}"
        )
        lines.append("")

        groups: dict[str, list[Finding]] = {}
        for f in self.findings:
            groups.setdefault(f.section, []).append(f)

        for section, findings in groups.items():
            lines.append(f"## {section}")
            for f in findings:
                loc = f" (`{f.file}`)" if f.file else ""
                lines.append(f"- **[{f.severity}]** {f.message}{loc}")
            lines.append("")
        return "\n".join(lines)


# ─── Public API ─────────────────────────────────────────────────────


def validate_v0_export(
    v0_export: Path,
    cfg: ValidatorConfig,
    scaffold: Path = None,
) -> ValidationReport:
    report = ValidationReport()

    _check_tsc(v0_export, cfg, report)
    if not cfg.skip_build:
        _check_build(v0_export, report)
    _check_naming_consistency(v0_export, report)
    _check_navigation(v0_export, cfg, report)
    _check_variant_coverage(v0_export, report)
    _check_shadcn_consistency(v0_export, report)

    if cfg.strict_quality:
        # Promote all warnings to BLOCKING
        for f in report.findings:
            if f.severity == "WARNING":
                f.severity = "BLOCKING"

    return report


# ─── Individual checks ──────────────────────────────────────────────


def _check_tsc(v0: Path, cfg: ValidatorConfig, report: ValidationReport) -> None:
    if not (v0 / "tsconfig.json").is_file():
        report.add("INFO", "TypeScript", "no tsconfig.json — skipping tsc check")
        return
    try:
        r = subprocess.run(
            ["npx", "--yes", "tsc", "--noEmit"],
            cwd=v0, capture_output=True, text=True, timeout=300,
        )
    except FileNotFoundError:
        report.add("INFO", "TypeScript", "npx not available — skipping tsc check")
        return
    except subprocess.TimeoutExpired:
        report.add("WARNING", "TypeScript", "tsc --noEmit timed out")
        return
    if r.returncode == 0:
        report.add("INFO", "TypeScript", "tsc --noEmit clean")
        return
    severity = "BLOCKING" if cfg.strict_tsc else "WARNING"
    # Show the first 80 + 20 lines — enough to cover typical tsc error bursts
    # (50-100 errors) without producing an unusable report.
    lines = (r.stdout or "").splitlines()[:80] + (r.stderr or "").splitlines()[:20]
    joined = "\n".join(lines)
    report.add(severity, "TypeScript", f"tsc errors:\n```\n{joined}\n```")


def _check_build(v0: Path, report: ValidationReport) -> None:
    if not (v0 / "package.json").is_file():
        report.add("BLOCKING", "Build", "missing package.json")
        return
    try:
        r = subprocess.run(
            ["pnpm", "install", "--frozen-lockfile"],
            cwd=v0, capture_output=True, text=True, timeout=600,
        )
    except FileNotFoundError:
        report.add("INFO", "Build", "pnpm not installed — skipping build check")
        return
    except subprocess.TimeoutExpired:
        report.add("BLOCKING", "Build", "pnpm install timed out")
        return
    if r.returncode != 0:
        report.add(
            "BLOCKING", "Build",
            f"pnpm install failed:\n```\n{(r.stderr or '')[:8000]}\n```",
        )
        return
    try:
        r = subprocess.run(
            ["pnpm", "build"],
            cwd=v0, capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        report.add("BLOCKING", "Build", "pnpm build timed out")
        return
    if r.returncode != 0:
        report.add(
            "BLOCKING", "Build",
            f"pnpm build failed:\n```\n{(r.stderr or '')[:8000]}\n```",
        )
    else:
        report.add("INFO", "Build", "pnpm build succeeded")


def _check_naming_consistency(v0: Path, report: ValidationReport) -> None:
    """Detect similar component names via token-similarity heuristic."""
    comp_dir = v0 / "components"
    if not comp_dir.is_dir():
        return
    names: list[str] = []
    for f in comp_dir.rglob("*.tsx"):
        if f.is_file():
            names.append(f.stem)
    if len(names) < 2:
        return

    # Simple token-based similarity: group names sharing a significant stem
    groups: dict[str, list[str]] = {}
    for n in names:
        tokens = re.split(r"[-_]", n.lower())
        main = next((t for t in tokens if len(t) >= 4), n.lower())
        groups.setdefault(main, []).append(n)
    for main, group in groups.items():
        if len(group) > 1:
            report.add(
                "WARNING", "Naming Inconsistencies",
                f"components with similar stem '{main}': {sorted(group)} — consider consolidating",
            )


def _check_navigation(v0: Path, cfg: ValidatorConfig, report: ValidationReport) -> None:
    """Every Link href + router.push destination must map to an existing route."""
    app_dir = v0 / "app"
    if not app_dir.is_dir():
        return

    routes: set[str] = set()
    for page in app_dir.rglob("page.tsx"):
        parts = list(page.relative_to(app_dir).parts[:-1])
        parts = [p for p in parts if not (p.startswith("(") and p.endswith(")"))]
        routes.add("/" + "/".join(parts) if parts else "/")

    # Find all Link href / router.push calls
    link_re = re.compile(r"""<Link\s+[^>]*href\s*=\s*["']([^"']+)["']""")
    push_re = re.compile(r"""router\.push\s*\(\s*["']([^"']+)["']""")

    referenced: set[tuple[str, str]] = set()  # (route, file)
    for f in v0.rglob("*.tsx"):
        if not f.is_file():
            continue
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in link_re.finditer(txt):
            referenced.add((m.group(1), str(f.relative_to(v0))))
        for m in push_re.finditer(txt):
            referenced.add((m.group(1), str(f.relative_to(v0))))

    broken: list[tuple[str, str]] = []
    for ref, file in referenced:
        if ref.startswith(("http://", "https://", "mailto:", "tel:", "#")):
            continue
        # strip query string + hash
        clean = ref.split("?")[0].split("#")[0]
        if not clean:
            continue
        # Normalize dynamic segments (e.g. /kavek/foo → must match /kavek/[slug])
        if clean in routes:
            continue
        matched = False
        for r in routes:
            if re.match(_route_to_regex(r), clean):
                matched = True
                break
        if not matched:
            broken.append((clean, file))

    for clean, file in broken:
        severity = "WARNING" if cfg.ignore_navigation else "BLOCKING"
        report.add(severity, "Navigation Integrity", f"broken link: {clean}", file=file)

    # Orphan pages — routes not referenced by any Link
    referenced_paths = {clean.split("?")[0].split("#")[0] for clean, _ in referenced}
    for r in routes:
        if r == "/":
            continue
        if not any(
            rp.startswith(r) or r.startswith(rp)
            for rp in referenced_paths
        ):
            report.add("WARNING", "Navigation Integrity", f"orphan route (no Link references): {r}")


def _route_to_regex(route: str) -> str:
    """Convert /kavek/[slug] → ^/kavek/[^/]+$."""
    pattern = re.sub(r"\[[^\]]+\]", "[^/]+", route)
    return "^" + pattern + "$"


def _check_variant_coverage(v0: Path, report: ValidationReport) -> None:
    """Detect shared components whose variants appear unevenly across pages."""
    # Heuristic: count occurrences of <Button variant="..."> tokens across pages
    app_dir = v0 / "app"
    if not app_dir.is_dir():
        return
    variant_re = re.compile(r"""<(?:Button|Badge|Alert)\s+[^>]*variant\s*=\s*["']([^"']+)["']""")
    per_page: dict[str, set[str]] = {}
    for page in app_dir.rglob("page.tsx"):
        try:
            txt = page.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        per_page[str(page.relative_to(v0))] = set(variant_re.findall(txt))

    if not per_page:
        return
    union = set().union(*per_page.values())
    for page, variants in per_page.items():
        missing = union - variants
        if missing and variants:
            report.add(
                "WARNING", "Variant Coverage Gaps",
                f"page uses variants {sorted(variants)} but other pages include {sorted(missing)}",
                file=page,
            )


def _check_shadcn_consistency(v0: Path, report: ValidationReport) -> None:
    """Flag pages using raw <button> where other pages use <Button>."""
    app_dir = v0 / "app"
    if not app_dir.is_dir():
        return
    raw_button = re.compile(r"<button[\s>]")
    shadcn_button = re.compile(r"<Button[\s>]")
    raw_count = 0
    shadcn_count = 0
    for page in app_dir.rglob("page.tsx"):
        try:
            txt = page.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if raw_button.search(txt):
            raw_count += 1
        if shadcn_button.search(txt):
            shadcn_count += 1
    if raw_count > 0 and shadcn_count > 0:
        report.add(
            "WARNING", "shadcn Consistency",
            f"{raw_count} page(s) use raw <button> while {shadcn_count} use shadcn <Button> — "
            f"standardize on one",
        )
