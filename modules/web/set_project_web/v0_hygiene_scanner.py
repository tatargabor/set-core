"""Design source hygiene scanner — 9 quality rules for TSX-based design sources.

Detects common antipatterns that propagate from the design source into
consumer runs. Used by `set-design-hygiene` CLI and the `--with-hygiene`
flag on `set-design-import`. Findings are severity-tiered (CRITICAL/WARN/INFO).

Source-agnostic at the rule level — the rules apply to any TSX-producing
design tool. Implementation lives in the web module because rules are
TSX-specific (regex over .tsx files).

Designed for incremental adoption: rules are independent. Adding a 10th
rule does not require changes to the harness; it adds a function.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from pathlib import Path
from typing import Optional

from set_orch.design_manifest import (
    HygieneFinding,
    HygieneSeverity,
    Manifest,
)

logger = logging.getLogger(__name__)


# ─── Public entry point ─────────────────────────────────────────────


def scan_v0_export(
    v0_root: Path,
    *,
    manifest: Optional[Manifest] = None,
) -> list[HygieneFinding]:
    """Run all 9 hygiene rules against a v0-export tree.

    Args:
        v0_root: Path to the v0-export/ directory.
        manifest: Optional Manifest for route-integrity rule (Rule 8).
                  When None, that rule is skipped.

    Returns:
        Flat list of HygieneFinding entries, sorted by (severity, file, line).
    """
    findings: list[HygieneFinding] = []
    if not v0_root.is_dir():
        logger.warning("hygiene scan: %s is not a directory", v0_root)
        return findings

    tsx_files = sorted(v0_root.rglob("*.tsx"))

    for tsx in tsx_files:
        # Skip components/ui/ shadcn primitives — they're library code, not
        # the project's design surface.
        if "components/ui/" in str(tsx):
            continue
        # Skip node_modules / .next / dist — third-party + build artifacts.
        path_str = str(tsx)
        if "/node_modules/" in path_str or "/.next/" in path_str or "/dist/" in path_str:
            continue
        try:
            text = tsx.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("could not read %s: %s", tsx, e)
            continue
        rel = str(tsx.relative_to(v0_root))
        findings.extend(_rule_1_mock_arrays(rel, text))
        findings.extend(_rule_2_hardcoded_strings(rel, text))
        findings.extend(_rule_3_placeholder_handlers(rel, text))
        findings.extend(_rule_5_mock_urls(rel, text))
        findings.extend(_rule_6_inline_lambdas(rel, text))
        findings.extend(_rule_7_any_types(rel, text))
        if manifest is not None:
            findings.extend(_rule_8_route_integrity(rel, text, manifest))
            findings.extend(_rule_9_locale_inconsistency(rel, text, manifest))

    # Cross-file rules
    findings.extend(_rule_4_shell_inconsistency(v0_root))

    findings.sort(
        key=lambda f: (
            ["critical", "warn", "info"].index(f.severity.value),
            f.file,
            f.line,
        )
    )
    return findings


# ─── Rule 1: MOCK arrays inline ────────────────────────────────────


_MOCK_RE = re.compile(
    r"^\s*const\s+(MOCK_\w+|FAKE_\w+|STUB_\w+)\s*=\s*\[",
    re.MULTILINE,
)


def _rule_1_mock_arrays(rel: str, text: str) -> list[HygieneFinding]:
    out = []
    for m in _MOCK_RE.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        var = m.group(1)
        out.append(HygieneFinding(
            rule="mock-arrays-inline",
            severity=HygieneSeverity.CRITICAL,
            file=rel, line=line,
            message=f"Mock data array `{var}` declared inline in component body",
            suggested_fix="Replace with prop-based data injection (e.g. `results?: T[]` prop)",
        ))
    return out


# ─── Rule 2: Hardcoded UI strings ──────────────────────────────────


# Strings of ≥3 alphabetic chars inside JSX bodies (between `>` and `<`).
# Excludes attribute values, comments, and strings inside `aria-*`/`data-*`.
# Heuristic: matches `>SomeText<` with text containing letters only.
_JSX_BODY_STRING_RE = re.compile(
    r">\s*([A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű][A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű\s]{2,}?)\s*<",
)


def _rule_2_hardcoded_strings(rel: str, text: str) -> list[HygieneFinding]:
    """Hardcoded UI strings in JSX bodies.

    Severity is INFO (not WARN) because v0-design sources are HU-only
    canonical previews by convention — the consumer agent transforms HU
    literals into i18n catalog calls at implementation time. The literal
    is the "source of truth" for the HU translation and is expected.

    This rule still flags so operators can audit i18n coverage, but does
    not block import or run.
    """
    out = []
    for m in _JSX_BODY_STRING_RE.finditer(text):
        # Skip if inside an attribute (heuristic: previous char before `>`
        # would be a quote or bracket — too brittle to fully validate via regex)
        snippet = m.group(1).strip()
        if len(snippet) < 3:
            continue
        # Skip common harmless-looking JSX content (single words like 'a', 'br')
        if snippet.lower() in {"true", "false", "null", "undefined"}:
            continue
        line = text.count("\n", 0, m.start()) + 1
        out.append(HygieneFinding(
            rule="hardcoded-ui-strings",
            severity=HygieneSeverity.INFO,
            file=rel, line=line,
            message=f"Hardcoded UI string in JSX body: {snippet[:40]!r}",
            suggested_fix=(
                "Expected in v0-design HU canonical preview — consumer "
                "transforms via i18n catalog (`t('key')`). Audit only if "
                "v0 needs design-time multi-locale rendering."
            ),
        ))
    # Cap noise: report at most 5 per file.
    return out[:5]


# ─── Rule 3: Placeholder action handlers ────────────────────────────


_PLACEHOLDER_HANDLER_RE = re.compile(
    r"on[A-Z]\w*\s*=\s*\([^)]*\)\s*=>\s*\{[^}]*?(?://\s*(?:TODO|FIXME|implement|Add\s+\w+\s+logic))",
    re.IGNORECASE | re.DOTALL,
)


def _rule_3_placeholder_handlers(rel: str, text: str) -> list[HygieneFinding]:
    out = []
    for m in _PLACEHOLDER_HANDLER_RE.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        out.append(HygieneFinding(
            rule="placeholder-action-handler",
            severity=HygieneSeverity.WARN,
            file=rel, line=line,
            message="Action handler contains placeholder comment (TODO/FIXME/implement)",
            suggested_fix="Replace with a prop callback (e.g. `onClick?: () => void`)",
        ))
    return out


# ─── Rule 4: Inconsistent shell adoption (cross-file) ───────────────


_SHELL_IMPORT_RE = re.compile(
    r"""from\s+['"](?:@/|\.\.?/)*components/(site-header|site-footer)['"]""",
)


def _rule_4_shell_inconsistency(v0_root: Path) -> list[HygieneFinding]:
    out = []
    app_dir = v0_root / "app"
    if not app_dir.is_dir():
        return out

    page_files = list(app_dir.rglob("page.tsx"))
    if len(page_files) < 4:
        return out  # too few pages to draw a conclusion

    for shell_name in ("site-header", "site-footer"):
        importing = []
        not_importing = []
        for page in page_files:
            try:
                content = page.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = str(page.relative_to(v0_root))
            # Pages under (group)/ are typically layout-shell scoped — for
            # the rule we still flag inconsistency since v0 may have
            # mismatched imports across them.
            has = bool(re.search(
                rf"from\s+['\"](?:@/|\.\.?/)*components/{shell_name}['\"]",
                content,
            ))
            (importing if has else not_importing).append(rel)
        total = len(importing) + len(not_importing)
        if total == 0:
            continue
        ratio = len(importing) / total
        if 0.3 <= ratio <= 0.7:
            # Genuinely split — likely intentional (some pages have shell, some don't)
            continue
        if ratio >= 0.7 and not_importing:
            # Most pages have it; the few without are inconsistent
            out.append(HygieneFinding(
                rule="inconsistent-shell-adoption",
                severity=HygieneSeverity.CRITICAL,
                file="app/",  # cross-file; no single file/line
                line=0,
                message=(
                    f"`{shell_name}.tsx` imported by {len(importing)}/{total} pages; "
                    f"missing from {len(not_importing)} pages: "
                    f"{', '.join(not_importing[:5])}"
                    + ("…" if len(not_importing) > 5 else "")
                ),
                suggested_fix=(
                    f"Move `<{_kebab_to_pascal(shell_name)} />` to `app/layout.tsx` "
                    "for global rendering, then remove per-page imports."
                ),
                extra={"missing_pages": not_importing},
            ))
    return out


def _kebab_to_pascal(name: str) -> str:
    return "".join(p.capitalize() for p in name.split("-"))


# ─── Rule 5: Mock URL images ───────────────────────────────────────


_MOCK_URL_RE = re.compile(
    r"""src=\s*[{"']\s*['"`]?(https?://(?:images\.)?(?:unsplash\.com|picsum\.photos|placeholder\.com|placehold\.co)[^"'`}]+)""",
)


def _rule_5_mock_urls(rel: str, text: str) -> list[HygieneFinding]:
    out = []
    for m in _MOCK_URL_RE.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        url = m.group(1)
        out.append(HygieneFinding(
            rule="mock-url-images",
            severity=HygieneSeverity.INFO,
            file=rel, line=line,
            message=f"Placeholder image URL: {url[:60]}",
            suggested_fix="Replace with prop `src` or local /public/ asset",
        ))
    return out


# ─── Rule 6: Inline lambda action handlers ──────────────────────────


# Match onX={(...) => { ... }} where the body is multi-line
_INLINE_LAMBDA_RE = re.compile(
    r"on[A-Z]\w*\s*=\s*\{?\s*\([^)]*\)\s*=>\s*\{",
)


def _rule_6_inline_lambdas(rel: str, text: str) -> list[HygieneFinding]:
    out = []
    for m in _INLINE_LAMBDA_RE.finditer(text):
        # Find matching closing brace
        depth = 0
        end = m.end() - 1
        body_lines = 0
        for i in range(m.end() - 1, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
            elif ch == "\n":
                body_lines += 1
        if body_lines >= 3:
            line = text.count("\n", 0, m.start()) + 1
            out.append(HygieneFinding(
                rule="inline-lambda-handler",
                severity=HygieneSeverity.INFO,
                file=rel, line=line,
                message=f"Inline lambda handler with {body_lines}+ line body",
                suggested_fix="Extract to a prop callback or named function",
            ))
    return out[:3]  # cap noise


# ─── Rule 7: TypeScript `any` usage ─────────────────────────────────


_ANY_TYPE_RE = re.compile(
    r"(?<![A-Za-z_])(?::\s*any\b|as\s+any\b)",
)


def _rule_7_any_types(rel: str, text: str) -> list[HygieneFinding]:
    out = []
    for m in _ANY_TYPE_RE.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        out.append(HygieneFinding(
            rule="any-type-usage",
            severity=HygieneSeverity.WARN,
            file=rel, line=line,
            message="TypeScript `any` type used (loses type safety)",
            suggested_fix="Replace with a specific type or `unknown` if truly opaque",
        ))
    return out[:3]


# ─── Rule 8: Broken route references ────────────────────────────────


_LINK_HREF_RE = re.compile(
    r"""<Link\s+[^>]*?href\s*=\s*['"]([^'"`{]+)['"]""",
)
_ROUTE_PUSH_RE = re.compile(
    r"""(?:router\.push|router\.replace|redirect)\s*\(\s*['"]([^'"`]+)['"]""",
)


def _rule_8_route_integrity(rel: str, text: str, manifest: Manifest) -> list[HygieneFinding]:
    out = []
    if not manifest or not manifest.routes:
        return out
    known_paths = {r.path for r in manifest.routes}

    def _extract_route(s: str) -> Optional[str]:
        # Drop query/hash fragments
        s = s.split("?")[0].split("#")[0].rstrip("/")
        if not s.startswith("/"):
            return None
        return s if s else "/"

    def _check(href: str, line: int, kind: str):
        path = _extract_route(href)
        if path is None:
            return  # external URL or template literal — skip
        # Normalize: strip dynamic segments like /kavek/[slug] for comparison
        # (manifest already includes [slug] form, so direct equality only
        # matches non-dynamic paths). For dynamic paths in manifest, also
        # check prefix match.
        if path in known_paths:
            return
        prefix_match = any(
            kp.split("/[")[0] == path.split("/[")[0]
            for kp in known_paths
            if "[" in kp
        )
        if prefix_match:
            return
        # Find closest match for suggestion
        suggestions = sorted(
            known_paths,
            key=lambda p: _path_distance(p, path),
        )[:2]
        out.append(HygieneFinding(
            rule="broken-route-reference",
            severity=HygieneSeverity.CRITICAL,
            file=rel, line=line,
            message=f"{kind} references unknown route `{path}`",
            suggested_fix=f"Did you mean: {', '.join(suggestions)}",
            extra={"href": href, "kind": kind},
        ))

    for m in _LINK_HREF_RE.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        _check(m.group(1), line, "Link href")
    for m in _ROUTE_PUSH_RE.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        _check(m.group(1), line, "router.push/redirect")

    return out


def _path_distance(a: str, b: str) -> int:
    """Simple Levenshtein distance (small inputs, no need for a library)."""
    if not a or not b:
        return max(len(a), len(b))
    if a == b:
        return 0
    m = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        m[i][0] = i
    for j in range(len(b) + 1):
        m[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            m[i][j] = min(m[i - 1][j] + 1, m[i][j - 1] + 1, m[i - 1][j - 1] + cost)
    return m[len(a)][len(b)]


# ─── Rule 9: Locale-prefix inconsistency ────────────────────────────


# Hungarian path slug heuristic — common HU words used by v0 sources.
_HU_PATH_TOKENS = {"kavek", "kereses", "kosar", "belepes", "regisztracio",
                   "fiokom", "elofizetes", "sztorik", "csomagok", "eszkozok",
                   "penztar", "rendeleseink", "jelszo-csere", "adatvedelem",
                   "aszf", "rolunk", "kapcsolat", "szallitas", "merch"}
_EN_PATH_TOKENS = {"coffees", "search", "cart", "login", "signup", "register",
                   "account", "subscription", "stories", "bundles", "tools",
                   "checkout", "orders", "password-reset", "privacy", "terms",
                   "about", "contact", "shipping"}


def _rule_9_locale_inconsistency(rel: str, text: str, manifest: Manifest) -> list[HygieneFinding]:
    out = []
    # Determine project's primary locale slug from manifest routes
    has_hu = any(any(tok in r.path for tok in _HU_PATH_TOKENS) for r in manifest.routes)
    has_en = any(any(tok in r.path for tok in _EN_PATH_TOKENS) for r in manifest.routes)
    if not has_hu and not has_en:
        return out
    # If only HU paths in manifest and we see EN tokens in this file's hrefs → flag
    primary_hu = has_hu and not has_en
    primary_en = has_en and not has_hu
    if not (primary_hu or primary_en):
        return out
    foreign_tokens = _EN_PATH_TOKENS if primary_hu else _HU_PATH_TOKENS

    for m in _LINK_HREF_RE.finditer(text):
        href = m.group(1)
        if not href.startswith("/"):
            continue
        # Strip locale prefix (e.g. /en/foo)
        path_segs = [s for s in href.split("/") if s]
        if not path_segs:
            continue
        first = path_segs[0]
        if first in foreign_tokens or (len(path_segs) > 1 and path_segs[1] in foreign_tokens):
            line = text.count("\n", 0, m.start()) + 1
            out.append(HygieneFinding(
                rule="locale-prefix-inconsistency",
                severity=HygieneSeverity.WARN,
                file=rel, line=line,
                message=f"{'HU' if primary_hu else 'EN'} project links to "
                        f"foreign-locale path: {href}",
                suggested_fix="Use the project's primary locale path or add a route alias",
            ))
    return out[:3]


# ─── Markdown checklist generator ──────────────────────────────────


def render_checklist(
    findings: list[HygieneFinding],
    *,
    project_id: str = "",
    source_dir: str = "v0-export/",
) -> str:
    """Render findings as a markdown checklist file.

    Severity tiers in fixed order: CRITICAL → WARN → INFO. Each finding
    becomes a `- [ ]` checkbox so operator can tick off items as they fix.
    """
    from datetime import datetime, timezone

    by_sev: dict[HygieneSeverity, list[HygieneFinding]] = {
        HygieneSeverity.CRITICAL: [],
        HygieneSeverity.WARN: [],
        HygieneSeverity.INFO: [],
    }
    for f in findings:
        by_sev[f.severity].append(f)

    crit_count = len(by_sev[HygieneSeverity.CRITICAL])
    warn_count = len(by_sev[HygieneSeverity.WARN])
    info_count = len(by_sev[HygieneSeverity.INFO])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = []
    title = f"# Design Source Hygiene"
    if project_id:
        title += f" — {project_id}"
    lines.append(title)
    lines.append("")
    lines.append(f"Auto-generated by `set-design-hygiene` from `{source_dir}` on {now}.")
    lines.append(f"{len(findings)} findings: "
                 f"{crit_count} CRITICAL, {warn_count} WARN, {info_count} INFO.")
    lines.append("")

    for sev_label, sev in [
        ("CRITICAL (blocks design adoption)", HygieneSeverity.CRITICAL),
        ("WARN (degrades agent quality)", HygieneSeverity.WARN),
        ("INFO (potential cleanup)", HygieneSeverity.INFO),
    ]:
        items = by_sev[sev]
        lines.append(f"## {sev_label}")
        lines.append("")
        if not items:
            lines.append("_No findings at this severity._")
            lines.append("")
            continue
        for f in items:
            loc = f"{f.file}:{f.line}" if f.line > 0 else f.file
            lines.append(f"- [ ] **{f.rule}** — `{loc}`")
            lines.append(f"      {f.message}")
            if f.suggested_fix:
                lines.append(f"      _Fix:_ {f.suggested_fix}")
            lines.append("")
    return "\n".join(lines)
