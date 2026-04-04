"""Unit tests for design-brief-dispatch: parser, brief output, and scope matching."""

import os
import tempfile
from pathlib import Path

import pytest

from set_orch.design_parser import (
    FigmaMakePromptParser,
    DesignSystem,
    PageSpec,
    get_parser,
    _normalize_page_name,
    _clean_prompt_content,
)


# ── Fixtures ────────────────────────────────────────────────────────


SAMPLE_FIGMA_MD = """\
# CraftBrew Figma Design Prompts

## Hogyan használd — Figma Make

This is instructional content, should be skipped.

---

## 1. DESIGN TOKENS & COMPONENT LIBRARY

```
Create a design token and component library page for "CraftBrew".

COLOR PALETTE:
- Primary: #78350F (dark coffee brown)
- Secondary: #D97706 (gold accent)
- Background: #FFFBEB (warm cream)

TYPOGRAPHY:
- Headings: Playfair Display (serif)
- Body: Inter (sans-serif)

SPACING: 8px base grid. Card padding 24px. Container max-width: 1280px.
COMPONENTS: Buttons: border-radius: 6px.
```

---

## 2. HOMEPAGE — DESKTOP (1280px)

```
Design the homepage for "CraftBrew" at 1280px.

HEADER (sticky):
- Left: CraftBrew logo
- Center nav: links
- Right: Search, Cart, User

HERO BANNER (full-width, ~500px tall):
- Large coffee photo background
- CTA button: "Fedezd fel" — filled #78350F, rounded 6px

FEATURED COFFEES:
- "Kedvenceink" — h2 centered
- 4 product cards in a row
```

---

## 3. HOMEPAGE — MOBILE (375px)

```
Design the CraftBrew homepage for mobile at 375px.

MOBILE HEADER:
- Hamburger icon, CraftBrew logo, Cart icon
- All touch targets minimum 44x44px

HERO: Full-width image, CTA button full-width below
```

---

## 4. PRODUCT CATALOG PAGE — COFFEES

```
Design a coffee catalog page for "CraftBrew". 1280px desktop.

Colors: cream #FFFBEB bg, brown #78350F primary, gold #D97706 accent.

PAGE TITLE: "Kávék" — h1

FILTER SIDEBAR (desktop, left, 280px):
- Origin, Roast level, Price range filters
```

---

## 16. AUTH PAGES — LOGIN, REGISTER, PASSWORD RESET

```
Design authentication pages for "CraftBrew".

LOGIN (/hu/belepes):
- Centered white card (max 420px)
- "Bejelentkezés" button — full-width, #78350F

REGISTER (/hu/regisztracio):
- Same card style
- "Regisztráció" button — full-width
```
"""


@pytest.fixture
def figma_md_path(tmp_path):
    p = tmp_path / "figma.md"
    p.write_text(SAMPLE_FIGMA_MD, encoding="utf-8")
    return str(p)


# ── FigmaMakePromptParser Tests ─────────────────────────────────────


class TestFigmaMakePromptParser:
    def test_detect_figma_md(self, figma_md_path):
        assert FigmaMakePromptParser.detect(figma_md_path) is True

    def test_detect_rejects_design_system(self, tmp_path):
        p = tmp_path / "design-system.md"
        p.write_text("## Design Tokens\n### Colors\n- primary: #000", encoding="utf-8")
        assert FigmaMakePromptParser.detect(str(p)) is False

    def test_detect_rejects_non_md(self, tmp_path):
        p = tmp_path / "test.txt"
        p.write_text("## 1. Something\n```\ncode\n```", encoding="utf-8")
        assert FigmaMakePromptParser.detect(str(p)) is False

    def test_parse_creates_pages(self, figma_md_path):
        parser = FigmaMakePromptParser()
        ds = parser.parse(figma_md_path)
        page_names = [p.name for p in ds.pages]
        assert "Home" in page_names
        assert "ProductCatalog" in page_names
        assert "Login" in page_names

    def test_parse_merges_desktop_mobile(self, figma_md_path):
        parser = FigmaMakePromptParser()
        ds = parser.parse(figma_md_path)
        home_pages = [p for p in ds.pages if p.name == "Home"]
        assert len(home_pages) == 1
        home = home_pages[0]
        assert "MOBILE" in home.visual_description
        assert "HEADER" in home.visual_description

    def test_parse_skips_instructional_sections(self, figma_md_path):
        parser = FigmaMakePromptParser()
        ds = parser.parse(figma_md_path)
        page_names = [p.name for p in ds.pages]
        # "Hogyan használd" section should not create a page
        assert "" not in page_names

    def test_parse_extracts_tokens(self, figma_md_path):
        parser = FigmaMakePromptParser()
        ds = parser.parse(figma_md_path)
        assert "Colors" in ds.tokens
        colors = ds.tokens["Colors"]
        assert colors.get("color-primary") == "#78350F"
        assert colors.get("color-secondary") == "#D97706"
        assert colors.get("color-background") == "#FFFBEB"

    def test_parse_extracts_fonts(self, figma_md_path):
        parser = FigmaMakePromptParser()
        ds = parser.parse(figma_md_path)
        assert "Playfair Display" in ds.fonts
        assert "Inter" in ds.fonts

    def test_parse_extracts_spacing(self, figma_md_path):
        parser = FigmaMakePromptParser()
        ds = parser.parse(figma_md_path)
        spacing = ds.tokens.get("Spacing", {})
        assert spacing.get("spacing-base") == "8px"
        assert spacing.get("spacing-card") == "24px"

    def test_factory_detects_figma_md(self, figma_md_path):
        parser = get_parser(figma_md_path)
        assert isinstance(parser, FigmaMakePromptParser)


# ── Page Name Normalization ─────────────────────────────────────────


class TestPageNameNormalization:
    def test_homepage_desktop(self):
        assert _normalize_page_name("HOMEPAGE — DESKTOP (1280px)") == "Home"

    def test_homepage_mobile(self):
        assert _normalize_page_name("HOMEPAGE — MOBILE (375px)") == "Home"

    def test_product_catalog(self):
        assert _normalize_page_name("PRODUCT CATALOG PAGE — COFFEES") == "ProductCatalog"

    def test_admin_product_management(self):
        assert _normalize_page_name("ADMIN — PRODUCT MANAGEMENT") == "AdminProducts"

    def test_auth_pages(self):
        assert _normalize_page_name("AUTH PAGES — LOGIN, REGISTER, PASSWORD RESET") == "Login"

    def test_checkout(self):
        assert _normalize_page_name("CHECKOUT — 3-STEP FLOW") == "Checkout"

    def test_subscription_wizard(self):
        assert _normalize_page_name("SUBSCRIPTION SETUP WIZARD") == "SubscriptionWizard"

    def test_design_tokens_skipped(self):
        assert _normalize_page_name("DESIGN TOKENS & COMPONENT LIBRARY") == ""


# ── Clean Prompt Content ────────────────────────────────────────────


class TestCleanPromptContent:
    def test_removes_create_prefix(self):
        result = _clean_prompt_content("Create a design token page for CraftBrew.\nHEADER: sticky")
        assert "Create a design" not in result
        assert "HEADER: sticky" in result

    def test_preserves_actionable_detail(self):
        text = "HERO BANNER (full-width, ~500px):\n- CTA: \"Shop now\" — #78350F filled"
        result = _clean_prompt_content(text)
        assert "HERO BANNER" in result
        assert "#78350F" in result


# ── to_brief_markdown() ────────────────────────────────────────────


class TestToBriefMarkdown:
    def test_generates_page_sections(self):
        ds = DesignSystem()
        ds.pages = [
            PageSpec(name="Home", visual_description="HERO: full-width banner\nFEATURED: 4 cards"),
            PageSpec(name="Login", visual_description="Centered card, max 420px"),
        ]
        brief = ds.to_brief_markdown()
        assert "## Page: Home" in brief
        assert "## Page: Login" in brief
        assert "HERO: full-width banner" in brief
        assert "Centered card" in brief

    def test_empty_when_no_visual_descriptions(self):
        ds = DesignSystem()
        ds.pages = [PageSpec(name="Home")]
        brief = ds.to_brief_markdown()
        assert brief == ""

    def test_skips_pages_without_visual(self):
        ds = DesignSystem()
        ds.pages = [
            PageSpec(name="Home", visual_description="Has visual"),
            PageSpec(name="Empty"),
        ]
        brief = ds.to_brief_markdown()
        assert "## Page: Home" in brief
        assert "## Page: Empty" not in brief


# ── Bridge.sh design_brief_for_dispatch() ───────────────────────────


class TestDesignBriefForDispatch:
    """Test the bridge.sh scope matching via subprocess."""

    @pytest.fixture
    def brief_file(self, tmp_path):
        content = """\
# Design Brief

## Page: Home

HERO: full-width, 500px, coffee photo background
CTA: "Shop now" — #78350F button

## Page: ProductCatalog

FILTER SIDEBAR: 280px left, checkboxes
PRODUCT GRID: 3 columns desktop

## Page: AdminProducts

PRODUCT LIST: DataTable with filters
PRODUCT EDITOR: 5 tabs
"""
        p = tmp_path / "design-brief.md"
        p.write_text(content, encoding="utf-8")
        return str(p)

    def _run_bridge(self, scope: str, brief_path: str) -> str:
        from set_orch.subprocess_utils import run_command
        bridge = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "lib", "design", "bridge.sh",
        )
        if not os.path.isfile(bridge):
            pytest.skip("bridge.sh not found")
        r = run_command(
            ["bash", "-c", f'source "{bridge}" 2>/dev/null && design_brief_for_dispatch "{scope}" "{brief_path}"'],
            timeout=5,
        )
        return r.stdout.strip() if r.exit_code == 0 else ""

    def test_matches_home_by_alias(self, brief_file):
        result = self._run_bridge("Homepage hero banner featured products", brief_file)
        assert "Visual Design: Home" in result
        assert "HERO:" in result

    def test_matches_catalog_by_name(self, brief_file):
        result = self._run_bridge("product catalog listing page filter", brief_file)
        assert "Visual Design: ProductCatalog" in result

    def test_no_false_positive_admin(self, brief_file):
        """'product reviews rating' should NOT match AdminProducts."""
        result = self._run_bridge("product reviews rating star moderation", brief_file)
        # AdminProducts should not match — "product" alone is not enough
        # but "moderation" is an AdminCoupons alias, not AdminProducts
        assert "AdminProducts" not in result

    def test_empty_when_no_match(self, brief_file):
        result = self._run_bridge("something completely unrelated xyz", brief_file)
        assert result == ""

    def test_returns_empty_when_no_brief(self, tmp_path):
        result = self._run_bridge("homepage hero", str(tmp_path / "nonexistent.md"))
        assert result == ""
