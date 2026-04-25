# Promotions Feature

## Coupons

### Coupon Types

| Code | Type | Value | Condition | Max uses | Expiry |
|---|---|---|---|---|---|
| ELSO10 | % | 10% | First order only | Unlimited | None |
| NYAR2026 | % | 15% | Any product | 500 | 2026-08-31 |
| BUNDLE20 | % | 20% | Bundle category only | Unlimited | None |

### Coupon Redemption Rules

1. Enter coupon code on the cart page
2. Validation:
   - Code exists and is active
   - Not expired
   - Has not reached max usage count
   - Category filter matches (if any) — at least 1 cart item is in the category
   - "First order only" coupon → user has no previous completed orders
   - Min. cart value is met (if any)
3. Success: discount applied, shown in summary. Category-filtered coupons (e.g., BUNDLE20) discount only the matching items in the cart, not the entire cart.
4. Failure: error message (specific reason: "Expired", "First order only", etc.)

### Coupon Stacking

- **Coupons with each other:** NOT stackable (max 1 coupon/order)
- **Coupon + gift card:** Yes, combinable. The coupon reduces the amount first, the gift card deducts from the remainder.
- **Coupon + promo day:** Yes, combinable. Promo day discount is automatic, the coupon is applied on top.
- **Order:** Promo day discount → Coupon discount → Gift card deduction → Card payment

### Discount calculation base

- **Unrestricted coupon (no category filter):** computes against the cart subtotal AFTER promo-day discounts (i.e. discounted subtotal). Example: cart 10 000 Ft, promo-day −10% → 9 000 Ft, then 1 000 Ft coupon → final 8 000 Ft.
- **Category-filtered coupon (e.g. BUNDLE20: bundles only):** computes against the per-item subtotal of matching items only, AFTER promo-day discounts on those items. Example: cart has 6 000 Ft bundle + 4 000 Ft coffee, promo-day −10% applies to all → 5 400 + 3 600 = 9 000. BUNDLE20 (20% on bundles) computes against the 5 400 Ft (post-promo) bundle subtotal → 1 080 Ft coupon discount. Final cart total: 9 000 − 1 080 = 7 920 Ft.
- **Item-level promo days (e.g. coffee-only −10%):** discount applies to coffee line items individually before the cart subtotal is computed. Coupon then computes against the (already-discounted) cart subtotal per its own filter.
- **Rounding:** all monetary intermediate values are rounded to the nearest forint at each step (no fractional Ft persisted).

## Promo Days

### Concept

Admin-configurable special days when an automatic discount applies. No coupon code needed — the discount applies automatically.

### How It Works

1. Admin configures: name, date, discount %, banner text
2. On the given day:
   - **Banner** appears on the homepage
   - At checkout, **automatic discount** is applied (shown as a separate line in the order summary: "Store Birthday -20%")
   - **Email** sent to all registered users (if not already sent)
3. After the day ends, the banner disappears and the discount no longer applies

### Seed Data for Promo Day

| Name | Date | Discount | Banner Text |
|---|---|---|---|
| Store Birthday | 03-15 | 20% | "CraftBrew turns 1 today! 🎉 20% off everything!" |
| World Coffee Day | 10-01 | 15% | "International Coffee Day! ☕ 15% off!" |

## Gift Cards

### Purchase

Available as product M4 in the shop. At purchase:
- Select denomination (5 000 / 10 000 / 20 000 Ft)
- Enter recipient email (required)
- Personal message (optional, max 200 characters)
- Card payment (normal checkout flow)

After successful purchase:
- Gift card is created with a unique code (GC-XXXX-XXXX format), with the purchased denomination
- Email is sent to the RECIPIENT with the code and message

### Redemption

At checkout (on the cart page):
- Gift card code input field
- Validation: code exists, active, has balance, not expired
- Success: balance deduction, remaining balance is displayed
- Partial use: if the balance is less than the order total, the difference must be paid by card
- If the balance covers the entire order: no card payment needed (0 Ft payable)

### Balance Management

- Every use and purchase is recorded as a transaction
- Current balance is always up to date
- Admin panel: card list, balances, transaction log
- Expiry: 1 year from purchase — expired cards cannot be redeemed
- Gift cards cannot be used to purchase other gift cards
