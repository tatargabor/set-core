---
paths:
  - "src/app/**/page.tsx"
  - "src/app/**/layout.tsx"
  - "src/app/sitemap*"
  - "src/app/robots*"
  - "src/app/opengraph-image*"
---
# SEO Conventions

## Metadata Export
- Every public `page.tsx` MUST export `metadata` or `generateMetadata`
- Include `title`, `description` at minimum
- Use template pattern in root layout: `title: { template: "%s | SiteName", default: "SiteName" }`
- Never duplicate the site name in page-level titles — the template adds it

## Open Graph & Social
- Set `openGraph` in metadata: `title`, `description`, `images`, `locale`, `type`
- Set `twitter` card: `card: "summary_large_image"`, `title`, `description`, `images`
- Use `opengraph-image.tsx` route for dynamic OG images when needed
- Social sharing images: 1200×630px recommended

## Structured Data (schema.org)
- Add JSON-LD via `<script type="application/ld+json">` in page components
- Common types: `Organization`, `WebSite`, `BreadcrumbList`, `Article`, `Product`, `FAQPage`
- Place JSON-LD helpers in `src/lib/structured-data.ts` — keep it DRY
- Validate with Google Rich Results Test before shipping

## Canonical & Alternate URLs
- Set `alternates.canonical` on every public page
- For i18n: set `alternates.languages` with hreflang mappings
- Canonical always points to the primary locale version
- Avoid duplicate content — use `canonical` to consolidate URL variants

## Sitemap & Robots
- Use Next.js `sitemap.ts` route handler (dynamic generation)
- Include all public pages, exclude auth/admin/api/account routes
- Set appropriate `changeFrequency` and `priority` per page type
- Use `robots.ts` route handler:
  - Allow all public routes
  - Disallow protected and non-indexable routes (`/admin/*`, `/api/*`, `/account/*`)
  - Reference sitemap URL

## Page Performance for SEO
- Server-render all public content pages (no client-only rendering for indexable content)
- Ensure meaningful content in initial HTML — don't rely on client-side data fetching for SEO-critical content
- Use `loading.tsx` for streaming — search engines see initial content immediately
