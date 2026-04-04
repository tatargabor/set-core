"""Design source parser — extract structured design tokens from design sources.

Parses .make files (Figma Make export ZIP), figma.md (Figma Make prompt
collections), and existing .md design files into a structured DesignSystem
that can be rendered as design-system.md and design-brief.md for the
orchestration pipeline.

Usage:
    python3 -m set_orch.design_parser --input docs/design.make --spec-dir docs/
    python3 -m set_orch.design_parser --input docs/figma.md --spec-dir docs/
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
    visual_description: str = ""  # Rich visual description from design brief


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

    def to_brief_markdown(self) -> str:
        """Render as design-brief.md with per-page visual descriptions.

        Unlike to_markdown() which outputs tokens + component index (lean),
        this outputs rich visual descriptions per page for agent dispatch.
        """
        lines: list[str] = ["# Design Brief", ""]
        lines.append("Per-page visual specifications for implementing agents.")
        lines.append("Each page section describes layout, components, and responsive behavior.")
        lines.append("")

        pages_with_visuals = [p for p in self.pages if p.visual_description]
        if not pages_with_visuals:
            return ""

        for page in pages_with_visuals:
            lines.append(f"## Page: {page.name}")
            lines.append("")
            lines.append(page.visual_description.strip())
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
        """Extract component specs from design-spec.md and .tsx files.

        Priority: design-spec.md COMPONENTS section (pixel-precise specs)
        Fallback: TSX file analysis (color refs, layout type)
        """
        # Try to extract from design-spec.md first (richest source)
        spec_components = self._extract_spec_components(writes)

        for path, content in writes.items():
            if not path.endswith(".tsx"):
                continue
            basename = os.path.basename(path).replace(".tsx", "")
            dirname = os.path.dirname(path).lower()
            is_page = ("pages" in dirname or
                       (dirname.endswith("/app") or "/app/" in dirname and "component" not in dirname))
            if is_page and "component" not in dirname:
                continue
            if basename in ("App", "Layout", "routes", "main"):
                continue

            comp = ComponentSpec(name=basename)

            # Use spec description if available (pixel-precise)
            if basename in spec_components:
                comp.layout_notes = spec_components[basename]
            else:
                # Fallback: extract from TSX
                color_refs = set(re.findall(r"var\(--([a-z-]+)\)", content))
                if color_refs:
                    comp.properties["colors"] = ", ".join(sorted(color_refs))
                if "flex" in content.lower():
                    comp.layout_notes = "flexbox"
                elif "grid" in content.lower():
                    comp.layout_notes = "grid"

            ds.components.append(comp)

    @staticmethod
    def _extract_spec_components(writes: dict[str, str]) -> dict[str, str]:
        """Extract component descriptions from design-spec.md COMPONENTS section.

        Returns dict mapping component name → description text.
        """
        spec_content = ""
        for path, content in writes.items():
            if re.search(r"figma-design-spec\.md|design-spec\.md", path, re.IGNORECASE):
                spec_content = content

        if not spec_content:
            return {}

        comp_match = re.search(
            r"## 🔧 COMPONENTS(.*?)(?=\n## [📱📸♿📐🔄🎭🚀📦✅🎯💡📞📚]|\Z)",
            spec_content, re.DOTALL,
        )
        if not comp_match:
            return {}

        result: dict[str, str] = {}
        # Split by ### Component Name
        comp_re = re.compile(r"### (.+?)(?=\n### |\Z)", re.DOTALL)
        for m in comp_re.finditer(comp_match.group(1)):
            title = m.group(1).split("\n")[0].strip()
            body = m.group(0).strip()

            # Normalize title: "Button Component" → "Button"
            name = re.sub(r"\s+Component$", "", title).strip()

            # Extract code block content (the spec details)
            code_blocks = re.findall(r"```\n?(.*?)```", body, re.DOTALL)
            if code_blocks:
                result[name] = "\n---\n".join(code_blocks).strip()
            else:
                # Use raw body minus the title
                lines = body.split("\n")[1:]
                result[name] = "\n".join(lines).strip()

        return result

    def _extract_pages(self, writes: dict[str, str], ds: DesignSystem) -> None:
        """Extract page layouts and visual descriptions from .make sources.

        Combines three sources for visual descriptions (priority order):
        1. design-spec.md SCREEN LAYOUTS (pixel-precise Figma descriptions)
        2. design-system.json pages (structured sections with elements)
        3. TSX section comments + headings (fallback for uncovered pages)
        """
        # Source 1: design-spec.md SCREEN LAYOUTS (richest, pixel-precise)
        spec_screens = self._extract_screen_layouts(writes)

        # Source 2: design-system.json pages (structured sections)
        json_pages = self._extract_json_pages(writes)

        # Source 3: TSX page files
        for path, content in writes.items():
            if not path.endswith(".tsx"):
                continue
            dirname = os.path.dirname(path).lower()
            if "pages" not in dirname:
                continue
            basename = os.path.basename(path).replace(".tsx", "")
            if basename in ("App", "Layout", "routes", "main", "_app", "_document"):
                continue

            page = PageSpec(name=basename)

            # Find section comments
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

            # Build visual_description — priority: spec > json > tsx
            page.visual_description = self._build_visual_description(
                basename, content, json_pages.get(basename, {}),
                spec_screens,
            )

            ds.pages.append(page)

    @staticmethod
    def _extract_screen_layouts(writes: dict[str, str]) -> dict[str, str]:
        """Extract SCREEN LAYOUTS sections from design-spec.md in the .make.

        Returns dict mapping normalized page name → raw layout description.
        Takes the LAST version of the spec (in case of dark→light mode fix).
        """
        spec_content = ""
        for path, content in writes.items():
            if re.search(r"figma-design-spec\.md|design-spec\.md", path, re.IGNORECASE):
                spec_content = content  # last write wins

        if not spec_content:
            return {}

        # Find SCREEN LAYOUTS section
        screen_match = re.search(
            r"## 📱 SCREEN LAYOUTS(.*?)(?=\n## [^\n#]|\Z)",
            spec_content, re.DOTALL,
        )
        if not screen_match:
            return {}

        # Split by ### N. headings
        screens: dict[str, str] = {}
        section_re = re.compile(r"### \d+\.\s+(.+?)(?=\n### \d+\.|\Z)", re.DOTALL)
        for m in section_re.finditer(screen_match.group(1)):
            full = m.group(0).strip()
            title_line = m.group(1).split("\n")[0].strip()

            # Normalize title to page name
            title_lower = re.sub(r"\s*\(.*?\)", "", title_line).strip().lower()
            page_name = ""
            for pattern, name in _TITLE_TO_PAGE.items():
                if pattern in title_lower:
                    page_name = name
                    break
            if not page_name:
                # Fallback: capitalize first word
                words = title_lower.split()
                page_name = words[0].capitalize() if words else ""

            if page_name:
                # Extract the code block content (between ``` markers)
                code_blocks = re.findall(r"```\n?(.*?)```", full, re.DOTALL)
                if code_blocks:
                    screens[page_name] = "\n\n".join(code_blocks).strip()
                else:
                    # No code blocks — use the raw text after the title line
                    body = "\n".join(full.split("\n")[1:]).strip()
                    screens[page_name] = body

        return screens

    @staticmethod
    def _extract_json_pages(writes: dict[str, str]) -> dict[str, dict]:
        """Extract structured page data from design-system.json."""
        json_pages: dict = {}
        for p, c in writes.items():
            if "design-system.json" in p.lower():
                try:
                    json_pages = json.loads(c).get("pages", {})
                except (json.JSONDecodeError, AttributeError):
                    pass
                break

        # Map camelCase JSON keys to PascalCase page names
        json_key_map = {
            "home": "Home", "productCatalog": "ProductCatalog",
            "productDetail": "ProductDetail", "cart": "Cart",
            "checkout": "Checkout", "subscriptionWizard": "SubscriptionWizard",
            "userDashboard": "UserDashboard", "adminDashboard": "AdminDashboard",
            "auth": "Login",
        }
        result: dict[str, dict] = {}
        for jk, pn in json_key_map.items():
            if jk in json_pages and isinstance(json_pages[jk], dict):
                result[pn] = json_pages[jk]
        return result

    @staticmethod
    def _build_visual_description(
        page_name: str,
        tsx_content: str,
        json_page: dict,
        spec_screens: dict[str, str],
    ) -> str:
        """Build rich visual description from spec > json > tsx (priority)."""
        parts: list[str] = []

        # Priority 1: design-spec.md SCREEN LAYOUTS (pixel-precise)
        spec_desc = spec_screens.get(page_name, "")
        if spec_desc:
            parts.append(spec_desc)

        # Priority 2: design-system.json sections (structured elements)
        if not parts and json_page and isinstance(json_page, dict):
            for sect in json_page.get("sections", []):
                if not isinstance(sect, dict):
                    continue
                name = sect.get("name", "")
                header = f"**{name}**"
                if sect.get("height"):
                    header += f" ({sect['height']})"
                if sect.get("layout"):
                    header += f" — {sect['layout']}"
                if sect.get("background"):
                    header += f" — {sect['background']}"
                parts.append(header)
                for el in sect.get("elements", []):
                    parts.append(f"  - {el}")

        # Priority 3: TSX structure (section comments + headings, fallback)
        if not parts:
            for line in tsx_content.split("\n"):
                stripped = line.strip()
                cm = re.search(r"\{/\*\s*(.+?)\s*\*/\}", stripped)
                if cm and len(cm.group(1)) < 60 and not cm.group(1).startswith("TODO"):
                    parts.append(f"\n**{cm.group(1)}**")
                    continue
                hm = re.search(r'<h([1-6])[^>]*>\s*"?([^<{"]+)"?\s*</h\1>', stripped)
                if hm and len(hm.group(2).strip()) > 2:
                    parts.append(f"  - h{hm.group(1)}: \"{hm.group(2).strip()}\"")
                gm = re.findall(r"grid-cols-\d+|gap-\d+", stripped)
                if gm and "className" in stripped:
                    parts.append(f"  - Layout: {' '.join(gm)}")

        return "\n".join(parts).strip()

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


# ─── Figma Make Prompt Parser ───────────────────────────────────────


# Normalize section titles to canonical page names
_TITLE_TO_PAGE: dict[str, str] = {
    "design tokens": "",  # Skip — these are component library prompts, not a page
    "component library": "",
    "homepage": "Home",
    "product catalog": "ProductCatalog",
    "coffees": "ProductCatalog",
    "product detail": "ProductDetail",
    "coffee": "ProductDetail",
    "cart": "Cart",
    "checkout": "Checkout",
    "subscription": "SubscriptionWizard",
    "user dashboard": "UserDashboard",
    "user account": "UserProfile",
    "admin dashboard": "AdminDashboard",
    "admin product": "AdminProducts",
    "product management": "AdminProducts",
    "admin order": "AdminOrders",
    "order management": "AdminOrders",
    "admin deliveries": "AdminOrders",
    "daily deliveries": "AdminOrders",
    "admin coupon": "AdminCoupons",
    "coupon": "AdminCoupons",
    "admin promo": "AdminCoupons",
    "promo day": "AdminCoupons",
    "admin gift": "AdminCoupons",
    "gift card": "AdminCoupons",
    "admin review": "AdminCoupons",
    "stories": "Stories",
    "content": "Stories",
    "story detail": "StoryDetail",
    "blog": "Stories",
    "auth": "Login",
    "login": "Login",
    "register": "Login",
    "promo banner": "PromoStates",
    "special states": "PromoStates",
    "error page": "PromoStates",
    "email": "EmailTemplates",
}


def _normalize_page_name(title: str) -> str:
    """Normalize a figma.md section title to a canonical page name.

    Examples:
        "HOMEPAGE — DESKTOP (1280px)" → "Home"
        "ADMIN — PRODUCT MANAGEMENT" → "AdminProducts"
        "AUTH PAGES — LOGIN, REGISTER" → "Login"
    """
    # Remove numbering prefix: "2. HOMEPAGE..." → "HOMEPAGE..."
    cleaned = re.sub(r"^\d+\.\s*", "", title).strip()
    # Remove resolution/dimension hints: "... (1280px)" or "... (375px)"
    cleaned = re.sub(r"\s*\([\d]+px\)", "", cleaned)
    # Remove "— DESKTOP" / "— MOBILE" suffixes for matching (keep for subsection)
    base = re.sub(r"\s*—\s*(DESKTOP|MOBILE).*", "", cleaned, flags=re.IGNORECASE)
    base_lower = base.lower().strip()

    # Try direct match
    for pattern, page_name in _TITLE_TO_PAGE.items():
        if pattern in base_lower:
            return page_name
    # Fallback: PascalCase the first word
    words = base_lower.split()
    if words:
        return words[0].capitalize()
    return ""


def _is_mobile_section(title: str) -> bool:
    """Check if a section title refers to a mobile variant."""
    return bool(re.search(r"mobile|375px", title, re.IGNORECASE))


def _clean_prompt_content(content: str) -> str:
    """Remove Figma Make meta-instructions, keep actionable design detail.

    Strips lines like "Create a design..." or "Design the..." that are
    prompts to Figma Make, not useful for implementing agents.
    """
    lines = content.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip Figma Make meta-instructions
        if re.match(r"^(Create|Design|Build|Make|Generate)\s+(a|the|an)\s+", stripped, re.IGNORECASE):
            continue
        # Skip brand repetition lines (already in tokens)
        if re.match(r"^(Colors?|Brand|BRAND):\s+", stripped) and "#" in stripped and len(stripped) > 100:
            continue
        # Skip typography repetition
        if re.match(r"^(Typography|TYPOGRAPHY):\s+", stripped) and "Playfair" in stripped and len(stripped) > 80:
            continue
        # Skip "Colors: cream #FFFBEB..." style single-line token dumps
        if re.match(r"^Colors?:\s+(cream|warm)", stripped, re.IGNORECASE) and stripped.count("#") >= 3:
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


class FigmaMakePromptParser(DesignParser):
    """Parse figma.md files containing Figma Make prompt collections.

    These files have numbered sections (## N. TITLE) followed by fenced
    code blocks containing design prompts. Each section describes one or
    more pages of the application.
    """

    @classmethod
    def detect(cls, path: str) -> bool:
        if not path.endswith(".md"):
            return False
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
            # Figma Make prompt files have numbered sections with code blocks
            has_numbered = bool(re.search(r"^## \d+\.", content, re.MULTILINE))
            has_code_blocks = content.count("```") >= 4
            # Must NOT be a design-system.md (has ## Design Tokens)
            is_design_system = "## Design Tokens" in content
            return has_numbered and has_code_blocks and not is_design_system
        except OSError:
            return False

    def parse(self, path: str) -> DesignSystem:
        ds = DesignSystem()
        content = Path(path).read_text(encoding="utf-8", errors="replace")

        # Split into sections by ## N. headings
        section_re = re.compile(r"^## (\d+)\.\s+(.+)$", re.MULTILINE)
        sections: list[tuple[str, str, str]] = []  # (num, title, content)

        matches = list(section_re.finditer(content))
        for i, m in enumerate(matches):
            num = m.group(1)
            title = m.group(2).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[start:end].strip()
            sections.append((num, title, section_content))

        # Extract code blocks from each section
        page_data: dict[str, list[str]] = {}  # page_name → [descriptions]

        for num, title, section_content in sections:
            page_name = _normalize_page_name(title)
            if not page_name:  # Skip non-page sections (e.g., component library)
                # But still extract tokens from component library section
                self._extract_tokens_from_section(section_content, ds)
                continue

            # Extract fenced code block content
            code_blocks = re.findall(r"```\n?(.*?)```", section_content, re.DOTALL)
            if not code_blocks:
                continue

            raw_description = "\n\n".join(code_blocks)
            cleaned = _clean_prompt_content(raw_description)

            if not cleaned.strip():
                continue

            # Add mobile/desktop label if applicable
            if _is_mobile_section(title):
                cleaned = f"MOBILE VERSION:\n{cleaned}"

            if page_name not in page_data:
                page_data[page_name] = []
            page_data[page_name].append(cleaned)

        # Build PageSpecs — merge desktop+mobile into one page
        for page_name, descriptions in page_data.items():
            visual = "\n\n".join(descriptions)
            page = PageSpec(
                name=page_name,
                visual_description=visual,
            )
            ds.pages.append(page)

        # Extract tokens from all code blocks globally
        all_code = "\n".join(
            block
            for _, _, sc in sections
            for block in re.findall(r"```\n?(.*?)```", sc, re.DOTALL)
        )
        self._extract_tokens_from_section(all_code, ds)

        # Extract fonts
        font_re = re.compile(r"(Playfair Display|Inter|JetBrains Mono|Roboto|Poppins|Open Sans|Lato|Montserrat)", re.IGNORECASE)
        for m in font_re.finditer(all_code):
            font = m.group(1)
            if font not in ds.fonts:
                ds.fonts.append(font)

        logger.info("Parsed %d page sections from figma.md", len(ds.pages))
        return ds

    def _extract_tokens_from_section(self, content: str, ds: DesignSystem) -> None:
        """Extract color, spacing, and typography tokens from prompt text."""
        # Extract hex colors with their context
        color_re = re.compile(r"(?:(\w[\w\s]*?):\s*)?#([0-9A-Fa-f]{6})\b")
        colors = ds.tokens.setdefault("Colors", {})
        for m in color_re.finditer(content):
            label = (m.group(1) or "").strip().lower()
            hex_val = f"#{m.group(2)}"
            # Map known color labels
            if "primary" in label or "brown" in label or "coffee" in label:
                colors.setdefault("color-primary", hex_val)
            elif "secondary" in label or "gold" in label or "accent" in label:
                colors.setdefault("color-secondary", hex_val)
            elif "background" in label or "cream" in label or "bg" in label:
                colors.setdefault("color-background", hex_val)
            elif "surface" in label or "white" in label or "card" in label:
                colors.setdefault("color-surface", hex_val)
            elif "text" in label or "main" in label:
                colors.setdefault("color-text", hex_val)
            elif "muted" in label or "placeholder" in label:
                colors.setdefault("color-muted", hex_val)
            elif "border" in label or "divider" in label:
                colors.setdefault("color-border", hex_val)
            elif "success" in label or "green" in label or "stock" in label:
                colors.setdefault("color-success", hex_val)
            elif "error" in label or "red" in label or "danger" in label:
                colors.setdefault("color-error", hex_val)
            elif "warning" in label:
                colors.setdefault("color-warning", hex_val)

        # Extract spacing values
        spacing_re = re.compile(r"(\d+)px\s+base\s+grid|padding[:\s]+(\d+)px|gap[:\s]+(\d+)px|max-width[:\s]+(\d+)px")
        spacing = ds.tokens.setdefault("Spacing", {})
        for m in spacing_re.finditer(content):
            if m.group(1):
                spacing.setdefault("spacing-base", f"{m.group(1)}px")
            if m.group(2):
                spacing.setdefault("spacing-card", f"{m.group(2)}px")
            if m.group(3):
                spacing.setdefault("spacing-grid", f"{m.group(3)}px")
            if m.group(4):
                spacing.setdefault("container-max", f"{m.group(4)}px")

        # Extract border radius
        radius_re = re.compile(r"border-radius[:\s]+(\d+)px|radius[:\s]+(\d+)px")
        radii = ds.tokens.setdefault("Border Radius", {})
        for m in radius_re.finditer(content):
            val = m.group(1) or m.group(2)
            if val and "radius-button" not in radii:
                radii["radius-button"] = f"{val}px"


# ─── Factory ─────────────────────────────────────────────────────────


_PARSERS: list[type[DesignParser]] = [MakeParser, FigmaMakePromptParser, PassthroughParser]
SUPPORTED_FORMATS = [
    ".make (Figma Make export)",
    ".md (Figma Make prompt collection with ## N. sections)",
    ".md (with '## Design Tokens' section)",
]


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

    # Generate design-brief.md if parser produced visual descriptions
    brief_content = design.to_brief_markdown()
    if brief_content:
        brief_path = os.path.join(output_dir, "design-brief.md")
        brief_lines = len(brief_content.split("\n"))
        if args.dry_run:
            print(f"[dry-run] Would write {brief_path} ({brief_lines} lines)")
        else:
            Path(brief_path).write_text(brief_content, encoding="utf-8")
            print(f"Generated: {brief_path} ({brief_lines} lines)")

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
