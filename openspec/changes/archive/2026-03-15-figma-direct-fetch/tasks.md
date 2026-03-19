# Tasks: figma-direct-fetch

## Phase 1: Core MCP client

- [x] 1. Create `lib/design/fetcher.py` — async MCP client core
  - OAuth token reader from `~/.claude/.credentials.json` (`mcpOAuth` → figma entry → `accessToken`)
  - `connect_figma_mcp()` using `mcp.client.streamable_http.streamablehttp_client`
  - `call_tool()` wrapper with error handling and raw JSON saving to output dir
  - `read_resource()` wrapper for Make file sources
  - File key extraction from Figma URLs (reuse regex from existing script)
  - Single session reused across all tool calls

- [x] 2. File type detection in `fetcher.py`
  - `detect_file_type(session, file_key)` → "design" | "make"
  - Based on `get_metadata` response analysis
  - Raw metadata always saved to `<output_dir>/metadata.json`

## Phase 2: Fetch strategies

- [x] 3. Design file strategy in `fetcher.py`
  - `fetch_design_file(session, file_key, output_dir)`
  - Call `get_variable_defs` → save `tokens.json`
  - Call `get_design_context` → save `hierarchy.json`
  - Call `get_screenshot` per frame → save PNGs to `screenshots/`
  - Assemble per-file `design-snapshot.md` in existing pipeline format

- [x] 4. Make file strategy in `fetcher.py`
  - `fetch_make_file(session, file_key, output_dir)`
  - Call `get_design_context` → save `hierarchy.json`
  - `list_resources()` + `read_resource()` for all source files → save to `sources/`
  - Skip `get_variable_defs` (empty for Make) and `get_screenshot` (unsupported)
  - Assemble per-file `design-snapshot.md` with Tailwind class preservation in hierarchy

## Phase 3: CLI, discovery, and combining

- [x] 5. Create `bin/wt-figma-fetch` — bash entry point
  - Source `wt-common.sh` for logging/config
  - Primary mode: `wt-figma-fetch <docs-dir>` — scan and fetch all
  - Single mode: `wt-figma-fetch <figma-url> -o <dir>` — fetch one
  - `--force` flag to re-fetch even if snapshots exist
  - `--reprocess` flag to re-assemble from raw without MCP calls
  - Delegate to `python3 lib/design/fetcher.py`
  - Print summary (files found, fetched, sizes)

- [x] 6. URL discovery and combined snapshot
  - `scan_docs_for_figma_urls(docs_dir)` — scan `docs_dir/**/*.md` for Figma URLs
  - Regex: `https?://[\w.]*figma\.com/(file|design|make)/([A-Za-z0-9]+)`
  - Deduplicate by file key (same Figma file from multiple md files → one fetch)
  - Per-key output: `<docs_dir>/figma-raw/<file_key>/` with raw + assembled snapshot
  - **Combined output**: concatenate all per-file snapshots → `./design-snapshot.md` (project root)
  - This is what the entire pipeline reads — planner L1276, dispatcher, verifier, engine all use CWD

## Phase 4: Planner integration

- [x] 7. Simplify `_fetch_design_context()` in `lib/set_orch/planner.py`
  - Keep the cache-read branch (L1275-1282): `os.path.isfile("design-snapshot.md")` → read + return
  - Remove L1284-1341: MCP detection, bridge.sh subprocess, 1800s timeout, RuntimeError
  - The `force` param becomes no-op (keep for signature compat)
  - Log info if no snapshot found: "Run wt-figma-fetch docs/ to fetch"
  - **No changes needed** in dispatcher.py, verifier.py, engine.py, templates.py, bridge.sh

## Phase 5: Testing and docs

- [x] 8. Manual integration test
  - Run `wt-figma-fetch` against a Make file URL (single mode)
  - Verify `figma-raw/<key>/` has raw MCP responses (metadata.json, hierarchy.json, sources/)
  - Verify per-file `design-snapshot.md` has structured hierarchy with Tailwind classes
  - Run `wt-figma-fetch docs/` (scan mode) and verify combined `./design-snapshot.md`
  - Verify `--reprocess` re-assembles without MCP calls
  - Verify planner reads the committed snapshot without attempting MCP calls

- [x] 9. Update docs
  - Add `wt-figma-fetch` to `docs/cli-reference.md`
  - Update `docs/orchestration.md` design section to reflect committed-snapshot model
  - Note that `figma-raw/` directories are committed artifacts, re-fetched only on design changes
