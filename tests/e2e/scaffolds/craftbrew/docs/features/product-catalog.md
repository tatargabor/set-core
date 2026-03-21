# Product Catalog Feature

> **Figma frames:** Homepage Desktop, Homepage Mobile, Coffee Catalog, Product Detail — see [design-system.md](../design/design-system.md#frame-mapping)

## Homepage

The homepage (`/hu` or `/en`) is the main entry point for customers.

### Sections (top to bottom)

1. **Hero banner** — full-width, CraftBrew branding, tagline ("Specialty Coffee Budapest"), CTA button: "Browse our coffees"
2. **Featured products** — 4 hand-picked products (from seed: Ethiopia Yirgacheffe, Starter Pack bundle, Hario V60, Colombia Huila). Product cards with "Add to Cart" shortcut.
3. **Subscription teaser** — "Fresh coffee, delivered regularly." brief description + CTA: "Set up your subscription"
4. **Story highlights** — 3 most recent published stories, card layout with cover image and title
5. **"What Our Customers Say"** — top 3 approved reviews (min 4 stars, most recent first). See reviews-wishlist.md for details.
6. **Newsletter / promo banner** — if a promo day is active today, the promo banner replaces this section

### Header (all pages)

```
┌────────────────────────────────────────────────────────────┐
│ [LOGO] CraftBrew    [Search...]   [HU/EN] [♡] [🛒 3] [👤] │
├────────────────────────────────────────────────────────────┤
│  Coffees  Equipment  Merch  Bundles  Stories  Subscription │
└────────────────────────────────────────────────────────────┘
```

- **Logo:** links to homepage
- **Search:** expands on focus, instant search results dropdown
- **Language switcher:** HU / EN toggle
- **Wishlist icon (♡):** links to favorites page (logged-in only, otherwise redirects to login)
- **Cart icon (🛒):** badge shows item count, links to cart page
- **User icon (👤):** logged out → login page; logged in → dropdown (Profile, My Orders, My Subscriptions, Logout)
- **Navigation:** main menu items as listed above. Active page highlighted.
- **Mobile:** hamburger menu (drawer from left), search icon, cart icon with badge

### Footer (all pages)

- Column 1: CraftBrew logo, brief description, social media links (Facebook, Instagram)
- Column 2: Shop links (Coffees, Equipment, Bundles, Subscription)
- Column 3: Information (About Us, Contact, Shipping & Returns, FAQ)
- Column 4: Legal (Terms & Conditions, Privacy Policy, Cookie Policy)
- Bottom row: "© 2026 CraftBrew. All rights reserved."

### Error Pages

- **404 — Page not found:** friendly message, search bar, link to homepage and coffees page
- **500 — Server error:** brief apology, link to homepage

## Product List Pages

Four main catalog pages:
- Coffees — 8 coffees
- Equipment — 7 equipment items
- Merch — 5 merch/promo items
- Bundles — 4 bundles

Each page uses a responsive grid: 1 column mobile (< 640px), 2 columns tablet (640-1023px), 3 columns desktop (>= 1024px).

## Product Card

Each card contains:
- Product image (placeholder)
- Name (by language HU/EN)
- Price (lowest variant price, e.g., "from 2 490 Ft")
- Average star rating (if reviews exist) + review count
- "New" badge if newer than 7 days
- "Out of Stock" badge if all variant stock is 0
- Favorite heart icon (for logged-in users)

## Product Details Page

Individual page for every product.

### Coffee Product Details

```
┌─────────────────────────────────────────────────────────┐
│  ┌──────────────┐  Name (large heading font)              │
│  │              │  Origin: Ethiopia, 1800-2200m          │
│  │  PRODUCT IMG │  Roast: ●○○ Light                     │
│  │   (large)    │  Processing: Washed                    │
│  │              │                                        │
│  │              │  Flavor Notes: [floral] [citrusy]      │
│  │              │                [jasmine] [bergamot]     │
│  └──────────────┘                                        │
│                                                          │
│  Description text (2-3 paragraphs)                      │
│                                                          │
│  ┌─ Variant Selector ────────────────────────────┐     │
│  │ Form:     [Whole Bean ▼]                        │     │
│  │ Size:       ○ 250g (2490 Ft)                    │     │
│  │             ● 500g (4680 Ft)                    │     │
│  │             ○ 1kg  (6580 Ft)                    │     │
│  │                                                 │     │
│  │ Grind (if ground): [Filter ▼]                   │     │
│  │                                                 │     │
│  │ Stock: 30 pcs                                   │     │
│  │                                                 │     │
│  │ Quantity: [- 1 +]                               │     │
│  │                                                 │     │
│  │ [████ Add to Cart ████] [♡ Favorite]            │     │
│  └─────────────────────────────────────────────────┘     │
│                                                          │
│  ── Recommended For You ─────────────────────────────   │
│  [V60 Dripper]  [V60 Filter]  [Starter Bundle]          │
│                                                          │
│  ── Reviews (4.5★ — 12 reviews) ────────────────────   │
│  [review list...]                                        │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Equipment/Merch Details

Simpler layout — no variant selector (except M2 t-shirt size, M4 gift card denomination, M5 workshop date).

## Variant Selector Logic

1. User selects the form (whole bean/ground)
2. If ground: grind type appears (filter/espresso/french press/turkish)
3. User selects the packaging size
4. Price, stock, and SKU update dynamically
5. If the selected variant stock is 0: "Out of Stock" — add-to-cart button disabled, "Notify Me" link (wishlist)

## Search

Search field in the header (on every page):
- Full-text search: product name, description, flavor notes
- Story article titles and content are also searchable
- Result list: products and stories in separate sections, products first
- Results sorted by relevance (name match > description match > flavor note match)
- Minimum 3 characters
- Results appear as the user types (instant search)
- Maximum 5 products + 3 stories in the dropdown; "See all results" link at the bottom for full results page

## Filtering (coffee page)

Left-side filter panel on the coffee list (slide-up drawer on mobile):
- **Origin:** checkbox list (Ethiopia, Colombia, Brazil, Guatemala, Kenya, Indonesia, Costa Rica, Rwanda)
- **Roast:** Light / Medium / Dark
- **Processing:** Washed / Natural / Honey / Wet-hulled
- **Price:** range slider (min-max)
- Filters are combinable (AND logic)
- Filtered view is bookmarkable and shareable (URL reflects the active filters)
- "Clear Filters" button

## Cross-sell

Each product has a maximum of 3 "Recommended For You" products:
- Admin manually configures the related products
- Seed data contains the default cross-sell pairs:
  - For coffees: relevant equipment + filter + bundle
  - For equipment: best-matching coffee
  - For bundles: complementary equipment or coffee

## Mobile

- Product cards in 1 column layout (< 640px)
- Filter panel in slide-up drawer (not inline sidebar)
- No horizontal overflow on any catalog page

## Bundle Page

Bundle product card extra info:
- Content list (component products)
- "Separate price" crossed out + "Bundle price" highlighted
- Savings % badge (e.g., "-28%")
- Bundle stock = minimum stock among components
