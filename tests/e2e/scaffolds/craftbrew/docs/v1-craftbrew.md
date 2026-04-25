# CraftBrew v1 — Specialty Coffee Webshop

> Business specification — the complete functional and content description of the CraftBrew specialty coffee webshop.

## Spec Structure

This spec is modular. The main file (this one) contains the overview, conventions, and verification checklist. Detailed specs are in subdirectories:

## Shared Domain Models (cross-feature index)

These entities are referenced from multiple features. To prevent schema drift, use these exact entity names, key fields, and relationships. Field types are illustrative — agents may add fields, but MUST NOT rename the listed ones.

| Entity | Key fields | Belongs to / related |
|---|---|---|
| `User` | `id`, `email` (unique), `password_hash`, `name`, `language` (`hu`\|`en`), `role` (`CUSTOMER`\|`ADMIN`), `created_at` | hasMany Address, Order, Subscription, Review, Wishlist, RestockNotification |
| `Address` | `id`, `user_id`, `label`, `name`, `postal_code`, `city`, `street`, `phone`, `is_default`, `zone` (computed: `BUDAPEST`\|`PLUS_20KM`\|`PLUS_40KM`) | belongsTo User |
| `Product` | `id`, `slug` (unique), `name_hu`, `name_en`, `description_hu`, `description_en`, `category` (`COFFEE`\|`EQUIPMENT`\|`MERCH`\|`BUNDLE`), `base_price`, `active`, plus coffee-specific (`origin`, `roast`, `processing`, `flavor_notes[]`, `altitude`, `farm`) | hasMany Variant, Review |
| `Variant` | `id`, `product_id`, `sku` (unique), `options` (JSON: `form`/`size`/`grind`/`tshirt_size`/etc.), `price_modifier`, `stock`, `active` | belongsTo Product |
| `Bundle` | (a Product with `category=BUNDLE`) plus `BundleComponent` join: `bundle_id`, `variant_id`, `quantity` | many-to-many Product via BundleComponent |
| `Cart` | `id`, `user_id` (nullable for anonymous), `session_id` (for anonymous), `created_at`, `updated_at` | hasMany CartItem |
| `CartItem` | `id`, `cart_id`, `variant_id`, `quantity`, `price_snapshot` | belongsTo Cart, Variant |
| `Order` | `id`, `order_number` (unique, `#1042` style), `user_id`, `status` (see Order State Machine in `features/cart-checkout.md`), `subtotal`, `discount_total`, `shipping_fee`, `grand_total`, `address_snapshot` (JSON), `coupon_id?`, `gift_card_id?`, `payment_id` (Stripe), `placed_at`, `delivered_at?`, `cancelled_at?` | hasMany OrderItem, belongsTo User |
| `OrderItem` | `id`, `order_id`, `variant_id`, `quantity`, `unit_price`, `subtotal` | belongsTo Order, Variant |
| `Subscription` | `id`, `user_id`, `variant_id`, `frequency` (`DAILY`\|`WEEKLY`\|`BIWEEKLY`\|`MONTHLY`), `time_window` (`MORNING`\|`FORENOON`\|`AFTERNOON`), `status` (`ACTIVE`\|`PAUSED`\|`CANCELLED`), `start_date`, `next_billing_date`, `current_cycle_snapshot` (JSON), `next_cycle_config` (JSON, nullable), `paused_until?`, `address_id` | hasMany SubscriptionDelivery, belongsTo User, Variant |
| `SubscriptionDelivery` | `id`, `subscription_id`, `scheduled_for`, `status` (`SCHEDULED`\|`SHIPPED`\|`DELIVERED`\|`SKIPPED_OOS`\|`SKIPPED_USER`\|`PAUSED`), `delivered_at?`, `delivered_email_at?` | belongsTo Subscription |
| `Coupon` | `id`, `code` (unique, uppercase), `type` (`PERCENT`\|`FIXED`), `value`, `min_order`, `max_uses?`, `category_filter?`, `first_order_only` (bool), `expires_at?`, `active`, `uses_count` | hasMany OrderCoupon (usage log) |
| `GiftCard` | `id`, `code` (unique, `GC-XXXX-XXXX` format), `original_amount`, `balance`, `buyer_user_id?`, `recipient_email`, `purchased_at`, `expires_at` (purchase + 1 year), `delivery_email_sent` (bool) | hasMany GiftCardTransaction |
| `GiftCardTransaction` | `id`, `gift_card_id`, `type` (`PURCHASE`\|`REDEMPTION`), `amount`, `order_id?`, `created_at` | belongsTo GiftCard, Order |
| `PromoDay` | `id`, `name_hu`, `name_en`, `date` (MM-DD recurring or full date), `discount_pct`, `banner_text_hu`, `banner_text_en`, `active`, `email_sent` (bool, set after promo day announcement) | — |
| `Review` | `id`, `product_id`, `user_id`, `stars` (1-5), `title`, `text`, `status` (`PENDING`\|`APPROVED`\|`REJECTED`), `admin_reply?`, `created_at` | belongsTo User, Product |
| `Wishlist` | `id`, `user_id`, `variant_id`, `restock_notification` (bool), `created_at` | belongsTo User, Variant |
| `RestockNotification` | `id`, `user_id`, `variant_id`, `requested_at`, `sent_at?` (one-time; null until restock email is sent) | belongsTo User, Variant |
| `Story` | `id`, `slug` (unique), `title_hu`, `title_en`, `category` (`ORIGIN`\|`ROASTING`\|`BREWING`\|`HEALTH`\|`GIFT`), `content_hu`, `content_en`, `cover_image_url?`, `author`, `status` (`DRAFT`\|`PUBLISHED`), `published_at`, `related_product_ids[]` (max 4) | — |
| `AuditLog` | `id`, `admin_user_id`, `action_type`, `entity_type`, `entity_id`, `before_value?` (JSON), `after_value?` (JSON), `created_at` | belongsTo User (admin) |

**Rules for changes:**
- A change that introduces a new entity adds it here in the same PR.
- A change that adds a field to an existing entity does NOT need to update this table — it's an index of the canonical names, not an exhaustive schema.
- NEVER rename an entity or one of its listed key fields without updating this index AND every reference across `features/*.md`.

State enum values are listed in UPPER_SNAKE_CASE — use these exact strings in code (DB enum values), regardless of the language Prisma/your ORM emits.

## Error Code Catalog

User-facing validation errors return a stable machine-readable `code` (UPPER_SNAKE_CASE) plus an HTTP status, plus a localized user message keyed by i18n. The `code` is what E2E tests assert on (via `data-testid="error-banner"` + the code as `data-error-code`); the message is what the user sees. Use these EXACT codes — agents that invent new codes break test assertions across other agents' work.

API response shape (4xx/5xx errors):
```json
{
  "error": {
    "code": "COUPON_EXPIRED",
    "message": "This coupon has expired.",
    "field": "coupon_code"
  }
}
```
- `code` — required, from the table below
- `message` — required, already localized (server reads `Accept-Language` or session locale)
- `field` — optional, name of the form field this error applies to (used by client to render inline error)

### Coupon validation (cart page)

| Code | HTTP | i18n key (HU / EN message) |
|---|---|---|
| `COUPON_NOT_FOUND` | 404 | `error.coupon.not_found` ("Ismeretlen kupon kód" / "Coupon code not found") |
| `COUPON_INACTIVE` | 400 | `error.coupon.inactive` ("Ez a kupon nem aktív" / "This coupon is not active") |
| `COUPON_EXPIRED` | 400 | `error.coupon.expired` ("Lejárt kupon" / "This coupon has expired") |
| `COUPON_MAX_USES_REACHED` | 400 | `error.coupon.max_uses` ("A kupon felhasználhatósága elfogyott" / "This coupon has reached its usage limit") |
| `COUPON_FIRST_ORDER_ONLY` | 400 | `error.coupon.first_order_only` ("Csak az első rendeléshez használható" / "First order only — you have previous orders") |
| `COUPON_MIN_ORDER_NOT_MET` | 400 | `error.coupon.min_order` ("Minimum rendelési összeg: {amount} Ft" / "Minimum order amount {amount} Ft not met") |
| `COUPON_CATEGORY_MISMATCH` | 400 | `error.coupon.category_mismatch` ("Ez a kupon csak {category} termékekre érvényes" / "This coupon applies only to {category} products") |
| `COUPON_ALREADY_APPLIED` | 400 | `error.coupon.already_applied` ("Csak egy kupon alkalmazható rendelésenként" / "Only one coupon per order") |

### Gift card validation (cart page)

| Code | HTTP | i18n key |
|---|---|---|
| `GIFT_CARD_NOT_FOUND` | 404 | `error.gift_card.not_found` |
| `GIFT_CARD_EXPIRED` | 400 | `error.gift_card.expired` |
| `GIFT_CARD_DEPLETED` | 400 | `error.gift_card.depleted` ("A kártyán nincs egyenleg" / "Gift card has no balance") |
| `GIFT_CARD_INVALID_FOR_GIFT_CARD` | 400 | `error.gift_card.cannot_buy_gift_card` ("Ajándékkártyával nem vásárolható másik ajándékkártya" / "Gift cards cannot be used to purchase other gift cards") |

### Cart / Stock errors

| Code | HTTP | When |
|---|---|---|
| `CART_EMPTY` | 400 | Checkout attempted with empty cart |
| `STOCK_INSUFFICIENT` | 409 | Requested quantity > available; response `meta.available` indicates current stock |
| `STOCK_VARIANT_INACTIVE` | 410 | Variant became inactive while in cart |
| `VARIANT_NOT_FOUND` | 404 | Variant ID doesn't exist |

### Checkout errors

| Code | HTTP | When |
|---|---|---|
| `ADDRESS_REQUIRED` | 400 | Step 1: no shipping address selected |
| `ADDRESS_ZONE_NOT_DELIVERABLE` | 400 | Postal code outside +40km AND order has subscription items with `frequency=DAILY` (see subscription pricing rules) |
| `PAYMENT_DECLINED` | 402 | Stripe returned card_declined / insufficient_funds — message includes Stripe decline reason |
| `PAYMENT_PROCESSING_ERROR` | 502 | Stripe network/timeout — user can retry |

### Order errors

| Code | HTTP | When |
|---|---|---|
| `ORDER_NOT_FOUND` | 404 | Order ID doesn't exist OR doesn't belong to the requesting user (deliberately conflated to avoid leaking order existence) |
| `ORDER_INVALID_TRANSITION` | 409 | Status transition not allowed by Order State Machine (see `features/cart-checkout.md`) |
| `ORDER_NOT_CANCELLABLE` | 409 | Customer self-cancel attempted on order in SHIPPING/DELIVERED — directs them to Returns flow |
| `RETURN_WINDOW_EXPIRED` | 400 | Return requested >14 days after delivery |
| `RETURN_COFFEE_OPENED` | 400 | Return for coffee item declared as `opened` (food safety) |

### Auth errors

| Code | HTTP | When |
|---|---|---|
| `AUTH_INVALID_CREDENTIALS` | 401 | Wrong email or password (do NOT distinguish — single message: "Invalid email or password") |
| `AUTH_EMAIL_TAKEN` | 409 | Registration with already-registered email |
| `AUTH_PASSWORD_TOO_SHORT` | 400 | < 8 characters |
| `AUTH_RESET_TOKEN_INVALID` | 400 | Token doesn't exist or is malformed |
| `AUTH_RESET_TOKEN_EXPIRED` | 400 | Token > 1 hour old |
| `AUTH_TERMS_NOT_ACCEPTED` | 400 | Registration without T&C checkbox |

### Review errors

| Code | HTTP | When |
|---|---|---|
| `REVIEW_NOT_PURCHASED` | 403 | User tries to review a product they never purchased |
| `REVIEW_ALREADY_EXISTS` | 409 | User already reviewed this product (use UPDATE flow instead) |
| `REVIEW_HTML_NOT_ALLOWED` | 400 | Submission contains `<` followed by a letter (see `features/reviews-wishlist.md` sanitization rules) |
| `REVIEW_TEXT_TOO_SHORT` | 400 | < 20 characters |

### Subscription errors

| Code | HTTP | When |
|---|---|---|
| `SUB_DAILY_NOT_AVAILABLE_IN_ZONE` | 400 | Daily frequency selected for +40km address |
| `SUB_PAUSE_RANGE_INVALID` | 400 | Pause `from > to`, or `from` in past |
| `SUB_PAYMENT_FAILED_THRESHOLD` | 402 | After 3 failed retries — subscription auto-paused |

**Rules:**
- The `code` is contractual; renaming it breaks E2E tests. Adding new codes is fine.
- The user-visible message MAY be reworded (it's i18n-keyed), but the i18n key MUST stay stable.
- Server NEVER returns raw exception messages or stack traces to the client.
- For 5xx errors not in this table, fall back to `code: "INTERNAL_ERROR"` with HTTP 500 and a generic message.

## E2E Test Conventions

Multiple changes write Playwright tests that interact with the same pages. Without a stable selector contract, tests written by Change A break when Change B changes the DOM. Follow these conventions:

### Selector strategy (in priority order)

1. **`getByRole()` with accessible name** — the gold standard. Accessibility-first selectors don't break with markup changes. Use this for buttons, links, form fields, headings.
   ```typescript
   page.getByRole('button', { name: /add to cart/i })
   page.getByRole('textbox', { name: /email/i })
   ```
2. **`data-testid` for non-semantic elements** — when role-based selection is impossible (cart badge counter, image-only buttons, modals). Use the naming pattern `data-testid="<feature>-<element>[-<modifier>]"` (kebab-case). Examples: `cart-badge`, `cart-item-row`, `product-card`, `error-banner`, `language-switcher`, `subscription-pause-button`.
3. **Never use `text=` selectors for assertions on translated UI text** — the test would be locale-coupled. Use role+name with case-insensitive regex, OR i18n-keyed `data-i18n-key` attributes.

### Required `data-testid` registry

These selectors MUST exist with these exact names — they're referenced by E2E tests across multiple changes:

| `data-testid` | Component / page | Notes |
|---|---|---|
| `header-cart-icon` | Header | Click to navigate to cart |
| `header-cart-badge` | Header | Item count, not rendered when 0 |
| `header-language-switcher` | Header | Renders HU/EN buttons inside |
| `header-user-menu` | Header | User dropdown trigger |
| `header-search-input` | Header | Top search field |
| `header-search-results` | Header | Instant-search dropdown |
| `product-card` | Product list pages | Multiple instances; use `nth()` or scope by parent. Each product card has `data-product-id` attribute too. |
| `product-add-to-cart` | Product card / detail | Add-to-cart button. Disabled when out of stock. |
| `cart-item-row` | Cart page | One per cart item, has `data-variant-id` |
| `cart-subtotal` | Cart page | Shows subtotal as text |
| `cart-grand-total` | Cart page | Shows final amount |
| `cart-coupon-input` | Cart page | Coupon code input field |
| `cart-coupon-apply` | Cart page | Coupon apply button |
| `cart-gift-card-input` | Cart page | Gift card code input |
| `error-banner` | Cart page, checkout, forms | Has `data-error-code` matching Error Code Catalog |
| `checkout-step-1` / `checkout-step-2` / `checkout-step-3` | Checkout | Step containers |
| `checkout-pay-button` | Step 2 | Submit payment |
| `order-status-badge` | Order detail / list | Has `data-status` attribute (UPPER_SNAKE_CASE matching Order State Machine) |
| `admin-status-button` | Admin order detail | Has `data-target-status` attribute (e.g., `data-target-status="PROCESSING"`) |
| `subscription-row` | Subscription dashboard | Has `data-subscription-id` |
| `subscription-pause-button`, `subscription-skip-button`, `subscription-cancel-button` | Subscription dashboard | Action buttons |
| `wishlist-heart` | Product card / detail | Has `data-product-id` and `data-favorited` (`true`/`false`) |
| `review-card` | Product detail page | Has `data-review-id`, `data-stars` |
| `review-form` | Product detail page | Form container |
| `promo-banner` | Homepage | Only rendered when active promo day matches today |

### Test data conventions

- **Test users:** seed creates `customer1@craftbrew.hu / customer123` (regular customer with prior order — eligible to write reviews) and `admin@craftbrew.hu / admin123`. Tests use these directly; do not create new users mid-test unless testing the registration flow.
- **Adversarial fixtures:** see "Test fixtures with adversarial payloads" section above.
- **Test isolation:** each test resets the DB to seed state via `beforeEach` (use a fast `prisma db push --force-reset && pnpm seed`, OR a transaction-rollback wrapper).
- **Time-sensitive tests:** for promo days / expiring coupons / 14-day return windows, use `page.clock.install()` to fix `Date.now()`. Do not rely on real wall clock.

### File layout

- E2E tests live under `tests/e2e/` (mirrors the framework convention).
- One test file per feature: `tests/e2e/cart.spec.ts`, `tests/e2e/checkout.spec.ts`, `tests/e2e/admin-orders.spec.ts`, etc.
- Shared selectors as exported constants from `tests/e2e/selectors.ts` — agents reuse these instead of hardcoding strings:
  ```typescript
  export const SEL = {
    cartBadge: '[data-testid="header-cart-badge"]',
    errorBanner: '[data-testid="error-banner"]',
    // ...
  } as const;
  ```

## Business Conventions

- **Currency:** HUF (Hungarian Forint). Integer, no decimals. Display format: `2 490 Ft`. All displayed prices are gross (VAT-inclusive, 27% Hungarian VAT).
- **Language:** HU/EN bilingual. Default language: HU. Admin panel: HU only.
- **Anonymous shopping:** Cart works without login (session-based). Checkout requires login.
- **Payment:** Card payment via Stripe. Invoicing via szamlazz.hu.
- **Email:** Transactional emails (mock mode in development — no real emails sent)
- **Images:** Realistic coffee-themed placeholder images in seed data. Use Unsplash Source URLs with coffee/cafe queries (e.g. `https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=600` for hero, `https://images.unsplash.com/photo-1497935586351-b67a49e012bf?w=400` for product cards). Each product gets a unique image URL. The `ImageWithFallback` component must show a styled SVG placeholder (coffee cup icon, brand colors from Figma design tokens, subtle animation) while loading and on error — never a broken image icon.

## Seed Data

The seed script must populate data from the following sources:

- `catalog/coffees.md` — 8 coffees with all variants
- `catalog/equipment.md` — 7 equipment items
- `catalog/merch.md` — 5 merch items (M2 t-shirt with sizes, M4 gift card with denominations, M5 workshop with dates)
- `catalog/bundles.md` — 4 bundles with components
- Coupons: ELSO10, NYAR2026, BUNDLE20 (see features/promotions.md)
- Promo days: Store Birthday, World Coffee Day (see features/promotions.md)
- 5 story categories + 10 stories (see features/content-stories.md)
- Admin user: admin@craftbrew.hu / admin123

### Test fixtures with adversarial payloads

Seed data and Playwright fixtures intentionally include adversarial inputs to verify sanitization paths:
- Reviews with `<script>alert(1)</script>`, `"><img src=x onerror=alert(1)>`, javascript: URLs
- Story content with HTML-like tags, SQL-injection-like strings (`'; DROP TABLE--`)
- User names with zero-width characters and RTL/LTR overrides
- Product flavor notes with control characters

These payloads are **intentional test fixtures**, NOT bugs. Do not "clean up" or remove them — they verify XSS escaping, input rejection, and SQL-injection protection. The expected behavior is that rendered output contains the literal escaped string, server-side validation rejects HTML-tagged submissions with 400, and database queries are parameterized. See `features/reviews-wishlist.md` for review-specific sanitization rules.

## Verification Checklist

Post-run verification. Each item must be manually or automatically checkable.

### Storefront
- [ ] Header: logo, search, language switcher, wishlist icon, cart icon with badge, user menu
- [ ] Footer: shop links, info links, legal links (Terms, Privacy, Cookie Policy)
- [ ] Homepage (`/hu`) hero banner with CraftBrew branding, featured products, subscription teaser, story highlights, "What Others Say" section
- [ ] 404 page with search bar and links to homepage
- [ ] `/hu/kavek` shows 8 coffee products in responsive grid (1/2/3 columns)
- [ ] `/hu/eszkozok` shows 7 equipment items
- [ ] `/hu/merch` shows merch items
- [ ] Product cards: image, name, price in HUF (e.g. "2 490 Ft"), average rating stars
- [ ] Product detail: large image, full description, flavor notes (coffee), variant selector (form/size/grind)
- [ ] Variant selection updates price dynamically
- [ ] Out-of-stock variant: disabled, "Out of Stock" badge
- [ ] Search bar: full-text search across products and stories
- [ ] Filter: by origin, roast level, processing method, price range
- [ ] Bundle page shows contents, individual vs bundle price, savings percentage
- [ ] Cross-sell: "Recommended With This" section on product detail pages
- [ ] Language switcher (HU/EN) in header, persists in session
- [ ] `/en/coffees` shows English content

### Cart & Checkout
- [ ] Add to cart with variant selection
- [ ] Cart page: items with variant info, quantity controls, line totals, cart total
- [ ] Coupon code input on cart page — "ELSO10" gives 10% off first order
- [ ] Gift card code input — partially redeemable, shows remaining balance
- [ ] Checkout step 1: shipping address + zone auto-detection + shipping cost display
- [ ] Checkout step 2: card payment form
- [ ] Checkout step 3: order summary with all line items, shipping, discount, total
- [ ] After order: cart cleared, stock decremented, order confirmation page
- [ ] Invoice generated and downloadable as PDF
- [ ] Shipping zones: Budapest 990 Ft, +20km 1490 Ft, +40km 2490 Ft
- [ ] Free shipping: Budapest over 15000 Ft, +20km over 25000 Ft
- [ ] Estimated delivery date shown at checkout (Budapest: next day, +20km: 1-2 days, +40km: 2-3 days)
- [ ] Return request from "My Orders" page (within 14 days of delivery)
- [ ] Invoice shows net amount, VAT (27%), and gross amount

### Subscription
- [ ] Subscription setup page: coffee selection, form/size, frequency (daily/weekly/biweekly/monthly)
- [ ] Delivery window selection: morning (6-9), forenoon (9-12), afternoon (14-17)
- [ ] Subscription pricing: daily -15%, weekly -10%, biweekly -7%, monthly -5%
- [ ] User dashboard: active subscriptions with next delivery date
- [ ] Pause subscription (date range)
- [ ] Skip single delivery
- [ ] Modify subscription (coffee, quantity, schedule)
- [ ] Cancel subscription
- [ ] Daily delivery not available for +40km zone

### User Account
- [ ] Registration form: name, email, password, Terms & Conditions checkbox
- [ ] Login with credentials
- [ ] Password reset via email with time-limited token
- [ ] Profile page: personal info, language preference, notification preferences
- [ ] Saved addresses with zone labels
- [ ] Order history with status tracking
- [ ] "My Orders" page shows all past orders with status badges
- [ ] Legal pages: Terms & Conditions, Privacy Policy, Cookie consent banner

### Reviews & Wishlist
- [ ] Product detail: star rating display (1-5) with count
- [ ] Write review: only for registered users who purchased the product
- [ ] Review form: star rating + title + text body
- [ ] Reviews appear after admin approval
- [ ] Admin reply visible below review
- [ ] Homepage "What Others Say" section shows top approved reviews
- [ ] Wishlist: heart icon on product cards, dedicated wishlist page
- [ ] "Back in Stock" restock notification opt-in on out-of-stock items

### Promotions
- [ ] Coupon "ELSO10": 10% off, first order only
- [ ] Coupon "NYAR2026": 15% off, expires 2026-08-31, max 500 uses
- [ ] Coupon "BUNDLE20": 20% off, bundles only
- [ ] Coupons not stackable (one per order)
- [ ] Promo day: banner on homepage, auto-discount at checkout, no code needed
- [ ] Gift card: purchasable in 5000/10000/20000 Ft denominations
- [ ] Gift card: redeemable at checkout, partial balance supported

### Content / Stories
- [ ] `/hu/sztorik` lists all published stories by category
- [ ] Story categories: Origin Stories, Roasting, Brew Guides, Health, Gift Ideas
- [ ] Story detail: title, author, date, cover image, body, related products
- [ ] Related products link to product pages
- [ ] At least 10 stories seeded with content

### Admin
- [ ] `/admin` login required (redirect to `/admin/login`)
- [ ] Dashboard: today's revenue, order count, active subscribers, new registrations (7d)
- [ ] Dashboard: top 3 products today, 7-day revenue trend, low stock alerts
- [ ] Products CRUD: DataTable, create/edit with variant management, SEO fields
- [ ] Bundle editor: select components, set bundle price, auto-calculate savings
- [ ] Orders: list with status filter, detail with line items, status flow (New → Processing → Packed → Shipping → Delivered)
- [ ] Daily deliveries view: date picker, grouped by time window, delivery checklist
- [ ] Subscriptions management: list, pause/modify/cancel on behalf of customer
- [ ] Coupons CRUD: code, type, value, expiry, max uses, category filter
- [ ] Promo days: set date, discount %, banner text (HU/EN)
- [ ] Gift cards: list with balance, transaction log
- [ ] Review moderation: approve/reject, admin reply
- [ ] Content/stories: create/edit, category, HU+EN, related products, draft/published
- [ ] Return management: approve/reject return requests, refund processing
- [ ] Admin action audit log visible on dashboard

### Email
- [ ] Welcome email on registration (in user's language)
- [ ] Order confirmation with line items, total, shipping address
- [ ] Shipping notification with estimated delivery
- [ ] Delivery confirmation + "How did you like it?" review request link
- [ ] "Back in Stock" restock notification to wishlist subscribers
- [ ] Promo day announcement to all subscribers
- [ ] All emails respect user language preference (HU/EN)

### SEO
- [ ] Meta title and description on all public pages
- [ ] schema.org Product structured data on product pages
- [ ] XML sitemap at `/sitemap.xml`
- [ ] Open Graph tags for social sharing
- [ ] Canonical URLs on all pages
- [ ] `hreflang` tags linking HU/EN versions
