# Admin Panel

> **Figma frames:** Admin Dashboard, Admin Products, Admin Orders & Deliveries, Admin Coupons/Promo/Gift/Reviews, Admin Subscriptions — see [design-system.md](../design/design-system.md#frame-mapping)

Admin panel — accessible only to logged-in users with the ADMIN role.

- Admin accounts are created via seed data only (no admin user management in v1)
- Single admin role: full access to all admin features
- Admin actions are logged: order status changes, review moderation, stock modifications, coupon creation/edit — log entry includes: admin name, timestamp, action type, affected entity

## Admin layout

```
┌─────────────────────────────────────────────────────────────┐
│  CraftBrew Admin                       Admin Name [Logout] │
├──────────┬──────────────────────────────────────────────────┤
│          │                                                  │
│  Home    │  (content appears here)                          │
│  Products│                                                  │
│  Orders  │                                                  │
│  Shipping│                                                  │
│  Subscr. │                                                  │
│  Coupons │                                                  │
│  GiftCard│                                                  │
│  Reviews │                                                  │
│  Promo   │                                                  │
│  Content │                                                  │
│          │                                                  │
└──────────┴──────────────────────────────────────────────────┘
```

On mobile, the sidebar collapses into a hamburger menu (drawer, opens from the left).

## Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│  Good morning, Admin!                         2026-03-10   │
│                                                             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐
│  │ Today's rev. │ │ Orders       │ │ Active subs. │ │ New users  │
│  │ 127 450 Ft   │ │ 12 (today)   │ │ 34 users     │ │ 8 (7 days)│
│  │ ▲ +23%       │ │ ▲ +15%       │ │ ▲ +5          │ │ ▼ -2      │
│  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘
│                                                             │
│  ┌─ Revenue trend (7 days) ────────────────────────────┐   │
│  │  ▂▃▅▇█▆▇                                            │   │
│  │  M  T  W  T  F  S  S                                │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─ Top 3 products today ─────────────────────────────┐    │
│  │ 1. Ethiopia Yirgacheffe (250g whole bean) — 8 pcs   │    │
│  │ 2. Starter bundle — 3 pcs                           │    │
│  │ 3. Colombia Huila (1kg whole bean) — 2 pcs          │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─ Low stock ───────────────────────────────────────┐     │
│  │ Rwanda Nyungwe 1kg whole bean — 5 pcs remaining     │    │
│  │ Fellow Stagg kettle — 8 pcs remaining               │    │
│  │ Kenya AA Nyeri 1kg whole bean — 8 pcs remaining     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

KPI cards: percentage change compared to the previous period (today vs yesterday, 7 days vs previous 7 days).
Low stock: products/variants with stock <= 10 units.

## Product Management

### Product List

DataTable: image (thumbnail), name, category, base price, aggregated stock, active/inactive, actions.

Filters: category (Coffee/Equipment/Merch/Bundle), active/inactive, search.

### Product Editing

#### Basic Tab
- Name HU / Name EN
- Description HU / Description EN (textarea)
- Category (select: Coffee / Equipment / Merch / Bundle)
- Base price (Ft)
- Images (URL list)
- Active toggle

#### Coffee-specific Tab (if category = Coffee)
- Origin
- Roast (Light / Medium / Dark)
- Processing (Washed / Natural / Honey / Wet-hulled)
- Flavor notes (tag input, comma-separated)
- Altitude (m)
- Farm name

#### Variants Tab
Variant list DataTable:
- SKU (auto-generated or manual)
- Options (form, size, grind)
- Price modifier (Ft, + or -)
- Stock
- Active toggle

"New variant" button → inline form: specify options, price modifier, initial stock.

Stock modification: inline number field, with save button. Stock change log (who, when, how much was modified).

#### SEO Tab
- Slug (auto-generated from name, editable)
- Meta title HU / EN
- Meta description HU / EN

#### Cross-sell Tab
- Related products multi-select (max 3)
- Search and select from the full catalog

### Bundle Editing

For products in the Bundle category, the "Basic Tab" extends with:
- Components list: product + variant selection + quantity
- Calculated "separate price" (sum of components)
- Bundle price manual input
- Savings % automatic calculation
- Bundle stock: not editable, automatic (minimum of components)

## Orders

### List

DataTable: order number, customer name, date, amount, status badge, actions.

Filters: status (New / Processing / Packed / Shipping / Delivered / Cancelled), date range, search (order number or customer name).

### Order Details

On click, modal or separate page:
- Line items list: product, variant, quantity, unit price, subtotal
- Shipping address + zone
- Coupon / gift card if applied
- Shipping fee
- Grand total
- Payment identifier
- Invoice download
- **Status change buttons**: Advance to the next status
  - New → Processing (button: "Start processing")
  - Processing → Packed (button: "Packed")
  - Packed → Shipping (button: "Handed to courier") → **email trigger: shipping notification**
  - Shipping → Delivered (button: "Delivered") → **email trigger: delivery + review request**
  - Any time: "Cancel order" (with confirmation) → refund → stock restoration

## Daily Deliveries

```
┌─────────────────────────────────────────────────────────────┐
│  Daily deliveries           [◄ 2026-03-10 ►]               │
│                                                             │
│  Morning (6:00-9:00) — 12 deliveries                       │
│  ┌──────┬───────────┬──────────────┬──────────┬──────────┐ │
│  │ Time │ Customer  │ Address      │ Product  │ Status   │ │
│  ├──────┼───────────┼──────────────┼──────────┼──────────┤ │
│  │ 6:30 │ Smith J.  │ Váci u. 12   │ Eth. 250g│ ☐ Prep.  │ │
│  │ 7:00 │ Doe J.    │ Dob u. 45    │ Col. 500g│ ☐ Prep.  │ │
│  └──────┴───────────┴──────────────┴──────────┴──────────┘ │
│                                                             │
│  Late morning (9:00-12:00) — 8 deliveries                  │
│  [...]                                                      │
│                                                             │
│  Afternoon (14:00-17:00) — 3 deliveries                    │
│  [...]                                                      │
│                                                             │
│  Summary:                                                   │
│  Total: 23 │ Subscription: 19 │ One-time: 4               │
│  Budapest: 18 │ +20km: 5                                   │
│                                                             │
│  [☐ All delivered] (bulk status button)                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Subscription-generated shipments and one-time orders appear together.

## Subscription Management

DataTable: customer, product, frequency, status (Active/Paused/Cancelled), next delivery.

Admin actions (on behalf of the customer, e.g., phone request):
- Pause (from date to date)
- Modify (coffee, variant, frequency, time window, address)
- Cancel (immediate / end of cycle)

## Coupon Management

### List

DataTable: code, type (% / fixed), value, category filter, expiry, usage/max, active.

### Coupon Creation/Editing

Form fields:
- **Code** (required, uppercase, unique, e.g., "FIRST10")
- **Type** (Percentage / Fixed amount)
- **Value** (number — if %, then 1-100; if fixed, then Ft)
- **Min. order amount** (optional, Ft)
- **Max uses** (optional, number — if empty: unlimited)
- **Category filter** (optional select: Coffee / Equipment / Merch / Bundle / All)
- **First order only** (checkbox)
- **Expiry** (optional date)
- **Active** (toggle)

Validation: code unique, value > 0, if % type then max 100.

## Promo Days

### List

DataTable: name, date, discount %, email sent, active.

### Promo Day Creation/Editing

Form fields:
- **Name HU** (required, e.g., "Store birthday")
- **Name EN** (required)
- **Date** (required, calendar picker)
- **Discount %** (required, 1-100)
- **Banner text HU** (required, max 200 characters)
- **Banner text EN** (required, max 200 characters)
- **Active** (toggle)

The banner automatically appears on the homepage on the given day.
The email is automatically sent to all registered users on the promo day (once).

## Gift Cards

### List

DataTable: code, original amount, current balance, buyer, recipient, expiry, status (active/expired/depleted).

Filters: has balance / depleted / expired.

### Details (on click)

- Card data
- Transaction log:
  - PURCHASE: "Purchase — 10 000 Ft", date, buyer
  - REDEMPTION: "Redemption — order #1042 — 2 490 Ft", date, user
  - REDEMPTION: "Redemption — order #1055 — 5 000 Ft", date, user
  - Current balance: 2 510 Ft

## Review Moderation

### List

DataTable: stars, product, user, title (truncated), status (New / Approved / Rejected), date.

Filters: status, min stars, product.

### Moderation

On the review card:
- Full review content (stars, title, text)
- User info
- Product link
- **Buttons:**
  - Approve → appears on the product page
  - Reject → does not appear
  - Reply → admin reply form (textarea, max 500 characters)
- Admin reply: displayed as "CraftBrew replied:" format below the review on the product page

## Mobile

- Admin sidebar collapses into hamburger drawer
- All DataTables horizontally scrollable (no layout break)
- All forms use vertical layout, full width fields

## Content/Stories Management

### List

DataTable: title, category, status (draft/published), publication date.

### Story Editing

Form fields:
- **Title HU** (required)
- **Title EN** (required)
- **Category** (select: Origin Stories / Roasting / Brewing / Health / Gift Tips)
- **Slug** (auto-generated from title, editable)
- **Content HU** (textarea or markdown editor, required)
- **Content EN** (textarea or markdown editor, required)
- **Cover image URL** (optional)
- **Author** (text, default: "CraftBrew team")
- **Related products** (multi-select, max 4)
- **SEO title HU/EN** (auto from title, editable)
- **SEO description HU/EN** (auto first 160 characters, editable)
- **Status** (Draft / Published)
- **Publication date** (auto now, editable — future date = scheduled)
