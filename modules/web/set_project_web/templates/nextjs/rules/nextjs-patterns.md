---
description: Next.js performance and data fetching patterns
globs:
  - "src/app/**/*.{ts,tsx}"
  - "app/**/*.{ts,tsx}"
  - "src/components/**/*.{ts,tsx}"
---

# Next.js Patterns

## 1. force-dynamic Anti-Pattern

Never use `export const dynamic = 'force-dynamic'` on pages with mixed static and dynamic content. It disables all caching for the entire page.

**Wrong — blanket force-dynamic because one section needs fresh data:**
```typescript
// Kills SSG/ISR for the ENTIRE page — all sections re-rendered on every request
export const dynamic = 'force-dynamic'

export default async function HomePage() {
  const products = await getProducts()         // these could be cached
  const categories = await getCategories()     // these could be cached
  const testimonials = await getTestimonials() // only this needs fresh data
  return <><Products /><Categories /><Testimonials /></>
}
```

**Correct — targeted caching for the dynamic parts only:**
```typescript
// Option A: ISR — entire page revalidates periodically
export const revalidate = 300  // 5-minute ISR

// Option B: per-query caching for the dynamic section
import { unstable_cache } from 'next/cache'
const getCachedTestimonials = unstable_cache(
  async () => db.review.findMany({ where: { featured: true } }),
  ['testimonials'],
  { revalidate: 300 }
)

// Option C: client-side fetch for the dynamic section, keep page static
// Use a client component with useEffect for testimonials only
```

**The rule:** Reserve `force-dynamic` for pages where EVERY byte must be personalized on every request (e.g., user dashboard with real-time data). For pages with mixed content, use ISR (`revalidate`), per-query caching (`unstable_cache`), or Suspense boundaries with streaming.

## 2. Server Actions in Client Effects

Prefer fetching data in server components and passing as props. If a server action must be called from a client `useEffect`, always wrap in try/catch with loading and error states.

**Wrong — server action in useEffect without error handling or auth scoping:**
```typescript
'use client'
export default function OrderDetail({ orderId }: { orderId: string }) {
  const [returnReq, setReturnReq] = useState(null)
  useEffect(() => {
    // No try/catch — unhandled rejection if server action fails
    // orderId comes from URL params — user can tamper with it
    getReturnRequest(orderId).then(setReturnReq)
  }, [orderId])
}
```

**Correct — server component fetch (preferred) or guarded client fetch:**
```typescript
// Option A (preferred): fetch in server component, pass as props
export default async function OrderDetail({ params }: { params: { id: string } }) {
  const user = await getCurrentUser()
  const order = await db.order.findUnique({ where: { id: params.id, userId: user.id } })
  const returnReq = await db.returnRequest.findFirst({
    where: { orderId: order.id, order: { userId: user.id } }
  })
  return <OrderDetailClient order={order} returnRequest={returnReq} />
}

// Option B: if client-side fetch is necessary
'use client'
export default function OrderDetail({ orderId }: { orderId: string }) {
  const [returnReq, setReturnReq] = useState(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    getReturnRequest(orderId)
      .then(setReturnReq)
      .catch(() => setError("Failed to load return request"))
      .finally(() => setLoading(false))
  }, [orderId])
}
```

**The rule:** Data fetching belongs in server components whenever possible. If a server action must be called from `useEffect`: (1) wrap in try/catch with error state, (2) show loading indicator, (3) ensure the server action internally scopes by userId — the ID comes from URL params the user controls.

## 3. Route Group Structure

Separate public and admin areas using Next.js route groups for layout isolation:

```
src/app/
├── (shop)/              ← public storefront layout
│   ├── layout.tsx       ← header, nav, footer for shoppers
│   ├── page.tsx         ← homepage
│   ├── products/
│   ├── cart/
│   └── orders/
├── admin/
│   ├── login/page.tsx   ← outside dashboard layout (no sidebar)
│   ├── register/page.tsx
│   └── (dashboard)/     ← admin layout with sidebar
│       ├── layout.tsx
│       ├── page.tsx     ← admin homepage
│       └── products/
├── api/                 ← API routes (no route group needed)
├── layout.tsx           ← root layout (html, body, providers)
└── globals.css
```

**Rules:**
- Public pages go under `(shop)/` — never directly under `src/app/`
  (except `layout.tsx`, `globals.css`, and `api/`)
- The homepage is `src/app/(shop)/page.tsx` — `src/app/page.tsx` should NOT exist
- Admin auth pages (login, register) sit under `admin/` directly — outside the dashboard layout so they render full-screen without sidebar
- Admin feature pages go under `admin/(dashboard)/` — inside the sidebar layout
- This separation prevents layout bugs where admin sub-pages lose the sidebar or storefront pages render without the shop nav

### CRITICAL: Root Layout Must NOT Render `<html>` (i18n projects)

In projects with `next-intl` or any `[locale]` route segment, the `[locale]/layout.tsx` renders `<html lang={locale}>`. If the root `src/app/layout.tsx` ALSO renders `<html>`, React produces a **hydration mismatch** — the server sends `<html lang="hu">` (root) but the client expects `<html lang="en">` (locale), and CSS class attributes diverge too.

**Wrong — BOTH layouts render `<html>` (causes hydration mismatch):**
```typescript
// src/app/layout.tsx (root) — BAD: creates a duplicate <html>
import "./globals.css";
export default function RootLayout({ children }) {
  return <html lang="hu"><body>{children}</body></html>
}

// src/app/[locale]/layout.tsx — ALSO renders <html> → nested <html> tags!
export default function LocaleLayout({ children, params }) {
  return <html lang={locale}><body>{children}</body></html>
}
```

Result: React hydration error on every page. The `lang` attribute and font `className` differ between server and client renders.

**Correct — root layout is a pass-through, locale layout owns `<html>`:**
```typescript
// src/app/layout.tsx (root) — pass-through shell
import "./globals.css";  // imported here so admin routes outside [locale] get styles
export default function RootLayout({ children }) {
  return children;  // NO <html>, NO <body> — delegate to [locale]/layout.tsx
}

// src/app/[locale]/layout.tsx — the ONLY place that renders <html>
import "../globals.css";  // Next.js dedupes; safe to import in both
export default async function LocaleLayout({ children, params }) {
  const { locale } = await params;
  return (
    <html lang={locale} className={`${heading.variable} ${body.variable}`}>
      <body className="bg-background text-foreground font-sans">
        <NextIntlClientProvider messages={messages}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
```

**The rule:** In i18n projects, ONLY the `[locale]/layout.tsx` may render `<html>` and `<body>`. The root layout returns `children` directly. Import `globals.css` in the root layout for admin/non-locale routes, but do NOT wrap children in HTML tags.

**Admin routes outside `[locale]/`:** If admin pages live at `/admin/*` (not under `[locale]/`), they don't inherit the locale layout's `<html>`. The admin layout MUST render its own `<html lang="...">` and `<body>`. Example:
```typescript
// src/app/admin/layout.tsx — admin gets its own <html>
export default function AdminLayout({ children }) {
  return (
    <html lang="hu">
      <body className="bg-neutral-50 text-neutral-900 font-sans">
        {children}
      </body>
    </html>
  );
}
```

**For non-i18n projects** (no `[locale]` segment): the root layout renders `<html>` and `<body>` as usual.

**Detection:** if Next.js dev console shows "A tree hydrated but some attributes of the server rendered HTML didn't match" with `lang` or `className` diffs on `<html>`, you have duplicate `<html>` tags from nested layouts.

## 4. Nested Layout Inheritance — DRY Rule

Next.js layouts compose hierarchically: a child layout receives the parent layout's chrome **automatically**. NEVER redeclare the parent's components, providers, or wrappers in a child layout — this creates duplicate state, double-mounted providers, and rendering races.

**Wrong — child layout duplicates parent's chrome and providers:**
```typescript
// src/app/(shop)/layout.tsx — parent
export default function ShopLayout({ children }) {
  return (
    <CartProvider>
      <Header />
      <main>{children}</main>
      <Footer />
      <Toaster />
    </CartProvider>
  )
}

// src/app/(shop)/checkout/layout.tsx — child (WRONG)
export default function CheckoutLayout({ children }) {
  return (
    <CartProvider>           {/* ← duplicates parent! Two cart states! */}
      <Header />              {/* ← double-rendered header */}
      <main>{children}</main>
      <Footer />              {/* ← double-rendered footer */}
      <Toaster />             {/* ← double toast manager */}
    </CartProvider>
  )
}
```

The two `CartProvider` instances each maintain their own state. After mutations (e.g., placing an order that empties the cart), one provider sees empty and redirects, the other still has items, causing redirect races and ghost-cart UI bugs.

**Correct — child layout only adds what's NEW, inherits the rest:**
```typescript
// src/app/(shop)/checkout/layout.tsx — child (CORRECT)
export default async function CheckoutLayout({ children }) {
  const session = await auth()
  if (!session?.user) redirect('/login')

  // Just return children — parent layout's CartProvider, Header, Footer
  // are inherited automatically. Add ONLY what this layout needs that
  // the parent doesn't provide (e.g., auth gate, checkout-specific UI).
  return <>{children}</>
}
```

**The rule:** A child layout should only add components/providers that the parent does NOT already provide. If you're tempted to copy-paste from a parent layout, you're creating a bug. Layouts compose, they don't override.

**Detection patterns:**
- Same provider imported in multiple layouts → duplicate state
- Same `<Header />` / `<Footer />` rendered in nested layouts → double-mount
- Cart/auth/theme state behaves differently on different routes → likely duplicate provider

**When you DO need a different layout:** use a route group (e.g., `(shop)` vs `(checkout-fullscreen)`) at the same level as the parent, NOT a nested layout that redeclares everything.

## 5. No Raw `<img>` — Always `next/image`

Raw `<img>` tags bypass Next.js image optimisation: no lazy loading, no responsive `srcset`, no format negotiation (AVIF/WebP), no CLS prevention. They also trip ESLint rules (`@next/next/no-img-element`) and the review gate consistently flags them.

**Wrong — raw `<img>`:**
```tsx
<img src={product.imageUrl} alt={product.name} className="h-64 w-full object-cover" />
```

**Correct — `next/image` with explicit dimensions or `fill`:**
```tsx
import Image from "next/image";

// Known intrinsic size:
<Image
  src={product.imageUrl}
  alt={product.name}
  width={640}
  height={480}
  className="object-cover"
/>

// Unknown size — parent container must be `relative`:
<div className="relative h-64 w-full">
  <Image src={product.imageUrl} alt={product.name} fill className="object-cover" />
</div>
```

**Remote hosts:** any external image origin MUST be listed in `next.config.js` → `images.remotePatterns`. Otherwise `next/image` throws at build time:

```js
// next.config.js
module.exports = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "placehold.co" },
      { protocol: "https", hostname: "cdn.example.com" },
    ],
  },
};
```

**The rule:** zero raw `<img>` tags in `src/app/**` and `src/components/**`. If the image source is dynamic/remote, whitelist the host in `remotePatterns`. Use `fill` only inside a `position: relative` parent.

## 6. `React.cache()` for `generateMetadata` + Page Dedup

When a page has both `generateMetadata` and a default export that each fetch the same record (product, story, user), the DB is hit twice per request. Wrap the shared loader in `React.cache()` so the second call returns the memoised result.

**Wrong — two queries per request:**
```tsx
// app/products/[slug]/page.tsx
export async function generateMetadata({ params }: Props) {
  const product = await db.product.findUnique({ where: { slug: params.slug } });
  return { title: product?.name };
}

export default async function Page({ params }: Props) {
  const product = await db.product.findUnique({ where: { slug: params.slug } });
  if (!product) notFound();
  return <ProductView product={product} />;
}
```

**Correct — `cache()`-wrapped loader, called twice but queried once:**
```tsx
import { cache } from "react";

const getProduct = cache(async (slug: string) => {
  return db.product.findUnique({ where: { slug } });
});

export async function generateMetadata({ params }: Props) {
  const product = await getProduct(params.slug);
  return { title: product?.name };
}

export default async function Page({ params }: Props) {
  const product = await getProduct(params.slug);
  if (!product) notFound();
  return <ProductView product={product} />;
}
```

**The rule:** any record fetched by both `generateMetadata` and the page's default export MUST go through a `React.cache()`-wrapped loader. The memoisation is per-request, so it's safe and automatic.

## 7. `next.config.js` — Preserve `images` Defaults

The shipped `next.config.js` template sets three `images` keys together as a matched set:

```js
images: {
  unoptimized: true,
  dangerouslyAllowSVG: true,
  contentSecurityPolicy: "default-src 'self'; script-src 'none'; sandbox;",
}
```

These exist because seeded fixtures and example data reference `placehold.co` which serves SVG, not PNG. Without `dangerouslyAllowSVG` the Next.js dev server crashes on `<Image src="https://placehold.co/...">` with *"type image/svg+xml but dangerouslyAllowSVG is disabled"*, breaking E2E tests that load product pages.

**Wrong — agent rewrites the config and drops protections:**
```js
// Removes unoptimized, adds remotePatterns, forgets dangerouslyAllowSVG
images: {
  remotePatterns: [
    { protocol: "https", hostname: "placehold.co" },
  ],
},
```
Result: every page that renders a product image triggers a 500 in dev mode because Next.js optimises the SVG and refuses to serve it.

**Correct — if you must switch to `remotePatterns`, keep SVG settings:**
```js
images: {
  remotePatterns: [
    { protocol: "https", hostname: "placehold.co" },
    { protocol: "https", hostname: "cdn.example.com" },
  ],
  dangerouslyAllowSVG: true,
  contentSecurityPolicy: "default-src 'self'; script-src 'none'; sandbox;",
},
```

Or replace every placehold.co reference in `prisma/seed.ts` + fixtures with a real PNG CDN first, then drop the SVG settings.

**The rule:** when editing `next.config.js`, preserve the existing `images` keys unless you also update seed data and fixtures. Removing `dangerouslyAllowSVG` + `contentSecurityPolicy` without replacing placehold.co references is a known regression that blocks E2E runs.

## 8. Navigation Link ↔ Page Coverage

Every entry rendered in shared navigation (header nav, footer nav, admin sidebar, language switcher, mobile drawer) MUST resolve to a real page that returns 200. Verify gates crawl the home page, follow every `<Link>` in the navigation, and fail if any target 404s. The failure mode is the same whether the link was added speculatively ("we'll build /merch later") or the route was renamed mid-scope ("/products" → "/shop").

**Wrong — foundation change seeds five nav items, only three have pages:**
```tsx
// src/components/Header.tsx
<nav>
  <Link href="/kavek">Kávék</Link>       {/* page exists */}
  <Link href="/eszkozok">Eszközök</Link> {/* page exists */}
  <Link href="/csomagok">Csomagok</Link> {/* 404 — page never created */}
  <Link href="/merch">Merch</Link>       {/* 404 */}
  <Link href="/sztorik">Sztorik</Link>   {/* 404 */}
</nav>
```
Result: verify gate follows each link, three return 404, the change hard-fails verify with "nav links return 404". Cost: a full retry cycle on the feature change, sometimes exhausting the retry budget for a missing placeholder the planner forgot.

**Correct — ship a placeholder for every link the same change renders:**
```tsx
// src/app/[locale]/(shop)/csomagok/page.tsx
export default function BundlesPage() {
  const t = useTranslations("bundles");
  return (
    <main className="mx-auto max-w-6xl px-4 py-12">
      <h1 className="text-3xl font-bold">{t("title")}</h1>
      <p className="text-muted-foreground mt-4">{t("comingSoon")}</p>
    </main>
  );
}
```

Any of these approaches is acceptable:
- Minimal placeholder page with `generateMetadata` + heading + "Coming soon" copy.
- Gate the link render behind a feature flag (`{flags.bundles && <Link … />}`) so the nav only shows what's live.
- Conditional rendering driven by seed data (`{categories.length > 0 && <Link … />}`).

**The rule:** do not merge a change whose navigation points at routes the same change does not also create. The dependency is "nav entry → page", not the other way around. A `grep -r 'href="' src/components/Header.tsx src/components/Footer.tsx` cross-referenced against `src/app/**/page.tsx` is the minimum manual check before committing.

Also relevant: inside-app navigation MUST use `next/link` `<Link>`, never raw `<a href>`. Raw anchors skip prefetch, skip client-side routing, and break the `/en/...` locale prefix injected by `next-intl`. Use `<a>` ONLY for external URLs (`https://...`) and explicit same-tab downloads.
