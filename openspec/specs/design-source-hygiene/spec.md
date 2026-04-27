# design-source-hygiene Specification

## Purpose
TBD - created by archiving change design-binding-completeness. Update Purpose after archive.
## Requirements
### Requirement: 9 hygiene rules detect common design-source antipatterns
The hygiene scanner SHALL implement 9 quality rules:

1. **MOCK arrays inline** — detect `const MOCK_*`, `FAKE_*`, `STUB_*` array declarations in component bodies → CRITICAL ("data injection prep needed")
2. **Hardcoded UI strings** — string literals (≥3 alphabetic chars, NOT in `aria-*`/`data-*` attrs, NOT in JSX attribute values) inside JSX bodies → WARN ("i18n leakage")
3. **Placeholder action handlers** — `// TODO`, `// FIXME`, `// implement`, `// Add ... logic` comments inside event-handler arrow functions → WARN
4. **Inconsistent shell adoption** — if ≥70% of pages import a given shell component AND the remaining pages do NOT → CRITICAL ("inconsistent header/shell adoption")
5. **Mock URL images** — `<Image src="..."/>` URLs matching `unsplash.com`, `picsum.photos`, `placeholder.com`, `placehold.co` → INFO ("placeholder images")
6. **Inline lambda action handlers** — `onClick={() => { ... }}` with ≥3 lines of body → INFO ("consider prop callback")
7. **TypeScript `any` usage** — `: any`, `as any` in `.tsx` files outside of type-assertion edge cases → WARN
8. **Broken route references** — `<Link href="/foo">` literal where `/foo` is not in `manifest.routes` → CRITICAL
9. **Locale-prefix inconsistency** — HU page importing/linking to EN-only path (or vice versa) → WARN

#### Scenario: MOCK array detected
- **GIVEN** `v0-export/components/search-palette.tsx` declares `const MOCK_PRODUCTS = [...]`
- **WHEN** `set-design-hygiene` runs
- **THEN** the output contains a CRITICAL finding: "MOCK arrays inline — components/search-palette.tsx:40 declares MOCK_PRODUCTS"
- **AND** suggests "Replace with prop-based data injection (`results?: SearchResult[]`)"

#### Scenario: Header inconsistency detected
- **GIVEN** 10 of 24 pages import `SiteHeader` and 14 do not
- **WHEN** the scanner runs
- **THEN** a CRITICAL finding lists the 14 pages without import
- **AND** suggests "Move `<SiteHeader />` to `app/layout.tsx`"

#### Scenario: Broken route detected
- **GIVEN** `<Link href="/loginnn">` in a TSX file
- **AND** the manifest has no `/loginnn` route
- **THEN** a CRITICAL finding fires
- **AND** suggests the closest match (`/login` or `/belepes`) from manifest

#### Scenario: Hardcoded HU string detected
- **GIVEN** `<Button>Kosárba</Button>` in a component
- **WHEN** scanner runs
- **THEN** a WARN finding for that string with file:line reference

### Requirement: Markdown checklist output
The scanner SHALL output a markdown file (default `docs/design-source-hygiene-checklist.md`) containing a project-id heading, a generation timestamp, finding count, and three checklist sections — CRITICAL (blocks design adoption), WARN (degrades agent quality), INFO (potential cleanup) — each with one item per finding using the format `<rule name> — <file>:<line>` plus a short description and suggested fix.

#### Scenario: Output file location
- **WHEN** `set-design-hygiene` runs in a project
- **THEN** by default writes to `docs/design-source-hygiene-checklist.md`
- **AND** with `--output <path>` writes to the given path

#### Scenario: CRITICAL findings cause non-zero exit
- **WHEN** any CRITICAL findings are present
- **THEN** the CLI exits with code 1
- **AND** the operator can opt-in pass with `--ignore-critical` for force-run

### Requirement: --with-hygiene flag on set-design-import
The `set-design-import` CLI (existing) SHALL accept an optional `--with-hygiene` flag. When set, after manifest regeneration, the CLI SHALL run the hygiene scanner and write the checklist as a post-step.

#### Scenario: Combined import + hygiene
- **WHEN** `set-design-import --git <url> --ref main --with-hygiene` runs
- **THEN** import completes, manifest regenerated, hygiene scan runs, checklist written
- **AND** if any CRITICAL finding, the import command exits with code 1

#### Scenario: Default off
- **WHEN** `set-design-import` runs without `--with-hygiene`
- **THEN** no hygiene scan is performed
- **AND** import behaves as today

