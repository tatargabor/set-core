# Spec: i18n Conventions

## Status: new

## Requirements

### REQ-I18N-TRANSLATION-KEYS: All user-facing strings must use translation keys
- Every user-visible string (labels, buttons, messages, errors, empty states) MUST use `t('key')` or equivalent — never hardcoded strings
- Units and measurements (piece, pinch, cup, etc.) MUST be translatable — add unit translation maps
- Pipeline/system messages shown to users (warnings, notes, status text) MUST be translated
- Seed data content (story text, descriptions) MUST have translations for all supported locales

### REQ-I18N-SIDECAR-RESILIENCE: Sidecar imports must be crash-resistant
- When using i18n sidecar files (per-change message files merged during archive), ALL sidecar imports MUST be wrapped in try/catch
- Pattern: `try { sidecar = await import('./messages/xx.feature.json') } catch { sidecar = {} }`
- After archive merges sidecar content into base message files, the import failing must not crash the app

### REQ-I18N-LANGUAGE-SWITCHER: Language switching must work without JS hydration
- Language/locale switchers MUST use `<Link>` with locale prop (renders `<a>` tag), NOT `<button onClick>` with `router.replace()`
- Reason: under E2E load or slow connections, React hydration may be delayed, leaving `<button>` inert
- This applies to both desktop and mobile navigation variants

### REQ-I18N-DYNAMIC-ROUTES: next-intl dynamic route Link format
- When using next-intl pathnames (locale-dependent URLs), dynamic `<Link>` hrefs MUST use object format: `{ pathname: '/products/[slug]', params: { slug } }`
- String interpolation (`/products/${slug}`) crashes with "Insufficient params provided for localized pathname"
- Language switcher on dynamic pages must use `next/navigation` `usePathname()` (returns real URL), not next-intl `usePathname()` (returns template path)

### REQ-I18N-E2E-LOCALE: E2E tests must set browser locale
- Playwright config MUST set `use.locale` matching the project's primary locale (e.g., `hu-HU`)
- Without this, next-intl may redirect to unexpected locale paths, breaking test assertions
- Test assertions on user-visible text must match the active locale's translations

### REQ-I18N-MIDDLEWARE: i18n middleware must exclude API routes
- next-intl middleware matcher MUST exclude `/api/**` routes — not just `/api/auth`
- If i18n middleware runs on API routes, it may redirect or rewrite them, breaking client-side fetches (e.g., profile/address saves returning HTML instead of JSON)
