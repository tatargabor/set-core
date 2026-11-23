## MODIFIED Requirements

### Requirement: 9 hygiene rules detect common design-source antipatterns
The hygiene scanner SHALL implement 9 quality rules:

1. **MOCK arrays inline** — detect `const MOCK_*`, `FAKE_*`, `STUB_*` array declarations in component bodies → CRITICAL ("data injection prep needed")
2. **Hardcoded UI strings** — string literals (≥3 alphabetic chars, NOT in `aria-*`/`data-*` attrs, NOT in JSX attribute values) inside JSX bodies → WARN. The "leaked" target depends on `i18n.mode` (resolved via `get_i18n_mode(project_path)` from the `web-template-i18n-modes` capability):
   - **Multi mode** (or legacy projects with no mode declared): a string is leaked if it does not appear as a value in any `messages/*.json` file. Finding label: "i18n leakage".
   - **Single mode**: a string is leaked if it does not appear as a value in `src/copy/index.ts`. Finding label: "copy-module leakage".
3. **Placeholder action handlers** — `// TODO`, `// FIXME`, `// implement`, `// Add ... logic` comments inside event-handler arrow functions → WARN
4. **Inconsistent shell adoption** — if ≥70% of pages import a given shell component AND the remaining pages do NOT → CRITICAL ("inconsistent header/shell adoption")
5. **Mock URL images** — `<Image src="..."/>` URLs matching `unsplash.com`, `picsum.photos`, `placeholder.com`, `placehold.co` → INFO ("placeholder images")
6. **Inline lambda action handlers** — `onClick={() => { ... }}` with ≥3 lines of body → INFO ("consider prop callback")
7. **TypeScript `any` usage** — `: any`, `as any` in `.tsx` files outside of type-assertion edge cases → WARN
8. **Broken route references** — `<Link href="/foo">` literal where `/foo` is not in `manifest.routes` → CRITICAL
9. **Locale-prefix inconsistency** — HU page importing/linking to EN-only path (or vice versa) → WARN. This rule applies ONLY in multi mode; in single mode the project has no locale-prefixed routes and the rule SHALL be skipped.

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

#### Scenario: Hardcoded HU string detected (multi mode)
- **GIVEN** a multi-mode project with `<Button>Kosárba</Button>` in a component
- **AND** the string `"Kosárba"` is not present as a value in any `messages/*.json` file
- **WHEN** scanner runs
- **THEN** a WARN finding fires labelled "i18n leakage" with file:line reference

#### Scenario: Hardcoded string in single mode is checked against copy module
- **GIVEN** a single-mode project with `<Button>Add to cart</Button>` in a component
- **AND** the string `"Add to cart"` is not present as a value in `src/copy/index.ts`
- **WHEN** scanner runs
- **THEN** a WARN finding fires labelled "copy-module leakage" with file:line reference

#### Scenario: Single-mode string referenced via copy module is not a finding
- **GIVEN** a single-mode project with `<Button>{copy.cart.add}</Button>` in a component
- **AND** `src/copy/index.ts` contains `cart: { add: "Add to cart" }`
- **WHEN** scanner runs
- **THEN** no finding fires for this string

#### Scenario: Locale-prefix inconsistency detected in multi mode
- **GIVEN** a multi-mode project where a Hungarian-prefixed page imports an English-prefixed-only path
- **WHEN** scanner runs
- **THEN** a WARN finding fires for rule #9

#### Scenario: Locale-prefix rule skipped in single mode
- **GIVEN** a single-mode project (no `[locale]` route segment)
- **WHEN** scanner runs
- **THEN** rule #9 SHALL produce no findings (it is mode-skipped)
