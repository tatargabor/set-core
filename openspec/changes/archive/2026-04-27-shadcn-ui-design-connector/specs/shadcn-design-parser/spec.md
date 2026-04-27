## ADDED Requirements

## IN SCOPE
- Parse `components.json` to extract shadcn/ui configuration (style, base color, CSS variables flag, aliases)
- Parse `tailwind.config.ts` / `tailwind.config.js` to extract `theme.extend` tokens (colors, fonts, spacing, radius, shadows)
- Parse `globals.css` (or configured CSS file) to extract CSS custom properties (`:root` and `.dark` blocks)
- Scan `src/components/ui/` directory to build installed component catalog (component name, file path)
- Generate `design-snapshot.md` in the same format consumed by bridge.sh (`## Design Tokens`, `## Component Hierarchy`)
- Handle Tailwind v3 (`theme.extend` in JS config) and Tailwind v4 (`@theme` in CSS) token locations

## OUT OF SCOPE
- Extracting component props/variants via AST parsing (catalog lists installed components only)
- Generating visual screenshots or references (no rendering engine)
- Modifying or writing back to shadcn/ui config files (read-only)
- Supporting non-shadcn Tailwind projects (detection requires `components.json`)
- Real-time file watching or incremental updates (snapshot is point-in-time)

### Requirement: Parse shadcn/ui configuration
The parser SHALL read `components.json` from the project root and extract the shadcn/ui configuration including style variant, base color, CSS variables flag, Tailwind config path, CSS file path, and component aliases.

#### Scenario: Valid components.json present
- **WHEN** `components.json` exists in the project root and contains valid JSON with a `tailwind` section
- **THEN** the parser extracts `style`, `tailwind.baseColor`, `tailwind.cssVariables`, `tailwind.config`, and `tailwind.css` values
- **AND** uses `tailwind.config` and `tailwind.css` paths to locate the corresponding files

#### Scenario: components.json missing or invalid
- **WHEN** `components.json` does not exist or lacks a `tailwind` section
- **THEN** the parser returns an error result indicating shadcn/ui is not detected
- **AND** does not attempt to parse Tailwind config or CSS files

### Requirement: Extract Tailwind theme tokens
The parser SHALL extract design tokens from the Tailwind configuration file. For Tailwind v3, this means parsing `theme.extend` from the JavaScript/TypeScript config. For Tailwind v4, this means parsing `@theme` blocks in the CSS file.

#### Scenario: Tailwind v3 config with theme.extend
- **WHEN** `tailwind.config.ts` (or `.js`) exists and contains `theme: { extend: { ... } }`
- **THEN** the parser extracts color definitions, font families, font sizes, spacing values, border radius values, and box shadows
- **AND** outputs them under `## Design Tokens` with subsections for each token category

#### Scenario: Tailwind v4 CSS-based config
- **WHEN** the CSS file contains `@theme { ... }` blocks (Tailwind v4 style)
- **THEN** the parser extracts `--color-*`, `--font-*`, `--spacing-*`, `--radius-*` declarations
- **AND** outputs them under `## Design Tokens` in the same format as v3 tokens

#### Scenario: No Tailwind config found
- **WHEN** neither `tailwind.config.ts` nor `tailwind.config.js` exists, and the CSS file has no `@theme` block
- **THEN** the parser falls back to CSS custom properties only (from `:root` block in globals.css)

### Requirement: Extract CSS custom properties
The parser SHALL extract CSS custom properties defined in `:root` and `.dark` selectors from the project's global CSS file.

#### Scenario: CSS variables in globals.css
- **WHEN** the global CSS file (path from `components.json` or default `src/app/globals.css`) contains `:root { --background: ...; --foreground: ...; }`
- **THEN** the parser extracts all `--*` properties and their values
- **AND** groups them by semantic category (colors, radius, spacing) based on naming convention

#### Scenario: Dark mode variables
- **WHEN** the CSS file contains a `.dark` selector with CSS custom properties
- **THEN** the parser extracts dark mode overrides as a separate subsection under Design Tokens

### Requirement: Build component catalog
The parser SHALL scan the shadcn/ui component directory to identify installed components.

#### Scenario: Components installed in ui/ directory
- **WHEN** the component directory (derived from `components.json` aliases or default `src/components/ui/`) contains `.tsx` or `.ts` files
- **THEN** the parser lists each component by name (derived from filename) under `## Component Hierarchy`
- **AND** groups them as "UI Library Components" (consistent with Figma fetcher format)

### Requirement: Generate design-snapshot.md
The parser SHALL produce a `design-snapshot.md` file compatible with the existing bridge.sh consumption functions (`design_context_for_dispatch`, `build_design_review_section`).

#### Scenario: Complete snapshot generation
- **WHEN** all parsing steps complete (config + tokens + CSS vars + components)
- **THEN** the output file contains: metadata header (source: shadcn/ui, type: local), `## Design Tokens` section, `## Component Hierarchy` section
- **AND** the `## Design Tokens` section uses the same subsection headers the bridge expects (Colors, Typography, Spacing, Radius, Shadows)

#### Scenario: Partial data available
- **WHEN** some sources are missing (e.g., no Tailwind config but CSS vars exist)
- **THEN** the parser generates a snapshot with available sections only
- **AND** includes a note listing which sources were not found
