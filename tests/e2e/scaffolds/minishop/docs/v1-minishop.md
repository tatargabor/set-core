# MiniShop v1 — Webshop Feature Spec

> Next.js 16 App Router webshop with Prisma (SQLite), shadcn/ui (slate / neutral), Tailwind CSS v4, NextAuth.js v5.
> Goal: real shop feel with a minimalist surface — browse → cart → checkout (cash on delivery) → order. No payments, no admin product CRUD, no inventory management. Step up from `micro-web` (static), step below `craftbrew` (Stripe + complex catalog).

## Design Source

The visual contract is defined in `v0-export/` — cloned at run time from
`scaffold.yaml::design_source` (currently `tatargabor/v0-minishop-e-commerce-demo`).

The design source is a complete Next.js 16 / React 19 / shadcn TSX project
that the implementing agent **mounts components from**. The agent's job is
**integration** (wire Prisma + NextAuth + server actions in place of the
mock `lib/*-context.tsx` providers and the inlined `lib/data.ts` arrays),
not re-creation. Component shells, layouts, theme tokens (`app/globals.css`),
and route URLs come from the v0 source.

What's authoritative from the design source:
- App Router file layout (`app/(auth)/`, `app/(storefront)/`, `app/admin/`) → URL routes
- shadcn/ui primitives in `components/ui/` → use as-is, do not reinvent
- Theme tokens in `app/globals.css` (`--primary`, `--background`, `--radius`, …) → reference via Tailwind classes
- Component shells (`storefront-header.tsx`, `admin-sidebar.tsx`, `product-card.tsx`, `variant-picker.tsx`, `site-footer.tsx`) → mount, then wire data
- shadcn config (`components.json`: style "new-york", baseColor "neutral", cssVariables true)

What the agent **discards and replaces** from the design source:
- `lib/auth-context.tsx`, `lib/cart-context.tsx`, `lib/orders-context.tsx` — mock React contexts. Replace with NextAuth session + server-action-driven cart bound to `session_id` cookie.
- `lib/data.ts` — inlined sample arrays. Replace with Prisma queries against the schema below. Re-use product / order shape only as a starting reference; the canonical schema is the Prisma model in this spec.
- `lib/types.ts` — design-source TS types. Replace with Prisma-generated types where they overlap.

The design-fidelity gate uses `docs/content-fixtures.yaml` (if present) to render both the design source and the agent build with the same data, then screenshot-diffs them at three viewports.

## Starting Point

There is NO application code in the scaffold. Agents create everything from scratch.

Platform configs are deployed by `set-project init --project-type web --template nextjs` before orchestration starts: `playwright.config.ts` (with `PW_PORT` env var for port isolation), `vitest.config.ts`, `tsconfig.json`, `postcss.config.mjs`, `next.config.js`, `components.json`, `set/orchestration/config.yaml`, `.claude/rules/` (Server Actions, shadcn/ui, Prisma singleton, "use client" boundaries, form validation, auth conventions). **Do not duplicate those conventions here.**

**Setup (done by `run-minishop.sh` before orchestration):**
1. Copy this spec to `docs/v1-minishop.md`
2. `git init && set-project init --project-type web --template nextjs`
3. Orchestration starts — agents create everything from this spec

## Dependencies (package.json)

```jsonc
{
  "name": "minishop",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run",
    "test:e2e": "playwright test"
  },
  "prisma": { "seed": "tsx prisma/seed.ts" },
  "dependencies": {
    "next": "^16.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "@prisma/client": "^5.20.0",
    "next-auth": "5.0.0-beta.25",
    "bcryptjs": "^2.4.3",
    "zod": "^3.23.0",
    "react-hook-form": "^7.54.0",
    "@hookform/resolvers": "^3.9.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^3.0.0",
    "lucide-react": "^0.500.0",
    "next-themes": "^0.4.0",
    "sonner": "^1.7.0",
    "class-variance-authority": "^0.7.0"
    // shadcn primitives drag in their own @radix-ui/react-* deps;
    // keep package.json in sync with v0-export/package.json on import.
  },
  "devDependencies": {
    "typescript": "^5.7.0",
    "prisma": "^5.20.0",
    "tsx": "^4.19.0",
    "@types/node": "^22.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@types/bcryptjs": "^2.4.6",
    "vitest": "^3.0.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.6.0",
    "@vitejs/plugin-react": "^4.3.0",
    "jsdom": "^25.0.0",
    "@playwright/test": "^1.48.0",
    "tailwindcss": "^4.0.0",
    "@tailwindcss/postcss": "^4.0.0",
    "postcss": "^8.4.0"
  }
}
```

## Prisma Schema

SQLite (`file:./dev.db`). Variant attributes are stored as a JSON blob — no normalized attribute tables.

```prisma
generator client { provider = "prisma-client-js" }
datasource db { provider = "sqlite"; url = "file:./dev.db" }

model Product {
  id          Int              @id @default(autoincrement())
  name        String
  description String           @default("")
  basePrice   Int                                   // EUR cents — fallback when variant.price is null
  imageUrl    String           @default("")
  createdAt   DateTime         @default(now())
  updatedAt   DateTime         @updatedAt
  variants    ProductVariant[]
}

model ProductVariant {
  id         Int         @id @default(autoincrement())
  productId  Int
  product    Product     @relation(fields: [productId], references: [id], onDelete: Cascade)
  sku        String      @unique
  label      String                                 // human-readable: "Black", "Red Switches", "Black / Red"
  attributes Json                                   // { color?: "Black", switch?: "Red" } — for the variant-picker UI
  price      Int?                                   // EUR cents — null = use Product.basePrice
  stock      Int         @default(0)
  createdAt  DateTime    @default(now())
  updatedAt  DateTime    @updatedAt
  cartItems  CartItem[]
  orderItems OrderItem[]
}

model User {
  id        Int      @id @default(autoincrement())
  name      String   @default("")
  email     String   @unique
  password  String                                  // bcryptjs hash
  role      String   @default("USER")               // "USER" | "ADMIN"
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
  orders    Order[]
}

model CartItem {
  id        Int            @id @default(autoincrement())
  sessionId String                                  // anonymous session cookie UUID
  quantity  Int            @default(1)
  variantId Int
  variant   ProductVariant @relation(fields: [variantId], references: [id], onDelete: Cascade)
  createdAt DateTime       @default(now())
  updatedAt DateTime       @updatedAt

  @@unique([sessionId, variantId])
}

model Order {
  id           Int         @id @default(autoincrement())
  sessionId    String                              // retained for cart-lineage audit
  userId       Int
  user         User        @relation(fields: [userId], references: [id])
  status       String      @default("PENDING")    // "PENDING" | "COMPLETED" | "CANCELLED"
  total        Int                                 // EUR cents — sum of line items
  // Cash-on-delivery shipping info captured at checkout (all required)
  customerName String
  phone        String
  addressLine  String
  city         String
  postcode     String
  createdAt    DateTime    @default(now())
  updatedAt    DateTime    @updatedAt
  items        OrderItem[]

  @@index([userId, createdAt])
  @@index([status, createdAt])
}

model OrderItem {
  id           Int            @id @default(autoincrement())
  quantity     Int
  price        Int                                 // snapshot of variant price at order time
  variantLabel String                              // snapshot: "Black / Red Switches"
  productName  String                              // snapshot: "Mechanical Keyboard"
  orderId      Int
  order        Order          @relation(fields: [orderId], references: [id], onDelete: Cascade)
  variantId    Int
  variant      ProductVariant @relation(fields: [variantId], references: [id])
}
```

## Seed Data

Idempotent (`upsert` for users, `deleteMany` + `createMany` for products/variants).

### Users

| email | password (plain) | role |
|-------|------------------|------|
| `admin@example.com` | `password123` | ADMIN |
| `alice@example.com` | `password123` | USER |

The USER seed exists so E2E checkout tests can sign in without going through registration.

### Products & Variants (5 products, 11 variants)

**1. Wireless Earbuds Pro** — basePrice 8999, image `https://placehold.co/400x300/EBF4FF/1E40AF?text=Earbuds+Pro&font=roboto`
description: "Crystal-clear audio with active noise cancellation. 24-hour battery life."

| SKU | label | attributes | price | stock |
|-----|-------|------------|-------|-------|
| EARBUDS-BLK | Black | `{"color":"Black"}` | null | 15 |
| EARBUDS-WHT | White | `{"color":"White"}` | null | 8 |
| EARBUDS-SLV | Silver | `{"color":"Silver"}` | null | 5 |

**2. Mechanical Keyboard** — basePrice 12999, image `https://placehold.co/400x300/FEF3C7/92400E?text=Keyboard&font=roboto`
description: "Cherry MX switches with RGB backlighting. Aluminum frame, programmable keys."

| SKU | label | attributes | price | stock |
|-----|-------|------------|-------|-------|
| KB-RED | Red Switches | `{"switch":"Red"}` | null | 5 |
| KB-BLUE | Blue Switches | `{"switch":"Blue"}` | null | 4 |
| KB-BROWN | Brown Switches | `{"switch":"Brown"}` | null | 3 |

**3. Wireless Mouse** — basePrice 3999, image `https://placehold.co/400x300/F3E8FF/6B21A8?text=Mouse&font=roboto`
description: "Precision optical sensor with adjustable DPI. Ergonomic design for all-day comfort."
**No variants** — single product card, no variant picker.

| SKU | label | attributes | price | stock |
|-----|-------|------------|-------|-------|
| MOUSE-DEFAULT | Default | `{}` | null | 12 |

**4. Phone Stand** — basePrice 2499, image `https://placehold.co/400x300/FFE4E6/9F1239?text=Phone+Stand&font=roboto`
description: "Aluminum stand with 360° rotation. Compatible with all phones and tablets."

| SKU | label | attributes | price | stock |
|-----|-------|------------|-------|-------|
| STAND-SLV | Silver | `{"color":"Silver"}` | null | 20 |
| STAND-GRY | Space Gray | `{"color":"Space Gray"}` | null | 15 |
| STAND-ROSE | Rose Gold | `{"color":"Rose Gold"}` | 2799 | 0 |

`STAND-ROSE` has `stock=0` to test the out-of-stock UI path. The product card stays "In Stock" because at least one variant has stock; the variant picker disables Rose Gold.

**5. USB-C Hub 7-in-1** — basePrice 4999, image `https://placehold.co/400x300/F0FDF4/166534?text=USB-C+Hub&font=roboto`
description: "7 ports including HDMI, USB 3.0, SD card. Single-cable expansion for laptops."
**No variants.**

| SKU | label | attributes | price | stock |
|-----|-------|------------|-------|-------|
| USBC-DEFAULT | Default | `{}` | null | 30 |

## Environment

No `.env` needed:
- **Database:** SQLite URL hardcoded in Prisma schema (`file:./dev.db`)
- **NextAuth secret:** `process.env.NEXTAUTH_SECRET ?? "dev-secret-do-not-use-in-production"` in auth config
- **NextAuth URL:** auto-detected on localhost

## Project-Specific Conventions

Only what is NOT in `.claude/rules/`:

- **Package manager:** pnpm
- **Install shadcn components:** `pnpm dlx shadcn@latest add <component>`
- **Currency:** EUR, stored as integer cents. Format: `` `€${(price / 100).toFixed(2)}` `` (`€129.99`).
- **Anonymous cart session:** httpOnly cookie `session_id` (UUID via `crypto.randomUUID()`).
- **Server Actions** for all mutations (add to cart, place order, register, etc.). No `/api/*` route handlers other than `/api/health`.
- **Tests:** Vitest + `@testing-library/react` for unit; Playwright for E2E (`pnpm test:e2e`).

## Features

### Storefront — Product Catalog

- `/` redirects to `/products`
- `/products` — grid of all 5 products. One card per product (NOT per variant). Each card shows:
  - Image, name, price (range when variants differ, single when uniform or no variants)
  - "In Stock" / "Out of Stock" badge — OOS only when ALL variants of the product have stock=0
  - "View Details" button → `/products/[id]`
- `/products/[id]` — detail page:
  - "← Back to Products" link top
  - Image, name, full description
  - Variant picker(s): one selector per attribute key in `variant.attributes` (e.g. Color, Switch). Products with empty attributes (`{}`) show no picker.
  - Price + stock badge update with selected variant
  - "Add to Cart" button — disabled with "Out of Stock" text when selected variant has stock=0
- `/api/health` returns `{ ok: true }`

Layout uses a `(shop)` route group with shared header. Header contains: brand link, Products, Cart (with item-count badge), Orders (visible when authenticated), and either Sign In or a user menu (name + Sign Out).

### Shopping Cart

Server-side cart bound to the anonymous `session_id` cookie. Cart items reference **variants**, not products.

- Add to cart from product detail (after picking a variant)
- Same variant added twice → quantity increments
- Different variants of the same product → separate lines
- Per-line "+" / "−" buttons and "Remove" button
- Cart total = sum of `effectivePrice * quantity` where `effectivePrice = variant.price ?? product.basePrice`
- Cannot add an out-of-stock variant (server-side guard, not just disabled UI)
- Cart persists across navigation
- Empty state: "Your cart is empty" + link to `/products`
- "Checkout" button at the bottom of the cart summary (disabled when empty)
  - Anonymous users see "Sign in to checkout" linking to `/login?returnTo=/checkout`

### Checkout (Cash on Delivery)

- `/checkout` — login required (unauthenticated → redirect to `/login?returnTo=/checkout`)
- Form fields (all required, validated with zod):
  - `customerName` — non-empty
  - `phone` — non-empty (no format validation in v1)
  - `addressLine` — non-empty
  - `city` — non-empty
  - `postcode` — non-empty
- Order summary panel beside the form: line items, line totals, grand total
- Payment is **cash on delivery only** — display "Payment: Cash on delivery" as a static info row. No payment form, no card input.
- "Place Order" submits the form → calls `placeOrder` server action.

`placeOrder` server action (transactional):
1. Assert authenticated session — return auth error otherwise (no silent guest order)
2. Load cart for current `session_id`; reject if empty
3. Verify each variant has `stock >= quantity`; reject if any variant is short (no partial order)
4. Create `Order` (PENDING) + `OrderItem` rows with snapshot price, variant label, product name, and the shipping fields from the form
5. Decrement variant stock
6. Clear `CartItem` rows for the session
7. Return `{ orderId }` for the client to navigate

After success the client navigates to `/orders/[id]/thanks`.

### Orders

- `/orders/[id]/thanks` — confirmation page after a successful order. Shows order id, total, "Pay on delivery" reminder, and links to `/orders/[id]` (View order) and `/products` (Continue shopping). Ownership check: 404 if not the user's order.
- `/orders` — list of the current user's orders (filtered by `userId`), sorted by `createdAt` DESC. Columns: Order #, Date, Status, Total, "View" link. Auth required.
- `/orders/[id]` — order detail. Ownership check (404 if not yours). "← Back to Orders" link top, line items (product name, variant label, quantity, price), shipping address block, grand total.

### Authentication

NextAuth v5 with Credentials provider, JWT strategy, bcryptjs.

- `/login` — email + password form. Success → `returnTo` query param (default `/products`). Admin users (`role="ADMIN"`) are redirected to `/admin/orders` when no explicit `returnTo` is provided.
- `/register` — name + email + password form. Always creates a `USER`. Success → auto-login → `returnTo` (default `/products`). No email verification, no password reset.
- Anonymous cart is preserved across login: keep the `session_id` cookie unchanged so the same `CartItem` rows continue to belong to the user's active session until `placeOrder` clears them.

**Route protection matrix**

| Route                          | Anonymous | USER | ADMIN |
|--------------------------------|-----------|------|-------|
| `/products`, `/products/[id]`  | ✓ | ✓ | ✓ |
| `/cart` (view)                 | ✓ | ✓ | ✓ |
| `/checkout`                    | ✗ login | ✓ | ✓ |
| `placeOrder` action            | ✗ | ✓ | ✓ |
| `/orders`, `/orders/[id]`, `/orders/[id]/thanks` | ✗ login | ✓ own only | ✓ own only |
| `/admin/orders`, `/admin/orders/[id]`, `/admin/products` | ✗ login | 403 | ✓ |

`src/middleware.ts` enforces the `/admin/*` gate. Server actions independently re-check the session to fail closed if middleware is bypassed.

### Admin — Orders + Products (Read-Only)

The admin surface is intentionally narrow. No mutations: no product CRUD, no admin self-registration, no order status changes, no stock edits. Products and stock are conceptually owned by an external inventory system; the admin pages just observe.

- `/admin/orders` — paginated table of all orders (sorted by `createdAt` DESC). Columns: Order #, Customer (name, fallback email), Date, Status, Total, "View".
- `/admin/orders/[id]` — same line-item layout as the customer detail page, plus a customer info block (name, email) and the shipping address. The status field is read-only text; no buttons to mutate.
- `/admin/products` — read-only product overview. Top of page: an info banner / Alert component reading **"Products and stock are synced from the inventory system (read-only). To add or edit a product, use your inventory backend."** Below: a Table listing products with columns: Image (small thumbnail), Name, Variants (count), Total stock (sum across variants), Status badge ("In Stock" / "Out of Stock" — same rule as the storefront grid). No row-level actions, no buttons, no input fields. Empty cells acceptable for products without variants.
- AdminSidebar layout with three nav items: "Orders", "Products", "Sign Out". Brand label "MiniShop Admin" at the top. Active state highlights the current section.

There is NO `/admin`, NO `/admin/dashboard`, NO `/admin/products/[id]`, NO `/admin/products/new`, NO `/admin/register`. The single admin signs in through `/login` (the same form everyone uses) and is redirected to `/admin/orders`.

## Out of Scope (v1)

Explicitly excluded — these belong in `craftbrew`, not here:

- Online payment (Stripe, PayPal, etc.) — v1 is cash-on-delivery only
- Inventory management UI — admin cannot adjust stock (the `/admin/products` overview is read-only)
- Product CRUD UI — products are seed-only; admin cannot create, edit, or delete them
- Order status transitions (PENDING → COMPLETED, etc.)
- Email confirmations, notifications
- Reviews, ratings, wishlists
- Search, filtering, sorting on the storefront grid
- Discount codes, promotions
- Multi-currency, internationalization
- Guest checkout — login is mandatory before placing an order
- Password reset, email verification
- Two-factor auth, social login
- Image upload (admin uploads), CDN

## Test Selectors (`data-testid` registry)

The v0 design source has NO `data-testid` attributes — they're a runtime
testing concern, not a design concern. When porting v0 components into
`src/components/` (or adapting page TSX), ADD these `data-testid`
attributes. Playwright tests reference them by name; missing testids
cause selector failures, not test errors that reveal the cause.

| `data-testid` | Where | Notes |
|---|---|---|
| `header-cart-icon` | storefront-header — Cart link | Visible on every storefront page |
| `header-cart-badge` | storefront-header — item count badge | Only present when cart is non-empty |
| `header-user-menu` | storefront-header — DropdownMenu trigger | Visible only when authenticated |
| `header-signin-link` | storefront-header — Sign In link | Visible only when anonymous |
| `product-card` | products grid — each card | Repeats N times; has `data-product-id` attribute |
| `product-add-to-cart` | products/[id] — primary CTA | Disabled when selected variant is OOS; text becomes "Out of Stock" |
| `product-variant-picker` | products/[id] — variant selector wrapper | Absent when product has no variants |
| `cart-item-row` | cart — one per cart line | Has `data-variant-id` attribute |
| `cart-grand-total` | cart — total amount text | Updates when quantity changes |
| `cart-checkout-button` | cart — primary CTA | Disabled when cart empty; replaced with "Sign in to checkout" link when anonymous |
| `checkout-form` | checkout — form root |  |
| `checkout-place-order` | checkout — submit button |  |
| `order-status-badge` | orders list + detail | Has `data-status="PENDING"` etc. (UPPER_SNAKE_CASE matching `Order.status` enum) |
| `admin-sidebar` | admin-sidebar — root nav | Has nested `data-testid="admin-nav-orders"`, `admin-nav-products`, `admin-nav-signout` items |
| `admin-products-readonly-banner` | admin/products — Alert at the top | Asserts the read-only-products contract is communicated in UI |
| `error-banner` | any form / page that surfaces an error | Has `data-error-code` attribute when present |

Tests assert on these selectors; renaming any one breaks E2E. The list is
EXHAUSTIVE for v1 — if a test wants to assert on an element not listed
here, add the testid to this registry first, then to the component.

## Design ↔ Spec Alignment Notes

Where the design source and the spec contradict, the **spec wins** for
implementation contracts; the design wins for visual layout. Known
divergences:

| Concern | Design source | Spec (canonical) | Resolution |
|---|---|---|---|
| ID type | `string` ("1", "1-black") | `Int` (autoincrement) | Spec — agent uses Prisma `Int @id @default(autoincrement())` |
| Price type | `number` (89.99) | `Int` cents (8999) | Spec — store as cents, format on render |
| Order status casing | `"pending" \| "completed" \| "cancelled"` | `"PENDING" \| "COMPLETED" \| "CANCELLED"` | Spec — UPPER_SNAKE_CASE; map for display when needed |
| Auth model | `lib/auth-context.tsx` mock | NextAuth v5 + bcryptjs | Spec — discard mock context, mount NextAuth; design's signed-in state shape is implied by what the header renders |
| Cart model | `lib/cart-context.tsx` (in-memory React state) | Server-side cart bound to `session_id` cookie + Prisma `CartItem` | Spec — discard context, replace `useCart()` consumers with server actions returning fresh data |
| User shape | `{ id, name, email, isAdmin?: boolean }` | `User` Prisma model with `role: "USER" \| "ADMIN"` | Spec — `role` enum, derive `isAdmin = role === "ADMIN"` for UI conditionals |
| Variant shape | `{ id, attributes, price, stock }` (no SKU, no label) | Prisma `ProductVariant` with `sku` (unique), `label`, `attributes`, `price?`, `stock` | Spec — `sku` and `label` are required; design's missing fields are added during implementation |
| Image source | `/images/<slug>.jpg` (static path) | placehold.co URLs in seed | Spec — seed uses placeholders to avoid binary asset management; agent may swap to real images later |
| Currency format | `€${price.toFixed(2)}` from `formatPrice()` in `lib/data.ts` | `€${(cents / 100).toFixed(2)}` (cents-aware) | Both produce `€89.99`; agent must port the cents-aware version |

Footer (`components/site-footer.tsx`) is mounted in `(storefront)/layout.tsx`
in the design source; the agent keeps that mount in place after wiring real
data.
