# MiniShop v1 — Webshop Feature Spec

> Next.js 14+ App Router webshop with Prisma (SQLite), shadcn/ui, Tailwind CSS, NextAuth.js v5

## Design

**Figma Design:** https://www.figma.com/make/9PH3uS4vWjSj6cUPhTGZSt/set-minishop?p=f&t=zvhTdumJeYUpKrJm-0

**Local design snapshot:** `docs/figma-raw/9PH3uS4vWjSj6cUPhTGZSt/` — pre-fetched via `set-figma-fetch`, contains source files, Tailwind tokens, component hierarchy, and assembled `design-snapshot.md`. Re-fetch with `set-figma-fetch --force docs/` if the Figma design changes.

## Starting Point

There is NO application code in the scaffold. Agents create everything from scratch.

Platform configs are deployed by `set-project init --project-type web --template nextjs` before orchestration starts. This includes: `playwright.config.ts` (with `PW_PORT` env var for port isolation), `vitest.config.ts`, `tsconfig.json`, `postcss.config.mjs`, `next.config.js`, `components.json`, `wt/orchestration/config.yaml`, and `.claude/rules/` covering Server Actions, shadcn/ui, Prisma singleton, "use client" rules, form validation, auth conventions, DataTable patterns. **Do not duplicate those conventions here.**

**Setup (done by `run.sh` before orchestration):**
1. Copy this spec to `docs/v1-minishop.md`
2. `git init && set-project init --project-type web --template nextjs`
3. Orchestration starts — agents create everything from this spec

## Dependencies (package.json)

Agents must create `package.json` with these dependencies:

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
  "prisma": {
    "seed": "tsx prisma/seed.ts"
  },
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "@prisma/client": "^5.20.0",
    "next-auth": "5.0.0-beta.25",
    "bcryptjs": "^2.4.3",
    "zod": "^3.23.0",
    "react-hook-form": "^7.53.0",
    "@hookform/resolvers": "^3.9.0",
    "@tanstack/react-table": "^8.20.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.5.0",
    "lucide-react": "^0.460.0",
    // shadcn/ui peer deps (installed by `pnpm dlx shadcn@latest add`)
    "@radix-ui/react-slot": "^1.1.0",
    "class-variance-authority": "^0.7.0"
  },
  "devDependencies": {
    "typescript": "^5.6.0",
    "prisma": "^5.20.0",
    "tsx": "^4.19.0",
    "@types/node": "^22.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@types/bcryptjs": "^2.4.6",
    "vitest": "^3.0.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.6.0",
    "@vitejs/plugin-react": "^4.3.0",
    "jsdom": "^25.0.0",
    "@playwright/test": "^1.48.0",
    "tailwindcss": "^4.0.0",
    "postcss": "^8.4.0"
  }
}
```

## Prisma Schema

Database: SQLite (`file:./dev.db`). Create `prisma/schema.prisma`:

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "sqlite"
  url      = "file:./dev.db"
}

model Product {
  id               Int              @id @default(autoincrement())
  name             String
  shortDescription String           @default("")     // shown on catalog card
  description      String           @default("")     // shown on detail page
  basePrice        Int                               // EUR cents — default price when no variant price override
  imageUrl         String           @default("")
  createdAt        DateTime         @default(now())
  updatedAt        DateTime         @updatedAt
  attributes       ProductAttribute[]
  variants         ProductVariant[]
}

model AttributeType {
  id        Int                @id @default(autoincrement())
  name      String             @unique          // e.g. "Color", "Size", "Memory"
  products  ProductAttribute[]
  values    VariantAttributeValue[]
}

model ProductAttribute {
  id              Int           @id @default(autoincrement())
  productId       Int
  product         Product       @relation(fields: [productId], references: [id], onDelete: Cascade)
  attributeTypeId Int
  attributeType   AttributeType @relation(fields: [attributeTypeId], references: [id])
  displayOrder    Int           @default(0)      // UI ordering of attribute selectors

  @@unique([productId, attributeTypeId])         // one attribute type per product
}

model ProductVariant {
  id         Int         @id @default(autoincrement())
  productId  Int
  product    Product     @relation(fields: [productId], references: [id], onDelete: Cascade)
  sku        String      @unique                 // e.g. "HEADPHONES-BLK-L"
  price      Int?                                // EUR cents — null means use Product.basePrice
  stock      Int         @default(0)
  createdAt  DateTime    @default(now())
  updatedAt  DateTime    @updatedAt
  attributes VariantAttributeValue[]
  cartItems  CartItem[]
  orderItems OrderItem[]
}

model VariantAttributeValue {
  id              Int            @id @default(autoincrement())
  variantId       Int
  variant         ProductVariant @relation(fields: [variantId], references: [id], onDelete: Cascade)
  attributeTypeId Int
  attributeType   AttributeType  @relation(fields: [attributeTypeId], references: [id])
  value           String                         // e.g. "Black", "XL", "16GB"

  @@unique([variantId, attributeTypeId])         // one value per attribute per variant
}

model User {
  id        Int      @id @default(autoincrement())
  name      String   @default("")
  email     String   @unique
  password  String                        // bcryptjs hash
  role      String   @default("USER")     // "USER" | "ADMIN"
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
  orders    Order[]
}

model CartItem {
  id        Int            @id @default(autoincrement())
  sessionId String                              // anonymous session cookie UUID
  quantity  Int            @default(1)
  variantId Int
  variant   ProductVariant @relation(fields: [variantId], references: [id], onDelete: Cascade)
  createdAt DateTime       @default(now())
  updatedAt DateTime       @updatedAt

  @@unique([sessionId, variantId])               // one cart item per variant per session
}

model Order {
  id        Int         @id @default(autoincrement())
  sessionId String                        // ties anonymous orders to session
  userId    Int?                          // optional — linked if logged in
  user      User?       @relation(fields: [userId], references: [id])
  status    String      @default("PENDING")  // "PENDING" | "COMPLETED" | "CANCELLED"
  total     Int                           // EUR cents, sum of line items
  createdAt DateTime    @default(now())
  updatedAt DateTime    @updatedAt
  items     OrderItem[]
}

model OrderItem {
  id              Int            @id @default(autoincrement())
  quantity        Int
  price           Int                            // snapshot of variant price at order time
  variantLabel    String         @default("")     // snapshot: "Black / Large" — human-readable
  orderId         Int
  order           Order          @relation(fields: [orderId], references: [id], onDelete: Cascade)
  variantId       Int
  variant         ProductVariant @relation(fields: [variantId], references: [id])
}
```

## Seed Data

Create `prisma/seed.ts`. Seed is idempotent (use `upsert` / `deleteMany` + `createMany` pattern).

### Attribute Types

| id | name |
|----|------|
| 1 | Color |
| 2 | Switch Type |

### Products & Variants

Product names and descriptions match the Figma design (`mockData.ts`).

**Product 1: Wireless Earbuds Pro** — basePrice: 8999, attributes: Color
- description: "Experience crystal-clear audio with active noise cancellation. Premium wireless earbuds with 24-hour battery life and premium sound quality."
- shortDescription: "Premium noise-canceling earbuds"

| SKU | Color | price (override) | stock |
|-----|-------|------------------|-------|
| EARBUDS-BLK | Black | null (=8999) | 15 |
| EARBUDS-WHT | White | null | 8 |
| EARBUDS-SLV | Silver | null | 5 |

**Product 2: USB-C Hub 7-in-1** — basePrice: 4999, attributes: Color
- description: "Expand your laptop's capabilities with 7 ports including HDMI, USB 3.0, SD card reader, and more. Perfect for professionals on the go."
- shortDescription: "Multi-port connectivity adapter"

| SKU | Color | price (override) | stock |
|-----|-------|------------------|-------|
| USBC-GRAY | Space Gray | null (=4999) | 30 |
| USBC-SLV | Silver | null | 20 |

**Product 3: Mechanical Keyboard** — basePrice: 12999, attributes: Switch Type, Color
- description: "Cherry MX switches with customizable RGB lighting. Durable aluminum frame and programmable keys for the ultimate typing experience."
- shortDescription: "RGB backlit gaming keyboard"

| SKU | Switch Type | Color | price (override) | stock |
|-----|-------------|-------|------------------|-------|
| KB-RED-BLK | Red | Black | null (=12999) | 5 |
| KB-BLUE-BLK | Blue | Black | null | 4 |
| KB-BROWN-BLK | Brown | Black | null | 3 |
| KB-RED-WHT | Red | White | 13499 | 3 |
| KB-BLUE-WHT | Blue | White | 13499 | 2 |
| KB-BROWN-WHT | Brown | White | 13499 | 2 |

**Product 4: Wireless Mouse** — basePrice: 3999, attributes: Color
- description: "Precision optical sensor with adjustable DPI. Ergonomic design for all-day comfort. Works seamlessly across multiple devices."
- shortDescription: "Ergonomic design, 6 buttons"

| SKU | Color | price (override) | stock |
|-----|-------|------------------|-------|
| MOUSE-BLK | Black | null (=3999) | 12 |
| MOUSE-WHT | White | null | 10 |
| MOUSE-GRY | Gray | null | 8 |

**Product 5: Phone Stand Adjustable** — basePrice: 2499, attributes: Color
- description: "Sleek aluminum stand with 360° rotation and adjustable viewing angles. Compatible with all smartphones and tablets."
- shortDescription: "Aluminum desktop holder"

| SKU | Color | price (override) | stock |
|-----|-------|------------------|-------|
| STAND-SLV | Silver | null (=2499) | 20 |
| STAND-GRAY | Space Gray | null | 15 |
| STAND-ROSE | Rose Gold | 2799 | 10 |

**Product 6: 4K Webcam** — basePrice: 15999, attributes: Resolution, Color
- description: "Ultra HD 4K resolution with auto-focus and built-in microphone. Perfect for streaming, video calls, and content creation."
- shortDescription: "Professional streaming camera"

| SKU | Resolution | Color | price (override) | stock |
|-----|------------|-------|------------------|-------|
| CAM-1080-BLK | 1080p | Black | 9999 | 0 |
| CAM-1080-WHT | 1080p | White | 9999 | 0 |
| CAM-4K-BLK | 4K | Black | null (=15999) | 0 |
| CAM-4K-WHT | 4K | White | null | 0 |

Product #6: ALL variants have stock=0 (used to test "Out of Stock" behavior).

imageUrl per product (placehold.co — reliable, no 404 risk):

| # | imageUrl |
|---|----------|
| 1 | `https://placehold.co/400x300/EBF4FF/1E40AF?text=Earbuds+Pro&font=roboto` |
| 2 | `https://placehold.co/400x300/F0FDF4/166534?text=USB-C+Hub&font=roboto` |
| 3 | `https://placehold.co/400x300/FEF3C7/92400E?text=Keyboard&font=roboto` |
| 4 | `https://placehold.co/400x300/F3E8FF/6B21A8?text=Mouse&font=roboto` |
| 5 | `https://placehold.co/400x300/FFE4E6/9F1239?text=Phone+Stand&font=roboto` |
| 6 | `https://placehold.co/400x300/E5E7EB/374151?text=4K+Webcam&font=roboto` |

## Environment

No `.env` file is needed:
- **Database:** SQLite URL is hardcoded in the Prisma schema (`file:./dev.db`)
- **NextAuth secret:** Use `process.env.NEXTAUTH_SECRET ?? "dev-secret-do-not-use-in-production"` in auth config
- **NextAuth URL:** NextAuth v5 auto-detects localhost in dev

## Project-Specific Conventions

Only conventions NOT covered by `.claude/rules/`:

- **Package manager:** pnpm (`pnpm dev`, `pnpm test`, `pnpm build`)
- **Install shadcn components:** `pnpm dlx shadcn@latest add <component>`
- **Currency:** Euro (EUR). Prices stored as integer cents. Format: `new Intl.NumberFormat("en-US", { style: "currency", currency: "EUR" }).format(price / 100)` yielding `€1,299.99`. Simpler alternative: `` `€${(price / 100).toFixed(2)}` ``.
- **Session:** Anonymous cart uses a `session_id` httpOnly cookie (UUID via `crypto.randomUUID()`).
- **Tests:** Vitest + `@testing-library/react` for unit tests (`pnpm test`). Playwright for E2E (`pnpm test:e2e`). `playwright.config.ts` and `vitest.config.ts` are deployed by the template — do not recreate them.

## Feature Roadmap

### Change 1: `products-page`

Build the product catalog -- the storefront landing page.

**Create these files:**

- `src/lib/utils.ts` -- `cn()` helper (clsx + tailwind-merge)
- `src/lib/prisma.ts` -- Prisma singleton client
- `src/lib/variants.ts` -- Variant helper functions:
  - `getEffectivePrice(variant, product)` -- returns `variant.price ?? product.basePrice`
  - `getPriceRange(product)` -- returns `{ min, max }` across all variants (for catalog card)
  - `getTotalStock(product)` -- sum of all variant stocks
  - `formatVariantLabel(variant)` -- "Black / Large" from variant attribute values
- `src/app/globals.css` -- Tailwind directives + shadcn CSS variables
- `src/app/layout.tsx` -- Root layout: globals.css, navigation header. Follow Figma design for nav structure and typography.
- `src/app/page.tsx` -- Redirect to `/products`
- `src/app/api/health/route.ts` -- `GET` returns `{ status: "ok" }` (used by smoke checks)
- `src/app/products/page.tsx` -- Product grid. Server Component, query products with variants included. Responsive grid using shadcn Card. Each card shows: product name, image, price range (e.g. "from €79.99" or just "€34.99" if all variants same price), total stock status. Follow Figma design for layout and breakpoints.
- `src/app/products/[id]/page.tsx` -- Product detail page. Follow Figma design for layout. Shows variant selectors (dropdowns/buttons per attribute type, e.g. Color picker + Size picker). Selected variant determines displayed price and stock. "Add to Cart" button (disabled until cart-feature). Products with no attributes (e.g. USB-C Hub) show no selectors -- just the single variant's price/stock.
- `src/components/product-card.tsx` -- Reusable card component for catalog grid.
- `src/components/variant-selector.tsx` -- Client Component (`"use client"`). Renders attribute selectors using RadioGroup with pill-style labels (per Figma design: `border-2 border-gray-300 rounded-lg px-4 py-2`, selected: `border-blue-600 bg-blue-50 text-blue-900`). One RadioGroup per attribute type. Manages selected combination state, calls back with selected variantId. Disables unavailable combinations (stock=0).
- `tests/products.test.tsx` -- Product list renders, detail renders, price formatting, variant selection logic.

**Install shadcn components:** button, card, badge, radio-group, label

**Acceptance criteria:**
- `/products` shows all 6 seeded products in a Card grid (one card per product, NOT per variant)
- Card shows price range when variants have different prices (e.g. "€129.99 – €134.99"), or single price when uniform
- Card shows aggregate stock: "Out of Stock" only when ALL variants are stock=0
- `/products/[id]` shows single product detail with variant selectors
- Variant selectors appear for products with attributes (Headphones: Color+Size, Keyboard: Color+Switch, etc.)
- No selectors for products without attributes (USB-C Hub)
- Selecting a variant updates displayed price and stock
- Out-of-stock variant: disabled "Add to Cart", "Out of Stock" indicator
- Price displayed as `€1,299.99` format
- Responsive layout matching Figma design (desktop + mobile)
- Navigation header on all pages matching Figma design
- `pnpm test` passes (vitest)

---

### Change 2: `cart-feature`

> depends_on: products-page

Server-side shopping cart with anonymous sessions (no auth required). Cart items reference **variants**, not products.

**Create these files:**

- `src/lib/session.ts` -- Get/set session ID from cookies. If no `session_id` cookie, generate UUID and set as httpOnly cookie.
- `src/actions/cart.ts` -- Server Actions:
  - `addToCart(variantId, quantity)` -- upsert CartItem by `[sessionId, variantId]`; validate variant stock > 0
  - `removeFromCart(cartItemId)` -- delete CartItem
  - `updateCartQuantity(cartItemId, quantity)` -- update or delete if <= 0
  - All revalidate `/cart`
- `src/app/cart/page.tsx` -- Cart page with item list, quantity controls, totals, and empty state. Each line shows: product name, variant label (e.g. "Black / Large"), effective price, quantity, subtotal. Follow Figma design for layout.
- `src/app/products/[id]/page.tsx` -- **Update:** Wire "Add to Cart" to `addToCart` action with selected variantId. Toast on success. Button disabled if no variant selected or variant out of stock.
- `src/app/layout.tsx` -- **Update:** Cart item count badge on nav.
- `tests/cart.test.tsx` -- Add variant to cart, remove, quantity update, empty cart, same variant added twice increments quantity, different variants of same product = separate line items.

**Install shadcn components:** toast, separator, input

**Acceptance criteria:**
- "Add to Cart" on product detail adds the selected variant to cart
- Must select a variant before adding (for products with attributes)
- Cart page shows items with variant labels, quantities, and totals
- +/- buttons update quantity
- Remove button works
- Same variant added twice increments quantity (not duplicate line)
- Different variants of same product = separate cart lines (e.g. Black/M and White/L Headphones)
- Cart total = sum(effective_price * quantity)
- Cannot add out-of-stock variant to cart
- Session persists across navigations
- `pnpm test` passes (vitest)

---

### Change 3: `orders-checkout`

> depends_on: cart-feature, products-page

Convert cart to order, manage stock, show order history. Stock is managed per **variant**.

**Create these files:**

- `src/actions/orders.ts` -- Server Actions:
  - `placeOrder()` -- Transactional (`prisma.$transaction`): verify variant stock -> create Order + OrderItems (snapshot effective price + variant label) -> decrement variant stock -> clear cart. Error if cart empty or any variant has insufficient stock. Stock check and decrement MUST be in same transaction.
  - Revalidates `/orders` and `/products`
- `src/app/orders/page.tsx` -- Order history for current session. Follow Figma design for layout.
- `src/app/orders/[id]/page.tsx` -- Order detail with line items. Each line shows product name, variant label, quantity, price, subtotal. Follow Figma design for layout.
- `src/app/cart/page.tsx` -- **Update:** "Place Order" button. Redirect to order detail on success. Error toast on failure.
- `tests/orders.test.tsx` -- Place order, variant stock decremented, history, empty cart error, insufficient variant stock error.

**Install shadcn components:** table

**Acceptance criteria:**
- "Place Order" creates order and clears cart
- Order creation is transactional (all or nothing)
- Variant stock decremented after order (not product-level)
- OrderItem snapshots: effective price + variant label at order time
- Empty cart -> error
- Insufficient variant stock -> error (no partial order)
- Orders page shows history with totals
- Order detail shows line items with variant labels
- `pnpm test` passes (vitest)

---

### Change 4: `admin-auth`

> depends_on: products-page

Admin authentication. **Only admin routes are protected** -- storefront remains fully public.

**Create these files:**

- `src/lib/auth.ts` -- NextAuth config: Credentials provider, JWT strategy, bcryptjs. Include user.id and user.role in session/JWT callbacks.
- `src/app/api/auth/[...nextauth]/route.ts` -- NextAuth route handler
- `src/app/admin/login/page.tsx` -- Login form. Follow Figma design for layout.
- `src/app/admin/register/page.tsx` -- Registration form. Auto-login after register. Follow Figma design.
- `src/app/admin/page.tsx` -- Dashboard with quick stats. Follow Figma design for layout.
- `src/app/admin/layout.tsx` -- Admin layout with sidebar navigation. Follow Figma design.
- `middleware.ts` -- Match `/admin/:path*` EXCEPT `/admin/login` and `/admin/register`. Do NOT protect storefront routes.
- `tests/auth.test.tsx` -- Register, login success/failure, admin routes protected, storefront public.

**Install shadcn components:** label, input, dialog

**Acceptance criteria:**
- Register creates user, redirects to admin dashboard
- Login: correct credentials -> admin, wrong -> error
- `/admin/*` requires auth (redirect to login)
- `/admin/login` and `/admin/register` publicly accessible
- `/products`, `/cart`, `/orders` remain public -- NO auth
- Middleware ONLY protects admin routes
- `pnpm test` passes (vitest)

---

### Change 5: `admin-products`

> depends_on: admin-auth, products-page

Admin CRUD for products with DataTable. Includes variant management.

**Create these files:**

- `src/app/admin/products/page.tsx` -- Product list with DataTable (per Figma: table with image thumbnail, name+shortDescription, basePrice, aggregate stock, edit/delete actions). Follow Figma design for layout.
- `src/app/admin/products/columns.tsx` -- Column definitions (`"use client"`)
- `src/app/admin/products/data-table.tsx` -- DataTable wrapper (`"use client"`)
- `src/app/admin/products/new/page.tsx` -- Create product form with zod + react-hook-form validation. Fields: name, shortDescription, description, basePrice, imageUrl, attribute types (multi-select from existing AttributeTypes). Follow Figma design.
- `src/app/admin/products/[id]/edit/page.tsx` -- Edit form, pre-filled. Includes variant management: list existing variants, add/remove variants, edit variant SKU/price/stock/attribute values.
- `src/app/admin/products/[id]/variants/page.tsx` -- Dedicated variant management page. List all variants with their attribute values, price overrides, and stock. Add/edit/delete variants.
- `src/actions/admin-products.ts` -- `createProduct`, `updateProduct`, `deleteProduct`, `createVariant`, `updateVariant`, `deleteVariant`. All require auth check. Revalidate `/admin/products` and `/products`.
- `tests/admin-products.test.tsx` -- Create product, edit product, delete product, create/edit/delete variants, validation errors.

**Install shadcn components:** dropdown-menu, table

**Acceptance criteria:**
- Admin product list shows DataTable with aggregate info (total stock across variants)
- Create product: validated (name required, basePrice > 0), creates product + can add initial variants
- Edit product: pre-filled, updates product fields
- Manage variants: add variant with SKU + attribute values + stock, edit variant price/stock, delete variant
- Delete product: with confirmation, cascades to variants, removes from storefront
- All admin actions require auth
- Validation: SKU unique, stock >= 0, attribute values required for each product attribute type
- `pnpm test` passes (vitest)

---

**Note:** E2E tests (Playwright) should be included within each feature change, not as a separate change. The decompose/planning phase decides how to distribute e2e coverage across changes. `playwright.config.ts` is provided by the template with `PW_PORT` env var for port isolation across parallel worktrees.

## Reszletes Ellenorzesi Lista (Verification Checklist)

Post-run verification. Each item must be manually checkable:

### Storefront
- [ ] `/products` page shows exactly 6 product cards (one per product, NOT per variant)
- [ ] Product prices display in EUR format (e.g., basePrice 12999 displays as "€129.99")
- [ ] Products with variant price differences show price range (e.g. "€129.99 – €134.99")
- [ ] Products with uniform variant prices show single price
- [ ] Product #6 (4K Webcam) shows "Out of Stock" badge (all variants stock=0)
- [ ] Products with stock > 0 show "In Stock" badge (green, per Figma design)
- [ ] Product detail page (`/products/[id]`) shows full info in 2-column grid layout (image left, details right)
- [ ] Variant selectors render as RadioGroup pill-style buttons (per Figma: border-2, rounded-lg, blue highlight on selected)
- [ ] Mechanical Keyboard shows 2 selector groups: Switch Type + Color
- [ ] USB-C Hub 7-in-1 shows 1 selector group: Color (Space Gray, Silver)
- [ ] Selecting a variant updates displayed price and stock status
- [ ] Out-of-stock variant disables "Add to Cart" button
- [ ] Responsive layout matches Figma desktop and mobile designs
- [ ] Navigation header matches Figma design: MiniShop logo, Products, Cart (with icon), Orders, Admin links

### Cart
- [ ] "Add to Cart" from product detail page adds selected variant to cart
- [ ] Must select variant attributes before adding (for products with multiple variants)
- [ ] Cart page shows items with variant labels (e.g. "Black / Red"), quantities, and totals
- [ ] Adding the same variant twice increments quantity (no duplicates)
- [ ] Different variants of same product = separate cart lines
- [ ] Quantity controls (+/- buttons in gray pill, per Figma) update quantity
- [ ] Remove button (red trash icon) works
- [ ] Cart total equals sum of (effective_price * quantity) for all items
- [ ] Cart persists across page navigations (session cookie)
- [ ] Cannot add out-of-stock variant to cart

### Checkout & Orders
- [ ] "Place Order" button on cart page creates an order
- [ ] After order: cart is empty, variant stock is decremented
- [ ] Order creation is transactional (stock rollback on failure)
- [ ] Placing order with empty cart shows error
- [ ] Placing order when variant stock insufficient shows error (no partial order)
- [ ] `/orders` shows order history with date, status, total (table layout per Figma)
- [ ] `/orders/[id]` shows line items with product name, variant label, quantity, price, subtotal

### Admin Auth
- [ ] `/admin/register` -- create account, auto-redirect to admin dashboard
- [ ] `/admin/login` -- login with correct credentials succeeds (centered card layout with lock icon, per Figma)
- [ ] `/admin/login` -- login with wrong password shows error
- [ ] Visiting `/admin` without auth redirects to `/admin/login`
- [ ] `/admin/login` and `/admin/register` accessible without auth
- [ ] Storefront routes (`/products`, `/cart`, `/orders`) do NOT require auth

### Admin Products
- [ ] `/admin/products` shows DataTable with all products (thumbnail, name, basePrice, aggregate stock)
- [ ] Create product form validates: name required, basePrice > 0
- [ ] New product appears in storefront after creation (with at least one variant)
- [ ] Edit form pre-fills existing data, updates on save
- [ ] Variant management: add/edit/delete variants with SKU, attribute values, stock, price override
- [ ] Delete product requires confirmation, cascades to variants, removes from storefront
- [ ] All admin actions fail if not authenticated

### Tests & Quality
- [ ] `pnpm test` passes (Vitest unit tests)
- [ ] `pnpm test:e2e` passes (Playwright E2E)
- [ ] `pnpm build` succeeds without errors
