"""Design source parser — extract structured design tokens from Figma Make exports.

Parses .make files (Figma Make export ZIP) into a structured DesignSystem
that can be rendered as design-system.md for the orchestration pipeline.

Usage:
    python3 -m set_orch.design_parser --input docs/design.make --spec-dir docs/
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# ─── Data Model ──────────────────────────────────────────────────────


@dataclass
class ComponentSpec:
    name: str
    properties: dict[str, str] = field(default_factory=dict)
    layout_notes: str = ""


@dataclass
class PageSection:
    name: str
    components: list[str] = field(default_factory=list)
    layout: str = ""


@dataclass
class PageSpec:
    name: str
    sections: list[PageSection] = field(default_factory=list)
    layout_description: str = ""


@dataclass
class ImageRef:
    context: str
    query: str


@dataclass
class DesignSystem:
    tokens: dict[str, dict[str, str]] = field(default_factory=dict)
    components: list[ComponentSpec] = field(default_factory=list)
    pages: list[PageSpec] = field(default_factory=list)
    images: list[ImageRef] = field(default_factory=list)
    fonts: list[str] = field(default_factory=list)
    raw_theme_css: str = ""

    def to_markdown(self) -> str:
        """Render as structured design-system.md."""
        lines: list[str] = ["# Design System", ""]

        # ── Tokens ──
        lines.append("## Design Tokens")
        lines.append("")
        for category, values in self.tokens.items():
            lines.append(f"### {category}")
            for name, value in values.items():
                lines.append(f"- `{name}`: `{value}`")
            lines.append("")

        # ── Fonts ──
        if self.fonts:
            lines.append("### Fonts")
            for f in self.fonts:
                lines.append(f"- {f}")
            lines.append("")

        # ── Components ──
        if self.components:
            lines.append("## Components")
            lines.append("")
            for comp in self.components:
                lines.append(f"### {comp.name}")
                if comp.properties:
                    for k, v in comp.properties.items():
                        lines.append(f"- **{k}**: {v}")
                if comp.layout_notes:
                    lines.append(f"- Layout: {comp.layout_notes}")
                lines.append("")

        # ── Pages ──
        if self.pages:
            lines.append("## Page Layouts")
            lines.append("")
            for page in self.pages:
                lines.append(f"### {page.name}")
                if page.layout_description:
                    lines.append(f"{page.layout_description}")
                    lines.append("")
                if page.sections:
                    for sec in page.sections:
                        components = ", ".join(sec.components) if sec.components else ""
                        layout_info = f" — {sec.layout}" if sec.layout else ""
                        comp_info = f" (uses: {components})" if components else ""
                        lines.append(f"- **{sec.name}**{layout_info}{comp_info}")
                lines.append("")

        # ── Images ──
        if self.images:
            lines.append("## Image References")
            lines.append("")
            for img in self.images:
                lines.append(f"- **{img.context}**: search \"{img.query}\"")
            lines.append("")

        # ── Raw Theme CSS ──
        if self.raw_theme_css:
            lines.append("## Raw Theme CSS")
            lines.append("")
            lines.append("```css")
            lines.append(self.raw_theme_css.strip())
            lines.append("```")
            lines.append("")

        return "\n".join(lines)


# ─── Parser ABC ──────────────────────────────────────────────────────


class DesignParser(ABC):
    """Base class for design source parsers."""

    @classmethod
    @abstractmethod
    def detect(cls, path: str) -> bool:
        """Return True if this parser can handle the given file."""

    @abstractmethod
    def parse(self, path: str) -> DesignSystem:
        """Parse the design source into a DesignSystem."""


# ─── Make Parser ─────────────────────────────────────────────────────


class MakeParser(DesignParser):
    """Parse Figma Make .make export files."""

    @classmethod
    def detect(cls, path: str) -> bool:
        if not path.endswith(".make"):
            return False
        return zipfile.is_zipfile(path)

    def parse(self, path: str) -> DesignSystem:
        ds = DesignSystem()

        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(tmp)

            chat_path = os.path.join(tmp, "ai_chat.json")
            if not os.path.isfile(chat_path):
                logger.warning("No ai_chat.json in .make file")
                return ds

            with open(chat_path, encoding="utf-8") as f:
                chat = json.load(f)

            # Extract write_tool calls
            writes: dict[str, str] = {}  # path -> content
            unsplash_queries: list[str] = []

            for thread in chat.get("threads", []):
                for msg in thread.get("messages", []):
                    for part in msg.get("parts", []):
                        if part.get("partType") != "tool-call-json-DO-NOT-USE-IN-PROD":
                            continue
                        try:
                            call = json.loads(part.get("contentJson", "{}"))
                            tool = call.get("toolName", "")
                            args = json.loads(call.get("argsJson", "{}"))
                        except (json.JSONDecodeError, TypeError):
                            continue

                        if tool == "write_tool":
                            file_path = args.get("path", "")
                            content = args.get("file_text", "")
                            if file_path and content:
                                writes[file_path] = content

                        elif tool == "unsplash_tool":
                            query = args.get("query", "")
                            if query:
                                unsplash_queries.append(query)

            logger.info("Extracted %d files and %d image queries from .make",
                        len(writes), len(unsplash_queries))

            # Parse tokens from theme/style files
            self._extract_tokens(writes, ds)

            # Parse fonts
            self._extract_fonts(writes, ds)

            # Parse components
            self._extract_components(writes, ds)

            # Parse pages
            self._extract_pages(writes, ds)

            # Parse images
            self._extract_images(unsplash_queries, writes, ds)

        return ds

    def _extract_tokens(self, writes: dict[str, str], ds: DesignSystem) -> None:
        """Extract CSS custom properties from theme/style files."""
        theme_content = ""
        for path, content in writes.items():
            if "theme" in path.lower() or "variables" in path.lower():
                theme_content = content
                break

        if not theme_content:
            # Try any CSS file with custom properties
            for path, content in writes.items():
                if path.endswith(".css") and "--color-" in content:
                    theme_content = content
                    break

        if not theme_content:
            return

        ds.raw_theme_css = theme_content

        # Parse CSS custom properties — keep first concrete value per name
        # (`:root` block has real hex values, `@theme inline` has var() self-refs)
        concrete: dict[str, str] = {}
        var_ref_re = re.compile(r"var\(--([a-zA-Z0-9_-]+)\)")
        prop_re = re.compile(r"--([a-zA-Z0-9_-]+)\s*:\s*([^;]+);")

        for match in prop_re.finditer(theme_content):
            name, value = match.group(1).strip(), match.group(2).strip()
            # Only keep first concrete (non-var) value per property
            if not var_ref_re.match(value) and name not in concrete:
                concrete[name] = value

        resolved_props = concrete

        # Categorize
        colors: dict[str, str] = {}
        typography: dict[str, str] = {}
        spacing: dict[str, str] = {}
        radii: dict[str, str] = {}
        container: dict[str, str] = {}

        for name, value in resolved_props.items():

            if name.startswith("color-"):
                colors[name] = value
            elif name.startswith("font-"):
                typography[name] = value
            elif name.startswith("text-"):
                typography[name] = value
            elif name.startswith("spacing-"):
                spacing[name] = value
            elif name.startswith("radius-"):
                radii[name] = value
            elif name.startswith("container-"):
                container[name] = value

        if colors:
            ds.tokens["Colors"] = colors
        if typography:
            ds.tokens["Typography"] = typography
        if spacing:
            ds.tokens["Spacing"] = spacing
        if radii:
            ds.tokens["Border Radius"] = radii
        if container:
            ds.tokens["Container"] = container

    def _extract_fonts(self, writes: dict[str, str], ds: DesignSystem) -> None:
        """Extract Google Fonts imports."""
        font_re = re.compile(r"family=([A-Za-z+]+)")
        for path, content in writes.items():
            if "font" in path.lower() or "googleapis.com/css" in content:
                for m in font_re.finditer(content):
                    font_name = m.group(1).replace("+", " ")
                    if font_name not in ds.fonts:
                        ds.fonts.append(font_name)

    def _extract_components(self, writes: dict[str, str], ds: DesignSystem) -> None:
        """Extract component names and key properties from .tsx files."""
        for path, content in writes.items():
            if not path.endswith(".tsx"):
                continue
            basename = os.path.basename(path).replace(".tsx", "")
            dirname = os.path.dirname(path).lower()
            # Only component files — skip pages, layouts, routes
            is_page = ("pages" in dirname or
                       (dirname.endswith("/app") or "/app/" in dirname and "component" not in dirname))
            if is_page and "component" not in dirname:
                continue
            if basename in ("App", "Layout", "routes", "main"):
                continue

            comp = ComponentSpec(name=basename)

            # Extract key visual properties from JSX
            color_refs = set(re.findall(r"var\(--([a-z-]+)\)", content))
            if color_refs:
                comp.properties["colors"] = ", ".join(sorted(color_refs))

            # Detect layout type
            if "flex" in content.lower():
                comp.layout_notes = "flexbox"
            elif "grid" in content.lower():
                comp.layout_notes = "grid"

            ds.components.append(comp)

    def _extract_pages(self, writes: dict[str, str], ds: DesignSystem) -> None:
        """Extract page layouts from page .tsx files."""
        for path, content in writes.items():
            if not path.endswith(".tsx"):
                continue
            dirname = os.path.dirname(path).lower()
            # Only page files — skip components
            if "pages" not in dirname:
                continue
            basename = os.path.basename(path).replace(".tsx", "")
            if basename in ("App", "Layout", "routes", "main", "_app", "_document"):
                continue

            page = PageSpec(name=basename)

            # Find section comments or major component usage
            section_re = re.compile(r"/\*\*?\s*\n?\s*\*?\s*(.*?)\s*\*/|{/\*\s*(.*?)\s*\*/}", re.MULTILINE)
            for m in section_re.finditer(content):
                section_name = (m.group(1) or m.group(2) or "").strip()
                if section_name and len(section_name) < 60:
                    page.sections.append(PageSection(name=section_name))

            # Find imported components
            import_re = re.compile(r"import\s+.*?{?\s*(\w+)\s*}?\s+from\s+['\"].*components/(\w+)")
            used_components = []
            for m in import_re.finditer(content):
                used_components.append(m.group(2))
            if used_components:
                page.layout_description = f"Uses: {', '.join(used_components)}"

            ds.pages.append(page)

    def _extract_images(self, queries: list[str], writes: dict[str, str], ds: DesignSystem) -> None:
        """Extract image references from Unsplash queries."""
        # Try to associate queries with context based on order
        contexts = ["hero", "product", "product", "product", "product",
                     "delivery", "brewing", "roasting", "lifestyle"]
        for i, query in enumerate(queries):
            ctx = contexts[i] if i < len(contexts) else f"image-{i+1}"
            ds.images.append(ImageRef(context=ctx, query=query))


# ─── Passthrough Parser ──────────────────────────────────────────────


class PassthroughParser(DesignParser):
    """For .md files that are already structured design-system files."""

    @classmethod
    def detect(cls, path: str) -> bool:
        if not path.endswith(".md"):
            return False
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
            return "## Design Tokens" in content
        except OSError:
            return False

    def parse(self, path: str) -> DesignSystem:
        # Return a minimal DesignSystem with the raw content
        # The file is already in the right format
        ds = DesignSystem()
        ds.raw_theme_css = f"(passthrough from {path})"
        return ds


# ─── Factory ─────────────────────────────────────────────────────────


_PARSERS: list[type[DesignParser]] = [MakeParser, PassthroughParser]
SUPPORTED_FORMATS = [".make (Figma Make export)", ".md (with '## Design Tokens' section)"]


def get_parser(path: str) -> DesignParser:
    """Auto-detect format and return the appropriate parser."""
    for parser_cls in _PARSERS:
        if parser_cls.detect(path):
            return parser_cls()
    supported = ", ".join(SUPPORTED_FORMATS)
    raise ValueError(
        f"Unsupported design source format: {path}\n"
        f"Supported formats: {supported}"
    )


# ─── Spec Sync ───────────────────────────────────────────────────────

# Keyword → page name mapping for spec matching
_PAGE_KEYWORDS: dict[str, list[str]] = {
    "Homepage": ["homepage", "home", "landing", "főoldal", "main page", "hero"],
    "Catalog": ["catalog", "listing", "products", "product list", "kávék", "coffees", "shop"],
    "Product Detail": ["product detail", "product page", "pdp", "termék"],
    "Cart": ["cart", "basket", "kosár", "shopping cart"],
    "Checkout": ["checkout", "payment", "fizetés", "order", "rendelés"],
    "Admin": ["admin", "dashboard", "management", "kezelő"],
    "Auth": ["auth", "login", "register", "bejelentkezés", "regisztráció", "sign in", "sign up"],
    "Subscription": ["subscription", "előfizetés", "recurring"],
    "Stories": ["stories", "blog", "sztorik", "articles", "cikkek"],
    "Profile": ["profile", "account", "fiók", "settings", "beállítások"],
    "Search": ["search", "keresés", "filter", "szűrő"],
}


def sync_specs(design: DesignSystem, spec_dir: str, dry_run: bool = False) -> list[str]:
    """Inject ## Design Reference sections into spec files.

    Returns list of modified file paths.
    """
    modified: list[str] = []
    spec_path = Path(spec_dir)

    if not spec_path.is_dir():
        logger.warning("Spec dir does not exist: %s", spec_dir)
        return modified

    # Build page lookup from design system
    page_lookup: dict[str, PageSpec] = {}
    for page in design.pages:
        page_lookup[page.name] = page

    for md_file in sorted(spec_path.glob("**/*.md")):
        if md_file.name == "design-system.md":
            continue

        try:
            content = md_file.read_text(encoding="utf-8")
        except OSError:
            continue

        content_lower = content.lower()
        matched_pages: list[str] = []

        for page_name, keywords in _PAGE_KEYWORDS.items():
            for kw in keywords:
                if kw in content_lower:
                    if page_name not in matched_pages:
                        matched_pages.append(page_name)
                    break

        if not matched_pages:
            continue

        # Build design reference section
        ref_lines = ["## Design Reference", ""]
        ref_lines.append("Use exact values from `docs/design-system.md` — do NOT use framework defaults.")
        ref_lines.append("")

        # Add token summary
        if design.tokens.get("Colors"):
            colors = design.tokens["Colors"]
            primary = colors.get("color-primary", colors.get("primary", ""))
            secondary = colors.get("color-secondary", colors.get("secondary", ""))
            bg = colors.get("color-background", colors.get("background", ""))
            if primary or secondary:
                ref_lines.append(f"**Key colors**: primary `{primary}`, secondary `{secondary}`, background `{bg}`")

        if design.fonts:
            ref_lines.append(f"**Fonts**: {', '.join(design.fonts)}")

        ref_lines.append("")
        ref_lines.append("**Matched pages:**")
        for pname in matched_pages:
            page = page_lookup.get(pname)
            if page and page.layout_description:
                ref_lines.append(f"- **{pname}**: {page.layout_description}")
            else:
                ref_lines.append(f"- **{pname}**: see design-system.md § Page Layouts")

        ref_lines.append("")

        ref_block = "\n".join(ref_lines)

        # Replace existing Design Reference or append
        design_ref_re = re.compile(
            r"## Design Reference\n.*?(?=\n## |\Z)",
            re.DOTALL,
        )
        if design_ref_re.search(content):
            new_content = design_ref_re.sub(ref_block, content)
        else:
            new_content = content.rstrip() + "\n\n" + ref_block + "\n"

        if new_content != content:
            if not dry_run:
                md_file.write_text(new_content, encoding="utf-8")
            modified.append(str(md_file))
            logger.info("Updated design reference in %s (pages: %s)", md_file, ", ".join(matched_pages))

    return modified


# ─── Config Update ───────────────────────────────────────────────────


def update_orchestration_config(design_system_path: str) -> bool:
    """Set design_file in orchestration config."""
    config_paths = [
        "set/orchestration/config.yaml",
        ".claude/orchestration.yaml",
    ]
    for cp in config_paths:
        if os.path.isfile(cp):
            try:
                content = Path(cp).read_text(encoding="utf-8")
                if "design_file:" in content:
                    content = re.sub(
                        r"design_file:.*",
                        f"design_file: {design_system_path}",
                        content,
                    )
                else:
                    content = content.rstrip() + f"\ndesign_file: {design_system_path}\n"
                Path(cp).write_text(content, encoding="utf-8")
                logger.info("Updated design_file in %s", cp)
                return True
            except OSError:
                continue
    return False


# ─── CLI Entry Point ─────────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse design sources and sync with spec files",
        prog="set-design-sync",
    )
    parser.add_argument("--input", required=True, help="Path to design source (.make file or .md)")
    parser.add_argument("--spec-dir", required=True, help="Directory containing spec .md files to update")
    parser.add_argument("--output", help="Path for generated design-system.md (default: same dir as input)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    parser.add_argument("--format", choices=["make", "md", "auto"], default="auto", help="Force input format")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Validate input
    if not os.path.isfile(args.input):
        print(f"Error: input file not found: {args.input}")
        raise SystemExit(1)

    if not os.path.isdir(args.spec_dir):
        print(f"Error: spec directory not found: {args.spec_dir}")
        raise SystemExit(1)

    # Parse
    try:
        design_parser = get_parser(args.input)
    except ValueError as e:
        print(f"Error: {e}")
        raise SystemExit(1)

    print(f"Parsing: {args.input} ({type(design_parser).__name__})")
    design = design_parser.parse(args.input)

    # Render design-system.md
    output_dir = os.path.dirname(args.output or args.input)
    output_path = args.output or os.path.join(output_dir, "design-system.md")

    md_content = design.to_markdown()
    line_count = len(md_content.split("\n"))

    if args.dry_run:
        print(f"\n[dry-run] Would write {output_path} ({line_count} lines)")
        print(md_content[:500] + "...")
    else:
        Path(output_path).write_text(md_content, encoding="utf-8")
        print(f"Generated: {output_path} ({line_count} lines)")

    # Sync specs
    print(f"\nScanning specs in: {args.spec_dir}")
    modified = sync_specs(design, args.spec_dir, dry_run=args.dry_run)

    if modified:
        prefix = "[dry-run] Would update" if args.dry_run else "Updated"
        for f in modified:
            print(f"  {prefix}: {f}")
    else:
        print("  No specs matched design pages")

    # Update config
    if not args.dry_run:
        rel_path = os.path.relpath(output_path)
        if update_orchestration_config(rel_path):
            print(f"\nConfig: design_file set to {rel_path}")

    # Summary
    print(f"\nSummary:")
    print(f"  Tokens: {sum(len(v) for v in design.tokens.values())} properties")
    print(f"  Components: {len(design.components)}")
    print(f"  Pages: {len(design.pages)}")
    print(f"  Images: {len(design.images)}")
    print(f"  Fonts: {', '.join(design.fonts) if design.fonts else 'none detected'}")
    print(f"  Specs updated: {len(modified)}")


if __name__ == "__main__":
    main()
