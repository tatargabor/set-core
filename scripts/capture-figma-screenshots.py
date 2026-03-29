#!/usr/bin/env python3
from __future__ import annotations
"""
Capture Figma Make preview screenshots for documentation.

Usage:
    python3 scripts/capture-figma-screenshots.py

Requires:
    - Playwright chromium installed
    - FIGMA_TOKEN in .env (not used for Make previews — they're public)

Output:
    docs/images/auto/figma/<name>.png
"""
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
OUT_DIR = ROOT_DIR / "docs" / "images" / "auto" / "figma"

# Figma Make preview URLs to capture
# Each entry: (output_filename, preview_url, description)
PREVIEWS = [
    (
        "product-detail-design",
        "https://www.figma.com/make/9PH3uS4vWjSj6cUPhTGZSt/wt-minishop?p=f&preview-route=%2Fproduct%2F2",
        "MiniShop product detail — Figma Make design preview",
    ),
    (
        "storefront-design",
        "https://www.figma.com/make/9PH3uS4vWjSj6cUPhTGZSt/wt-minishop?p=f&preview-route=%2F",
        "MiniShop storefront — Figma Make design preview",
    ),
]


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    filter_name = sys.argv[1] if len(sys.argv) > 1 else None
    previews = PREVIEWS
    if filter_name:
        previews = [p for p in PREVIEWS if p[0] == filter_name]
        if not previews:
            print(f"Unknown preview: {filter_name}")
            print(f"Available: {', '.join(p[0] for p in PREVIEWS)}")
            sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})

        for filename, url, description in previews:
            print(f"Capturing: {description} ...", end=" ", flush=True)
            try:
                page = ctx.new_page()
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(5000)  # Let Figma render fully
                png_path = OUT_DIR / f"{filename}.png"
                page.screenshot(path=str(png_path))
                size = png_path.stat().st_size
                print(f"OK ({size // 1024}KB)")
                page.close()
            except Exception as e:
                print(f"FAILED: {e}")

        ctx.close()
        browser.close()

    print(f"\nDone. Screenshots in: {OUT_DIR}")


if __name__ == "__main__":
    main()
