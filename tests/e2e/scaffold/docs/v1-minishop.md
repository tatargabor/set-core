# MiniShop v1 — Webshop Feature Spec

> Next.js 14+ App Router webshop with Prisma (SQLite), shadcn/ui, Tailwind CSS, NextAuth.js v5

## Design

**Figma Design:** https://www.figma.com/make/9PH3uS4vWjSj6cUPhTGZSt/wt-minishop?p=f&t=zvhTdumJeYUpKrJm-0

Agents should use the Figma MCP to query design tokens, component specs, and layout details during implementation. The design file contains desktop and mobile layouts for all pages.

## Starting Point

There is NO application code in the scaffold. Agents create everything from scratch.

Platform configs (tsconfig, tailwind, next.config, postcss, components.json, `.claude/rules/`) are deployed by `wt-project init --project-type web --template nextjs` before orchestration starts. Those rules already cover: Server Actions patterns, shadcn/ui usage, Prisma singleton, "use client" rules, form validation with zod + react-hook-form, auth conventions, DataTable patterns. **Do not duplicate those conventions here.**

**Setup (done by `run.sh` before orchestration):**
1. Copy this spec to `docs/v1-minishop.md`
2. `git init && wt-project init --project-type web --template nextjs`
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
    "test": "jest",
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
    "jest": "^29.7.0",
    "@jest/types": "^29.6.0",
    "ts-jest": "^29.2.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.6.0",
    "jest-environment-jsdom": "^29.7.0",
    "@playwright/test": "^1.48.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0"
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
  id          Int         @id @default(autoincrement())
  name        String
  description String      @default("")
  price       Int                         // EUR cents (e.g., 129999 = EUR 1,299.99)
  stock       Int         @default(0)
  imageUrl    String      @default("")
  createdAt   DateTime    @default(now())
  updatedAt   DateTime    @updatedAt
  cartItems   CartItem[]
  orderItems  OrderItem[]
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
  id        Int      @id @default(autoincrement())
  sessionId String                        // anonymous session cookie UUID
  quantity  Int      @default(1)
  productId Int
  product   Product  @relation(fields: [productId], references: [id], onDelete: Cascade)
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  @@unique([sessionId, productId])        // one cart item per product per session
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
  id        Int     @id @default(autoincrement())
  quantity  Int
  price     Int                           // snapshot of product price at order time
  orderId   Int
  order     Order   @relation(fields: [orderId], references: [id], onDelete: Cascade)
  productId Int
  product   Product @relation(fields: [productId], references: [id])
}
```

## Seed Data

Create `prisma/seed.ts`. Insert exactly 6 products using `upsert` (idempotent):

| # | name | price (cents) | stock | imageUrl |
|---|---|---|---|---|
| 1 | Wireless Headphones | 7999 | 25 | `https://placehold.co/400x300?text=Headphones` |
| 2 | Mechanical Keyboard | 12999 | 15 | `https://placehold.co/400x300?text=Keyboard` |
| 3 | USB-C Hub | 3499 | 50 | `https://placehold.co/400x300?text=USB-C+Hub` |
| 4 | Laptop Stand | 4599 | 30 | `https://placehold.co/400x300?text=Laptop+Stand` |
| 5 | 4K Monitor | 42999 | 8 | `https://placehold.co/400x300?text=4K+Monitor` |
| 6 | Ergonomic Mouse | 5999 | 0 | `https://placehold.co/400x300?text=Mouse` |

Product #6 has stock=0 (used to test "Out of Stock" behavior).

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
- **Tests:** Jest + `@testing-library/react` for unit tests (`pnpm test`). Playwright for E2E (`pnpm test:e2e`).

## Feature Roadmap

### Change 1: `products-page`

Build the product catalog -- the storefront landing page.

**Create these files:**

- `src/lib/utils.ts` -- `cn()` helper (clsx + tailwind-merge)
- `src/lib/prisma.ts` -- Prisma singleton client
- `src/app/globals.css` -- Tailwind directives + shadcn CSS variables
- `src/app/layout.tsx` -- Root layout: globals.css, navigation header. Follow Figma design for nav structure and typography.
- `src/app/page.tsx` -- Redirect to `/products`
- `src/app/api/health/route.ts` -- `GET` returns `{ status: "ok" }` (used by smoke checks)
- `src/app/products/page.tsx` -- Product grid. Server Component, `prisma.product.findMany()`. Responsive grid using shadcn Card. Each card shows product info and stock status. Follow Figma design for layout and breakpoints.
- `src/app/products/[id]/page.tsx` -- Product detail page. Follow Figma design for layout. "Add to Cart" button (disabled until cart-feature).
- `src/components/product-card.tsx` -- Reusable card component.
- `tests/products.test.tsx` -- Product list renders, detail renders, price formatting.

**Install shadcn components:** button, card, badge

**Acceptance criteria:**
- `/products` shows all 6 seeded products in a Card grid
- `/products/[id]` shows single product detail
- Price displayed as `€1,299.99` format
- Stock=0: "Out of Stock" indicator, "Add to Cart" disabled
- Responsive layout matching Figma design (desktop + mobile)
- Navigation header on all pages matching Figma design
- `pnpm test` passes

---

### Change 2: `cart-feature`

> depends_on: products-page

Server-side shopping cart with anonymous sessions (no auth required).

**Create these files:**

- `src/lib/session.ts` -- Get/set session ID from cookies. If no `session_id` cookie, generate UUID and set as httpOnly cookie.
- `src/actions/cart.ts` -- Server Actions:
  - `addToCart(productId, quantity)` -- upsert CartItem; validate stock > 0
  - `removeFromCart(cartItemId)` -- delete CartItem
  - `updateCartQuantity(cartItemId, quantity)` -- update or delete if <= 0
  - All revalidate `/cart`
- `src/app/cart/page.tsx` -- Cart page with item list, quantity controls, totals, and empty state. Follow Figma design for layout.
- `src/app/products/[id]/page.tsx` -- **Update:** Wire "Add to Cart" to `addToCart` action. Toast on success.
- `src/app/layout.tsx` -- **Update:** Cart item count badge on nav.
- `tests/cart.test.tsx` -- Add, remove, quantity update, empty cart.

**Install shadcn components:** toast, separator, input

**Acceptance criteria:**
- "Add to Cart" on product detail works
- Cart page shows items with quantities and totals
- +/- buttons update quantity
- Remove button works
- Same product added twice increments quantity
- Cart total = sum(price * quantity)
- Session persists across navigations
- `pnpm test` passes

---

### Change 3: `orders-checkout`

> depends_on: cart-feature, products-page

Convert cart to order, manage stock, show order history.

**Create these files:**

- `src/actions/orders.ts` -- Server Actions:
  - `placeOrder()` -- Transactional (`prisma.$transaction`): verify stock -> create Order + OrderItems (snapshot prices) -> decrement stock -> clear cart. Error if cart empty or insufficient stock. Stock check and decrement MUST be in same transaction.
  - Revalidates `/orders` and `/products`
- `src/app/orders/page.tsx` -- Order history for current session. Follow Figma design for layout.
- `src/app/orders/[id]/page.tsx` -- Order detail with line items. Follow Figma design for layout.
- `src/app/cart/page.tsx` -- **Update:** "Place Order" button. Redirect to order detail on success. Error toast on failure.
- `tests/orders.test.tsx` -- Place order, stock decremented, history, empty cart error, insufficient stock error.

**Install shadcn components:** table

**Acceptance criteria:**
- "Place Order" creates order and clears cart
- Order creation is transactional (all or nothing)
- Stock decremented after order
- Empty cart -> error
- Insufficient stock -> error
- Orders page shows history with totals
- Order detail shows line items
- `pnpm test` passes

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
- `pnpm test` passes

---

### Change 5: `admin-products`

> depends_on: admin-auth, products-page

Admin CRUD for products with DataTable.

**Create these files:**

- `src/app/admin/products/page.tsx` -- Product list with DataTable. Follow Figma design for layout.
- `src/app/admin/products/columns.tsx` -- Column definitions (`"use client"`)
- `src/app/admin/products/data-table.tsx` -- DataTable wrapper (`"use client"`)
- `src/app/admin/products/new/page.tsx` -- Create product form with zod + react-hook-form validation. Follow Figma design.
- `src/app/admin/products/[id]/edit/page.tsx` -- Edit form, pre-filled.
- `src/actions/admin-products.ts` -- `createProduct`, `updateProduct`, `deleteProduct`. All require auth check. Revalidate `/admin/products` and `/products`.
- `tests/admin-products.test.tsx` -- Create, edit, delete, validation errors.

**Install shadcn components:** dropdown-menu, table

**Acceptance criteria:**
- Admin product list shows DataTable
- Create: validated, product appears in storefront
- Edit: pre-filled, updates product
- Delete: with confirmation, removes product
- All admin actions require auth
- Validation: name required, price > 0, stock >= 0
- `pnpm test` passes

---

### Change 6: `playwright-e2e`

> depends_on: products-page, cart-feature, orders-checkout, admin-auth, admin-products

Playwright E2E tests covering the full user journey.

**Create these files:**

- `playwright.config.ts` -- Headless Chromium, baseURL `http://localhost:3000`, webServer `pnpm dev`, retries 0.
- `tests/e2e/storefront.spec.ts` -- Products render with images, prices, stock badges. Navigation.
- `tests/e2e/cart.spec.ts` -- Add to cart, quantity update, remove, total.
- `tests/e2e/checkout.spec.ts` -- Full checkout: add items -> place order -> stock decremented -> order in history.
- `tests/e2e/admin.spec.ts` -- Register -> login -> add product -> edit -> delete.
- `tests/e2e/responsive.spec.ts` -- Mobile viewport (375px): cards stack, nav works.
- `tests/e2e/capture-screenshots.ts` -- Visit each main page, save PNG to `e2e-screenshots/`.

**Acceptance criteria:**
- All E2E tests pass: `pnpm test:e2e`
- Full journey: browse -> cart -> checkout -> admin
- Mobile responsive verified
- Screenshots captured for all main pages
- Tests use fresh database state

## Orchestrator Directives

```
max_parallel: 2
smoke_command: pnpm test
smoke_blocking: true
test_command: pnpm test
merge_policy: checkpoint
checkpoint_auto_approve: true
auto_replan: true
```

## Reszletes Ellenorzesi Lista (Verification Checklist)

Post-run verification. Each item must be manually checkable:

### Storefront
- [ ] `/products` page shows exactly 6 product cards
- [ ] Product prices display in EUR format (e.g., price 129999 displays as "€1,299.99")
- [ ] Product #6 (Ergonomic Mouse) shows "Out of Stock" badge and disabled "Add to Cart"
- [ ] Products with stock > 0 show stock badge (style per Figma design)
- [ ] Product detail page (`/products/[id]`) shows full info (layout per Figma design)
- [ ] Responsive layout matches Figma desktop and mobile designs
- [ ] Navigation header matches Figma design on every page

### Cart
- [ ] "Add to Cart" from product detail page adds item to cart
- [ ] Adding the same product twice increments quantity (no duplicates)
- [ ] Cart page shows items with quantities and totals (layout per Figma design)
- [ ] Quantity controls update quantity; quantity 0 removes item
- [ ] Cart total equals sum of (price * quantity) for all items
- [ ] Cart persists across page navigations (session cookie)
- [ ] Cannot add out-of-stock product to cart

### Checkout & Orders
- [ ] "Place Order" button on cart page creates an order
- [ ] After order: cart is empty, stock is decremented
- [ ] Order creation is transactional (stock rollback on failure)
- [ ] Placing order with empty cart shows error
- [ ] Placing order when stock insufficient shows error (no partial order)
- [ ] `/orders` shows order history with date, status, total
- [ ] `/orders/[id]` shows line items with product name, quantity, price, subtotal

### Admin Auth
- [ ] `/admin/register` -- create account, auto-redirect to admin dashboard
- [ ] `/admin/login` -- login with correct credentials succeeds
- [ ] `/admin/login` -- login with wrong password shows error
- [ ] Visiting `/admin` without auth redirects to `/admin/login`
- [ ] `/admin/login` and `/admin/register` accessible without auth
- [ ] Storefront routes (`/products`, `/cart`, `/orders`) do NOT require auth

### Admin Products
- [ ] `/admin/products` shows DataTable with all products
- [ ] Create product form validates: name required, price > 0, stock >= 0
- [ ] New product appears in storefront after creation
- [ ] Edit form pre-fills existing data, updates on save
- [ ] Delete requires confirmation, removes product from storefront
- [ ] All admin actions fail if not authenticated

### Tests & Quality
- [ ] `pnpm test` passes (Jest unit tests)
- [ ] `pnpm test:e2e` passes (Playwright E2E)
- [ ] `pnpm build` succeeds without errors
- [ ] Screenshots captured in `e2e-screenshots/` for: products grid, product detail, cart with items, orders list, admin login, admin dashboard, admin products table
