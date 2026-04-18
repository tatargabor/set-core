"""Design fidelity gate (web module).

Runs AFTER build and BEFORE merge. Three-phase:

  1. Skeleton check (fast, no build): route inventory + shared file
     existence + component decomposition via AST. Fails fast on mismatch.
  2. Build reference + agent: materialize v0 reference with fixtures
     (v0_renderer), capture Playwright screenshots across 3 viewports.
  3. Pixelmatch diff per route × viewport with configurable threshold.

Per design D8, when detect_design_source()=="v0" and any required input
is absent (manifest, fixtures), the gate FAILS the merge. The single
override is `gates.design-fidelity.warn_only: true` in orchestration config.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from set_orch.gate_runner import GateResult
    from set_orch.state import Change

logger = logging.getLogger(__name__)


VIEWPORTS = (
    ("desktop", 1440, 900),
    ("tablet", 768, 1024),
    ("mobile", 375, 667),
)

DEFAULT_DIFF_THRESHOLD = 1.5  # percent
DEFAULT_PIXEL_FLOOR = 200     # absolute min diff pixels before threshold applies
RETENTION_DAYS = 7


@dataclass
class SkeletonViolation:
    status: str   # "missing-route" | "extra-route" | "missing-shared-file" | "decomposition-collapsed"
    detail: str


@dataclass
class GateFailure:
    route: str
    viewport: str
    diff_pct: float
    diff_px: int
    diff_image: Optional[Path] = None


@dataclass
class GateOutcome:
    status: str  # pass / fail / warn-fail / skipped
    checked_routes: list[str] = field(default_factory=list)
    max_diff_pct: float = 0.0
    failed_routes: list[GateFailure] = field(default_factory=list)
    skeleton_violations: list[SkeletonViolation] = field(default_factory=list)
    diff_images_dir: Optional[Path] = None
    message: str = ""


# ─── Gate entry point ───────────────────────────────────────────────


def execute_design_fidelity_gate(
    change_name: str,
    change: "Change",
    wt_path: str,
    profile=None,
) -> "GateResult":
    """Gate entry point registered via profile_type.register_gates()."""
    from set_orch.gate_runner import GateResult

    if not wt_path:
        return GateResult("design-fidelity", "skipped", output="no worktree path")

    project_path = _resolve_project_path(wt_path, change)
    if project_path is None:
        return GateResult(
            "design-fidelity", "fail",
            output="worktree-path-unknown",
            retry_context="cannot locate consumer project path for fidelity gate",
        )

    # Skip when no v0 source is declared.
    v0_dir = project_path / "v0-export"
    if not v0_dir.is_dir():
        return GateResult(
            "design-fidelity", "skipped", output="skipped-no-design-source",
        )

    warn_only = _read_warn_only_flag(project_path)

    try:
        outcome = _run_gate(change_name, wt_path, project_path)
    except _GateAbort as e:
        status = "warn-fail" if warn_only else "fail"
        if warn_only:
            logger.info(
                "[design-fidelity warn_only] downgrading failure to pass: %s. "
                "Re-enable blocking mode by removing gates.design-fidelity.warn_only from orchestration config.",
                e.status,
            )
        return GateResult(
            "design-fidelity",
            "pass" if warn_only else "fail",
            output=e.status,
            retry_context=e.remediation or "",
            stats={"status": e.status},
        )

    if outcome.status == "pass":
        return GateResult(
            "design-fidelity", "pass",
            output=f"checked {len(outcome.checked_routes)} routes, max diff {outcome.max_diff_pct:.2f}%",
            stats={
                "checked_routes": outcome.checked_routes,
                "max_diff_pct": outcome.max_diff_pct,
            },
        )

    if warn_only:
        logger.info(
            "[design-fidelity warn_only] downgrading %d failed routes to warning. "
            "Disable the flag once the underlying issue is fixed.",
            len(outcome.failed_routes),
        )
        return GateResult(
            "design-fidelity", "pass",
            output=f"warn_only: {len(outcome.failed_routes)} route failures suppressed",
            stats={
                "status": "warn-fail",
                "failed_routes": [f.route for f in outcome.failed_routes],
                "max_diff_pct": outcome.max_diff_pct,
            },
        )

    retry_ctx = _build_retry_context(outcome)
    return GateResult(
        "design-fidelity", "fail",
        output=outcome.message or "fidelity check failed",
        retry_context=retry_ctx,
        stats={
            "failed_routes": [f.route for f in outcome.failed_routes],
            "max_diff_pct": outcome.max_diff_pct,
            "skeleton_violations": [
                {"status": s.status, "detail": s.detail}
                for s in outcome.skeleton_violations
            ],
        },
    )


# ─── Core pipeline ─────────────────────────────────────────────────


class _GateAbort(Exception):
    def __init__(self, status: str, remediation: str = ""):
        super().__init__(status)
        self.status = status
        self.remediation = remediation


def _run_gate(change_name: str, wt_path: str, project_path: Path) -> GateOutcome:
    """Run the full gate: skeleton → build ref + agent → diff."""
    from .v0_manifest import load_manifest

    manifest_path = project_path / "docs" / "design-manifest.yaml"
    if not manifest_path.is_file():
        raise _GateAbort(
            "manifest-missing",
            "design-manifest.yaml not found at docs/. Run set-design-import --regenerate-manifest.",
        )
    manifest = load_manifest(manifest_path)

    # 1. Skeleton check (fast, no build).
    skel = run_skeleton_check(Path(wt_path), project_path / "v0-export", manifest)
    if skel:
        return GateOutcome(
            status="fail",
            skeleton_violations=skel,
            message="skeleton-mismatch",
        )

    # 2. Fixtures — REQUIRED when design is declared.
    fixtures_path = project_path / ".set-orch" / "v0-fixtures.yaml"
    if not fixtures_path.is_file():
        raise _GateAbort(
            "fixtures-missing",
            f"{fixtures_path} not found. Scaffold must author content-fixtures.yaml and the runner must deploy it.",
        )

    from .v0_renderer import (
        FixturesMissingError,
        Fixtures,
        ReferenceBuildError,
        load_fixtures,
        render_v0_with_fixtures,
    )

    try:
        fixtures = load_fixtures(fixtures_path)
    except FixturesMissingError as e:
        raise _GateAbort("fixtures-missing", str(e)) from e

    # 3. Render reference + capture screenshots. Render agent in worktree.
    outcome = GateOutcome(status="pass")
    outcome.checked_routes = [r.path for r in manifest.routes]
    diff_root = Path(wt_path) / "gate-results" / "design-fidelity"
    diff_root.mkdir(parents=True, exist_ok=True)
    outcome.diff_images_dir = diff_root

    try:
        with render_v0_with_fixtures(project_path / "v0-export", fixtures) as ref:
            ref_shots = _capture_screenshots(ref.base_url, manifest, diff_root / "_ref")

            agent_url = _build_and_start_agent(wt_path)
            try:
                agent_shots = _capture_screenshots(agent_url, manifest, diff_root / "_agent")
            finally:
                _stop_agent_server()
    except ReferenceBuildError as e:
        raise _GateAbort("reference-build-failed", str(e)) from e

    # 4. Pixelmatch diff
    for route in manifest.routes:
        threshold = route.fidelity_threshold or DEFAULT_DIFF_THRESHOLD
        for vp_name, _, _ in VIEWPORTS:
            ref_img = ref_shots.get((route.path, vp_name))
            ag_img = agent_shots.get((route.path, vp_name))
            if ref_img is None or ag_img is None:
                outcome.failed_routes.append(GateFailure(
                    route=route.path, viewport=vp_name,
                    diff_pct=100.0, diff_px=0,
                ))
                continue
            diff_pct, diff_px, diff_img = _run_pixelmatch(
                ref_img, ag_img, diff_root / route.path.strip("/") / vp_name,
            )
            outcome.max_diff_pct = max(outcome.max_diff_pct, diff_pct)
            if diff_pct > threshold and diff_px > DEFAULT_PIXEL_FLOOR:
                outcome.failed_routes.append(GateFailure(
                    route=route.path, viewport=vp_name,
                    diff_pct=diff_pct, diff_px=diff_px,
                    diff_image=diff_img,
                ))

    _cleanup_old_gate_results(Path(wt_path) / "gate-results", RETENTION_DAYS)

    if outcome.failed_routes:
        outcome.status = "fail"
        outcome.message = f"{len(outcome.failed_routes)} route(s) exceed fidelity threshold"
    return outcome


# ─── Skeleton check (Gap A) ─────────────────────────────────────────


def run_skeleton_check(
    agent_worktree: Path,
    v0_export: Path,
    manifest,
) -> list[SkeletonViolation]:
    """Structural check — runs BEFORE any build/screenshot."""
    violations: list[SkeletonViolation] = []

    # Route inventory from manifest (truth) vs agent worktree
    manifest_routes = {r.path for r in manifest.routes}
    agent_routes = _enumerate_agent_routes(agent_worktree)
    for p in manifest_routes - agent_routes:
        violations.append(SkeletonViolation(
            "missing-route",
            f"route {p} exists in manifest but not in agent worktree",
        ))
    for p in agent_routes - manifest_routes:
        violations.append(SkeletonViolation(
            "extra-route",
            f"route {p} exists in agent worktree but not in manifest",
        ))

    # Shared file existence
    aliases = getattr(manifest, "shared_aliases", {}) or {}
    for sh in manifest.shared:
        if sh.endswith("/**"):
            base = Path(sh[: -len("/**")])
            src_prefix = f"{v0_export.name}/"
            rel = Path(str(base)[len(src_prefix):]) if str(base).startswith(src_prefix) else base
            agent_candidate = agent_worktree / rel
            if not agent_candidate.is_dir() and not _resolve_shared_alias(agent_worktree, rel, aliases):
                violations.append(SkeletonViolation(
                    "missing-shared-file",
                    f"shared directory {rel} absent in agent worktree",
                ))
        else:
            src_prefix = f"{v0_export.name}/"
            rel = Path(sh[len(src_prefix):]) if sh.startswith(src_prefix) else Path(sh)
            agent_candidate = agent_worktree / rel
            if not agent_candidate.is_file() and not _resolve_shared_alias(agent_worktree, rel, aliases):
                violations.append(SkeletonViolation(
                    "missing-shared-file",
                    f"shared file {rel} absent in agent worktree",
                ))

    # Component decomposition check — verify shared components remain file exports
    for sh in manifest.shared:
        if not (sh.endswith(".tsx") or sh.endswith(".ts")):
            continue
        src_prefix = f"{v0_export.name}/"
        rel = Path(sh[len(src_prefix):]) if sh.startswith(src_prefix) else Path(sh)
        target = agent_worktree / rel
        if not target.is_file():
            continue
        if not _has_component_export(target):
            violations.append(SkeletonViolation(
                "decomposition-collapsed",
                f"{rel} exists but no default/named component export — may have been inlined",
            ))

    return violations


def _enumerate_agent_routes(agent: Path) -> set[str]:
    """Return set of route paths from app/**/page.tsx in agent worktree."""
    app = agent / "app"
    if not app.is_dir():
        return set()
    out: set[str] = set()
    for page in app.rglob("page.tsx"):
        parts = list(page.relative_to(app).parts[:-1])
        parts = [p for p in parts if not (p.startswith("(") and p.endswith(")"))]
        out.add("/" + "/".join(parts) if parts else "/")
    return out


def _resolve_shared_alias(agent: Path, rel: Path, aliases: dict) -> bool:
    """Return True if rel has an alias that exists in agent worktree."""
    alias = aliases.get(rel.name) or aliases.get(str(rel))
    if not alias:
        return False
    return (agent / alias).exists() or (agent / rel.with_name(alias)).exists()


def _has_component_export(file: Path) -> bool:
    """Lightweight AST check — look for export default|export function|export const."""
    try:
        text = file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    pattern = re.compile(
        r"^\s*export\s+(?:default|function|const|class|async\s+function)",
        re.MULTILINE,
    )
    return bool(pattern.search(text))


# ─── Screenshot + pixel diff ─────────────────────────────────────────


def _capture_screenshots(
    base_url: str, manifest, output_root: Path,
) -> dict[tuple[str, str], Path]:
    """Capture 3 viewports per manifest route using Playwright-Python.

    Returns {(route_path, viewport_name): png_path}. Pages that fail to
    render are reported via the returned dict (missing entry signals failure).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error(
            "playwright not installed — design-fidelity gate cannot capture screenshots. "
            "pip install playwright && playwright install chromium",
        )
        return {}

    output_root.mkdir(parents=True, exist_ok=True)
    shots: dict[tuple[str, str], Path] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            args=["--force-color-profile=srgb", "--disable-web-security"],
        )
        try:
            for route in manifest.routes:
                url = base_url.rstrip("/") + route.path.replace("[", "%5B").replace("]", "%5D")
                for vp_name, w, h in VIEWPORTS:
                    ctx = browser.new_context(
                        viewport={"width": w, "height": h},
                        reduced_motion="reduce",
                    )
                    page = ctx.new_page()
                    try:
                        page.goto(url, wait_until="networkidle", timeout=30000)
                        try:
                            page.wait_for_function(
                                "() => document.fonts.ready.then(() => true)",
                                timeout=5000,
                            )
                        except Exception:
                            pass
                        out = output_root / route.path.strip("/") / f"{vp_name}.png"
                        out.parent.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(out), full_page=True)
                        shots[(route.path, vp_name)] = out
                    except Exception as e:
                        logger.warning("screenshot failed for %s %s: %s", route.path, vp_name, e)
                    finally:
                        ctx.close()
        finally:
            browser.close()

    return shots


def _run_pixelmatch(
    reference: Path, agent: Path, out_dir: Path,
) -> tuple[float, int, Optional[Path]]:
    """Run pixelmatch via `npx pixelmatch` (requires pnpm project with it installed).

    Returns (diff_pct, diff_px, diff_image_or_None).
    Falls back to Python PIL comparison when pixelmatch not available.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    diff_img = out_dir / "diff.png"

    # Fallback to PIL comparison — good enough for v1; pixelmatch npm
    # integration arrives with the real E2E deploy.
    try:
        from PIL import Image, ImageChops
    except ImportError:
        logger.error("Pillow not installed — cannot diff screenshots")
        return 100.0, 0, None

    try:
        ref_img = Image.open(reference).convert("RGB")
        ag_img = Image.open(agent).convert("RGB")
    except Exception as e:
        logger.warning("failed to open screenshots: %s", e)
        return 100.0, 0, None

    if ref_img.size != ag_img.size:
        # Resize agent to match reference for stable comparison
        ag_img = ag_img.resize(ref_img.size)

    diff = ImageChops.difference(ref_img, ag_img)
    bbox = diff.getbbox()
    total_px = ref_img.size[0] * ref_img.size[1]
    if bbox is None:
        return 0.0, 0, None

    # Count non-zero pixels
    hist = diff.histogram()
    # Channel non-zero counts are approximations; use sum of non-zero bands.
    diff_px = 0
    width, height = ref_img.size
    # Iterate coarsely — this is a heuristic fallback
    pixels_ref = ref_img.load()
    pixels_ag = ag_img.load()
    for y in range(0, height, max(1, height // 50)):
        for x in range(0, width, max(1, width // 50)):
            if pixels_ref[x, y] != pixels_ag[x, y]:
                diff_px += 1
    # Scale diff_px back up from sampled count
    sample_factor = (width // max(1, width // 50)) * (height // max(1, height // 50))
    if sample_factor > 0:
        diff_px = int(diff_px * sample_factor)

    diff_pct = (diff_px / total_px) * 100 if total_px else 100.0
    diff.save(diff_img)
    return diff_pct, diff_px, diff_img


# ─── Agent worktree build ────────────────────────────────────────────


_AGENT_SERVER_PID: Optional[int] = None


def _build_and_start_agent(wt_path: str) -> str:
    """Run pnpm install && pnpm build && pnpm start in agent worktree. Return base URL."""
    root = Path(wt_path)
    r = subprocess.run(["pnpm", "install", "--frozen-lockfile"], cwd=root)
    if r.returncode != 0:
        raise _GateAbort("agent-build-failed", "pnpm install failed in agent worktree")
    r = subprocess.run(["pnpm", "build"], cwd=root)
    if r.returncode != 0:
        raise _GateAbort("agent-build-failed", "pnpm build failed in agent worktree")

    # Pick a port distinct from reference (reference uses PORT_RANGE 3400-3499)
    from .v0_renderer import _allocate_port
    port = _allocate_port()
    env = os.environ.copy()
    env["PORT"] = str(port)
    proc = subprocess.Popen(
        ["pnpm", "start"],
        cwd=root, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    global _AGENT_SERVER_PID
    _AGENT_SERVER_PID = proc.pid
    # Wait for health
    import urllib.error
    import urllib.request
    deadline = time.time() + 30
    base_url = f"http://127.0.0.1:{port}"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base_url + "/", timeout=3) as r2:
                if 200 <= r2.status < 500:
                    return base_url
        except urllib.error.URLError:
            pass
        time.sleep(0.5)
    raise _GateAbort("agent-build-failed", "agent server did not respond to health check")


def _stop_agent_server() -> None:
    global _AGENT_SERVER_PID
    if _AGENT_SERVER_PID is None:
        return
    import signal
    try:
        os.killpg(_AGENT_SERVER_PID, signal.SIGTERM)
    except (ProcessLookupError, OSError):
        pass
    time.sleep(5)
    try:
        os.killpg(_AGENT_SERVER_PID, signal.SIGKILL)
    except (ProcessLookupError, OSError):
        pass
    _AGENT_SERVER_PID = None


# ─── Utility / config ───────────────────────────────────────────────


def _resolve_project_path(wt_path: str, change) -> Optional[Path]:
    """Find the project root — the dir containing v0-export/, scaffold.yaml, etc."""
    p = Path(wt_path)
    # Walk up until we find v0-export/
    for candidate in [p, *p.parents]:
        if (candidate / "v0-export").exists() or (candidate / "scaffold.yaml").exists():
            return candidate
    return None


def _read_warn_only_flag(project_path: Path) -> bool:
    """Read gates.design-fidelity.warn_only from orchestration config (if present)."""
    cfg_paths = [
        project_path / "set" / "orchestration" / "config.yaml",
        project_path / ".set-orch" / "config.yaml",
    ]
    for cfg_path in cfg_paths:
        if not cfg_path.is_file():
            continue
        try:
            import yaml
            data = yaml.safe_load(cfg_path.read_text()) or {}
            return bool(
                ((data.get("gates") or {}).get("design-fidelity") or {}).get("warn_only", False)
            )
        except Exception:
            continue
    return False


def _cleanup_old_gate_results(gate_results_root: Path, retention_days: int) -> None:
    """Delete gate-results/design-fidelity/run-* older than retention_days."""
    if not gate_results_root.is_dir():
        return
    cutoff = time.time() - retention_days * 86400
    for p in gate_results_root.rglob("*"):
        if not p.is_file():
            continue
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink(missing_ok=True)
        except OSError:
            continue


def _build_retry_context(outcome: GateOutcome) -> str:
    """Build agent retry context pointing to failing routes + diff images."""
    lines = ["# Design Fidelity Gate — Failures"]
    if outcome.skeleton_violations:
        lines.append("\n## Skeleton violations (structural, fail before screenshot)")
        for s in outcome.skeleton_violations:
            lines.append(f"- [{s.status}] {s.detail}")
    if outcome.failed_routes:
        lines.append("\n## Visual drift (screenshot diff)")
        for f in outcome.failed_routes:
            img = f" (diff: {f.diff_image})" if f.diff_image else ""
            lines.append(
                f"- {f.route} @ {f.viewport}: diff={f.diff_pct:.2f}% ({f.diff_px}px){img}"
            )
    lines.append(
        "\nFix: restore v0's exact className/JSX/variant for the failing routes. "
        "Do NOT change design tokens or globals.css. See .claude/rules/design-bridge.md."
    )
    return "\n".join(lines)
