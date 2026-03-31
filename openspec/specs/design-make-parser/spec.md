# Spec: Design Make Parser

## Status: new

## Requirements

### REQ-MAKE-PARSE: Parse .make files into structured design-system.md
- The parser SHALL accept a `.make` file path as input
- It SHALL unzip the `.make` file (which is a ZIP archive) and read `ai_chat.json`
- It SHALL extract `write_tool` calls from the AI chat messages to find generated files
- It SHALL extract design tokens from `theme.css` or similar style files (CSS custom properties: colors, typography, spacing, radii)
- It SHALL extract component layouts from `*.tsx` files (Header, Footer, ProductCard, etc.) — component name, key props, layout structure
- It SHALL extract page layouts from `pages/*.tsx` or `app/**/*.tsx` — page name, sections, component usage
- It SHALL extract image references from `unsplash_tool` calls — query strings for placeholder images
- It SHALL extract font imports from `fonts.css` or equivalent
- Output: a structured `design-system.md` with sections: Design Tokens, Components, Page Layouts, Image References

### REQ-MAKE-FORMAT: design-system.md output format
- Section 1 "Design Tokens": CSS custom properties grouped by category (colors, typography, spacing, radii, container)
- Section 2 "Components": for each component — name, key visual properties (colors, sizes, border-radius), layout notes
- Section 3 "Page Layouts": for each page — name, sections list with layout description (column count, aspect ratios, alignment), key components used
- Section 4 "Image References": Unsplash query strings or placeholder URLs per context (hero, products, stories)
- Total output SHOULD be under 300 lines — concise enough for dispatch context

### REQ-MAKE-EXTENSIBLE: Support future input formats
- The parser SHALL use a format detection layer: check file extension and magic bytes
- `.make` → Figma Make parser
- `.md` with frontmatter `type: design-system` → passthrough (already structured)
- Unknown format → error with message listing supported formats
- Architecture: `DesignParser` base class with `parse(path) -> DesignSystem` method, `MakeParser(DesignParser)` for .make files

### REQ-MAKE-CLI: CLI interface
- Command: `set-design-sync --input <path> --spec-dir <path> [--output <path>]`
- `--input`: path to `.make` file or other supported design source (REQUIRED)
- `--spec-dir`: directory containing spec `.md` files to update with design references (REQUIRED)
- `--output`: path for generated `design-system.md` (default: same directory as `--input`)
- `--dry-run`: show what would change without writing
- `--format`: force input format (auto-detect by default)
