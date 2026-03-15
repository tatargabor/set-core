# Design: figma-direct-fetch

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  wt-figma-fetch CLI                                         │
│                                                             │
│  bin/wt-figma-fetch (bash entry)                            │
│    └→ lib/design/fetcher.py (Python core)                   │
│        ├─ MCP client (mcp SDK, HTTP transport)              │
│        │   └→ https://mcp.figma.com/mcp                     │
│        ├─ OAuth token reader                                │
│        │   └→ ~/.claude/.credentials.json                   │
│        ├─ File type router (Design vs Make)                 │
│        ├─ Raw response saver                                │
│        └─ Snapshot assembler                                │
│                                                             │
│  Input:                                                     │
│    wt-figma-fetch docs/                                     │
│    └→ scans docs/**/*.md for Figma URLs                     │
│       finds: docs/spec.md → figma.com/make/ABC              │
│              docs/admin/spec.md → figma.com/design/DEF      │
│                                                             │
│  Output (per Figma URL):                                    │
│    docs/figma-raw/ABC/                                      │
│    ├── design-snapshot.md        (assembled, per-file)      │
│    ├── metadata.json             (get_metadata response)    │
│    ├── tokens.json               (get_variable_defs resp.)  │
│    ├── hierarchy.json            (get_design_context resp.) │
│    ├── sources/                  (Make file sources only)   │
│    │   ├── page1.txt                                        │
│    │   └── page2.txt                                        │
│    └── screenshots/              (Design files only)        │
│        ├── Frame1.png                                       │
│        └── Frame2.png                                       │
│    docs/figma-raw/DEF/                                      │
│    ├── design-snapshot.md                                   │
│    ├── metadata.json                                        │
│    └── ...                                                  │
│                                                             │
│  PLUS: combined snapshot at project root (pipeline compat): │
│    ./design-snapshot.md          ← concat of all per-file   │
│                                    snapshots, written last   │
└─────────────────────────────────────────────────────────────┘
```

### Directory naming convention

Each Figma file gets its own subdirectory under `figma-raw/` in the scanned docs root:
- Directory name = Figma file key (the `ABC123` from the URL)
- Multiple Figma URLs from different md files → separate subdirs
- `figma-raw/` lives as a sibling to the scanned markdown files
- All raw MCP responses saved flat (no `raw/` subdirectory — the whole dir IS raw + assembled)

### Pipeline compatibility: combined project-root snapshot

The existing orchestration pipeline (planner, dispatcher, verifier, engine) ALL hardcode `design-snapshot.md` in `os.getcwd()` (project root):

```
planner.py:1276    os.path.isfile("design-snapshot.md")
dispatcher.py:850  design_context_for_dispatch "..." "."
verifier.py:473    build_design_review_section "."
engine.py:471+     design_snapshot_dir=os.getcwd()
```

**To avoid touching any of these callers**, `wt-figma-fetch` writes a combined `design-snapshot.md` at the project root after assembling per-file snapshots. If there's one Figma file → straight copy. If multiple → concatenated with `---` separator. The dispatcher's `awk`-based frame matching and the verifier's token extraction both work on concatenated content.

This means:
- **Planner**: unchanged — cache check at L1276 finds the committed file, returns content[:5000]
- **Dispatcher**: unchanged — `design_context_for_dispatch()` reads from `$DESIGN_SNAPSHOT_DIR/design-snapshot.md` which is CWD
- **Verifier**: unchanged — `build_design_review_section()` same path
- **Engine**: unchanged — passes `design_snapshot_dir=os.getcwd()` everywhere

Only `_fetch_design_context()` changes: remove the MCP fetch branch, keep the cache-read branch.

## Component: bin/wt-figma-fetch

Bash entry point following wt-tools convention (like `wt-new`, `wt-close`, etc.).

```bash
#!/usr/bin/env bash
# wt-figma-fetch - Fetch Figma design data via direct MCP calls

# Usage:
#   wt-figma-fetch <docs-dir>            — scan docs-dir/**/*.md for Figma URLs, fetch all
#   wt-figma-fetch <figma-url> -o <dir>  — fetch single URL into dir
#   wt-figma-fetch --force <docs-dir>    — re-fetch even if snapshots exist
#
# Examples:
#   wt-figma-fetch docs/                 — scan docs/ for Figma links, save to docs/figma-raw/<key>/
#   wt-figma-fetch https://figma.com/make/ABC -o design/  — single fetch
```

Primary mode: give it a docs directory, it scans all `*.md` files for Figma URLs, creates `figma-raw/<file-key>/` per URL with raw data + assembled snapshot.

Delegates to `lib/design/fetcher.py` for the actual MCP work.

## Component: lib/design/fetcher.py

Python module — the core logic. Replaces the Claude-subprocess approach in `scripts/fetch-figma-design.py`.

### MCP Connection

```python
async def connect_figma_mcp() -> ClientSession:
    """Connect to Figma MCP using stored OAuth token."""
    creds = read_oauth_credentials()  # from ~/.claude/.credentials.json
    headers = {"Authorization": f"Bearer {creds['accessToken']}"}

    read_stream, write_stream, _ = await streamablehttp_client(
        "https://mcp.figma.com/mcp", headers=headers
    )
    session = ClientSession(read_stream, write_stream)
    await session.initialize()
    return session
```

### File Type Detection

```python
async def detect_file_type(session, file_key: str) -> str:
    """Detect if Figma file is Design or Make type."""
    result = await session.call_tool("get_metadata", {"fileKey": file_key})
    raw_save("metadata.json", result)

    # Make files have specific indicators in metadata
    if is_make_file(result):
        return "make"
    return "design"
```

### Design File Strategy

```python
async def fetch_design_file(session, file_key, output_dir):
    """Full fetch for standard Design files."""
    # 1. Tokens (variables/styles)
    tokens = await session.call_tool("get_variable_defs", {"fileKey": file_key})
    raw_save("tokens.json", tokens)

    # 2. Component hierarchy
    hierarchy = await session.call_tool("get_design_context", {"fileKey": file_key})
    raw_save("hierarchy.json", hierarchy)

    # 3. Screenshots
    screenshots = await fetch_screenshots(session, file_key, output_dir)

    return assemble_design_snapshot(metadata, tokens, hierarchy, screenshots)
```

### Make File Strategy

Based on session log analysis — Session 1 approach that produced 13 frames with full Tailwind tokens.

```python
async def fetch_make_file(session, file_key, output_dir):
    """Fetch for Make files (code-based prototypes)."""
    # 1. Design context (gives frame/component structure)
    hierarchy = await session.call_tool("get_design_context", {"fileKey": file_key})
    raw_save("hierarchy.json", hierarchy)

    # 2. Read all source files via MCP resources
    resources = await session.list_resources()
    sources = {}
    for resource in resources:
        content = await session.read_resource(resource.uri)
        sources[resource.name] = content
        raw_save(f"sources/{resource.name}", content)

    # 3. Skip tokens (Make files don't have variable_defs)
    # 4. Skip screenshots (not supported for Make files)

    return assemble_make_snapshot(metadata, hierarchy, sources)
```

### Snapshot Assembly

Output format matches what `bridge.sh` already parses — `design_context_for_dispatch()` and `build_design_review_section()` work unchanged.

```markdown
# Design Snapshot
Source: <figma-url>

## Pages & Frames
<structured list from metadata>

## Design Tokens
<from variable_defs for Design, or parsed from Tailwind for Make>

## Component Hierarchy
### FrameName
- ComponentName (type, tailwind-classes)
  - ChildName (type, tailwind-classes)
<from get_design_context + source enrichment>

## Visual References
<screenshot descriptions or source-derived descriptions>

## Layout Breakpoints
<inferred from frame dimensions>
```

### URL Discovery from Markdown

```python
FIGMA_URL_RE = re.compile(r'https?://[\w.]*figma\.com/(file|design|make)/([A-Za-z0-9]+)[^\s)]*')

def scan_docs_for_figma_urls(docs_dir: str) -> list[dict]:
    """Scan all markdown files in docs_dir for Figma URLs.

    Returns list of {url, file_key, file_type_hint, source_file, output_dir}.
    Each unique file_key gets its own subdir under docs_dir/figma-raw/<key>/.
    """
    refs = []
    seen_keys = set()

    for md_file in sorted(Path(docs_dir).rglob("*.md")):
        content = md_file.read_text(errors="replace")
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
                "output_dir": str(Path(docs_dir) / "figma-raw" / file_key),
            })

    return refs
```

Key behavior:
- Deduplicates by file key (same Figma file referenced from multiple md files → one fetch)
- Output always goes to `<docs_dir>/figma-raw/<file_key>/`
- The URL type hint (`/make/` vs `/design/`) gives an early signal but `get_metadata` is authoritative

## Component: Planner preflight disable

Minimal change to `lib/wt_orch/planner.py` `_fetch_design_context()` (L1256-1341):

**Keep the cache-read branch (L1275-1282), remove everything after it.**

```python
def _fetch_design_context(force: bool = False) -> str:
    """Read committed design snapshot. No runtime MCP fetch."""
    # The combined design-snapshot.md is written to project root by wt-figma-fetch.
    # The existing cache check (L1276) already handles this correctly.
    if os.path.isfile("design-snapshot.md"):
        try:
            content = Path("design-snapshot.md").read_text(errors="replace")
            if content.strip():
                logger.info("Design snapshot loaded (%d bytes)", len(content))
                return content[:5000]
        except OSError:
            pass

    logger.info("No design-snapshot.md — run 'wt-figma-fetch <docs-dir>' to fetch")
    return ""
```

**What gets removed:** L1284-1341 — the MCP detection, bridge.sh subprocess call, 1800s timeout, and RuntimeError on fetch failure. The `force` parameter becomes a no-op (kept for signature compat).

**What stays unchanged:**
- `bridge.sh` functions (`design_context_for_dispatch`, `build_design_review_section`, `design_prompt_section`) — all read from snapshot file
- `dispatcher.py` L848-854 — calls `design_context_for_dispatch` with CWD
- `verifier.py` L467-479 — calls `build_design_review_section` with CWD
- `engine.py` L471,526,833,918 — passes `design_snapshot_dir=os.getcwd()`
- `templates.py` L465-466 — injects design_context if non-empty
- `_detect_design_mcp()` and `_load_design_file_ref()` — can stay as dead code or be removed

## Data flow

```
User runs:  wt-figma-fetch docs/
                │
                ├─ scan docs/**/*.md for Figma URLs
                │   found: docs/spec.md → figma.com/make/ABC
                │          docs/admin/overview.md → figma.com/design/DEF
                │
                ├─ connect to Figma MCP once (single session, reused)
                │
                ├─ for ABC (Make file):
                │   ├─ mkdir docs/figma-raw/ABC/
                │   ├─ get_metadata → save metadata.json
                │   ├─ get_design_context → save hierarchy.json
                │   ├─ read_resource × N → save sources/
                │   └─ assemble docs/figma-raw/ABC/design-snapshot.md
                │
                ├─ for DEF (Design file):
                │   ├─ mkdir docs/figma-raw/DEF/
                │   ├─ get_metadata → save metadata.json
                │   ├─ get_variable_defs → save tokens.json
                │   ├─ get_design_context → save hierarchy.json
                │   ├─ get_screenshot × N → save screenshots/
                │   └─ assemble docs/figma-raw/DEF/design-snapshot.md
                │
                ├─ COMBINE: concat all per-file snapshots
                │   └─ write ./design-snapshot.md (project root)
                │
                └─ print summary, user commits all

Orchestration:  planner reads ./design-snapshot.md (existing L1276 cache check)
                dispatcher frame-matches from ./design-snapshot.md (existing)
                verifier token-checks from ./design-snapshot.md (existing)
                NO runtime MCP calls, NO code changes needed in pipeline
```

### Reprocessing (no MCP calls)

```
wt-figma-fetch --reprocess docs/
    │
    ├─ for each docs/figma-raw/<key>/:
    │   └─ re-assemble design-snapshot.md from existing raw files
    │
    └─ re-combine → ./design-snapshot.md

Useful when: assembler logic changes, no need to re-fetch from Figma
```

## Dependencies

- Python `mcp` SDK (v1.26.0, already installed in miniconda)
- `~/.claude/.credentials.json` for OAuth token (set up by Claude Code's Figma MCP auth flow)
- No new external dependencies
