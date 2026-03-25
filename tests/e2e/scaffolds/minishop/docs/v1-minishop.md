# MiniShop v1 — Webshop Feature Spec

> Next.js 14+ App Router webshop with Prisma (SQLite), shadcn/ui, Tailwind CSS, NextAuth.js v5

## Design

**Figma Design:** https://www.figma.com/make/9PH3uS4vWjSj6cUPhTGZSt/set-minishop?p=f&t=zvhTdumJeYUpKrJm-0

**Local design snapshot:** `docs/figma-raw/9PH3uS4vWjSj6cUPhTGZSt/` — pre-fetched via `set-figma-fetch`, contains source files, Tailwind tokens, component hierarchy, and assembled `design-snapshot.md`. Re-fetch with `set-figma-fetch --force docs/` if the Figma design changes.

## Starting Point

There is NO application code in the scaffold. Agents create everything from scratch.

Platform configs are deployed by `set-project init --project-type web --template nextjs` before orchestration starts. This includes: `playwright.config.ts` (with `PW_PORT` env var for port isolation), `vitest.config.ts`, `tsconfig.json`, `postcss.config.mjs`, `next.config.js`, `components.json`, `set/orchestration/config.yaml`, and `.claude/rules/` covering Server Actions, shadcn/ui, Prisma singleton, "use client" rules, form validation, auth conventions, DataTable patterns. **Do not duplicate those conventions here.**

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

## Features

### Product Catalog (Storefront)

Product grid at `/products` showing all 6 seeded products (one card per product, NOT per variant). Each card:
- Product image
- Product name
- Price range (e.g. "€129.99 – €134.99" when variants differ, single price when uniform)
- Stock badge: "In Stock" (green) or "Out of Stock" (red, only when ALL variants are stock=0)
- **"View Details" button** linking to `/products/[id]`

Product detail at `/products/[id]`:
- **"← Back to Products" link** at top, linking back to `/products`
- Product image, name, full description
- Price display for selected variant
- Stock badge: "In Stock" / "Out of Stock" per selected variant
- Variant selectors — one selector per attribute type (e.g. Color picker, Switch Type picker). Selecting a variant updates displayed price and stock
- **"Add to Cart" button** (disabled with "Out of Stock" text when variant stock=0)
- Products without attributes show no selectors

Navigation header on all storefront pages (use a `(shop)` route group with shared layout). Header contains: MiniShop logo/brand, Products link, Cart link with item count badge, Orders link. Root `/` redirects to `/products`. Health endpoint at `/api/health`.

Price format: EUR cents → `€1,299.99`. Responsive layout following Figma design.

### Shopping Cart

Server-side cart with anonymous sessions (httpOnly cookie, UUID). Cart items reference **variants**, not products.

- Add to cart from product detail (must select variant first)
- Same variant added twice → increments quantity
- Different variants of same product → separate cart lines
- Quantity controls: **"+" and "−" buttons** per line item, **"Remove" button**
- Cart total = sum(effective_price * quantity), displayed as order summary
- Cannot add out-of-stock variant
- Session persists across navigations
- Cart item count badge in navigation header
- **"Place Order" button** (blue, full-width) at bottom of cart summary
- Empty cart state: message indicating cart is empty

### Checkout & Orders

Convert cart to order via `placeOrder()` — **transactional**: verify variant stock → create Order + OrderItems (snapshot price + variant label) → decrement variant stock → clear cart. All or nothing.

- Empty cart → error
- Insufficient variant stock → error (no partial order)
- Order history at `/orders`: list of orders with status, date, total, **"View Details" link** per order
- Order detail at `/orders/[id]`: **"← Back to Orders" link** at top, line items with variant label + quantity + price, order total

### Admin Authentication

NextAuth v5 with Credentials provider, JWT strategy, bcryptjs. **Only admin routes protected** — storefront stays public.

- Register → auto-login → admin dashboard
- Login with wrong credentials → error
- `/admin/*` requires auth (except `/admin/login`, `/admin/register`)
- Storefront routes (`/products`, `/cart`, `/orders`) NO auth required

### Admin Product Management

CRUD for products with DataTable. Includes variant management.

- Product list with aggregate info (total stock across variants)
- Create product: validated (name required, basePrice > 0)
- Edit product: pre-filled form
- Variant management: add/edit/delete variants with SKU, attribute values, stock, price override
- Delete product: confirmation, cascades to variants
- All admin actions require auth
- Validation: SKU unique, stock >= 0
