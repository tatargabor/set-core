#!/usr/bin/env python3
"""Fetch Figma design data via direct MCP protocol calls.

No Claude subprocess — uses the Python mcp SDK to talk directly to the
Figma MCP server over HTTP transport.  Saves raw responses + assembled
design-snapshot.md.

Usage:
    python3 fetcher.py <docs-dir>                   # scan & fetch all
    python3 fetcher.py <figma-url> -o <output-dir>  # single fetch
    python3 fetcher.py --reprocess <docs-dir>        # re-assemble from raw
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# ─── Figma URL parsing ────────────────────────────────────────────────

FIGMA_URL_RE = re.compile(
    r'https?://[\w.]*figma\.com/(file|design|make)/([A-Za-z0-9]+)[^\s)]*'
)


def extract_file_key(url_or_key: str) -> str:
    """Extract Figma file key from URL or bare key."""
    m = re.search(r'figma\.com/(?:file|design|make)/([A-Za-z0-9]+)', url_or_key)
    if m:
        return m.group(1)
    if re.match(r'^[A-Za-z0-9]{20,}$', url_or_key):
        return url_or_key
    raise ValueError(f"Cannot extract Figma file key from: {url_or_key}")


# ─── OAuth credentials ───────────────────────────────────────────────

def read_oauth_token() -> dict:
    """Read Figma OAuth token from Claude Code credentials.

    Returns dict with 'accessToken' and 'serverUrl'.
    """
    cred_path = Path.home() / ".claude" / ".credentials.json"
    if not cred_path.is_file():
        raise FileNotFoundError(
            f"No credentials file at {cred_path}. "
            "Authenticate Figma MCP in Claude Code first."
        )

    data = json.loads(cred_path.read_text())
    oauth = data.get("mcpOAuth", {})

    # Find the figma entry
    for key, entry in oauth.items():
        if "figma" in key.lower():
            token = entry.get("accessToken", "")
            url = entry.get("serverUrl", "https://mcp.figma.com/mcp")
            if not token:
                raise ValueError("Figma OAuth token is empty — re-authenticate in Claude Code")
            return {"accessToken": token, "serverUrl": url}

    raise ValueError(
        "No Figma entry in mcpOAuth. "
        "Add the Figma MCP server in Claude Code and authenticate."
    )


# ─── MCP Client ──────────────────────────────────────────────────────

from contextlib import asynccontextmanager

@asynccontextmanager
async def figma_mcp_session():
    """Connect to Figma MCP and yield an initialized ClientSession.

    Usage:
        async with figma_mcp_session() as session:
            result = await session.call_tool("get_metadata", {...})
    """
    from mcp.client.streamable_http import streamablehttp_client
    from mcp.client.session import ClientSession

    creds = read_oauth_token()
    headers = {"Authorization": f"Bearer {creds['accessToken']}"}

    async with streamablehttp_client(creds["serverUrl"], headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def _tool_args(file_key: str, **extra) -> dict:
    """Build standard Figma MCP tool arguments."""
    args = {
        "fileKey": file_key,
        "nodeId": "",  # empty string = root node
    }
    args.update(extra)
    return args


async def call_tool_safe(session, tool_name: str, arguments: dict) -> Any:
    """Call an MCP tool, return the result content or None on error."""
    try:
        result = await session.call_tool(tool_name, arguments)
        return result
    except Exception as e:
        print(f"  WARN: {tool_name} failed: {e}", file=sys.stderr)
        return None


def extract_text_from_result(result) -> str:
    """Extract text content from an MCP tool result."""
    if result is None:
        return ""
    # MCP results have .content which is a list of content blocks
    if hasattr(result, "content"):
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts)
    return str(result)


def extract_resource_links(result) -> list[dict]:
    """Extract resource_link blocks from an MCP tool result.

    Returns list of {name, uri, mimeType} for each resource_link block.
    Used by Make files where get_design_context returns source file references.
    """
    if result is None or not hasattr(result, "content"):
        return []
    links = []
    for block in result.content:
        if getattr(block, "type", None) == "resource_link":
            links.append({
                "name": getattr(block, "name", ""),
                "uri": str(getattr(block, "uri", "")),
                "mimeType": getattr(block, "mimeType", None),
            })
    return links


# ─── Raw response saving ─────────────────────────────────────────────

def raw_save(output_dir: str, filename: str, data: Any):
    """Save raw MCP response to output directory."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)

    if isinstance(data, (dict, list)):
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    elif isinstance(data, bytes):
        with open(path, "wb") as f:
            f.write(data)
    else:
        # MCP result object — save text representation
        text = extract_text_from_result(data) if not isinstance(data, str) else data
        with open(path, "w") as f:
            f.write(text)

    print(f"  saved: {path}", file=sys.stderr)


# ─── File type detection ─────────────────────────────────────────────

async def detect_file_type(
    session, file_key: str, output_dir: str, url_hint: str = ""
) -> tuple[str, Any]:
    """Detect if Figma file is Design or Make type.

    Uses URL hint first (/make/ vs /design/), falls back to metadata analysis.
    Returns (file_type, metadata_result) where file_type is "design" or "make".
    """
    # URL hint is most reliable — Figma URL path encodes file type
    if "/make/" in url_hint:
        # get_metadata returns "not supported" for Make files, so skip it
        # and save a note instead
        raw_save(output_dir, "metadata.json", {"note": "Make file — detected from URL", "url": url_hint})
        return "make", None

    # For Design files, get_metadata works
    result = await call_tool_safe(session, "get_metadata", _tool_args(file_key))
    raw_save(output_dir, "metadata.json", result)

    text = extract_text_from_result(result)
    text_lower = text.lower()

    # Check for Make file indicators in metadata response
    if any(kw in text_lower for kw in ("make file", "not supported for make", "make project")):
        return "make", result

    return "design", result


# ─── Design file fetch ───────────────────────────────────────────────

async def fetch_design_file(session, file_key: str, output_dir: str, metadata_result) -> str:
    """Fetch strategy for standard Figma Design files."""
    print(f"  Strategy: Design file", file=sys.stderr)

    # 1. Tokens
    print(f"  Fetching design tokens...", file=sys.stderr)
    tokens = await call_tool_safe(session, "get_variable_defs", _tool_args(file_key))
    raw_save(output_dir, "tokens.json", tokens)

    # 2. Component hierarchy
    print(f"  Fetching component hierarchy...", file=sys.stderr)
    hierarchy = await call_tool_safe(session, "get_design_context", _tool_args(file_key))
    raw_save(output_dir, "hierarchy.json", hierarchy)

    # 3. Screenshots (best-effort)
    print(f"  Fetching screenshots...", file=sys.stderr)
    screenshots_text = ""
    try:
        screenshots = await call_tool_safe(session, "get_screenshot", _tool_args(file_key))
        if screenshots:
            raw_save(output_dir, "screenshots.json", screenshots)
            screenshots_text = extract_text_from_result(screenshots)
            # Save actual images if present
            if hasattr(screenshots, "content"):
                ss_dir = os.path.join(output_dir, "screenshots")
                os.makedirs(ss_dir, exist_ok=True)
                for i, block in enumerate(screenshots.content):
                    if hasattr(block, "data") and hasattr(block, "mimeType"):
                        import base64
                        ext = "png" if "png" in block.mimeType else "jpg"
                        img_path = os.path.join(ss_dir, f"frame_{i}.{ext}")
                        with open(img_path, "wb") as f:
                            f.write(base64.b64decode(block.data))
                        print(f"  saved: {img_path}", file=sys.stderr)
    except Exception as e:
        print(f"  WARN: screenshots failed: {e}", file=sys.stderr)

    return assemble_snapshot(
        file_key=file_key,
        file_type="design",
        metadata=extract_text_from_result(metadata_result),
        tokens=extract_text_from_result(tokens),
        hierarchy=extract_text_from_result(hierarchy),
        screenshots=screenshots_text,
    )


# ─── Make file fetch ─────────────────────────────────────────────────

async def fetch_make_file(session, file_key: str, output_dir: str, metadata_result) -> str:
    """Fetch strategy for Figma Make files (code-based prototypes).

    For Make files, get_design_context returns resource_link blocks pointing
    to source files. We read each source via session.read_resource(uri).
    get_metadata and get_screenshot don't work for Make files.
    """
    print(f"  Strategy: Make file", file=sys.stderr)

    # 1. Design context — returns resource_link blocks for source files
    print(f"  Fetching design context...", file=sys.stderr)
    hierarchy = await call_tool_safe(
        session, "get_design_context",
        _tool_args(file_key, clientLanguages="typescript,html,css", clientFrameworks="react")
    )

    # Save raw hierarchy (text + resource link manifest)
    resource_links = extract_resource_links(hierarchy)
    hierarchy_data = {
        "text": extract_text_from_result(hierarchy),
        "resource_links": resource_links,
    }
    raw_save(output_dir, "hierarchy.json", hierarchy_data)

    # 2. Read source files from resource links
    sources: dict[str, str] = {}
    if resource_links:
        sources_dir = os.path.join(output_dir, "sources")
        os.makedirs(sources_dir, exist_ok=True)
        print(f"  Reading {len(resource_links)} source files...", file=sys.stderr)

        images_dir = os.path.join(output_dir, "images")
        for link in resource_links:
            name = link["name"]
            uri = link["uri"]
            is_image = name.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico"))
            # Skip fonts
            if name.endswith((".woff", ".woff2", ".ttf", ".eot")):
                print(f"    skip (font): {name}", file=sys.stderr)
                continue
            try:
                content_result = await session.read_resource(uri)
                if is_image:
                    # Save binary images
                    import base64
                    os.makedirs(images_dir, exist_ok=True)
                    for c in content_result.contents:
                        blob = getattr(c, "blob", None)
                        if blob:
                            img_path = os.path.join(images_dir, name)
                            with open(img_path, "wb") as f:
                                f.write(base64.b64decode(blob))
                            print(f"    image: {img_path}", file=sys.stderr)
                else:
                    text = ""
                    for c in content_result.contents:
                        t = getattr(c, "text", None)
                        if t:
                            text += t
                    if text:
                        sources[name] = text
                        safe_name = name.replace("/", "__")
                        raw_save(sources_dir, safe_name, text)
            except Exception as e:
                print(f"    WARN: failed to read {name}: {e}", file=sys.stderr)

        print(f"  Read {len(sources)} source files", file=sys.stderr)

    metadata_text = ""
    if metadata_result is not None:
        metadata_text = extract_text_from_result(metadata_result)
    else:
        metadata_text = f"*Make file (file key: {file_key})*"

    return assemble_snapshot(
        file_key=file_key,
        file_type="make",
        metadata=metadata_text,
        tokens="",  # Make files don't have variable_defs
        hierarchy=extract_text_from_result(hierarchy),
        sources=sources if sources else None,
    )


# ─── Snapshot assembly ────────────────────────────────────────────────

def assemble_snapshot(
    *,
    file_key: str,
    file_type: str,
    metadata: str,
    tokens: str = "",
    hierarchy: str = "",
    screenshots: str = "",
    sources: dict[str, str] | None = None,
) -> str:
    """Assemble design-snapshot.md from fetched data.

    Output format matches what bridge.sh design_context_for_dispatch()
    and build_design_review_section() already parse.
    """
    lines = [
        f"# Design Snapshot",
        f"",
        f"File key: {file_key}",
        f"Type: {file_type}",
        f"",
    ]

    # Pages & Frames
    lines.append("## Pages & Frames")
    lines.append("")
    if metadata.strip():
        lines.append(metadata.strip())
    else:
        lines.append("*No metadata available*")
    lines.append("")

    # Design Tokens
    lines.append("## Design Tokens")
    lines.append("")
    if tokens.strip():
        lines.append(tokens.strip())
    elif sources:
        # For Make files: extract Tailwind classes from app-specific sources only
        app_only = {k: v for k, v in sources.items() if "/components/ui/" not in k}
        tw_tokens = _extract_tailwind_tokens(app_only)
        if tw_tokens:
            lines.append(tw_tokens)
        else:
            lines.append("*Tokens embedded in source code (Tailwind classes)*")
    else:
        lines.append("*No design tokens available*")
    lines.append("")

    # Component Hierarchy
    lines.append("## Component Hierarchy")
    lines.append("")
    if hierarchy.strip():
        lines.append(hierarchy.strip())
    else:
        lines.append("*No component hierarchy available*")
    lines.append("")

    # Visual References
    if screenshots.strip():
        lines.append("## Visual References")
        lines.append("")
        lines.append(screenshots.strip())
        lines.append("")

    # Source Files (Make files only)
    if sources:
        # Separate app-specific from UI library files
        app_sources = {}
        lib_sources = {}
        for name, content in sources.items():
            if "/components/ui/" in name or name.startswith("src/app/components/ui/"):
                lib_sources[name] = content
            else:
                app_sources[name] = content

        lines.append("## Source Files")
        lines.append("")

        # App-specific files: include full source
        for name, content in sorted(app_sources.items()):
            lines.append(f"### {name}")
            lines.append("```")
            if len(content) > 5000:
                lines.append(content[:5000])
                lines.append(f"... ({len(content) - 5000} chars truncated)")
            else:
                lines.append(content)
            lines.append("```")
            lines.append("")

        # UI library files: just list them (full source in raw/sources/)
        if lib_sources:
            lines.append("### UI Library Components")
            lines.append(f"*{len(lib_sources)} shadcn/ui primitives available in `sources/` (not inlined):*")
            lines.append("")
            for name in sorted(lib_sources):
                lines.append(f"- `{name}`")
            lines.append("")

    return "\n".join(lines)


def _extract_tailwind_tokens(sources: dict[str, str]) -> str:
    """Extract commonly used Tailwind classes from Make file sources as pseudo-tokens."""
    # Collect all Tailwind-like class references
    class_re = re.compile(r'(?:className|class)=["\']([^"\']+)["\']')
    class_counts: dict[str, int] = {}

    for content in sources.values():
        for m in class_re.finditer(content):
            for cls in m.group(1).split():
                class_counts[cls] = class_counts.get(cls, 0) + 1

    if not class_counts:
        return ""

    # Group by category
    colors = set()
    typography = set()
    spacing = set()
    borders = set()
    shadows = set()

    for cls in class_counts:
        if any(cls.startswith(p) for p in ("bg-", "text-") if "gray" in cls or "blue" in cls or "red" in cls or "green" in cls or "white" in cls or "black" in cls or "indigo" in cls):
            colors.add(cls)
        elif any(cls.startswith(p) for p in ("text-xs", "text-sm", "text-base", "text-lg", "text-xl", "text-2xl", "text-3xl", "text-4xl", "text-5xl", "font-")):
            typography.add(cls)
        elif any(cls.startswith(p) for p in ("p-", "px-", "py-", "pt-", "pb-", "pl-", "pr-", "m-", "mx-", "my-", "mt-", "mb-", "ml-", "mr-", "gap-", "space-")):
            spacing.add(cls)
        elif any(cls.startswith(p) for p in ("rounded", "border")):
            borders.add(cls)
        elif cls.startswith("shadow"):
            shadows.add(cls)

    lines = []
    if colors:
        lines.append("### Colors (from Tailwind classes)")
        for c in sorted(colors):
            lines.append(f"- `{c}` (×{class_counts[c]})")
    if typography:
        lines.append("### Typography")
        for c in sorted(typography):
            lines.append(f"- `{c}` (×{class_counts[c]})")
    if spacing:
        lines.append("### Spacing")
        for c in sorted(spacing):
            lines.append(f"- `{c}` (×{class_counts[c]})")
    if borders:
        lines.append("### Borders & Radius")
        for c in sorted(borders):
            lines.append(f"- `{c}` (×{class_counts[c]})")
    if shadows:
        lines.append("### Shadows")
        for c in sorted(shadows):
            lines.append(f"- `{c}` (×{class_counts[c]})")

    return "\n".join(lines)


# ─── URL Discovery ───────────────────────────────────────────────────

def scan_docs_for_figma_urls(docs_dir: str) -> list[dict]:
    """Scan markdown files in docs_dir for Figma URLs.

    Returns list of {url, file_key, file_type_hint, source_file, output_dir}.
    Deduplicates by file key.
    """
    refs = []
    seen_keys: set[str] = set()
    docs_path = Path(docs_dir)

    if not docs_path.is_dir():
        print(f"ERROR: {docs_dir} is not a directory", file=sys.stderr)
        return []

    for md_file in sorted(docs_path.rglob("*.md")):
        # Skip figma-raw directory itself
        if "figma-raw" in md_file.parts:
            continue
        try:
            content = md_file.read_text(errors="replace")
        except OSError:
            continue

        for m in FIGMA_URL_RE.finditer(content):
            url = m.group(0)
            file_key = m.group(2)
            file_type_hint = m.group(1)  # "file", "design", or "make"
            if file_key in seen_keys:
                continue
            seen_keys.add(file_key)
            refs.append({
                "url": url,
                "file_key": file_key,
                "file_type_hint": file_type_hint,
                "source_file": str(md_file),
                "output_dir": str(docs_path / "figma-raw" / file_key),
            })

    return refs


# ─── Reprocess (assemble from raw, no MCP) ───────────────────────────

def reprocess_dir(figma_raw_dir: str) -> str | None:
    """Re-assemble design-snapshot.md from existing raw files in a figma-raw/<key>/ dir."""
    d = Path(figma_raw_dir)
    if not d.is_dir():
        return None

    metadata = ""
    tokens = ""
    hierarchy = ""
    screenshots = ""
    sources: dict[str, str] = {}
    file_key = d.name

    # Read raw files
    meta_path = d / "metadata.json"
    if meta_path.is_file():
        metadata = meta_path.read_text(errors="replace")

    tokens_path = d / "tokens.json"
    if tokens_path.is_file():
        tokens = tokens_path.read_text(errors="replace")

    hier_path = d / "hierarchy.json"
    if hier_path.is_file():
        hierarchy = hier_path.read_text(errors="replace")

    ss_path = d / "screenshots.json"
    if ss_path.is_file():
        screenshots = ss_path.read_text(errors="replace")

    sources_dir = d / "sources"
    if sources_dir.is_dir():
        for src_file in sorted(sources_dir.iterdir()):
            if src_file.is_file():
                # Restore original path from flattened name (__ → /)
                original_name = src_file.name.replace("__", "/")
                sources[original_name] = src_file.read_text(errors="replace")

    file_type = "make" if sources else "design"

    return assemble_snapshot(
        file_key=file_key,
        file_type=file_type,
        metadata=metadata,
        tokens=tokens,
        hierarchy=hierarchy,
        screenshots=screenshots,
        sources=sources if sources else None,
    )


# ─── Combined snapshot ────────────────────────────────────────────────

def write_combined_snapshot(docs_dir: str):
    """Concatenate all per-file snapshots into docs_dir/design-snapshot.md."""
    figma_raw = Path(docs_dir) / "figma-raw"
    if not figma_raw.is_dir():
        return

    snapshots = []
    for snap in sorted(figma_raw.glob("*/design-snapshot.md")):
        content = snap.read_text(errors="replace").strip()
        if content:
            snapshots.append(content)

    if not snapshots:
        return

    combined = "\n\n---\n\n".join(snapshots)
    out_path = os.path.join(docs_dir, "design-snapshot.md")
    with open(out_path, "w") as f:
        f.write(combined)
    print(f"Combined snapshot: {out_path} ({len(combined)} bytes)", file=sys.stderr)


# ─── Main fetch orchestration ────────────────────────────────────────

async def fetch_single(url_or_key: str, output_dir: str) -> str:
    """Fetch a single Figma file and save to output_dir."""
    file_key = extract_file_key(url_or_key)
    os.makedirs(output_dir, exist_ok=True)

    print(f"Connecting to Figma MCP...", file=sys.stderr)
    async with figma_mcp_session() as session:
        print(f"Fetching {file_key}...", file=sys.stderr)

        # Detect file type
        file_type, metadata = await detect_file_type(
            session, file_key, output_dir, url_hint=url_or_key
        )
        print(f"  Detected: {file_type} file", file=sys.stderr)

        # Fetch based on type
        if file_type == "make":
            snapshot = await fetch_make_file(session, file_key, output_dir, metadata)
        else:
            snapshot = await fetch_design_file(session, file_key, output_dir, metadata)

        # Save per-file snapshot
        snap_path = os.path.join(output_dir, "design-snapshot.md")
        with open(snap_path, "w") as f:
            f.write(snapshot)
        print(f"  Snapshot: {snap_path} ({len(snapshot)} bytes)", file=sys.stderr)

        return snapshot


async def fetch_from_docs(docs_dir: str, force: bool = False) -> int:
    """Scan docs for Figma URLs and fetch all. Returns count of fetched files."""
    refs = scan_docs_for_figma_urls(docs_dir)
    if not refs:
        print(f"No Figma URLs found in {docs_dir}/**/*.md", file=sys.stderr)
        return 0

    print(f"Found {len(refs)} Figma file(s):", file=sys.stderr)
    for ref in refs:
        print(f"  {ref['file_key']} ({ref['file_type_hint']}) from {ref['source_file']}", file=sys.stderr)

    # Connect once, reuse for all
    print(f"Connecting to Figma MCP...", file=sys.stderr)
    fetched = 0
    async with figma_mcp_session() as session:
        for ref in refs:
            output_dir = ref["output_dir"]

            # Skip if already fetched (unless --force)
            snap_path = os.path.join(output_dir, "design-snapshot.md")
            if not force and os.path.isfile(snap_path):
                print(f"\n  Skipping {ref['file_key']} (snapshot exists, use --force to re-fetch)", file=sys.stderr)
                continue

            os.makedirs(output_dir, exist_ok=True)
            print(f"\nFetching {ref['file_key']}...", file=sys.stderr)

            # Detect type
            file_type, metadata = await detect_file_type(
                session, ref["file_key"], output_dir, url_hint=ref["url"]
            )
            print(f"  Detected: {file_type} file", file=sys.stderr)

            # Fetch
            if file_type == "make":
                snapshot = await fetch_make_file(session, ref["file_key"], output_dir, metadata)
            else:
                snapshot = await fetch_design_file(session, ref["file_key"], output_dir, metadata)

            # Save per-file snapshot
            with open(snap_path, "w") as f:
                f.write(snapshot)
            print(f"  Snapshot: {snap_path} ({len(snapshot)} bytes)", file=sys.stderr)
            fetched += 1

    # Write combined snapshot into docs_dir
    write_combined_snapshot(docs_dir)

    return fetched


def reprocess_from_docs(docs_dir: str) -> int:
    """Re-assemble all snapshots from existing raw files. No MCP calls."""
    figma_raw = Path(docs_dir) / "figma-raw"
    if not figma_raw.is_dir():
        print(f"No figma-raw/ directory in {docs_dir}", file=sys.stderr)
        return 0

    count = 0
    for key_dir in sorted(figma_raw.iterdir()):
        if not key_dir.is_dir():
            continue
        print(f"Reprocessing {key_dir.name}...", file=sys.stderr)
        snapshot = reprocess_dir(str(key_dir))
        if snapshot:
            snap_path = key_dir / "design-snapshot.md"
            snap_path.write_text(snapshot)
            print(f"  {snap_path} ({len(snapshot)} bytes)", file=sys.stderr)
            count += 1

    # Re-combine into docs_dir
    write_combined_snapshot(docs_dir)

    return count


# ─── CLI ──────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args or "--help" in args or "-h" in args:
        print(__doc__, file=sys.stderr)
        sys.exit(0 if "--help" in args or "-h" in args else 1)

    force = "--force" in args
    reprocess = "--reprocess" in args
    args = [a for a in args if a not in ("--force", "--reprocess")]

    output_dir = None
    target = None

    i = 0
    while i < len(args):
        if args[i] in ("-o", "--output") and i + 1 < len(args):
            output_dir = args[i + 1]
            i += 2
        elif target is None:
            target = args[i]
            i += 1
        else:
            i += 1

    if not target:
        print("ERROR: specify a docs directory or Figma URL", file=sys.stderr)
        sys.exit(1)

    # Reprocess mode
    if reprocess:
        count = reprocess_from_docs(target)
        print(f"\nReprocessed {count} file(s)", file=sys.stderr)
        sys.exit(0)

    # Is target a directory (scan mode) or a URL (single mode)?
    if os.path.isdir(target):
        count = asyncio.run(fetch_from_docs(target, force=force))
        print(f"\nFetched {count} file(s)", file=sys.stderr)
    else:
        # Single URL mode
        if not output_dir:
            file_key = extract_file_key(target)
            output_dir = os.path.join("figma-raw", file_key)
        asyncio.run(fetch_single(target, output_dir))
        print(f"\nDone. Output: {output_dir}/", file=sys.stderr)


if __name__ == "__main__":
    main()
