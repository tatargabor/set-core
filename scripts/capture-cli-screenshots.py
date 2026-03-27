#!/usr/bin/env python3
"""
Capture CLI command output as styled PNG screenshots for documentation.

Dependencies:
    pip install ansi2html playwright
    playwright install chromium

Usage:
    python3 scripts/capture-cli-screenshots.py              # all commands
    python3 scripts/capture-cli-screenshots.py set-list      # single command

Output:
    docs/images/auto/cli/<command-name>.png
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

try:
    from ansi2html import Ansi2HTMLConverter
except ImportError:
    print("ERROR: ansi2html not installed. Run: pip install ansi2html")
    sys.exit(1)

# ── Configuration ──

SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
OUT_DIR = ROOT_DIR / "docs" / "images" / "auto" / "cli"

# Commands to capture. Each entry: (output_filename, shell_command, description)
COMMANDS = [
    # ── Worktree & project management ──
    ("set-list", "set-list", "Worktree listing"),
    ("set-status", "set-status", "Orchestration & agent status"),
    ("set-version", "set-version", "Version info"),
    ("set-config-editor-list", "set-config editor list 2>/dev/null || echo 'No editors detected'", "Editor configuration"),

    # ── OpenSpec ──
    ("openspec-status", "openspec status", "OpenSpec change status"),
    ("openspec-list", "openspec list 2>/dev/null || echo 'No active changes'", "OpenSpec change list"),

    # ── Memory ──
    ("set-memory-stats", "set-memory stats 2>/dev/null || echo 'Memory system not initialized'", "Memory statistics"),
    ("set-memory-health", "set-memory health 2>/dev/null || echo 'Memory not available'", "Memory health check"),

    # ── Project health ──
    ("set-audit-scan", "set-audit scan 2>/dev/null || echo 'No project context'", "Project health audit"),

    # ── Usage & reporting ──
    ("set-usage", "set-usage 2>/dev/null || echo 'No usage data'", "Token usage statistics"),

    # ── Sentinel findings ──
    ("set-sentinel-finding-list", "set-sentinel-finding list --open-only 2>/dev/null || echo 'No findings'", "Sentinel findings"),
]

# ── HTML template (dark terminal theme) ──

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #1e1e2e;
    padding: 0;
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
    font-size: 13px;
    -webkit-font-smoothing: antialiased;
  }}
  .window {{
    background: #1e1e2e;
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #313244;
    display: inline-block;
    min-width: 700px;
    max-width: 900px;
  }}
  .titlebar {{
    background: #181825;
    padding: 10px 16px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .dot {{ width: 12px; height: 12px; border-radius: 50%; }}
  .dot-red {{ background: #f38ba8; }}
  .dot-yellow {{ background: #f9e2af; }}
  .dot-green {{ background: #a6e3a1; }}
  .title {{
    color: #6c7086;
    font-size: 12px;
    margin-left: 8px;
    font-family: inherit;
  }}
  .content {{
    padding: 16px 20px;
    color: #cdd6f4;
    line-height: 1.5;
    white-space: pre;
    overflow-x: auto;
  }}
  /* Override ansi2html colors to match Catppuccin Mocha */
  .ansi1 {{ color: #f38ba8; }} /* red */
  .ansi2 {{ color: #a6e3a1; }} /* green */
  .ansi3 {{ color: #f9e2af; }} /* yellow */
  .ansi4 {{ color: #89b4fa; }} /* blue */
  .ansi5 {{ color: #f5c2e7; }} /* magenta */
  .ansi6 {{ color: #94e2d5; }} /* cyan */
  .ansi7 {{ color: #cdd6f4; }} /* white */
  .ansi1.bold {{ color: #f38ba8; font-weight: bold; }}
  .ansi2.bold {{ color: #a6e3a1; font-weight: bold; }}
  .ansi3.bold {{ color: #f9e2af; font-weight: bold; }}
  .ansi4.bold {{ color: #89b4fa; font-weight: bold; }}
  .body_background {{ background-color: #1e1e2e !important; }}
  .body_foreground {{ color: #cdd6f4 !important; }}
  /* ansi2html inline overrides */
  .ansi2html-content {{ background: transparent !important; color: #cdd6f4 !important; }}
  span {{ font-family: inherit !important; }}
</style>
</head>
<body>
<div class="window">
  <div class="titlebar">
    <div class="dot dot-red"></div>
    <div class="dot dot-yellow"></div>
    <div class="dot dot-green"></div>
    <span class="title">{title}</span>
  </div>
  <div class="content">{content}</div>
</div>
</body>
</html>
"""


def capture_command(cmd: str) -> str:
    """Run a shell command and return its ANSI output."""
    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    # Force color output for tools that check isatty
    env["FORCE_COLOR"] = "1"
    env["CLICOLOR_FORCE"] = "1"

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=15, env=env, cwd=str(ROOT_DIR)
        )
        output = result.stdout
        if result.stderr and not result.stdout:
            output = result.stderr
        return output.rstrip()
    except subprocess.TimeoutExpired:
        return f"(command timed out: {cmd})"
    except Exception as e:
        return f"(error running command: {e})"


def ansi_to_html(ansi_text: str) -> str:
    """Convert ANSI text to HTML spans via ansi2html."""
    conv = Ansi2HTMLConverter(inline=False, dark_bg=True, scheme="dracula")
    return conv.convert(ansi_text, full=False)


def render_to_png(html_path: Path, png_path: Path):
    """Use Playwright to screenshot an HTML file to PNG."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  WARNING: playwright not installed, saving HTML only")
        return False

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 960, "height": 600})
        page.goto(f"file://{html_path}")
        # Screenshot the .window element for tight crop
        window = page.locator(".window")
        window.screenshot(path=str(png_path))
        browser.close()
    return True


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Filter commands if specific one requested
    commands = COMMANDS
    if len(sys.argv) > 1:
        filter_name = sys.argv[1]
        commands = [c for c in COMMANDS if c[0] == filter_name or c[1].startswith(filter_name)]
        if not commands:
            print(f"Unknown command: {filter_name}")
            print(f"Available: {', '.join(c[0] for c in COMMANDS)}")
            sys.exit(1)

    tmp_dir = Path("/tmp/cli-screenshots")
    tmp_dir.mkdir(exist_ok=True)

    for filename, cmd, description in commands:
        print(f"Capturing: {cmd} ...", end=" ", flush=True)

        # 1. Run command
        output = capture_command(cmd)
        if not output.strip():
            print("(empty output, skipping)")
            continue

        # 2. Convert ANSI → HTML
        html_content = ansi_to_html(output)

        # 3. Wrap in styled template — clean title (strip fallback/redirect noise)
        clean_cmd = cmd.split(' 2>/dev/null')[0].split(' ||')[0].strip()
        full_html = HTML_TEMPLATE.format(
            title=f"$ {clean_cmd}",
            content=html_content,
        )

        html_path = tmp_dir / f"{filename}.html"
        html_path.write_text(full_html)

        # 4. Screenshot via Playwright
        png_path = OUT_DIR / f"{filename}.png"
        if render_to_png(html_path, png_path):
            size = png_path.stat().st_size
            print(f"OK ({size // 1024}KB)")
        else:
            # Fallback: copy HTML to output
            fallback = OUT_DIR / f"{filename}.html"
            shutil.copy2(html_path, fallback)
            print(f"HTML saved (no Playwright)")

    # Cleanup
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"\nDone. Screenshots in: {OUT_DIR}")


if __name__ == "__main__":
    main()
