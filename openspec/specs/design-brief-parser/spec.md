# Spec: Design Brief Parser

## ADDED Requirements

## IN SCOPE
- Parsing Figma Make prompt files (figma.md) into structured per-page design briefs
- Extracting page names, visual descriptions, layout specs, component details from prompt sections
- Generating design-brief.md with standardized `## Page: <name>` structure
- Integration with existing `set-design-sync` CLI and `DesignSystem` data model

## OUT OF SCOPE
- Lovable or other future design tool bridges (separate changes)
- shadcn/ui parsing (covered by shadcn-ui-design-connector change)
- Figma MCP runtime fetching (existing fetcher.py handles this)
- Modifying the design-system.md token format

### Requirement: Parse Figma Make prompt files

The system SHALL parse `figma.md` files containing Figma Make prompt collections into structured design data. Each numbered section (`## N. TITLE`) followed by a fenced code block SHALL be recognized as a page design prompt.

#### Scenario: Parse well-structured figma.md
- **WHEN** `FigmaMakePromptParser.parse()` is called with a `figma.md` file
- **AND** the file contains sections like `## 2. HOMEPAGE — DESKTOP (1280px)` with fenced code blocks
- **THEN** each section is parsed into a `PageSpec` with extracted page name and visual description
- **AND** the section title is normalized to a page name matching design-system.md conventions (e.g., "HOMEPAGE — DESKTOP" → "Home")

#### Scenario: Extract design tokens from prompt content
- **WHEN** a prompt section contains color values (e.g., `#78350F`), font names, or spacing values
- **THEN** these are extracted into the `DesignSystem.tokens` structure
- **AND** duplicate tokens across sections are deduplicated

#### Scenario: Handle combined desktop+mobile sections
- **WHEN** separate sections exist for desktop and mobile versions of the same page (e.g., "HOMEPAGE — DESKTOP" and "HOMEPAGE — MOBILE")
- **THEN** both are merged into a single `PageSpec` with desktop and mobile subsections

#### Scenario: Skip non-page sections
- **WHEN** the file contains instructional sections (e.g., "Hogyan használd", "Lépések")
- **THEN** these sections are skipped and not included in the parsed output

### Requirement: Generate design-brief.md output

The system SHALL generate a `design-brief.md` file with per-page visual descriptions in a standardized format that the dispatcher can scope-match against change names.

#### Scenario: Generate brief with page sections
- **WHEN** `DesignSystem.to_brief_markdown()` is called
- **THEN** the output contains `## Page: <name>` sections for each parsed page
- **AND** each section contains the condensed visual description (layout, components, colors, responsive notes)
- **AND** page names match the names used in design-system.md Page Layouts (e.g., "Home", "ProductCatalog", "Login")

#### Scenario: Brief content preserves actionable detail
- **WHEN** a page section is generated
- **THEN** it preserves concrete design values: pixel dimensions, color hex codes, exact CTA text, component counts, grid column counts
- **AND** removes Figma Make meta-instructions ("Create a design...", "Design the...")
- **AND** the output is suitable for an implementing agent to build from

#### Scenario: set-design-sync outputs both files
- **WHEN** `set-design-sync --input figma.md --spec-dir docs/` is run
- **THEN** `design-system.md` is generated with tokens and component index (lean)
- **AND** `design-brief.md` is generated alongside with full visual descriptions
- **AND** both files are written to the output directory
