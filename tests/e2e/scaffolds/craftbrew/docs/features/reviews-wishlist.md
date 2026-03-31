# Reviews & Wishlist Feature

> **Figma frames:** Product Detail (reviews section), User Orders & Profile (favorites), Admin Coupons/Promo/Gift/Reviews — see [design-system.md](../design/design-system.md#frame-mapping)

## Reviews

### Who Can Write a Review?
- Only registered, logged-in users
- Only for products they have purchased (at least 1 completed order contains the product)
- A user can write only 1 review per product (update is allowed)

### Review Form

Appears on the product details page, at the top of the reviews section (if the user is eligible):

- **Stars:** 1-5, clickable star icons (required)
- **Title:** short summary, max 100 characters (required)
- **Text:** detailed review, max 1000 characters (required, min 20 characters)

### Review Display

On the product page, in the "Reviews" section:

```
── Reviews (4.5★ — 12 reviews) ───────────────────────────

┌─────────────────────────────────────────────────────────┐
│ ★★★★★  "The best coffee of my life"                     │
│ John Smith — 2026-03-08                                  │
│                                                          │
│ This was my first time ordering specialty coffee and     │
│ I was completely blown away. The floral aroma is         │
│ noticeable right from grinding, and the cup tastes       │
│ like pure jasmine tea. I love it!                        │
│                                                          │
│ 💬 CraftBrew replied:                                   │
│ "Thank you John! The Yirgacheffe is truly special.      │
│  Try the Rwanda Nyungwe too if you enjoy fruity          │
│  tasting notes!"                                         │
│                                                          │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ ★★★☆☆  "Good, but not my favorite"                     │
│ Jane Doe — 2026-03-05                                    │
│                                                          │
│ Quality coffee, but a bit too acidic for my taste.       │
│ I prefer the Brazil Cerrado style. The shipping was      │
│ fast though, arrived the next day.                       │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Review Moderation

- New review → PENDING status (not publicly visible)
- Admin approval → APPROVED (visible)
- Admin rejection → REJECTED (not visible, user is notified)
- Admin reply: one-level reply, publicly displayed below the review
- Admin reply appears under the CraftBrew name

### Average Rating

- On product cards: star icon + number (e.g., "★ 4.5 (12)")
- On product page: large stars + text "12 reviews"
- Only APPROVED reviews count toward the average
- If no reviews: "No reviews yet" text, stars grayed out

### Reviews Mobile

- Review form renders full width
- Star rating icons easily tappable (min 44px touch target)

## "What Our Customers Say" Section

On the homepage (bottom section), the highest-rated, approved reviews:

```
── What Our Customers Say ────────────────────────────────

┌──────────┐ ┌──────────┐ ┌──────────┐
│ ★★★★★    │ │ ★★★★★    │ │ ★★★★☆    │
│ "Best    │ │ "Starter │ │ "Always  │
│ coffee   │ │ bundle   │ │ arrives  │
│ ever"    │ │ perfect  │ │ fresh"   │
│          │ │ start"   │ │          │
│ Smith J. │ │ Brown M. │ │ Davis K. │
│ Ethiopia │ │ B1 bundle│ │ Subscr.  │
└──────────┘ └──────────┘ └──────────┘
```

Selection logic: TOP 3 reviews by rating + recency, minimum 4 stars.

## Favorites (Wishlist)

### Favorites Button

- Heart icon (♡ / ❤️) on product cards and the product details page
- Click: toggle (add / remove)
- Only shown to logged-in users
- Anonymous: redirects to login on click

### Favorites Page

- Product card grid (same as catalog, but only favorites)
- "Remove" button on every card
- Empty state: "You have no favorites yet. Browse our coffees!"

### Wishlist Mobile

- Heart icon touch-friendly at 44px minimum

### "Back in Stock" Notification

When a product/variant stock is 0:
- On the product details page, instead of "Add to cart" button: "Notify me when back in stock"
- On click: the product is added to the favorites list with a "back in stock notification" flag
- When admin restocks (stock > 0): email sent to all users who requested notification
- After sending, the flag is removed (one-time notification)

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
- **Profile**: see design-system.md § Page Layouts

