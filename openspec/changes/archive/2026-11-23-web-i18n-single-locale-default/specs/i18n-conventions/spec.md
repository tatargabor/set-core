## ADDED Requirements

### Requirement: Applicability
The requirements in this specification SHALL apply ONLY to projects in `i18n.mode: multi` (as resolved via `get_i18n_mode(project_path)` defined in the `web-template-i18n-modes` capability). Projects in `i18n.mode: single` SHALL instead follow the typed copy module pattern defined in `web-template-i18n-modes`. Projects with no `i18n.mode` declared (legacy projects) SHALL be treated as multi-mode and SHALL follow these requirements.

#### Scenario: Multi-mode project subject to these requirements
- **GIVEN** a project with `set/plugins/project-type.yaml` containing `i18n.mode: multi`
- **WHEN** the engine evaluates compliance with this specification
- **THEN** every requirement defined in this spec SHALL be evaluated against the project

#### Scenario: Single-mode project not subject to these requirements
- **GIVEN** a project with `set/plugins/project-type.yaml` containing `i18n.mode: single`
- **WHEN** the engine evaluates compliance with this specification
- **THEN** every requirement defined in this spec SHALL be skipped (the project follows `web-template-i18n-modes` instead)

#### Scenario: Legacy project treated as multi-mode
- **GIVEN** a project with `set/plugins/project-type.yaml` containing no `i18n.mode` key (predates this capability)
- **WHEN** the engine evaluates compliance with this specification
- **THEN** every requirement defined in this spec SHALL be evaluated (legacy projects retain current behavior)

## MODIFIED Requirements

### REQ-I18N-TRANSLATION-KEYS: All user-facing strings must use translation keys
**Applies to: projects with `i18n.mode: multi` (or legacy projects with no mode declared).**

- Every user-visible string (labels, buttons, messages, errors, empty states) MUST use `t('key')` or equivalent — never hardcoded strings
- Units and measurements (piece, pinch, cup, etc.) MUST be translatable — add unit translation maps
- Pipeline/system messages shown to users (warnings, notes, status text) MUST be translated
- Seed data content (story text, descriptions) MUST have translations for all supported locales

#### Scenario: Multi-mode component uses translation key
- **GIVEN** a multi-mode project
- **WHEN** a component renders a user-visible string
- **THEN** the source SHALL invoke `t('namespace.key')` rather than embed a hardcoded literal

#### Scenario: Single-mode component exempt
- **GIVEN** a single-mode project
- **WHEN** a component renders a user-visible string
- **THEN** this requirement SHALL NOT apply (the typed copy module requirement in `web-template-i18n-modes` applies instead)

### REQ-I18N-SIDECAR-RESILIENCE: Sidecar imports must be crash-resistant
**Applies to: projects with `i18n.mode: multi` (or legacy projects with no mode declared).**

- When using i18n sidecar files (per-change message files merged during archive), ALL sidecar imports MUST be wrapped in try/catch
- Pattern: `try { sidecar = await import('./messages/xx.feature.json') } catch { sidecar = {} }`
- After archive merges sidecar content into base message files, the import failing must not crash the app

#### Scenario: Multi-mode sidecar import is wrapped
- **GIVEN** a multi-mode project's `src/i18n/request.ts` imports a sidecar file
- **WHEN** the import is evaluated
- **THEN** the import expression SHALL be inside a try/catch block

#### Scenario: Single-mode project has no sidecars
- **GIVEN** a single-mode project
- **WHEN** the engine evaluates this requirement
- **THEN** the requirement SHALL NOT apply (single-mode projects have no `messages/` directory and no sidecar pattern)

### REQ-I18N-LANGUAGE-SWITCHER: Language switching must work without JS hydration
**Applies to: projects with `i18n.mode: multi` (or legacy projects with no mode declared).**

- Language/locale switchers MUST use `<Link>` with locale prop (renders `<a>` tag), NOT `<button onClick>` with `router.replace()`
- Reason: under E2E load or slow connections, React hydration may be delayed, leaving `<button>` inert
- This applies to both desktop and mobile navigation variants

#### Scenario: Multi-mode language switcher uses Link
- **GIVEN** a multi-mode project with a language switcher component
- **WHEN** the switcher is rendered
- **THEN** it SHALL use `<Link href=… locale={otherLocale}>` rather than a button with `router.replace`

#### Scenario: Single-mode project has no language switcher
- **GIVEN** a single-mode project
- **WHEN** the engine evaluates this requirement
- **THEN** the requirement SHALL NOT apply (single-mode projects do not expose locale switching)

### REQ-I18N-DYNAMIC-ROUTES: next-intl dynamic route Link format
**Applies to: projects with `i18n.mode: multi` (or legacy projects with no mode declared).**

- When using next-intl pathnames (locale-dependent URLs), dynamic `<Link>` hrefs MUST use object format: `{ pathname: '/products/[slug]', params: { slug } }`
- String interpolation (`/products/${slug}`) crashes with "Insufficient params provided for localized pathname"
- Language switcher on dynamic pages must use `next/navigation` `usePathname()` (returns real URL), not next-intl `usePathname()` (returns template path)

#### Scenario: Multi-mode dynamic route uses object href
- **GIVEN** a multi-mode project rendering a dynamic-route Link
- **WHEN** the Link points to a parameterized pathname
- **THEN** the `href` SHALL be `{ pathname, params }` rather than a string literal

#### Scenario: Single-mode project does not use next-intl pathnames
- **GIVEN** a single-mode project
- **WHEN** the engine evaluates this requirement
- **THEN** the requirement SHALL NOT apply

### REQ-I18N-E2E-LOCALE: E2E tests must set browser locale
**Applies to: projects with `i18n.mode: multi` (or legacy projects with no mode declared).**

- Playwright config MUST set `use.locale` matching the project's primary locale (e.g., `hu-HU`)
- Without this, next-intl may redirect to unexpected locale paths, breaking test assertions
- Test assertions on user-visible text must match the active locale's translations

#### Scenario: Multi-mode Playwright config sets locale
- **GIVEN** a multi-mode project's `playwright.config.ts`
- **WHEN** the config is loaded
- **THEN** `use.locale` SHALL be set to a non-empty BCP-47 string

#### Scenario: Single-mode Playwright config follows PRIMARY_LOCALE
- **GIVEN** a single-mode project's `playwright.config.ts`
- **WHEN** the config is loaded
- **THEN** the requirement under this spec SHALL NOT apply; instead `playwright.config.ts` SHOULD set `use.locale` to `PRIMARY_LOCALE` from `@/copy/locale` (governed by `web-template-i18n-modes`)

### REQ-I18N-MIDDLEWARE: i18n middleware must exclude API routes
**Applies to: projects with `i18n.mode: multi` (or legacy projects with no mode declared).**

- next-intl middleware matcher MUST exclude `/api/**` routes — not just `/api/auth`
- If i18n middleware runs on API routes, it may redirect or rewrite them, breaking client-side fetches (e.g., profile/address saves returning HTML instead of JSON)

#### Scenario: Multi-mode middleware excludes API routes
- **GIVEN** a multi-mode project's `src/middleware.ts`
- **WHEN** the matcher is evaluated
- **THEN** it SHALL match `'/((?!api|_next|.*\\..*).*)'` (or equivalent pattern) excluding all `/api` paths

#### Scenario: Single-mode project has no i18n middleware
- **GIVEN** a single-mode project
- **WHEN** the engine evaluates this requirement
- **THEN** the requirement SHALL NOT apply (single-mode projects do not register next-intl middleware)
