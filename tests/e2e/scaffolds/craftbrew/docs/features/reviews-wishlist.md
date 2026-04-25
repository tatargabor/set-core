# Reviews & Wishlist Feature

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

### Review Content Sanitization (security — required)

Review title and text are user-generated content. Implementation MUST:
- **Escape HTML on render** — render review text as plain text via React's default text-node escaping. NEVER use `dangerouslySetInnerHTML` for review content. Newlines in user input render as `<br/>` (preserve line breaks; nothing else).
- **Strip control characters** before persistence (zero-width chars, RTL/LTR overrides, NULL).
- **Reject submissions** that contain HTML-like tags (`<` followed by a letter) on the server side — return 400 with field-level error "HTML and code are not allowed in reviews". This is a server-side check; do NOT trust client-side stripping.

**Test fixtures with intentional XSS payloads.** The seed data and test fixtures include reviews with payloads like `<script>alert(1)</script>`, `"><img src=x onerror=alert(1)>`, javascript: URLs, and SQL-injection-like strings (`'; DROP TABLE reviews;--`). These are intentional and MUST remain in the seed/fixtures unchanged — they verify the sanitization paths work correctly. Do NOT "fix" them by removing the payloads. The test assertion is that the rendered HTML contains the literal escaped string (not executed code).

### Review Display

On the product page, in the "Reviews" section:

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
