#!/usr/bin/env python3
"""Fetch Figma design data via MCP or REST API into a figma/ directory.

Everything goes into one directory: design-snapshot.md + screenshots/*.png.

Usage:
    # MCP mode (works for Make/Slides files too):
    python3 fetch-figma-design.py --mcp-config /path/to/mcp.json <figma-url>
    python3 fetch-figma-design.py --mcp-config /path/to/mcp.json <url> -o ./my-figma/

    # REST API mode (Design files only):
    FIGMA_TOKEN=figd_xxx python3 fetch-figma-design.py <figma-url>
    FIGMA_TOKEN=figd_xxx python3 fetch-figma-design.py <url> -o ./my-figma/

Output structure:
    figma/
      design-snapshot.md    — structured markdown (pages, tokens, components)
      screenshots/
        Homepage.png        — PNG screenshots of key frames
        ProductDetail.png
        ...

Env:
    FIGMA_TOKEN     — Figma Personal Access Token (REST API mode)
    RUN_CLAUDE_BIN  — path to claude binary (default: claude)
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from collections import defaultdict
from typing import Any


# ─── Figma REST API (fallback for Design files) ─────────────────────────

FIGMA_API = "https://api.figma.com"


def api_get(path: str, token: str) -> dict:
    url = f"{FIGMA_API}{path}"
    req = urllib.request.Request(url, headers={
        "X-Figma-Token": token,
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        print(f"WARN: Figma API {e.code} on {path}: {body}", file=sys.stderr)
        raise


def extract_file_key(url_or_key: str) -> str:
    m = re.search(r'figma\.com/(?:file|design|make)/([A-Za-z0-9]+)', url_or_key)
    if m:
        return m.group(1)
    if re.match(r'^[A-Za-z0-9]{20,}$', url_or_key):
        return url_or_key
    print(f"ERROR: Cannot extract Figma file key from: {url_or_key}", file=sys.stderr)
    sys.exit(1)


# ─── MCP Mode: Sequential focused calls ─────────────────────────────────

def run_claude_mcp(prompt: str, mcp_config: str, timeout: int = 120) -> str:
    """Run a single focused MCP call via claude CLI. Returns text output."""
    claude_bin = os.environ.get("RUN_CLAUDE_BIN", "claude")
    cmd = [
        claude_bin, "--output-format", "text",
        "--mcp-config", mcp_config,
        "--allowedTools", "mcp__figma__*",
        "-p", prompt,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "DISABLE_PROMPT_CACHING": "1"}
        )
        if result.returncode != 0:
            err = result.stderr.strip()[:200] if result.stderr else ""
            print(f"WARN: claude returned {result.returncode}: {err}", file=sys.stderr)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"WARN: claude call timed out after {timeout}s", file=sys.stderr)
        return ""
    except FileNotFoundError:
        print(f"ERROR: '{claude_bin}' not found. Set RUN_CLAUDE_BIN.", file=sys.stderr)
        return ""


def mcp_fetch_metadata(design_ref: str, mcp_config: str) -> str:
    """Step 1: Get page/frame structure via MCP."""
    print("  [1/4] Fetching metadata (pages, frames, dimensions)...", file=sys.stderr)
    prompt = f"""You have a Figma MCP available. Call get_metadata for this design file:
{design_ref}

Return ONLY a structured list in this EXACT format (no other text):

PAGES_AND_FRAMES:
- Page: <page_name>
  - Frame: <frame_name> | Type: <FRAME/COMPONENT/SECTION> | Size: <width>x<height> | Children: <count>
  - Frame: <next_frame> | Type: ... | Size: ... | Children: ...
- Page: <next_page>
  ...

List ALL pages and ALL top-level frames. Do not skip any."""
    return run_claude_mcp(prompt, mcp_config, timeout=120)


def mcp_fetch_tokens(design_ref: str, mcp_config: str) -> str:
    """Step 2: Get design tokens (variables/styles) via MCP."""
    print("  [2/4] Fetching design tokens (colors, typography, spacing)...", file=sys.stderr)
    prompt = f"""You have a Figma MCP available. Call get_variable_defs for this design file:
{design_ref}

Return ONLY a structured list in this EXACT format (no other text):

DESIGN_TOKENS:
Colors:
- <name>: <hex_value> (or rgba if has alpha)
Typography:
- <name>: <font-family>, <size>px, weight <weight>
Spacing:
- <name>: <value>px
Shadows:
- <name>: <definition>
Other:
- <name>: <value>

If a category has no tokens, write "none".
List ALL tokens with their actual values, not just "defined"."""
    return run_claude_mcp(prompt, mcp_config, timeout=120)


def mcp_fetch_components(design_ref: str, mcp_config: str) -> str:
    """Step 3: Get component hierarchy via MCP."""
    print("  [3/4] Fetching component hierarchy...", file=sys.stderr)
    prompt = f"""You have a Figma MCP available. Call get_design_context for this design file:
{design_ref}

Return ONLY the component tree in this EXACT format (no other text):

COMPONENT_HIERARCHY:
### <Frame Name>
- <ComponentName> (<type>)
  - <ChildName> (<type>)
    - <GrandchildName> (<type>)

### <Next Frame>
...

Show max 4 levels deep. Include component properties if available.
Cover ALL major frames, not just the first few."""
    return run_claude_mcp(prompt, mcp_config, timeout=180)


def mcp_fetch_screenshots(design_ref: str, mcp_config: str, output_dir: str) -> list[dict]:
    """Step 4: Get screenshots of key frames via MCP. Returns list of {name, path}."""
    print("  [4/4] Fetching screenshots of key frames...", file=sys.stderr)
    os.makedirs(output_dir, exist_ok=True)

    # First ask which frames to screenshot
    prompt = f"""You have a Figma MCP available. For this design file:
{design_ref}

Call get_screenshot for these key frames/pages (call get_screenshot once per frame):
1. The homepage / main landing page
2. A product detail page
3. The checkout or cart page

For each screenshot, describe what you see in this EXACT format (no other text):

SCREENSHOTS:
- frame: <frame_name>
  description: <2-3 sentence visual description of layout, colors, key elements>
- frame: <frame_name>
  description: <2-3 sentence visual description>
- frame: <frame_name>
  description: <2-3 sentence visual description>

If a frame doesn't exist, skip it. Get at most 3 screenshots."""

    result = run_claude_mcp(prompt, mcp_config, timeout=180)

    # Also try to get actual image files via the REST API if we have a token
    token = os.environ.get("FIGMA_TOKEN", "")
    file_key = extract_file_key(design_ref)
    screenshots = []

    if token:
        try:
            screenshots = _fetch_screenshot_images(file_key, token, output_dir)
        except Exception as e:
            print(f"  WARN: REST screenshot fetch failed: {e}", file=sys.stderr)

    return screenshots, result


def _fetch_screenshot_images(file_key: str, token: str, output_dir: str) -> list[dict]:
    """Fetch actual PNG images of top-level frames via REST API."""
    # Get file to find frame IDs — use depth=2 to catch nested frames
    try:
        file_data = api_get(f"/v1/files/{file_key}?depth=2", token)
    except Exception:
        return []

    document = file_data.get("document", {})
    frame_ids = []
    frame_names = {}
    for page in document.get("children", []):
        if page.get("type") != "CANVAS":
            continue
        for child in page.get("children", []):
            if child.get("type") in ("FRAME", "COMPONENT", "COMPONENT_SET", "SECTION"):
                fid = child.get("id", "")
                fname = child.get("name", "frame")
                frame_ids.append(fid)
                frame_names[fid] = fname
                # Also grab sub-frames (depth=2)
                for sub in child.get("children", []):
                    if sub.get("type") in ("FRAME", "SECTION"):
                        sfid = sub.get("id", "")
                        sfname = sub.get("name", "subframe")
                        frame_ids.append(sfid)
                        frame_names[sfid] = sfname

    if not frame_ids:
        return []

    # Request images for up to 8 frames
    ids_param = ",".join(frame_ids[:8])
    try:
        img_data = api_get(f"/v1/images/{file_key}?ids={ids_param}&format=png&scale=1", token)
    except Exception:
        return []

    images = img_data.get("images", {})
    screenshots = []
    for fid, url in images.items():
        if not url:
            continue
        fname = frame_names.get(fid, fid).replace("/", "-").replace(" ", "_")
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '', fname)
        out_path = os.path.join(output_dir, f"{safe_name}.png")

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                with open(out_path, "wb") as f:
                    f.write(resp.read())
            screenshots.append({"name": frame_names.get(fid, fid), "path": out_path})
            print(f"    Saved: {out_path}", file=sys.stderr)
        except Exception as e:
            print(f"    WARN: Failed to download {fname}: {e}", file=sys.stderr)

    return screenshots


def mcp_assemble_snapshot(design_ref: str, mcp_config: str, screenshot_dir: str | None = None) -> str:
    """Fetch all data via MCP and assemble into markdown."""
    file_key = extract_file_key(design_ref)
    print(f"Figma file key: {file_key}", file=sys.stderr)
    print(f"Mode: MCP (sequential calls)", file=sys.stderr)

    metadata = mcp_fetch_metadata(design_ref, mcp_config)
    tokens = mcp_fetch_tokens(design_ref, mcp_config)
    components = mcp_fetch_components(design_ref, mcp_config)

    # Screenshots
    screenshots = []
    screenshot_descriptions = ""
    if screenshot_dir:
        screenshots, screenshot_descriptions = mcp_fetch_screenshots(
            design_ref, mcp_config, screenshot_dir
        )

    # Assemble markdown
    lines = []
    lines.append(f"# Design Snapshot")
    lines.append(f"")
    lines.append(f"Source: {design_ref}")
    lines.append(f"")

    # Metadata section
    lines.append("## Pages & Frames")
    lines.append("")
    if metadata and "PAGES_AND_FRAMES:" in metadata:
        # Extract just the structured data
        idx = metadata.index("PAGES_AND_FRAMES:")
        lines.append(metadata[idx + len("PAGES_AND_FRAMES:"):].strip())
    elif metadata:
        lines.append(metadata)
    else:
        lines.append("*Failed to fetch metadata*")
    lines.append("")

    # Tokens section
    lines.append("## Design Tokens")
    lines.append("")
    if tokens and "DESIGN_TOKENS:" in tokens:
        idx = tokens.index("DESIGN_TOKENS:")
        lines.append(tokens[idx + len("DESIGN_TOKENS:"):].strip())
    elif tokens:
        lines.append(tokens)
    else:
        lines.append("*Failed to fetch design tokens*")
    lines.append("")

    # Components section
    lines.append("## Component Hierarchy")
    lines.append("")
    if components and "COMPONENT_HIERARCHY:" in components:
        idx = components.index("COMPONENT_HIERARCHY:")
        lines.append(components[idx + len("COMPONENT_HIERARCHY:"):].strip())
    elif components:
        lines.append(components)
    else:
        lines.append("*Failed to fetch component hierarchy*")
    lines.append("")

    # Screenshots section
    if screenshots or screenshot_descriptions:
        lines.append("## Visual References")
        lines.append("")
        if screenshots:
            for s in screenshots:
                rel_path = os.path.basename(s["path"])
                lines.append(f"### {s['name']}")
                lines.append(f"![{s['name']}]({rel_path})")
                lines.append("")
        if screenshot_descriptions:
            marker = "SCREENSHOTS:"
            if marker in screenshot_descriptions:
                idx = screenshot_descriptions.index(marker)
                lines.append(screenshot_descriptions[idx + len(marker):].strip())
            else:
                lines.append(screenshot_descriptions)
            lines.append("")

    return "\n".join(lines)


# ─── REST API Mode (original, for standard Design files) ────────────────

def rest_fetch_snapshot(url_or_key: str, token: str) -> str:
    """Fetch via REST API — works for standard Design files only."""
    file_key = extract_file_key(url_or_key)
    print(f"Figma file key: {file_key}", file=sys.stderr)
    print(f"Mode: REST API", file=sys.stderr)

    print("Fetching file data...", file=sys.stderr)
    file_data = get_file_data(file_key, token)
    file_name = file_data.get("name", "Untitled")
    print(f"File: {file_name}", file=sys.stderr)

    print("Fetching local variables...", file=sys.stderr)
    variables_data = get_local_variables(file_key, token)

    document = file_data.get("document", {})
    frames = extract_frames(document)
    print(f"Found {len(frames)} frames", file=sys.stderr)

    components = extract_component_hierarchy(document)
    variables = extract_variables(variables_data)
    styles = extract_styles(file_data)

    var_count = sum(len(v) for v in variables.values())
    style_count = sum(len(v) for v in styles.values())
    print(f"Tokens: {var_count} variables, {style_count} styles", file=sys.stderr)

    return generate_markdown(file_name, frames, components, variables, styles)


def get_file_data(file_key: str, token: str) -> dict:
    return api_get(f"/v1/files/{file_key}?depth=3", token)


def get_local_variables(file_key: str, token: str) -> dict | None:
    try:
        return api_get(f"/v1/files/{file_key}/variables/local", token)
    except Exception:
        return None


# ─── REST API Data Extraction ────────────────────────────────────────────

def extract_frames(document: dict) -> list[dict]:
    frames = []
    for page in document.get("children", []):
        if page.get("type") != "CANVAS":
            continue
        page_name = page.get("name", "Untitled")
        for child in page.get("children", []):
            if child.get("type") not in ("FRAME", "COMPONENT", "COMPONENT_SET", "SECTION"):
                continue
            bbox = child.get("absoluteBoundingBox", {})
            w = int(bbox.get("width", 0))
            h = int(bbox.get("height", 0))
            frames.append({
                "page": page_name,
                "name": child.get("name", ""),
                "type": child.get("type", ""),
                "width": w, "height": h,
                "id": child.get("id", ""),
                "children_count": len(child.get("children", [])),
            })
    return frames


def extract_component_hierarchy(document: dict) -> dict[str, list]:
    result = defaultdict(list)

    def _walk(node: dict, depth: int, frame_name: str):
        if depth > 4:
            return
        name = node.get("name", "")
        ntype = node.get("type", "")
        indent = "  " * depth
        label = f"{indent}- {name} ({ntype})"
        props = node.get("componentProperties", {})
        if props:
            prop_strs = [f"{k}={v.get('value', '?')}" for k, v in props.items()]
            label += f" [{', '.join(prop_strs)}]"
        result[frame_name].append(label)
        for child in node.get("children", []):
            _walk(child, depth + 1, frame_name)

    for page in document.get("children", []):
        if page.get("type") != "CANVAS":
            continue
        for frame in page.get("children", []):
            if frame.get("type") not in ("FRAME", "COMPONENT", "COMPONENT_SET", "SECTION"):
                continue
            frame_name = frame.get("name", "Untitled")
            for child in frame.get("children", []):
                _walk(child, 0, frame_name)

    return dict(result)


def extract_variables(variables_data: dict | None) -> dict[str, list[str]]:
    categories: dict[str, list[str]] = {
        "Colors": [], "Typography": [], "Spacing": [], "Shadows": [], "Other": [],
    }
    if not variables_data:
        return categories

    meta = variables_data.get("meta", {})
    variables = meta.get("variables", {})
    collections = meta.get("variableCollections", {})

    col_names = {cid: col.get("name", cid) for cid, col in collections.items()}

    for vid, var in variables.items():
        name = var.get("name", vid)
        resolved_type = var.get("resolvedType", "")
        col_name = col_names.get(var.get("variableCollectionId", ""), "")

        values_by_mode = var.get("valuesByMode", {})
        val = next(iter(values_by_mode.values()), None)

        val_str = _format_variable_value(val, resolved_type)
        entry = f"`{name}`: {val_str}"
        if col_name:
            entry += f" (collection: {col_name})"

        name_lower = name.lower()
        col_lower = col_name.lower()
        if resolved_type == "COLOR" or "color" in name_lower:
            categories["Colors"].append(entry)
        elif any(k in name_lower or k in col_lower for k in ("font", "type", "text", "heading", "body", "display")):
            categories["Typography"].append(entry)
        elif any(k in name_lower or k in col_lower for k in ("space", "spacing", "gap", "padding", "margin", "radius", "size")):
            categories["Spacing"].append(entry)
        elif any(k in name_lower or k in col_lower for k in ("shadow", "elevation", "blur")):
            categories["Shadows"].append(entry)
        else:
            categories["Other"].append(entry)

    return categories


def _format_variable_value(val: Any, resolved_type: str) -> str:
    if val is None:
        return "*(unset)*"
    if isinstance(val, dict):
        if "r" in val and "g" in val and "b" in val:
            r, g, b = int(val["r"] * 255), int(val["g"] * 255), int(val["b"] * 255)
            a = val.get("a", 1)
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            return f"{hex_color} (alpha: {a:.2f})" if a < 1 else hex_color
        if val.get("type") == "VARIABLE_ALIAS":
            return f"→ alias({val.get('id', '?')})"
        return json.dumps(val, ensure_ascii=False)
    if isinstance(val, (int, float)) and resolved_type == "FLOAT":
        return f"{int(val)}px" if val == int(val) else f"{val}px"
    return str(val)


def extract_styles(file_data: dict) -> dict[str, list[str]]:
    categories: dict[str, list[str]] = {"Colors": [], "Typography": [], "Shadows": []}
    for sid, style in file_data.get("styles", {}).items():
        name = style.get("name", sid)
        stype = style.get("styleType", "")
        desc = style.get("description", "")
        entry = f"`{name}`" + (f" — {desc}" if desc else "")
        if stype == "FILL":
            categories["Colors"].append(entry)
        elif stype == "TEXT":
            categories["Typography"].append(entry)
        elif stype == "EFFECT":
            categories["Shadows"].append(entry)
    return categories


def generate_markdown(
    file_name: str, frames: list[dict], components: dict[str, list],
    variables: dict[str, list[str]], styles: dict[str, list[str]],
) -> str:
    lines = [f"# Design Snapshot: {file_name}", ""]

    lines += ["## Pages & Frames", "",
              "| Page | Frame | Type | Dimensions | Children |",
              "|------|-------|------|------------|----------|"]
    for f in frames:
        dims = f"{f['width']}x{f['height']}" if f["width"] else "—"
        lines.append(f"| {f['page']} | {f['name']} | {f['type']} | {dims} | {f['children_count']} |")
    if not frames:
        lines.append("| *(no frames found)* | | | | |")
    lines.append("")

    lines += ["## Design Tokens", ""]
    for category in ("Colors", "Typography", "Spacing", "Shadows", "Other"):
        var_items = variables.get(category, [])
        style_items = styles.get(category, [])
        all_items = var_items + style_items
        if not all_items and category == "Other":
            continue
        lines += [f"### {category}", ""]
        lines += [f"- {item}" for item in all_items] if all_items else ["*No data available*"]
        lines.append("")

    lines += ["## Component Hierarchy", ""]
    shown = 0
    for frame_name, tree in components.items():
        if shown >= 20:
            lines.append(f"*(... and {len(components) - 20} more frames)*")
            break
        lines += [f"### {frame_name}", ""]
        lines += tree[:50]
        if len(tree) > 50:
            lines.append(f"  *(... {len(tree) - 50} more nodes)*")
        lines.append("")
        shown += 1
    if not components:
        lines += ["*No component hierarchy extracted*", ""]

    lines += ["## Layout Breakpoints", ""]
    breakpoints = _infer_breakpoints(frames)
    lines += [f"- {bp}" for bp in breakpoints] if breakpoints else ["*No responsive breakpoints detected*"]
    lines.append("")

    return "\n".join(lines)


def _infer_breakpoints(frames: list[dict]) -> list[str]:
    widths = defaultdict(list)
    for f in frames:
        w = f["width"]
        if w == 0:
            continue
        if w <= 480:
            widths["Mobile"].append(f"{f['name']} ({w}px)")
        elif w <= 768:
            widths["Tablet"].append(f"{f['name']} ({w}px)")
        elif w <= 1024:
            widths["Small Desktop"].append(f"{f['name']} ({w}px)")
        else:
            widths["Desktop"].append(f"{f['name']} ({w}px)")

    result = []
    for bp_name in ("Mobile", "Tablet", "Small Desktop", "Desktop"):
        items = widths.get(bp_name, [])
        if items:
            examples = ", ".join(items[:3])
            if len(items) > 3:
                examples += f" (+{len(items) - 3} more)"
            result.append(f"**{bp_name}**: {examples}")
    return result


# ─── Main ────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    # Parse args
    args = sys.argv[1:]
    mcp_config = None
    output_dir = None
    url_or_key = None
    design_url = None  # optional Design file URL for PNG export (when main is Make)

    i = 0
    while i < len(args):
        if args[i] == "--mcp-config" and i + 1 < len(args):
            mcp_config = args[i + 1]
            i += 2
        elif args[i] in ("-o", "--output-dir") and i + 1 < len(args):
            output_dir = args[i + 1]
            i += 2
        elif args[i] == "--design-url" and i + 1 < len(args):
            design_url = args[i + 1]
            i += 2
        elif not url_or_key:
            url_or_key = args[i]
            i += 1
        else:
            i += 1

    if not url_or_key:
        print("ERROR: Figma URL or file key required", file=sys.stderr)
        sys.exit(1)

    # Default output dir: ./figma/
    if not output_dir:
        output_dir = "figma"

    os.makedirs(output_dir, exist_ok=True)
    snapshot_file = os.path.join(output_dir, "design-snapshot.md")
    screenshot_subdir = os.path.join(output_dir, "screenshots")

    # Choose mode
    token = os.environ.get("FIGMA_TOKEN", "")

    if mcp_config:
        # MCP mode — works for Make/Slides files too
        md = mcp_assemble_snapshot(url_or_key, mcp_config, screenshot_dir=screenshot_subdir)
        # If a separate Design file URL is given, fetch PNG screenshots from it via REST
        if design_url and token:
            print("Fetching PNG screenshots from Design file...", file=sys.stderr)
            design_key = extract_file_key(design_url)
            rest_screenshots = _fetch_screenshot_images(design_key, token, screenshot_subdir)
            if rest_screenshots:
                md += "\n## PNG Screenshots (from Design file)\n\n"
                for s in rest_screenshots:
                    rel_path = os.path.join("screenshots", os.path.basename(s["path"]))
                    md += f"### {s['name']}\n![{s['name']}]({rel_path})\n\n"
    elif token:
        # REST API mode — standard Design files only
        try:
            md = rest_fetch_snapshot(url_or_key, token)
            # Also fetch screenshots via REST
            file_key = extract_file_key(url_or_key)
            screenshots = _fetch_screenshot_images(file_key, token, screenshot_subdir)
            if screenshots:
                md += "\n## Visual References\n\n"
                for s in screenshots:
                    rel_path = os.path.join("screenshots", os.path.basename(s["path"]))
                    md += f"### {s['name']}\n![{s['name']}]({rel_path})\n\n"
        except urllib.error.HTTPError as e:
            if e.code == 400:
                print("", file=sys.stderr)
                print("This appears to be a Figma Make/Slides file.", file=sys.stderr)
                print("REST API doesn't support these. Use --mcp-config mode instead.", file=sys.stderr)
                sys.exit(1)
            raise
    else:
        print("ERROR: Set FIGMA_TOKEN env var or use --mcp-config", file=sys.stderr)
        sys.exit(1)

    # Write snapshot markdown
    with open(snapshot_file, "w") as f:
        f.write(md)
    print(f"Written to {snapshot_file} ({len(md)} bytes)", file=sys.stderr)

    # Summary
    png_count = 0
    if os.path.isdir(screenshot_subdir):
        png_count = len([f for f in os.listdir(screenshot_subdir) if f.endswith(".png")])

    print(f"\nOutput directory: {output_dir}/", file=sys.stderr)
    print(f"  design-snapshot.md  ({len(md)} bytes)", file=sys.stderr)
    if png_count:
        print(f"  screenshots/        ({png_count} PNG files)", file=sys.stderr)


if __name__ == "__main__":
    main()
