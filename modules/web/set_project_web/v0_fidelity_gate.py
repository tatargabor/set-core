"""Design fidelity gate (web module).

Runs AFTER the build gate and BEFORE merge. The check is scope-aware:
each change is held to the routes its own scope describes, not the
whole v0 manifest.

Default pipeline (fast, no server):
  1. Skeleton — route inventory + shared-file existence + component
     decomposition, matched against the change's scope.
  2. Token guard — hardcoded hex/rgb/hsl colors in newly added src/
     code (design tokens live in globals.css ``:root``).
  3. className preservation — for each scoped route directory and each
     shared component referenced by scoped routes, the agent must keep
     most of v0's className vocabulary. Credit is given for:
       - the server/client split (aggregate tokens across the directory),
       - shadcn imports (``<Button>`` carries Button's classes),
       - intentional stubs ("coming soon" pages under min tokens).

Optional pixel-diff phase (expensive, off by default):
  4. Render v0 with fixtures + agent worktree, capture Playwright
     screenshots across 3 viewports, pixelmatch diff per route.

Enable the screenshot phase only when it's worth the flakiness:
  gates:
    design-fidelity:
      pixel_diff: true
      warn_only: true  # downgrade fail → pass if you need breathing room
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

from .v0_manifest import match_routes_by_scope

if TYPE_CHECKING:
    from set_orch.gate_runner import GateResult
    from set_orch.state import Change

logger = logging.getLogger(__name__)


def _deferred_route_paths(manifest) -> set[str]:
    """Normalise ``manifest.deferred_design_routes`` to a ``{route, ...}`` set.

    The schema declares ``list[dict]`` (with ``{"route": ..., "reason": ...}``
    entries), but operator-authored manifests sometimes use bare strings. This
    helper accepts both so the skeleton check never crashes on mixed input.
    """
    out: set[str] = set()
    for d in getattr(manifest, "deferred_design_routes", None) or []:
        if isinstance(d, dict):
            route = d.get("route")
            if route:
                out.add(route)
        elif isinstance(d, str):
            out.add(d)
    return out


def _scoped_routes(manifest, change_scope: str) -> list:
    """Return the subset of ``manifest.routes`` the change's scope matches.

    Empty ``change_scope`` → return the full route list (legacy callers +
    non-orchestrated invocations stay useful). Strict path-first matching
    is used so keyword coincidences (e.g. ``slug`` appearing in a product
    form description) don't sweep in sibling changes' routes.
    """
    if not change_scope:
        return list(manifest.routes)
    try:
        return list(match_routes_by_scope(manifest, change_scope, strict=True))
    except Exception:
        logger.debug("match_routes_by_scope failed", exc_info=True)
        return list(manifest.routes)


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
    status: str   # "missing-route" | "extra-route" | "missing-shared-file" | "decomposition-collapsed" | "decomposition-shadow" | "shell-not-mounted" | "shadow-alias" | "shadcn-primitive-missing" | "hardcoded-color" | "classname-rewritten"
    detail: str


# Distinctive shadcn primitives. These have HIGH agent-temptation to replace
# with simpler vanilla equivalents (Dialog → modal, dropdown anchored to input
# instead of CommandDialog, plain Select instead of Combobox, etc.). When the
# v0 design source uses one of these, the implementation MUST also use it
# (or carry an explicit waiver). Adding to this list is cheap; primitives
# that don't appear in any v0 export simply don't trigger the parity check.
_DISTINCTIVE_SHADCN_PRIMITIVES = frozenset({
    # Command palette family — frequently substituted with plain dropdown
    "CommandDialog", "Command", "CommandInput", "CommandItem",
    "CommandGroup", "CommandList", "CommandEmpty", "CommandSeparator",
    # Sheet drawer — frequently substituted with Dialog modal
    "Sheet", "SheetContent", "SheetTrigger", "SheetHeader", "SheetTitle",
    # Hover/Popover patterns — frequently substituted with Tooltip or inline
    "HoverCard", "HoverCardContent", "HoverCardTrigger",
    # Drawer — frequently substituted with Sheet or Dialog
    "Drawer", "DrawerContent", "DrawerTrigger",
    # Combobox — frequently substituted with plain Select or two separate fields
    "Combobox",
    # Resizable panels — frequently substituted with plain grid
    "ResizablePanel", "ResizablePanelGroup", "ResizableHandle",
    # Scroll-area — frequently substituted with overflow CSS
    "ScrollArea", "ScrollBar",
    # Stepper / multi-step indicator — frequently inlined as text
    "Stepper", "Step",
})


# ─── Static design-drift checks (no build required) ──────────────────
# Token guard: new code in src/ must use oklch tokens, not literal colors.
# Exclude common false-positive zones (comments, test fixtures, shadcn chart).
_HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}(?![0-9a-fA-F])")
_FN_COLOR_RE = re.compile(r"\b(?:rgb|rgba|hsl|hsla)\s*\(")
_TOKEN_GUARD_PATH_PREFIX = "src/"
_TOKEN_GUARD_FILE_EXT = (".ts", ".tsx", ".css")
# Files where static color literals are legitimate: shadcn chart injects
# theme CSS variables, globals.css is the token source itself, and HTML
# email templates MUST use inline literal colors because most email clients
# strip CSS custom properties before render.
_TOKEN_GUARD_EXEMPT_SUFFIX = (
    "src/components/ui/chart.tsx",
    "src/app/globals.css",
)
_TOKEN_GUARD_EXEMPT_PREFIX = (
    "src/lib/email-templates/",
    "src/app/admin/email-templates/",  # admin preview of the same HTML
)


def _iter_diff_added_lines(wt_path: Path, diff_base: str) -> list[tuple[str, int, str]]:
    """Return added [(file, line_num, content), ...] from `git diff diff_base..HEAD`.

    Shares logic with the lint gate; kept local here to avoid a cross-module
    import cycle (gates.py → project_type → v0_fidelity_gate).
    """
    try:
        r = subprocess.run(
            ["git", "diff", "--unified=0", f"{diff_base}..HEAD"],
            cwd=wt_path, capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return []
    except Exception:
        return []

    out: list[tuple[str, int, str]] = []
    file_path = None
    line_num = 0
    for raw in r.stdout.splitlines():
        if raw.startswith("+++ b/"):
            file_path = raw[6:]
        elif raw.startswith("@@"):
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", raw)
            if m:
                line_num = int(m.group(1)) - 1
        elif raw.startswith("+") and not raw.startswith("+++"):
            line_num += 1
            if file_path:
                out.append((file_path, line_num, raw[1:]))
    return out


def run_token_guard_check(agent_worktree: Path, diff_base: str) -> list[SkeletonViolation]:
    """Flag hardcoded colors in diff. Design tokens must come from globals.css :root."""
    if not diff_base:
        return []
    violations: list[SkeletonViolation] = []
    for path, line_num, content in _iter_diff_added_lines(agent_worktree, diff_base):
        if not path.startswith(_TOKEN_GUARD_PATH_PREFIX):
            continue
        if not path.endswith(_TOKEN_GUARD_FILE_EXT):
            continue
        if any(path.endswith(ex) for ex in _TOKEN_GUARD_EXEMPT_SUFFIX):
            continue
        if any(path.startswith(pref) for pref in _TOKEN_GUARD_EXEMPT_PREFIX):
            continue
        stripped = content.strip()
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
            continue
        if _HEX_COLOR_RE.search(content) or _FN_COLOR_RE.search(content):
            violations.append(SkeletonViolation(
                "hardcoded-color",
                f"{path}:{line_num} uses literal color — reference an oklch token from globals.css :root",
            ))
    return violations


_CLASSNAME_ATTR_RE = re.compile(r'className\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|`([^`]*)`)')
# Covers shadcn patterns: cn()/clsx()/classNames() helpers and cva() base class arg.
# Nested `variants: { default: "..." }` string blobs are missed by design —
# matching them reliably without false positives requires AST parsing.
_CLASSNAME_FN_RE = re.compile(r'(?:cn|clsx|classNames|cva)\s*\(([^)]*)\)', re.DOTALL)
# `.` allowed so bracket modifiers like `text-[1.125rem]` remain one token.
_CLASSNAME_TOKEN_RE = re.compile(r"[A-Za-z0-9:_\[\]/\-.]+")
_CLASSNAME_MIN_TOKENS = 6          # files with fewer className tokens are not worth checking
_CLASSNAME_OVERLAP_THRESHOLD = 0.5  # <50% overlap = likely rewritten

# Match imports of the form:
#   import { Button, Card } from "@/components/ui/button"
#   import { Input } from "components/ui/input"
# We only need to know which ui/<name> files were pulled in — the agent
# gets credit for the class tokens those files ship, since rendering
# `<Button>` effectively inlines Button's className vocabulary.
_SHADCN_IMPORT_RE = re.compile(
    r'''from\s+["']\s*(?:@/)?(?:src/)?components/ui/([A-Za-z0-9_-]+)["']''',
)


def _extract_classname_tokens(text: str) -> set[str]:
    """Return the set of CSS class tokens referenced anywhere in the file."""
    blobs: list[str] = []
    for m in _CLASSNAME_ATTR_RE.finditer(text):
        for g in m.groups():
            if g:
                blobs.append(g)
    for m in _CLASSNAME_FN_RE.finditer(text):
        blobs.append(m.group(1))
    tokens: set[str] = set()
    for blob in blobs:
        for t in _CLASSNAME_TOKEN_RE.findall(blob):
            if len(t) >= 2:
                tokens.add(t)
    return tokens


def _collect_shadcn_import_tokens(text: str, agent_worktree: Path) -> set[str]:
    """Return className tokens pulled in transitively via shadcn ui imports.

    Using ``<Button>`` / ``<Card>`` from ``components/ui/`` is a legitimate
    refactor of v0's inline Tailwind — the component internally carries the
    class vocabulary. Without crediting imports we'd punish the correct
    shadcn pattern; agents are forced to inline tokens to satisfy the gate,
    which directly conflicts with the "keep v0 design" intent.
    """
    tokens: set[str] = set()
    for m in _SHADCN_IMPORT_RE.finditer(text):
        name = m.group(1)
        for base in (agent_worktree / "src" / "components" / "ui",
                     agent_worktree / "components" / "ui"):
            p = base / f"{name}.tsx"
            if p.is_file():
                try:
                    tokens |= _extract_classname_tokens(
                        p.read_text(encoding="utf-8", errors="ignore")
                    )
                except OSError:
                    pass
                break
    return tokens


def run_classname_preservation_check(
    agent_worktree: Path, v0_export: Path,
    manifest, change_scope: str = "",
) -> list[SkeletonViolation]:
    """Flag scoped files whose className overlap with their v0 counterpart is low.

    For each v0-export file that has an agent counterpart (mapped via
    ``src/`` prefix), compute the Jaccard overlap of className tokens.
    If the agent kept fewer than ``_CLASSNAME_OVERLAP_THRESHOLD`` of v0's
    tokens, it likely rewrote the component instead of adapting it.

    Routes in ``manifest.deferred_design_routes`` are skipped (intentional
    divergence authorised by the scaffold).
    """
    violations: list[SkeletonViolation] = []
    deferred = _deferred_route_paths(manifest)

    scoped_route_paths: set[str] = set()
    if change_scope:
        for r in _scoped_routes(manifest, change_scope):
            if r.path not in deferred:
                scoped_route_paths.add(r.path)

    def _check_pair(v0_file: Path, agent_file: Path, label: str) -> None:
        try:
            v0_text = v0_file.read_text(encoding="utf-8", errors="ignore")
            agent_text = agent_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return
        v0_tokens = _extract_classname_tokens(v0_text)
        if len(v0_tokens) < _CLASSNAME_MIN_TOKENS:
            return
        agent_tokens = _extract_classname_tokens(agent_text)
        # Credit shadcn imports: <Button>/<Card>/... transitively bring in
        # the class vocabulary v0 wrote inline, so using them is NOT drift.
        agent_tokens |= _collect_shadcn_import_tokens(agent_text, agent_worktree)
        if not agent_tokens:
            violations.append(SkeletonViolation(
                "classname-rewritten",
                f"{label}: agent file has no className tokens (v0 has {len(v0_tokens)})",
            ))
            return
        overlap = len(v0_tokens & agent_tokens) / max(len(v0_tokens), 1)
        if overlap < _CLASSNAME_OVERLAP_THRESHOLD:
            violations.append(SkeletonViolation(
                "classname-rewritten",
                f"{label}: only {overlap:.0%} of v0 className tokens preserved "
                f"(v0={len(v0_tokens)} agent={len(agent_tokens)}). Keep the v0 "
                f"className vocabulary; adapt data/imports without rewriting markup.",
            ))

    # Scoped route pages: compare v0's route (directory-level className set)
    # with the agent's route directory. Aggregation matters because the
    # agent legitimately splits v0's monolithic page.tsx into a server
    # component + one or more client components in the same directory;
    # per-file comparison gives a false "page has no className" signal
    # when the className content just moved to a sibling file.
    for route_path in scoped_route_paths:
        rel_segments = [s for s in route_path.strip("/").split("/") if s]
        v0_page = v0_export / "app" / Path(*rel_segments) / "page.tsx" if rel_segments else v0_export / "app" / "page.tsx"
        if not v0_page.is_file():
            continue
        v0_tokens = _extract_classname_tokens(
            v0_page.read_text(encoding="utf-8", errors="ignore")
        )
        if len(v0_tokens) < _CLASSNAME_MIN_TOKENS:
            continue

        agent_dirs: list[Path] = []
        base_options = [agent_worktree / "app", agent_worktree / "src" / "app"]
        for base in base_options:
            if not base.is_dir():
                continue
            for match in base.rglob("page.tsx"):
                parts = list(match.relative_to(base).parts[:-1])
                parts_normalised = [
                    p for p in parts
                    if not (p.startswith("(") and p.endswith(")")) and p != "[locale]"
                ]
                agent_route = "/" + "/".join(parts_normalised) if parts_normalised else "/"
                if agent_route == route_path:
                    agent_dirs.append(match.parent)

        for agent_dir in agent_dirs:
            agent_tokens: set[str] = set()
            for f in agent_dir.iterdir():
                if f.is_file() and f.suffix in (".tsx", ".ts"):
                    try:
                        text = f.read_text(encoding="utf-8", errors="ignore")
                    except OSError:
                        continue
                    agent_tokens |= _extract_classname_tokens(text)
                    # Credit the agent for tokens carried transitively via
                    # shadcn <Button>/<Card>/etc. imports — otherwise the
                    # check punishes correct refactors.
                    agent_tokens |= _collect_shadcn_import_tokens(text, agent_worktree)
            # If the agent directory has very few className tokens, treat
            # it as an intentional stub/placeholder (e.g. "Coming soon"
            # link target for a future change). Other gates (build, e2e,
            # spec_verify) ensure scope-required routes are functional;
            # flagging stubs here produces false positives for legitimate
            # navigation targets that the scope mentions but does not ask
            # the current change to build.
            if len(agent_tokens) < _CLASSNAME_MIN_TOKENS:
                continue
            overlap = len(v0_tokens & agent_tokens) / max(len(v0_tokens), 1)
            if overlap < _CLASSNAME_OVERLAP_THRESHOLD:
                violations.append(SkeletonViolation(
                    "classname-rewritten",
                    f"route {route_path}: only {overlap:.0%} of v0 className tokens preserved across "
                    f"{agent_dir.name}/ (v0={len(v0_tokens)} agent={len(agent_tokens)}). Keep the v0 "
                    f"className vocabulary; adapt data/imports without rewriting markup.",
                ))

    # Scoped shared components referenced by matched routes.
    matched = _scoped_routes(manifest, change_scope) if change_scope else []
    seen_deps: set[str] = set()
    for r in matched:
        if r.path in deferred:
            continue
        for dep in getattr(r, "component_deps", []) or []:
            if dep in seen_deps:
                continue
            seen_deps.add(dep)
            if not dep.startswith("v0-export/"):
                continue
            rel = dep[len("v0-export/"):]
            v0_file = v0_export / rel
            if not v0_file.is_file():
                continue
            for agent_base in (agent_worktree, agent_worktree / "src"):
                agent_file = agent_base / rel
                if agent_file.is_file():
                    _check_pair(v0_file, agent_file, f"component {rel}")
                    break

    return violations


# ─── Screenshot diff config flag ─────────────────────────────────────
# Pixel-level screenshot diffing is heavyweight (dual server build +
# Playwright + diff) and fragile (font rendering, animations, seeded data
# drift). It is OFF by default; the static checks above cover the real
# drift classes. To re-enable, set in orchestration config:
#   gates:
#     design-fidelity:
#       pixel_diff: true


def _read_pixel_diff_flag(project_path: Path) -> bool:
    cfg_paths = [
        project_path / "set" / "orchestration" / "config.yaml",
        project_path / ".set-orch" / "config.yaml",
    ]
    for cfg_path in cfg_paths:
        if not cfg_path.is_file():
            continue
        try:
            import yaml as _yaml
            data = _yaml.safe_load(cfg_path.read_text()) or {}
            return bool(
                ((data.get("gates") or {}).get("design-fidelity") or {}).get("pixel_diff", False)
            )
        except Exception:
            continue
    return False


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
        outcome = _run_gate(change_name, wt_path, project_path, change=change)
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


def _run_gate(
    change_name: str,
    wt_path: str,
    project_path: Path,
    change=None,
) -> GateOutcome:
    """Run the full gate: skeleton → build ref + agent → diff."""
    from .v0_manifest import load_manifest

    manifest_path = project_path / "docs" / "design-manifest.yaml"
    if not manifest_path.is_file():
        raise _GateAbort(
            "manifest-missing",
            "design-manifest.yaml not found at docs/. Run set-design-import --regenerate-manifest.",
        )
    manifest = load_manifest(manifest_path)

    # 1. Skeleton check (fast, no build). Scope-aware: only routes matched
    # to this change's scope via manifest scope_keywords are required.
    change_scope = getattr(change, "scope", "") if change is not None else ""
    # Compute routes inherited from the base commit so extra-route does
    # not flag them against the current agent. Without this, routes like
    # /admin/login or /bundles (created by foundation/auth siblings that
    # already merged) flood every subsequent UI change's retry_context.
    inherited_routes: set[str] = set()
    try:
        from set_orch.verifier import _get_merge_base
        base_sha = _get_merge_base(str(Path(wt_path))) or ""
        if base_sha:
            inherited_routes = _enumerate_routes_at_ref(Path(wt_path), base_sha)
    except Exception:
        logger.debug("inherited-routes lookup failed for skeleton check", exc_info=True)
    skel = run_skeleton_check(
        Path(wt_path), project_path / "v0-export", manifest,
        change_scope=change_scope,
        base_routes=inherited_routes,
    )
    # Only structural-absence violations are blocking. `extra-route` is
    # informational — Next.js framework pages (/403, /404, /500, error.tsx),
    # API routes, and content merged from sibling changes legitimately
    # produce extras that the agent cannot delete without breaking the app.
    blocking_statuses = {
        "missing-route", "missing-shared-file", "decomposition-collapsed",
        # design-fidelity-shell-hardening: hard fail on missing/aliased shells
        "shell-not-mounted", "shadow-alias",
    }
    blocking = [v for v in skel if v.status in blocking_statuses]
    if blocking:
        return GateOutcome(
            status="fail",
            skeleton_violations=blocking,
            message="skeleton-mismatch",
        )

    # 2. Token guard — newly added src/ code must use oklch tokens, not
    # literal hex/rgb/hsl colors. Caught drift class: agent hardcodes
    # colors instead of referencing globals.css :root vars.
    diff_base = ""
    try:
        from set_orch.verifier import _get_merge_base
        diff_base = _get_merge_base(str(Path(wt_path))) or ""
    except Exception:
        logger.debug("merge-base lookup failed for token guard", exc_info=True)
    token_violations = run_token_guard_check(Path(wt_path), diff_base) if diff_base else []

    # 3. className preservation — INFORMATIONAL ONLY.
    #
    # The design is a *guideline*, not a literal template — if we wanted
    # byte-for-byte fidelity we would ship v0's generated code unchanged.
    # The agent is allowed (and expected) to refactor: server/client split,
    # shadcn prefab swaps, new subfolder components, synonym classnames.
    # The Jaccard token-overlap metric conflates "changed code layout" with
    # "changed design", and in craftbrew-run-20260421-0025 it produced
    # ~47 violations of which ~90% were false positives (agent used
    # <Button> instead of inline classes, split page.tsx into _components/,
    # extended v0 layouts — agent=71 > v0=20 still flagged "only 35%").
    # We still run the check so operators can see drift signals in the
    # retry_context, but a low overlap alone no longer blocks the merge.
    # Real design-drift protection comes from:
    #   - token_guard (hardcoded colors — strict)
    #   - skeleton_check (missing routes / components — strict)
    #   - pixel_diff (opt-in, visual ground truth for critical routes)
    classname_violations = run_classname_preservation_check(
        Path(wt_path), project_path / "v0-export", manifest,
        change_scope=change_scope,
    )

    # token_guard still blocks; classname findings surface as context only.
    if token_violations:
        return GateOutcome(
            status="fail",
            skeleton_violations=(
                token_violations
                + classname_violations
                + [v for v in skel if v not in blocking]
            ),
            message="design-drift",
        )

    # classname findings alone do not block, but log them so forensic
    # review can spot systemic drift patterns across the run.
    if classname_violations:
        logger.info(
            "design-fidelity: %d classname-preservation finding(s) recorded "
            "(informational — not blocking merge). Sample: %s",
            len(classname_violations),
            classname_violations[0].detail[:200],
        )

    # 4. Screenshot + pixel diff (OPT-IN). Expensive (dual server build +
    # Playwright), flaky (font rendering, animations, data fixtures),
    # and the static checks above already cover the real drift classes.
    # Enable via orchestration config:
    #   gates: { design-fidelity: { pixel_diff: true } }
    scoped_routes = _scoped_routes(manifest, change_scope)
    if not _read_pixel_diff_flag(project_path):
        outcome = GateOutcome(status="pass")
        outcome.checked_routes = [r.path for r in scoped_routes]
        outcome.message = "static-checks-only (pixel_diff disabled)"
        # Preserve classname findings in the outcome so gate_runner stats
        # / forensic tools can see them even when the gate passes.
        outcome.skeleton_violations = classname_violations
        return outcome

    # Fixtures — REQUIRED when pixel_diff is on.
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

    # Scope screenshot/diff to routes matched to this change — sibling
    # routes won't exist in the agent worktree and would produce
    # guaranteed failures. A change with a scope but zero matched routes
    # has no UI footprint; skip the expensive phase with a pass.
    if change_scope and not scoped_routes:
        logger.info(
            "design-fidelity: scope matches no routes for %s — gate pass (no UI)",
            change_name,
        )
        return GateOutcome(status="pass", message="scope-no-ui-routes")

    outcome = GateOutcome(status="pass")
    outcome.checked_routes = [r.path for r in scoped_routes]
    diff_root = Path(wt_path) / "gate-results" / "design-fidelity"
    diff_root.mkdir(parents=True, exist_ok=True)
    outcome.diff_images_dir = diff_root

    try:
        with render_v0_with_fixtures(project_path / "v0-export", fixtures) as ref:
            ref_shots = _capture_screenshots(
                ref.base_url, manifest, diff_root / "_ref", routes=scoped_routes,
            )

            agent_url = _build_and_start_agent(wt_path)
            try:
                agent_shots = _capture_screenshots(
                    agent_url, manifest, diff_root / "_agent", routes=scoped_routes,
                )
            finally:
                _stop_agent_server()
    except ReferenceBuildError as e:
        raise _GateAbort("reference-build-failed", str(e)) from e

    # 4. Pixelmatch diff
    for route in scoped_routes:
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
    change_scope: str = "",
    base_routes: set[str] | None = None,
) -> list[SkeletonViolation]:
    """Structural check — runs BEFORE any build/screenshot.

    Scope-aware: missing-route violations are only flagged for routes matched
    to ``change_scope`` via manifest ``scope_keywords``. Each feature-type
    change only builds its own slice of the app; siblings' routes live in
    other worktrees and will be present only after those changes merge. If
    ``change_scope`` is empty or matches no routes, the route inventory
    check is skipped entirely (the change has no UI footprint by scope).
    """
    violations: list[SkeletonViolation] = []

    manifest_routes = {r.path for r in manifest.routes}
    deferred = _deferred_route_paths(manifest)
    agent_routes = _enumerate_agent_routes(agent_worktree)

    # Scope-matched routes = this change's own design footprint. When
    # change_scope is empty (e.g. non-orchestrated runs or legacy callers),
    # fall back to the full manifest so the check remains useful.
    if change_scope:
        expected_routes = {r.path for r in _scoped_routes(manifest, change_scope)}
    else:
        expected_routes = set(manifest_routes)
    # Deferred routes are authorised to diverge — drop them from the
    # expected set so they don't fire as missing-route violations.
    expected_routes -= deferred

    # Missing-route: only flag routes this change is supposed to build
    for p in expected_routes - agent_routes:
        violations.append(SkeletonViolation(
            "missing-route",
            f"route {p} exists in manifest but not in agent worktree",
        ))
    # Extra-route: agent has a route that's not in the manifest at all
    # (not the same as "belongs to a sibling change" — those ARE in manifest).
    # Routes listed in deferred_design_routes are exempt — they exist in the
    # app but have no v0-export counterpart (e.g. error pages, auth gates).
    # Routes inherited from the base commit (already on main) are also
    # exempt — the current agent cannot be held responsible for routes
    # foundation/auth/other siblings created. Without this, `/admin/login`,
    # `/bundles`, `/coffees`, `/equipment` etc. get flagged on every
    # subsequent UI change and flood the retry_context.
    inherited = base_routes or set()
    for p in agent_routes - manifest_routes - deferred - inherited:
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
            src_candidate = agent_worktree / "src" / rel
            if (
                not agent_candidate.is_dir()
                and not src_candidate.is_dir()
                and not _resolve_shared_alias(agent_worktree, rel, aliases)
            ):
                violations.append(SkeletonViolation(
                    "missing-shared-file",
                    f"shared directory {rel} absent in agent worktree",
                ))
        else:
            src_prefix = f"{v0_export.name}/"
            rel = Path(sh[len(src_prefix):]) if sh.startswith(src_prefix) else Path(sh)
            agent_candidate = agent_worktree / rel
            src_candidate = agent_worktree / "src" / rel
            if (
                not agent_candidate.is_file()
                and not src_candidate.is_file()
                and not _resolve_shared_alias(agent_worktree, rel, aliases)
            ):
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
            target = agent_worktree / "src" / rel
        if not target.is_file():
            continue
        if not _has_component_export(target):
            violations.append(SkeletonViolation(
                "decomposition-collapsed",
                f"{rel} exists but no default/named component export — may have been inlined",
            ))

    # design-binding-completeness: shell-shadow check — detect parallel
    # implementations of known shell components. Heuristic: the agent has a
    # file in src/components/ whose filename token-overlaps with a manifest
    # shell AND whose imports overlap with the shell's shadcn primitives.
    # Severity is WARN (not BLOCK) by default; operator can promote via
    # `gate_overrides.design-fidelity.shell_shadow_severity: critical`.
    violations.extend(_check_shell_shadow(agent_worktree, manifest, aliases, v0_export))

    # design-fidelity-shell-hardening: stricter shell mounting check — every
    # top-level v0 shell MUST be mounted at its canonical filename in
    # src/components/. Catches the "different-name shadow" pattern that
    # filename-token heuristics miss (e.g. `Navbar.tsx` shadowing
    # `site-header.tsx`) and the shadow-alias re-export trick that games
    # the skeleton check.
    violations.extend(_check_shell_mounting(agent_worktree, manifest, aliases, v0_export))

    # design-fidelity-shell-hardening: shadcn primitive parity — distinctive
    # primitives present in v0 (CommandDialog, Sheet, HoverCard, Combobox,
    # ...) must also be imported somewhere under src/. Catches the "agent
    # reinterpreted the UX pattern" failure mode (WARN severity).
    violations.extend(_check_shadcn_primitive_parity(agent_worktree, manifest, v0_export))

    # design-fidelity-jsx-parity: structural JSX comparison. Closes the
    # gap between "right primitives imported" and "right composition":
    # detects collapsed CommandGroups, swapped layout primitives
    # (space-y → grid-cols), and missing inner trigger contents
    # (HoverCardTrigger missing <Avatar>). All current statuses are
    # informational by default — operator can promote via
    # gate_overrides.design-fidelity once validated.
    violations.extend(_check_jsx_structural_parity(agent_worktree, v0_export))

    return violations


def _check_shell_shadow(
    agent_worktree: Path,
    manifest,
    aliases: dict,
    v0_export: Path,
) -> list[SkeletonViolation]:
    """Detect agent-created files that shadow existing manifest shells.

    Returns a list of `decomposition-shadow` violations (severity WARN).
    """
    out: list[SkeletonViolation] = []
    # Build a set of legitimate shell base-names (kebab-case identifiers)
    shell_basenames: dict[str, str] = {}  # base → original path
    for sh in manifest.shared:
        if not sh.endswith(".tsx"):
            continue
        base = sh.rsplit("/", 1)[-1][:-len(".tsx")]
        shell_basenames[base] = sh

    if not shell_basenames:
        return out

    # Scan agent's src/components/**/*.tsx
    agent_components_dir = agent_worktree / "src" / "components"
    if not agent_components_dir.is_dir():
        return out

    aliased_targets = set()
    if isinstance(aliases, dict):
        for k, v in aliases.items():
            aliased_targets.add(k)
            aliased_targets.add(v)

    for agent_file in agent_components_dir.rglob("*.tsx"):
        if "components/ui/" in str(agent_file):
            continue
        agent_base = agent_file.stem
        agent_rel = str(agent_file.relative_to(agent_worktree))

        # Skip if the agent file IS the shell (legitimate adoption)
        if agent_base in shell_basenames:
            continue
        # Skip if aliased (operator whitelisted)
        if any(agent_rel.endswith(a) for a in aliased_targets):
            continue

        # Heuristic 1: filename token-overlap
        agent_tokens = set(agent_base.split("-"))
        for shell_base, shell_path in shell_basenames.items():
            shell_tokens = set(shell_base.split("-"))
            if not agent_tokens & shell_tokens:
                continue
            # Heuristic 2: imports overlap (≥2 common shadcn primitives)
            try:
                agent_text = agent_file.read_text(encoding="utf-8", errors="replace")
                shell_full_path = v0_export.parent / shell_path
                if not shell_full_path.is_file():
                    # Try resolving relative to agent worktree's ancestor
                    shell_full_path = Path(shell_path)
                    if not shell_full_path.is_absolute():
                        shell_full_path = v0_export.parent / shell_path
                if not shell_full_path.is_file():
                    continue
                shell_text = shell_full_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            agent_imports = _extract_shadcn_imports(agent_text)
            shell_imports = _extract_shadcn_imports(shell_text)
            common = agent_imports & shell_imports
            if len(common) >= 2:
                out.append(SkeletonViolation(
                    "decomposition-shadow",
                    f"{agent_rel} appears to shadow {shell_path} "
                    f"(filename tokens {agent_tokens & shell_tokens}, "
                    f"shared imports {common}). "
                    f"Mount the existing component instead — see design-bridge.md.",
                ))
                break  # one shadow violation per agent file is enough

    return out


def _extract_shadcn_imports(text: str) -> set[str]:
    """Extract shadcn primitive names imported by a TSX file."""
    import re as _re
    out: set[str] = set()
    # Match `import { X, Y } from '@/components/ui/foo'`
    for m in _re.finditer(
        r"import\s+\{([^}]+)\}\s+from\s+['\"](?:@/|\.\.?/)*components/ui/[\w/-]+['\"]",
        text,
    ):
        names = m.group(1)
        for name in names.split(","):
            cleaned = name.strip().split(" as ")[0].strip()
            if cleaned:
                out.add(cleaned)
    return out


def _check_shell_mounting(
    agent_worktree: Path,
    manifest,
    aliases: dict,
    v0_export: Path,
) -> list[SkeletonViolation]:
    """Verify each top-level v0 shell is mounted under its canonical filename.

    For each `v0-export/components/<X>.tsx` (top-level only, excluding `ui/`):
      1. `src/components/<X>.tsx` MUST exist (CRITICAL `shell-not-mounted` if not).
      2. If it exists, it MUST NOT be a shadow alias — i.e. the file's only real
         content is `export const Foo = LocalSibling` re-exporting another
         agent-authored sibling file. That pattern games the skeleton check
         while bypassing the v0 design source. CRITICAL `shadow-alias`.

    Both new statuses are blocking. Operators can still waive a specific shell
    via `gate_overrides.design-fidelity.aliases` (already-existing path → path
    map): listing the v0 path as either key or value skips the mount check.
    """
    import re as _re
    out: list[SkeletonViolation] = []

    src_components = agent_worktree / "src" / "components"
    if not src_components.is_dir():
        # No src/components/ at all — earlier missing-shared-file check fires
        # for individual shells; don't double-report here.
        return out

    aliased_paths: set[str] = set()
    if isinstance(aliases, dict):
        for k, v in aliases.items():
            aliased_paths.add(k)
            aliased_paths.add(v)

    for shared_path in manifest.shared:
        if not shared_path.endswith(".tsx"):
            continue
        if "components/ui/" in shared_path:
            continue
        # Top-level shell only — `components/foo.tsx`, not `components/foo/bar.tsx`
        if "components/" not in shared_path:
            continue
        rel = shared_path.split("components/", 1)[1]
        if "/" in rel:
            continue

        if any(shared_path.endswith(a) for a in aliased_paths):
            continue
        base = rel[: -len(".tsx")]
        target = src_components / f"{base}.tsx"

        if not target.is_file():
            out.append(SkeletonViolation(
                "shell-not-mounted",
                f"v0 shell `{shared_path}` is not mounted at "
                f"`src/components/{base}.tsx`. Mount the v0 component there "
                f"directly, or re-export it: "
                f"`export {{ default }} from '@/v0-export/components/{base}'`. "
                f"If a different filename is intentional, add it to "
                f"`gate_overrides.design-fidelity.aliases` in orchestration config.",
            ))
            continue

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        if _is_shadow_alias(content):
            out.append(SkeletonViolation(
                "shadow-alias",
                f"`src/components/{base}.tsx` re-exports a sibling local file "
                f"instead of the v0 design source. This bypasses the v0 shell "
                f"`{shared_path}`. Either copy the v0 shell content here OR "
                f"re-export from `@/v0-export/components/{base}`. Aliasing to "
                f"a custom local file (e.g. `export const Foo = CustomBar`) "
                f"defeats the design-fidelity check.",
            ))
    return out


def _is_shadow_alias(content: str) -> bool:
    """Detect shadow alias pattern: a near-empty file whose only purpose is to
    re-export a sibling LOCAL file (not a v0-export import).

    Triggers on:
      - `export const Foo = LocalY` where Y is from `./Y` (sibling)
      - `export default LocalY` where Y is from `./Y` (sibling)
      - `export { Y as default }` where Y is from `./Y`
    AND the file has < 5 non-trivial lines (no real implementation).
    """
    import re as _re

    # Collect names imported from sibling local files (./X). Imports from
    # `@/v0-export/...` are LEGITIMATE — those are intentional v0 re-exports.
    sibling_names: set[str] = set()
    for m in _re.finditer(
        r"import\s+(?:\{([^}]+)\}|(\w+))\s+from\s+['\"]\.\/([\w-]+)['\"]",
        content,
    ):
        if m.group(2):
            sibling_names.add(m.group(2))
        elif m.group(1):
            for name in m.group(1).split(","):
                cleaned = name.strip().split(" as ")[0].strip()
                if cleaned:
                    sibling_names.add(cleaned)

    if not sibling_names:
        return False

    # Look for re-export of a sibling-imported name
    has_reexport = False
    for sib in sibling_names:
        sib_re = _re.escape(sib)
        if (
            _re.search(rf"export\s+(?:const|let|var|default)\s+\w+\s*=\s*{sib_re}\b", content)
            or _re.search(rf"export\s+default\s+{sib_re}\b", content)
            or _re.search(rf"export\s*\{{[^}}]*\b{sib_re}\b[^}}]*\}}", content)
        ):
            has_reexport = True
            break

    if not has_reexport:
        return False

    # Count "real" lines — anything that's not blank, comment, import, or export
    real_lines = 0
    for raw in content.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("//", "/*", "*", "*/")):
            continue
        if line.startswith("import "):
            continue
        if line.startswith("export "):
            continue
        real_lines += 1

    return real_lines < 5


def _check_shadcn_primitive_parity(
    agent_worktree: Path,
    manifest,
    v0_export: Path,
) -> list[SkeletonViolation]:
    """Detect distinctive shadcn primitives present in v0 shells but absent
    from the implementation.

    Catches the "agent reinterpreted the UX pattern" failure mode where v0
    uses `<CommandDialog>` and the implementation silently substitutes a
    `<Card>` dropdown. Severity is WARN — not all primitive substitutions
    are wrong (e.g. `Sheet` → `Drawer` for mobile may be valid design
    nuance), but every flagged miss is a divergence the operator should
    look at.
    """
    out: list[SkeletonViolation] = []

    # Collect distinctive primitives used across ALL v0 shell files (top-level
    # components and pages — anything in v0-export's app/ or top-level
    # components/ directories).
    v0_primitives: set[str] = set()
    v0_root = v0_export

    for shared_path in manifest.shared:
        if not shared_path.endswith(".tsx"):
            continue
        full = v0_root / shared_path.split("v0-export/", 1)[-1] if "v0-export/" in shared_path else None
        if full is None or not full.is_file():
            # Try resolving as relative path under the worktree
            cand = agent_worktree / shared_path
            if cand.is_file():
                full = cand
        if full is None or not full.is_file():
            continue
        try:
            text = full.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        v0_primitives |= (_extract_shadcn_imports(text) & _DISTINCTIVE_SHADCN_PRIMITIVES)

    # Also walk v0-export app/ pages (route entries are in manifest as routes,
    # but their files contain UX patterns we want to check)
    v0_app = v0_root / "app"
    if v0_app.is_dir():
        for f in v0_app.rglob("*.tsx"):
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            v0_primitives |= (_extract_shadcn_imports(text) & _DISTINCTIVE_SHADCN_PRIMITIVES)

    if not v0_primitives:
        return out

    # Walk implementation src/ for the same primitives
    src = agent_worktree / "src"
    if not src.is_dir():
        return out

    impl_primitives: set[str] = set()
    for f in src.rglob("*.tsx"):
        if "/components/ui/" in str(f):
            continue  # primitives' own definitions
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        impl_primitives |= _extract_shadcn_imports(text)

    missing = v0_primitives - impl_primitives
    for prim in sorted(missing):
        out.append(SkeletonViolation(
            "shadcn-primitive-missing",
            f"v0 design uses `<{prim}>` (a distinctive shadcn pattern) but "
            f"no file under `src/` imports it. This usually means the "
            f"implementation replaced the v0 UX pattern with a simpler "
            f"alternative (e.g. CommandDialog → plain dropdown, Sheet → "
            f"Dialog modal, HoverCard → Tooltip). If intentional, add "
            f"a waiver in proposal.md under "
            f"`design.primitive_waivers: [{prim}]` with the reason.",
        ))
    return out


# ───────────────────────────────────────────────────────────────────────
# JSX structural parity — checks that compose JSX into the same shape
# the v0 design uses, not just the same primitive imports.
#
# Layered with shell mounting and primitive parity, this completes the
# "structural design preservation" goal: the agent can refactor file
# layout (page.tsx → page.tsx + components/X.tsx) but the rendered tree
# must compose the same elements with the same layout semantics.
# ───────────────────────────────────────────────────────────────────────

# Layout-determining className tokens. Selected because changing them
# materially changes the page's visual rhythm:
#
#   grid / flex / block / hidden  → display mode
#   grid-cols-N / grid-rows-N     → column/row count (kept with version)
#   flex-col / flex-row / flex-wrap → flex direction
#   space-y / space-x / gap       → spacing rhythm (version stripped —
#                                   `space-y-4` ≈ `space-y-6` semantically)
#   items-* / justify-*           → cross-axis alignment
#
# Excluded: padding/margin, color, typography, border, shadow — those
# are tweaks, not structural decisions. The agent is allowed to tune them.
_LAYOUT_CLASS_RE = re.compile(
    r"\b("
    # Longer alternatives MUST come before shorter — regex alternation
    # is left-to-right, so `flex|flex-col` matches `flex` first when
    # given `flex-col`. Ordering by length-desc avoids that pitfall.
    r"items-(?:start|center|end|stretch|baseline)|"
    r"justify-(?:start|center|end|between|around|evenly)|"
    r"flex-nowrap|flex-wrap|"
    r"flex-col|flex-row|"
    r"grid-cols-\d+|grid-rows-\d+|"  # column/row counts kept
    r"space-y(?:-\d+)?|space-x(?:-\d+)?|gap(?:-\d+)?|"
    r"grid|flex|block|hidden"
    r")\b"
)
# Tokens we normalize by dropping the version (semantic equivalence).
_LAYOUT_NORMALIZE_PREFIXES = ("space-y", "space-x", "gap")


def _normalize_layout_token(tok: str) -> str:
    for prefix in _LAYOUT_NORMALIZE_PREFIXES:
        if tok == prefix or tok.startswith(prefix + "-"):
            return prefix
    return tok


# Trigger-style elements where the inner JSX matters: HoverCardTrigger
# inner <Avatar> is a recurring v0 idiom that agents drop. These
# anchors pair naturally with their content twin (HoverCardContent etc.)
# but for divergence detection we only need the trigger inner content —
# that's where the agent makes the visible compositional choice.
_ANCHOR_ELEMENTS = (
    "HoverCardTrigger",
    "PopoverTrigger",
    "SheetTrigger",
    "DialogTrigger",
    "DropdownMenuTrigger",
    "TooltipTrigger",
    "AccordionTrigger",
    "CollapsibleTrigger",
)


def _extract_jsx_signature(content: str) -> dict:
    """Build a structural fingerprint of a JSX/TSX file's render tree.

    Returns a dict with four axes:

    - ``element_counts``: ``{TagName: count}`` Counter for every
      ``<PascalCase>`` element. Lowercase HTML tags excluded.
    - ``layout_classes``: set of layout-determining className tokens
      (normalized — see ``_LAYOUT_CLASS_RE``). Catches "v0 uses
      ``space-y-6`` for a list, agent uses ``grid-cols-3``" drift.
    - ``command_group_headings``: set of ``CommandGroup heading="X"``
      values. Catches "v0 has Categories+Posts groups, agent has
      Categories only" drift.
    - ``anchor_inner``: ``{AnchorElement: {ChildTagName, ...}}`` for
      trigger-style elements. Catches "v0 puts ``<Avatar>`` inside
      ``HoverCardTrigger``, agent has nothing there" drift.
    """
    from collections import Counter as _Counter

    elements = re.findall(r"<([A-Z][\w]*)\b", content)
    element_counts = _Counter(elements)

    layout_classes: set[str] = set()
    for cn_match in re.finditer(
        r'className\s*=\s*["\'`{]([^"\'`}]*)["\'`}]', content,
    ):
        for tok in _LAYOUT_CLASS_RE.findall(cn_match.group(1)):
            layout_classes.add(_normalize_layout_token(tok))

    headings: set[str] = set()
    for h_match in re.finditer(
        r'<CommandGroup\b[^>]*\bheading\s*=\s*["\']([^"\']+)["\']', content,
    ):
        headings.add(h_match.group(1).strip())

    anchor_inner: dict[str, set[str]] = {}
    for anchor in _ANCHOR_ELEMENTS:
        # Match `<Anchor ...>...</Anchor>` non-greedily, multiline. We
        # don't try to handle nested same-name anchors (rare in practice
        # and would need a real parser to do correctly).
        pattern = rf"<{anchor}\b[^>]*>(.*?)</{anchor}>"
        children: set[str] = set()
        for block in re.findall(pattern, content, flags=re.DOTALL):
            children.update(re.findall(r"<([A-Z][\w]*)\b", block))
        if children:
            anchor_inner[anchor] = children

    return {
        "element_counts": element_counts,
        "layout_classes": layout_classes,
        "command_group_headings": headings,
        "anchor_inner": anchor_inner,
    }


def _aggregate_jsx_signatures(root: Path, scan_subdirs: tuple[str, ...]) -> dict:
    """Walk the given subdirectories under ``root`` and merge JSX
    signatures. Skips ``components/ui/`` (vendored shadcn primitives) and
    test files."""
    from collections import Counter as _Counter

    agg = {
        "element_counts": _Counter(),
        "layout_classes": set(),
        "command_group_headings": set(),
        "anchor_inner": {},
    }
    for subdir in scan_subdirs:
        sub = root / subdir
        if not sub.is_dir():
            continue
        for f in sub.rglob("*.tsx"):
            sf = str(f)
            if "/components/ui/" in sf:
                continue
            if (
                f.name.endswith(".spec.tsx")
                or f.name.endswith(".test.tsx")
                or "/tests/" in sf
                or "/__tests__/" in sf
            ):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            sig = _extract_jsx_signature(text)
            agg["element_counts"].update(sig["element_counts"])
            agg["layout_classes"].update(sig["layout_classes"])
            agg["command_group_headings"].update(sig["command_group_headings"])
            for anchor, children in sig["anchor_inner"].items():
                agg["anchor_inner"].setdefault(anchor, set()).update(children)
    return agg


def _check_jsx_structural_parity(
    agent_worktree: Path,
    v0_export: Path,
) -> list[SkeletonViolation]:
    """Compare the agent's rendered JSX shape to v0's, project-wide.

    The check is intentionally project-level rather than per-file: the
    agent is allowed to refactor (extract a `BlogList` from v0's inline
    page logic), but the *aggregate* element multiset, layout-class
    palette, CommandGroup heading set, and trigger-inner contents must
    align.

    Witnessed regressions this catches:

    - ``Categories+Posts`` CommandGroups → ``Categories`` only
    - v0 ``space-y-6`` post list → agent ``grid-cols-3`` post grid
    - v0 ``HoverCardTrigger`` containing ``<Avatar>`` → agent has none

    Severity: WARN by default (status names not in ``blocking_statuses``).
    Operator can promote via ``gate_overrides.design-fidelity`` in
    orchestration config once the check has been validated on a few runs.
    """
    out: list[SkeletonViolation] = []
    if not v0_export.is_dir():
        return out

    v0_sig = _aggregate_jsx_signatures(v0_export, ("app", "components"))
    agent_sig = _aggregate_jsx_signatures(agent_worktree / "src", ("app", "components"))

    # 1. CommandGroup heading divergence — clearest structural signal,
    #    near-zero false-positive rate (heading values are deliberate).
    missing_headings = v0_sig["command_group_headings"] - agent_sig["command_group_headings"]
    for heading in sorted(missing_headings):
        out.append(SkeletonViolation(
            "jsx-command-group-missing",
            f"v0 has `<CommandGroup heading=\"{heading}\">` somewhere but "
            f"no file under `src/` does. The agent likely collapsed two "
            f"CommandGroups into one, or replaced a Command-driven section "
            f"with plain markup. Mount the missing group with the same "
            f"heading text, or document the choice in `proposal.md` under "
            f"`design.command_group_waivers`.",
        ))

    # 2. Layout-class divergence — v0 has a layout token agent doesn't.
    #    Normalized tokens (space-y, gap) are equivalent across versions.
    missing_layout = v0_sig["layout_classes"] - agent_sig["layout_classes"]
    if missing_layout:
        out.append(SkeletonViolation(
            "jsx-layout-divergence",
            f"v0 uses layout class(es) {sorted(missing_layout)!r} in some "
            f"file under `v0-export/`, but no file under `src/` uses them. "
            f"Common drift: v0 stacks items with `space-y-N` for vertical "
            f"rhythm, agent rebuilds as `grid grid-cols-N`. Match v0's "
            f"layout primitive — list semantics differ from grid semantics "
            f"in screen reader output and responsive behavior.",
        ))

    # 3. Anchor-inner divergence — for each trigger element where v0
    #    has child elements that agent doesn't.
    for anchor, v0_children in sorted(v0_sig["anchor_inner"].items()):
        agent_children = agent_sig["anchor_inner"].get(anchor, set())
        missing = v0_children - agent_children
        # Filter out children that DO appear elsewhere — only flag when
        # the agent doesn't use them at all in any anchor of this type.
        # This avoids flagging cosmetic nesting differences.
        truly_missing = {
            c for c in missing
            if c not in agent_children
        }
        if truly_missing:
            out.append(SkeletonViolation(
                "jsx-anchor-inner-divergence",
                f"v0 puts {sorted(truly_missing)!r} inside `<{anchor}>` "
                f"(an idiomatic v0 pattern — e.g. `<Avatar>` next to a name "
                f"in `<HoverCardTrigger>` so the trigger is visually rich, "
                f"not just text). Agent's `<{anchor}>` blocks contain only "
                f"{sorted(agent_children)!r}. Mirror the v0 trigger "
                f"composition or document the simplification in "
                f"`proposal.md` under `design.anchor_simplifications`.",
            ))

    return out


def _enumerate_routes_at_ref(worktree: Path, ref: str) -> set[str]:
    """Return route set present at `ref` (typically merge-base with main).

    Uses `git ls-tree -r --name-only` to read the tree without touching
    the working directory. The normalisation (dropping `(group)` /
    `[locale]` segments) matches `_enumerate_agent_routes`.
    """
    import subprocess
    try:
        res = subprocess.run(
            ["git", "-C", str(worktree), "ls-tree", "-r", "--name-only", ref],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    if res.returncode != 0:
        return set()
    routes: set[str] = set()
    for line in res.stdout.splitlines():
        if not line.endswith("page.tsx"):
            continue
        # Strip leading app/ or src/app/ prefix
        parts = line.split("/")
        if parts and parts[0] == "src" and len(parts) > 1 and parts[1] == "app":
            segs = parts[2:-1]  # drop src/app and the page.tsx filename
        elif parts and parts[0] == "app":
            segs = parts[1:-1]
        else:
            continue
        segs = [
            s for s in segs
            if not (s.startswith("(") and s.endswith(")"))
            and s != "[locale]"
        ]
        routes.add("/" + "/".join(segs) if segs else "/")
    return routes


def _enumerate_agent_routes(agent: Path) -> set[str]:
    """Return set of route paths from app/**/page.tsx in agent worktree."""
    out: set[str] = set()
    for base in [agent / "app", agent / "src" / "app"]:
        if not base.is_dir():
            continue
        for page in base.rglob("page.tsx"):
            parts = list(page.relative_to(base).parts[:-1])
            parts = [
                p for p in parts
                if not (p.startswith("(") and p.endswith(")"))
                and p != "[locale]"
            ]
            out.add("/" + "/".join(parts) if parts else "/")
    return out


def _resolve_shared_alias(agent: Path, rel: Path, aliases: dict) -> bool:
    """Return True if rel has an alias that exists in agent worktree."""
    alias = aliases.get(rel.name) or aliases.get(str(rel))
    if not alias:
        return False
    return (agent / alias).exists() or (agent / rel.with_name(alias)).exists()


def _has_component_export(file: Path) -> bool:
    """Lightweight AST check — does the file produce any component export?

    Recognized forms:
      - export default …
      - export function/const/class/async function …
      - export { Name } from "…"          (re-export from another module)
      - export { Name as default } from "…" (default re-export)
      - export * from "…"                  (wildcard re-export)

    The re-export forms are documented in the design-bridge skill
    (`export { default } from '@/v0-export/components/<base>'`) and used
    by agents to mount v0 shells without inlining the implementation.
    """
    try:
        text = file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    pattern = re.compile(
        r"^\s*export\s+(?:"
        r"default|function|const|class|async\s+function"
        r"|\{[^}]*\}\s*from\s+['\"]"
        r"|\*\s*from\s+['\"]"
        r")",
        re.MULTILINE,
    )
    return bool(pattern.search(text))


# ─── Screenshot + pixel diff ─────────────────────────────────────────


def _capture_screenshots(
    base_url: str, manifest, output_root: Path,
    routes=None,
) -> dict[tuple[str, str], Path]:
    """Capture 3 viewports per route using Playwright-Python.

    ``routes`` (list of RouteEntry) overrides ``manifest.routes`` when
    provided — used to scope capture to the change's own design footprint.

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
            iter_routes = routes if routes is not None else manifest.routes
            for route in iter_routes:
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
    """Run pnpm install && pnpm build && pnpm start in agent worktree. Return base URL.

    If the verify gate already built the worktree (`.next/BUILD_ID` present),
    skip the install+build steps and reuse the existing build. This is both
    faster and avoids a class of false-positive "pnpm build failed" results
    where re-running install+build after a successful verify build produces
    a different outcome (stale caches, concurrent lockfile rewrites, etc.).
    """
    root = Path(wt_path)
    already_built = (root / ".next" / "BUILD_ID").is_file()
    if not already_built:
        r = subprocess.run(
            ["pnpm", "install", "--frozen-lockfile"], cwd=root,
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise _GateAbort(
                "agent-build-failed",
                f"pnpm install failed in agent worktree:\n{(r.stderr or r.stdout or '')[-2000:]}",
            )
        r = subprocess.run(
            ["pnpm", "build"], cwd=root,
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise _GateAbort(
                "agent-build-failed",
                f"pnpm build failed in agent worktree:\n{(r.stderr or r.stdout or '')[-2000:]}",
            )
    else:
        logger.info(
            "design-fidelity: reusing existing .next/ build in agent worktree "
            "(verify gate already built)"
        )

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
