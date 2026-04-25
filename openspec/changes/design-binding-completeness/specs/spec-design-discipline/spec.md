## ADDED Requirements

## IN SCOPE
- Strict anti-pattern detection in write-spec skill (BLOCK on visual descriptors).
- Required entity-reference markers (`@component:`, `@route:`) for any UI feature.
- Operator opt-in migration of legacy specs via `set-spec-clean-design` CLI.
- Grandfather clause: existing specs not blocked unless explicit re-write.

## OUT OF SCOPE
- Auto-correction of spec content (LLM rewrites are operator-triggered, not automatic).
- Enforcement at decompose-time of specs from old projects (legacy specs grandfathered).
- Cross-project spec audits.

### Requirement: Strict anti-pattern detection in write-spec
The `/set:write-spec` skill's anti-pattern detector SHALL include the following severity-tiered checks for any requirement scenario or section body:

| Pattern | Severity |
|---|---|
| Hex/rgb/rgba/oklch color literal (e.g., `#78350F`, `rgb(...)`) | BLOCK |
| Shadcn primitive component name (`<Button>`, `<Card>`, `<Input>`, `<Sheet>`, `<CommandDialog>`, etc.) | BLOCK |
| PascalCase TSX component name (`SiteHeader`, `ProductCard`) | WARN |
| Layout descriptor (`modal`, `dropdown`, `sidebar`, `popup`, `dialog`, `popover`) | WARN |
| Tailwind className (`bg-primary`, `text-muted-foreground`) | BLOCK |
| File path containing `.tsx`, `src/`, `components/` | BLOCK |
| UI feature with NO `@component:` or `@route:` reference | WARN |

#### Scenario: Color literal blocks spec save
- **GIVEN** an operator writes a requirement: `Button background uses #78350F`
- **WHEN** they attempt to save the spec via write-spec
- **THEN** the skill blocks the save and reports the offending line
- **AND** suggests using design tokens via design source manifest

#### Scenario: Shadcn primitive in requirement blocks save
- **GIVEN** a requirement says `Use <Button variant="ghost"> for the action`
- **WHEN** save is attempted
- **THEN** the save is blocked
- **AND** the suggestion: "Reference @component:NAME instead — components and styling live in the design source"

#### Scenario: UI feature without entity reference triggers warn
- **GIVEN** a requirement reads `Users can search products` with no `@component:` or `@route:` marker
- **WHEN** validated
- **THEN** the skill emits a WARN: "UI feature lacks entity reference. Add @component:search-palette or @route:/kereses to bind."

#### Scenario: Operator can override with grandfather comment
- **GIVEN** an existing spec in a legacy project has `Use shadcn Command/Popover pattern`
- **WHEN** the operator does NOT want to migrate
- **THEN** they can add `<!-- design-discipline-exempt -->` HTML comment on the line
- **AND** the lint emits no error (downgraded to silent)

### Requirement: Optional spec migration via set-spec-clean-design CLI
A new CLI `set-spec-clean-design` SHALL be available (off by default) that uses an LLM to extract visual descriptions from existing spec files and produce:
1. A cleaned spec (visual content removed, entity-reference markers inserted)
2. A separate `docs/design-references.md` archiving the extracted visual descriptions

#### Scenario: Migrate a legacy spec
- **GIVEN** `docs/specs/catalog-search.md` contains "shadcn Command/Popover dropdown with two sections"
- **WHEN** operator runs `set-spec-clean-design docs/specs/catalog-search.md`
- **THEN** the CLI proposes a diff:
  - Spec body becomes: "Users can search products and stories. @component:search-palette displays results in two sections."
  - `docs/design-references.md` archives: "search-palette is the visual entity (was: shadcn Command/Popover)"
- **AND** the operator can accept, edit, or reject the diff

#### Scenario: Default off in scaffolds
- **WHEN** a new project is scaffolded via `set-project init`
- **THEN** `set-spec-clean-design` is NOT invoked automatically
- **AND** the lint defaults are STRICT for new specs
