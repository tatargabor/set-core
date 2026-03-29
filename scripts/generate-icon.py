#!/usr/bin/env python3
from __future__ import annotations
"""Generate app icon files from SVG source.

Dev tool — run manually when the icon changes.
Requires: PySide6 (already a project dependency)
On macOS: also uses iconutil (built-in) for .icns generation.
"""

import os
import sys
import shutil
import subprocess
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")

SVG_CONTENT = '''\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <rect x="8" y="8" width="240" height="240" rx="40" ry="40" fill="#2D3748"/>
  <text x="128" y="185" font-family="Helvetica" font-size="140" font-weight="bold" fill="white" text-anchor="middle">WT</text>
</svg>
'''

SIZES = [16, 32, 64, 128, 256, 512]


def write_svg():
    path = os.path.join(ASSETS_DIR, "icon.svg")
    with open(path, "w") as f:
        f.write(SVG_CONTENT)
    print(f"  Written: {path}")
    return path


def svg_to_png(svg_path, png_path, size):
    """Render SVG to PNG at given size using PySide6."""
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    with open(svg_path, "r") as f:
        svg_data = f.read()

    renderer = QSvgRenderer(QByteArray(svg_data.encode()))
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)

    painter = QPainter(image)
    renderer.render(painter)
    painter.end()

    image.save(png_path, "PNG")


def render_png(svg_path):
    png_path = os.path.join(ASSETS_DIR, "icon.png")
    svg_to_png(svg_path, png_path, 256)
    print(f"  Written: {png_path} (256x256)")


def generate_icns(svg_path):
    if sys.platform != "darwin":
        print("  Skipping .icns generation (not macOS)")
        return

    iconset_dir = tempfile.mkdtemp(suffix=".iconset")
    try:
        for size in SIZES:
            out = os.path.join(iconset_dir, f"icon_{size}x{size}.png")
            svg_to_png(svg_path, out, size)

            if size <= 256:
                out_2x = os.path.join(iconset_dir, f"icon_{size}x{size}@2x.png")
                svg_to_png(svg_path, out_2x, size * 2)

        icns_path = os.path.join(ASSETS_DIR, "icon.icns")
        subprocess.run(["iconutil", "-c", "icns", iconset_dir, "-o", icns_path], check=True)
        print(f"  Written: {icns_path}")
    finally:
        shutil.rmtree(iconset_dir)


def main():
    # PySide6 requires a QGuiApplication (even for offscreen rendering)
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    os.makedirs(ASSETS_DIR, exist_ok=True)
    print("Generating icon files...")

    svg_path = write_svg()
    render_png(svg_path)
    generate_icns(svg_path)

    print("Done!")


if __name__ == "__main__":
    main()
