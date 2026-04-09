---
paths:
  - "src/i18n/**"
  - "messages/**"
  - "src/middleware.*"
  - "src/components/**/Header*"
  - "src/components/**/Footer*"
  - "src/components/**/Nav*"
---
# i18n Conventions

## Translation Keys

- **Every** user-visible string (labels, buttons, messages, errors, empty states, tooltips) MUST use `t('key')` or the framework's equivalent — never hardcoded strings
- Units and measurements (piece, pinch, cup, gram, ml, etc.) MUST have translation maps — do not display English units to non-English users
- Pipeline/system messages shown to users (warnings, notes, status text) MUST be translated — if the source generates English strings, add a translation layer before display
- Seed data content (stories, descriptions, placeholder text) MUST have translations for all supported locales — do not seed with English-only content for a multilingual app

## No Hardcoded Locale Strings

Any call to `Intl.*`, `toLocaleString`, `toLocaleDateString`, `Intl.DateTimeFormat`, `Intl.NumberFormat`, or hand-written `aria-label` values that embed language text MUST use the current locale from `useLocale()` / `getLocale()` — not a hardcoded string like `"hu-HU"` or `"en-US"`.

**Wrong — hardcoded locale ignores the user's language:**
```typescript
// Hungarian date format even when the page is rendered in English
const formatted = date.toLocaleDateString("hu-HU");

// Hungarian currency even for English users
const price = amount.toLocaleString("hu-HU", { style: "currency", currency: "HUF" });

// English aria-label even when the page is Hungarian
<button aria-label="Add to wishlist">...</button>
```

**Correct — derive from the current locale:**
```typescript
"use client";
import { useLocale, useTranslations } from "next-intl";

export function ReviewDate({ date }: { date: Date }) {
  const locale = useLocale();
  return <time>{date.toLocaleDateString(locale)}</time>;
}

// Server component equivalent
import { getLocale, getTranslations } from "next-intl/server";
const locale = await getLocale();
const formatted = date.toLocaleDateString(locale);

// aria-label uses a translation key, not a hardcoded string
const t = useTranslations("wishlist");
<button aria-label={t("add")}>...</button>
```

**The rule:** the first argument to any `toLocale*` / `Intl.*` constructor MUST be `locale` from `useLocale()` / `getLocale()`. The only exception is code that intentionally normalises to a specific locale (e.g., log lines written in English) — add an inline comment explaining why.

## Sidecar Files Must Never Be Wiped

`messages/<locale>.<change>.json` per-change sidecar files (see Sidecar File Resilience below) are the vehicle that moves translations from a feature worktree into `messages/<locale>.json` on archive. Until the archive step runs, each change's sidecar holds that change's strings — and ONLY that change's strings.

- **Never overwrite a sidecar that belongs to a different scope** (e.g., a cart change must not write `messages/hu.admin_panel.json`).
- **Never reset a sidecar to `{}`** as a "clean slate" — that drops whatever was already merged from upstream changes and breaks all localised text on merged-in features.
- **If your change adds keys to an existing sidecar, merge — do not replace.** Read the file, spread the existing content, add your keys, write it back.

The same append-only discipline applies to `set/orchestration/e2e-manifest.json` (REQ coverage) — see testing-conventions.md § "`e2e-manifest.json` — Append-Only REQ Coverage".

## Sidecar File Resilience

When using per-change i18n sidecar files (e.g., `messages/hu.feature_name.json` that get merged into base `messages/hu.json` during archive), ALL sidecar imports MUST use try/catch:

```typescript
// ✓ CORRECT — survives after archive deletes the sidecar file
let featureSidecar = {};
try {
  featureSidecar = (await import(`../messages/${locale}.feature_name.json`)).default;
} catch {
  // Sidecar merged into base messages during archive — this is expected
}

const messages = {
  ...baseMessages,
  ...featureSidecar,
};
```

```typescript
// ✗ WRONG — crashes the dev server after archive
import featureSidecar from `../messages/${locale}.feature_name.json`;
// Error: Cannot find module '../messages/hu.feature_name.json'
```

**Why:** The orchestrator's archive step merges sidecar content into base message files and deletes the sidecar files. Bare imports without try/catch crash the Next.js dev server, breaking all E2E tests for subsequent changes.

## Language Switcher

Language/locale switchers MUST use `<Link>` with locale prop, NOT `<button onClick>` with `router.replace()`:

```typescript
// ✓ CORRECT — works without React hydration (renders <a> tag)
import { Link } from '@/i18n/routing';
// or: import NextLink from 'next/link';

<Link href={pathname} locale={otherLocale}>
  {otherLocale.toUpperCase()}
</Link>

// ✗ WRONG — requires React hydration to attach onClick handler
<button onClick={() => router.replace(pathname, { locale: otherLocale })}>
  {otherLocale.toUpperCase()}
</button>
```

**Why:** Under E2E test load or slow connections, React hydration may be delayed. A `<button>` with `onClick` stays inert until hydration completes — the user clicks but nothing happens. A `<Link>` renders a standard `<a>` tag that works immediately.

## Dynamic Route Links

When using next-intl pathnames (locale-dependent URL mapping like `/hu/kavek` → `/en/coffees`), dynamic `<Link>` hrefs MUST use object format:

```typescript
// ✓ CORRECT — provides params for localized pathname compilation
<Link href={{ pathname: '/products/[slug]', params: { slug: product.slug } }}>
  {product.name}
</Link>

// ✗ WRONG — crashes with "Insufficient params provided for localized pathname"
<Link href={`/products/${product.slug}`}>
  {product.name}
</Link>
```

**Language switcher on dynamic pages** — use `next/navigation` `usePathname()` (returns real URL like `/hu/kavek/arabica`) instead of next-intl `usePathname()` (returns template path like `/products/[slug]`). Then swap the locale prefix:

```typescript
import { usePathname as useNextPathname } from 'next/navigation';
import NextLink from 'next/link';

const pathname = useNextPathname(); // "/hu/kavek/arabica"
const otherPath = pathname.replace(/^\/(hu|en)/, `/${otherLocale}`);
<NextLink href={otherPath}>{otherLocale.toUpperCase()}</NextLink>
```

## E2E Testing with i18n

- Playwright config MUST set `use.locale` matching the project's primary locale (e.g., `hu-HU` for Hungarian)
- Without this, next-intl may redirect `/` to an unexpected locale path, breaking test assertions
- Test assertions on user-visible text MUST match the active locale's translations — do not assert English text when the test runs in Hungarian locale
- When testing locale switching, verify both the URL change and the visible text change

## Middleware Configuration

The next-intl middleware has the same API route exclusion requirement as auth middleware. The matcher MUST exclude all `/api` routes:

```typescript
// In middleware.ts — exclude API routes from i18n rewriting
export const config = { matcher: ['/((?!api|_next|.*\\..*).*)'] };
```

If i18n middleware runs on API routes, it may redirect JSON responses or add locale prefixes to API paths, breaking client-side fetches. See auth-middleware.md for the full middleware matcher pattern.
