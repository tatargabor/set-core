# Tasks: design-make-parser

## 1. Design Parser Module

- [x] 1.1 Create `lib/set_orch/design_parser.py` with `DesignSystem` dataclass: `tokens` (dict with colors, typography, spacing, radii, container), `components` (list of ComponentSpec: name, properties, layout_notes), `pages` (list of PageSpec: name, sections, components_used, layout_description), `images` (list of ImageRef: context, query) [REQ: REQ-MAKE-PARSE]
- [x] 1.2 Create `DesignParser` ABC with `parse(path: str) -> DesignSystem` and `detect(path: str) -> bool` class methods. Add `get_parser(path: str) -> DesignParser` factory that checks file extension and magic bytes [REQ: REQ-MAKE-EXTENSIBLE]
- [x] 1.3 Implement `MakeParser(DesignParser)`: unzip .make file to temp dir, read `ai_chat.json`, extract `write_tool` calls from messages, categorize by file path (styles/, components/, pages/) [REQ: REQ-MAKE-PARSE]
- [x] 1.4 Token extraction in MakeParser: find `theme.css` or `*.css` with CSS custom properties, parse `--color-*`, `--font-*`, `--spacing-*`, `--radius-*`, `--text-*`, `--container-*` values into tokens dict [REQ: REQ-MAKE-PARSE]
- [x] 1.5 Component extraction in MakeParser: find `*.tsx` files in components/ path, extract component name from filename, parse key visual props (colors, sizes referenced), extract layout structure (flex/grid, column count) from JSX [REQ: REQ-MAKE-PARSE]
- [x] 1.6 Page extraction in MakeParser: find `*.tsx` files in pages/ or app/ path, extract page name, identify sections (by comment blocks or component usage), list components used per section [REQ: REQ-MAKE-PARSE]
- [x] 1.7 Image extraction in MakeParser: find `unsplash_tool` calls in ai_chat messages, extract query strings, associate with context (hero, product, story, etc.) based on surrounding write_tool calls [REQ: REQ-MAKE-PARSE]
- [x] 1.8 Font extraction in MakeParser: find `fonts.css` or Google Fonts import URLs, extract font family names and weights [REQ: REQ-MAKE-PARSE]
- [x] 1.9 Implement `PassthroughParser(DesignParser)`: for `.md` files with frontmatter `type: design-system`, return content as-is (already structured) [REQ: REQ-MAKE-EXTENSIBLE]
- [x] 1.10 Implement `DesignSystem.to_markdown() -> str` renderer: generates structured design-system.md with sections Design Tokens, Components, Page Layouts, Image References. Target under 300 lines [REQ: REQ-MAKE-FORMAT]

## 2. Spec Sync Logic

- [x] 2.1 Add `sync_specs(design: DesignSystem, spec_dir: str, dry_run: bool = False) -> list[str]` function to design_parser.py: scans spec_dir for .md files, matches page/feature keywords, adds/replaces `## Design Reference` sections. Returns list of modified file paths [REQ: REQ-SPEC-SYNC]
- [x] 2.2 Implement keyword matching: map keywords to design pages — {"homepage": ["homepage", "home", "landing", "főoldal"], "catalog": ["catalog", "listing", "products", "kávék"], "cart": ["cart", "basket", "kosár"], ...}. Match case-insensitive against full spec content [REQ: REQ-SPEC-SYNC]
- [x] 2.3 Implement `## Design Reference` section generation: for each matched page, include page name, layout summary (from DesignSystem.pages), critical tokens (primary color, heading font, key spacing), reference to design-system.md section number [REQ: REQ-SPEC-SYNC]
- [x] 2.4 Implement marker-based replacement: find existing `## Design Reference` heading, replace everything until next `## ` or EOF. If not found, append to end. Preserve all other content and frontmatter [REQ: REQ-SPEC-PRESERVE, REQ-SPEC-IDEMPOTENT]

## 3. CLI Tool

- [x] 3.1 Create `bin/set-design-sync` bash script: parse args (--input, --spec-dir, --output, --dry-run, --format), validate paths exist, call Python parser via `python3 -m set_orch.design_parser` [REQ: REQ-MAKE-CLI]
- [x] 3.2 Add `__main__` block to `design_parser.py`: accept CLI args, run parse + render + sync pipeline, print summary (files generated, specs updated) [REQ: REQ-MAKE-CLI]
- [x] 3.3 Add `set-design-sync` to PATH (create symlink or add to bin/ directory alongside other set-* tools) [REQ: REQ-MAKE-CLI]

## 4. Dispatcher Fallback

- [x] 4.1 Update `design_context_for_dispatch()` in `lib/design/bridge.sh`: before reading design-snapshot.md, check for `docs/design-system.md` (or other common locations: `design-system.md`, `docs/design/design-system.md`). If found and contains `## Design Tokens`, use it as primary source [REQ: REQ-DISPATCH-FALLBACK]
- [x] 4.2 Update page matching logic: when using design-system.md, match `### PageName` subsections under `## Page Layouts` against scope text. Always include `## Design Tokens` section. Truncate at 200 lines [REQ: REQ-DISPATCH-PAGE-MATCH]

## 5. Documentation

- [x] 5.1 Create `docs/guide/design-integration.md`: full guide covering why design context matters, supported sources (.make, manual), step-by-step workflow (Figma Make → export → set-design-sync → verify → sentinel), design-system.md format, how design references appear in specs, updating design, troubleshooting [REQ: REQ-DOCS-GUIDE]
- [x] 5.2 Add "## Pre-Run Checklist" section to `docs/guide/orchestration.md`: items include spec quality review, design sync if Figma exists, config review, project health audit. Emphasize spec quality = output quality [REQ: REQ-DOCS-ORCHESTRATION]
- [x] 5.3 Add "## Spec Quality Prerequisites" section to `docs/guide/sentinel.md`: what makes a good spec, importance of concrete design values, link to design-integration.md, warning about vague specs producing generic results [REQ: REQ-DOCS-SENTINEL]

## Acceptance Criteria

- [x] AC-1: WHEN `set-design-sync --input test.make --spec-dir docs/` is run on a valid .make file THEN docs/design-system.md is generated with Design Tokens, Components, Page Layouts, and Image References sections [REQ: REQ-MAKE-PARSE, REQ-MAKE-FORMAT]
- [x] AC-2: WHEN a spec file mentions "homepage" THEN a `## Design Reference` section is added referencing the homepage layout from design-system.md [REQ: REQ-SPEC-SYNC]
- [x] AC-3: WHEN set-design-sync is run twice with same input THEN output is identical [REQ: REQ-SPEC-IDEMPOTENT]
- [x] AC-4: WHEN design-system.md exists in docs/ THEN the dispatcher injects its tokens into agent context instead of the snapshot's Tailwind class statistics [REQ: REQ-DISPATCH-FALLBACK]
- [x] AC-5: WHEN an unsupported file format is given to --input THEN a clear error lists supported formats [REQ: REQ-MAKE-EXTENSIBLE]
- [x] AC-6: WHEN docs/guide/design-integration.md is deployed THEN it covers the full Figma Make → sentinel workflow [REQ: REQ-DOCS-GUIDE]
- [x] AC-7: WHEN docs/guide/orchestration.md is deployed THEN it has a Pre-Run Checklist mentioning design sync [REQ: REQ-DOCS-ORCHESTRATION]
- [x] AC-8: WHEN docs/guide/sentinel.md is deployed THEN it has a Spec Quality Prerequisites section [REQ: REQ-DOCS-SENTINEL]
