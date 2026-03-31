# SEO & Metadata

## Meta Tags

On every public page:
- `<title>` — unique per page
- `<meta name="description">` — max 160 characters
- Public pages: indexable
- Admin, checkout, account pages: not indexable

### Page-specific Title Format

| Page | Title |
|---|---|
| Homepage | "CraftBrew — Specialty Coffee Budapest" |
| Coffees list | "Our Coffees — CraftBrew" |
| Coffee detail | "{name} — CraftBrew" |
| Equipment | "Coffee Equipment — CraftBrew" |
| Stories | "Stories — CraftBrew" |
| Story detail | "{title} — CraftBrew" |
| Cart | "Cart — CraftBrew" |

## Open Graph Tags

On every public page:
- `og:type` — "website" (or "product" on product pages)
- `og:title`
- `og:description`
- `og:image` — product image or default banner
- `og:url`
- `og:locale` — "hu_HU" or "en_US"
- `og:locale:alternate` — the other language
- `og:site_name` — "CraftBrew"

## schema.org Structured Data

Required structured data types:

- **Product** (on product pages) — name, description, image, brand ("CraftBrew"), offers (AggregateOffer, HUF, availability), aggregateRating
- **BreadcrumbList** (on every page) — navigation hierarchy
- **Article** (on story pages) — headline, author (Organization: CraftBrew), datePublished, image

## hreflang Tags

On every public page, both language versions and x-default (hu) must be specified:
- `hreflang="hu"` — Hungarian version
- `hreflang="en"` — English version
- `hreflang="x-default"` — Hungarian version (primary language)

## Canonical URLs

Every page must have a canonical URL. The canonical always points to the HU version (primary language).

## XML Sitemap

The `/sitemap.xml` contains:
- Homepage (hu + en)
- Every coffee/equipment/merch/bundle product (hu + en)
- Every published story (hu + en)
- Category pages (hu + en)
- Subscription page (hu + en)

Does NOT contain:
- Admin pages
- Checkout pages
- Account pages
- Draft stories

## Robots.txt

```
User-agent: *
Allow: /
Disallow: /admin/
Disallow: /*/penztar/
Disallow: /*/checkout/
Disallow: /*/fiokom/
Disallow: /*/account/
Sitemap: https://craftbrew.hu/sitemap.xml
```

## Design Reference

Use exact values from `docs/design-system.md` — do NOT use framework defaults.

**Key colors**: primary `#78350F`, secondary `#D97706`, background `#FFFBEB`
**Fonts**: Playfair Display, Inter, JetBrains Mono

**Matched pages:**
- **Homepage**: see design-system.md § Page Layouts
- **Catalog**: see design-system.md § Page Layouts
- **Product Detail**: see design-system.md § Page Layouts
- **Cart**: Uses: Button, figma
- **Checkout**: Uses: Button
- **Admin**: see design-system.md § Page Layouts
- **Auth**: see design-system.md § Page Layouts
- **Subscription**: see design-system.md § Page Layouts
- **Stories**: Uses: figma
- **Profile**: see design-system.md § Page Layouts

