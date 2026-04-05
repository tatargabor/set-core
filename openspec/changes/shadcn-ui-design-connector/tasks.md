# Tasks: shadcn/ui Design Connector

## 1. Parser Core

- [ ] 1.1 Create `lib/design/shadcn_parser.py` with main `parse_shadcn_project(project_root) -> str` entry point [REQ: parse-shadcn-ui-configuration]
- [ ] 1.2 Implement `components.json` parser — extract style, baseColor, cssVariables, tailwind config path, CSS file path, aliases [REQ: parse-shadcn-ui-configuration]
- [ ] 1.3 Implement Tailwind v3 config parser — regex extraction of `theme.extend` colors, fontFamily, fontSize, spacing, borderRadius, boxShadow from `.ts`/`.js` config [REQ: extract-tailwind-theme-tokens]
- [ ] 1.4 Implement Tailwind v4 CSS parser — extract `@theme { ... }` block declarations (`--color-*`, `--font-*`, `--spacing-*`, `--radius-*`) [REQ: extract-tailwind-theme-tokens]
- [ ] 1.5 Implement CSS custom properties parser — extract `:root` and `.dark` selector variables from globals.css [REQ: extract-css-custom-properties]
- [ ] 1.6 Implement component catalog scanner — list `.tsx`/`.ts` files in ui/ directory, extract component names from filenames [REQ: build-component-catalog]

## 2. Snapshot Generation

- [ ] 2.1 Implement `generate_snapshot()` — assemble `design-snapshot.md` with metadata header (`Source: shadcn-ui`, `Type: local`), `## Design Tokens` sections (Colors, Typography, Spacing, Radius, Shadows), `## Component Hierarchy` section [REQ: generate-design-snapshot-md]
- [ ] 2.2 Handle partial data — generate snapshot with available sections when some sources missing, include note about missing sources [REQ: generate-design-snapshot-md]
- [ ] 2.3 Verify generated snapshot is parseable by `bridge.sh` functions (`design_context_for_dispatch`, `build_design_review_section`) [REQ: generate-design-snapshot-md]

## 3. Detection & Bridge Integration

- [ ] 3.1 Add `detect_shadcn_project()` function to `lib/design/bridge.sh` — check for `components.json` with valid `tailwind` section, return 0 + path or 1 [REQ: detect-shadcn-ui-project]
- [ ] 3.2 Update `_fetch_design_context()` in `lib/set_orch/planner.py` — when `detect_design_mcp()` returns 1, call `detect_shadcn_project()` as fallback, invoke `shadcn_parser.py` if detected [REQ: preflight-integration]
- [ ] 3.3 Ensure MCP priority — verify that when both MCP and shadcn are available, MCP path is taken [REQ: preflight-integration]
- [ ] 3.4 Integrate caching — shadcn-generated snapshots use same cache path and freshness logic as MCP snapshots [REQ: snapshot-caching-in-state-directory]

## 4. Dispatch & Verify Compatibility

- [ ] 4.1 Verify `design_context_for_dispatch()` in bridge.sh correctly parses shadcn-generated snapshot (section headers match expectations) [REQ: req-dispatch-fallback]
- [ ] 4.2 Verify `build_design_review_section()` in bridge.sh works with shadcn snapshot (token extraction for verify gate) [REQ: req-dispatch-fallback]
- [ ] 4.3 Update fallback chain documentation in bridge.sh comments to include shadcn path [REQ: req-dispatch-fallback]

## 5. Tests

- [ ] 5.1 Unit tests for `shadcn_parser.py` — test components.json parsing, Tailwind v3 extraction, Tailwind v4 extraction, CSS vars extraction, component catalog scan [REQ: parse-shadcn-ui-configuration]
- [ ] 5.2 Unit tests for partial data scenarios — missing tailwind config, missing CSS vars, empty components dir [REQ: generate-design-snapshot-md]
- [ ] 5.3 Unit test for `detect_shadcn_project()` in bridge.sh — positive and negative detection [REQ: detect-shadcn-ui-project]
- [ ] 5.4 Integration test — end-to-end from project root with shadcn/ui files to valid design-snapshot.md consumed by bridge functions [REQ: generate-design-snapshot-md]

## 6. E2E Scaffold

- [ ] 6.1 Create shadcn/ui fixture files for testing — sample `components.json`, `tailwind.config.ts` (v3), CSS with `:root` vars, minimal `src/components/ui/` directory with 3-4 component files [REQ: parse-shadcn-ui-configuration]
- [ ] 6.2 Add fixture for Tailwind v4 variant — CSS file with `@theme` block instead of JS config [REQ: extract-tailwind-theme-tokens]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN `components.json` exists with valid `tailwind` section THEN parser extracts style, baseColor, cssVariables, config and css paths [REQ: parse-shadcn-ui-configuration, scenario: valid-components-json-present]
- [ ] AC-2: WHEN `components.json` missing or invalid THEN parser returns error, does not attempt further parsing [REQ: parse-shadcn-ui-configuration, scenario: components-json-missing-or-invalid]
- [ ] AC-3: WHEN tailwind.config has `theme.extend` THEN parser extracts colors, fonts, spacing, radius, shadows as Design Tokens [REQ: extract-tailwind-theme-tokens, scenario: tailwind-v3-config-with-theme-extend]
- [ ] AC-4: WHEN CSS file has `@theme` block THEN parser extracts `--color-*`, `--font-*`, `--spacing-*`, `--radius-*` declarations [REQ: extract-tailwind-theme-tokens, scenario: tailwind-v4-css-based-config]
- [ ] AC-5: WHEN no tailwind config and no `@theme` block THEN parser falls back to `:root` CSS custom properties [REQ: extract-tailwind-theme-tokens, scenario: no-tailwind-config-found]
- [ ] AC-6: WHEN globals.css has `:root` and `.dark` selectors THEN parser extracts both light and dark mode variables [REQ: extract-css-custom-properties, scenario: dark-mode-variables]
- [ ] AC-7: WHEN ui/ directory has .tsx files THEN parser lists components by name under Component Hierarchy [REQ: build-component-catalog, scenario: components-installed-in-ui-directory]
- [ ] AC-8: WHEN all parsing completes THEN snapshot has metadata, Design Tokens, and Component Hierarchy sections [REQ: generate-design-snapshot-md, scenario: complete-snapshot-generation]
- [ ] AC-9: WHEN some sources missing THEN snapshot has available sections plus missing-source note [REQ: generate-design-snapshot-md, scenario: partial-data-available]
- [ ] AC-10: WHEN no MCP but shadcn detected THEN planner generates snapshot via local parser [REQ: preflight-integration, scenario: no-mcp-but-shadcn-ui-present]
- [ ] AC-11: WHEN MCP registered and shadcn present THEN MCP fetch is used, shadcn parser not invoked [REQ: preflight-integration, scenario: mcp-takes-priority-over-local-detection]
- [ ] AC-12: WHEN shadcn snapshot in fallback chain THEN dispatch extracts Design Tokens and Component Hierarchy identically [REQ: req-dispatch-fallback, scenario: shadcn-generated-snapshot-in-fallback-chain]
