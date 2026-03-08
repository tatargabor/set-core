# MiniShop v1 — Webshop Feature Spec

> Next.js 14+ App Router webshop with Prisma (SQLite), shadcn/ui, Tailwind CSS, NextAuth.js v5

## v0 Status (scaffold)

| What | Status |
|---|---|
| `package.json` with all dependencies | Done (scaffold) |
| Prisma schema (Product, User, Order, OrderItem, CartItem) | Done (scaffold) |
| Prisma seed (6 products, English names, EUR prices) | Done (scaffold) |
| `.env.example` with DATABASE_URL, NEXTAUTH_SECRET, NEXTAUTH_URL | Done (scaffold) |
| Tailwind + PostCSS + TypeScript + Next.js config | Deployed by `wt-project init --project-type web` |
| `components.json` (shadcn/ui) | Deployed by `wt-project init --project-type web` |
| Root layout (`src/app/layout.tsx`) | **Not started** — agents create |
| Pages, components, actions | **Not started** — agents create |

**Setup (done by `run.sh` before orchestration):**
1. `cp .env.example .env`
2. `pnpm install`
3. `pnpm prisma generate && pnpm prisma migrate dev --name init && pnpm prisma db seed`

**Important:** There is NO app code in the scaffold. The agents must create everything under `src/` from scratch: root layout, all pages, all components, all Server Actions, all tests.

## Tech Conventions (project-specific)

> General Next.js conventions (shadcn/ui, Server Components, Server Actions pattern, Prisma singleton, form validation) are provided by `.claude/rules/` — deployed by `wt-project init`. Below are only this project's specifics.

- **Package manager:** pnpm (`pnpm dev`, `pnpm test`, `pnpm build`)
- **Install shadcn components:** `pnpm dlx shadcn@latest add <component>`
- **cn() helper:** Create at `src/lib/utils.ts`: `import { clsx } from "clsx"; import { twMerge } from "tailwind-merge"; export function cn(...inputs) { return twMerge(clsx(inputs)); }`
- **Auth:** NextAuth.js v5 — Credentials provider, JWT strategy, bcryptjs passwords. Use `auth()` for session.
- **Database:** SQLite (`file:./dev.db`). Prisma schema at `prisma/schema.prisma`.
- **Currency:** Euro (EUR). Prices stored as integers in cents. Format as `€X,XXX.XX` (e.g., price 129999 → `€1,299.99`). Use `(price / 100).toFixed(2)` for display.
- **Tests:** Jest + `@testing-library/react`. Files: `tests/*.test.tsx`. Run: `pnpm test`.

## Feature Roadmap

### Change 1: `products-page`

Build the product catalog — the storefront landing page.

**Create these files:**

- `src/lib/utils.ts` — `cn()` helper (clsx + tailwind-merge)
- `src/lib/prisma.ts` — Prisma singleton client (globalThis pattern for dev hot reload)
- `src/app/globals.css` — Tailwind directives (`@tailwind base/components/utilities`) + shadcn CSS variables (`:root` with `--background`, `--foreground`, `--primary`, etc.)
- `src/app/layout.tsx` — Root layout: `<html>`, `<body>` with Inter font, globals.css import. Navigation header with links: Products, Cart, Orders, Admin. Use shadcn Button for nav links.
- `src/app/page.tsx` — Redirect to `/products`
- `src/app/products/page.tsx` — Product grid. Server Component that queries `prisma.product.findMany()`. Renders products in a responsive grid (1 col mobile, 2 col tablet, 3 col desktop) using shadcn Card. Each card: product image (use `<img>` with imageUrl), name, description, price formatted as `€X,XXX.XX`, stock badge (green if >0, red if 0).
- `src/app/products/[id]/page.tsx` — Product detail page. Shows full product info with larger image, full description, price, stock status, "Add to Cart" button (disabled for now, wired in cart-feature change).
- `src/components/product-card.tsx` — Reusable product card component used in the grid.
- `tests/products.test.tsx` — Tests: product list renders, product detail page renders, price formatting correct.

**Install shadcn components:** button, card, badge

**Acceptance criteria:**
- `/products` shows all 6 seeded products in a Card grid
- `/products/[id]` shows single product detail
- Price displayed as `€X,XXX.XX` (e.g., `€1,299.99`)
- Stock=0 products: badge shows "Out of Stock", "Add to Cart" button disabled
- Responsive: 1 col on mobile, 2 on tablet, 3 on desktop
- Navigation header visible on all pages
- `pnpm test` passes

---

### Change 2: `cart-feature`

> depends_on: products-page

Server-side shopping cart with anonymous sessions (no auth required).

**Create these files:**

- `src/lib/session.ts` — Helper to get/set session ID from cookies. Use `cookies()` from `next/headers`. If no `session_id` cookie, generate UUID with `crypto.randomUUID()` and set it as httpOnly cookie.
- `src/actions/cart.ts` — Server Actions:
  - `addToCart(productId: number, quantity: number)` — upsert CartItem (if exists, increment quantity). Validate product exists and has stock > 0. Return error if out of stock.
  - `removeFromCart(cartItemId: number)` — delete CartItem
  - `updateCartQuantity(cartItemId: number, quantity: number)` — update quantity, delete if quantity <= 0
  - All actions call `revalidatePath("/cart")`
- `src/app/cart/page.tsx` — Cart page. Server Component that queries cart items with product details for current session. Shows: product name, quantity with +/- buttons, line total, cart total. Empty state message when no items.
- `src/app/products/[id]/page.tsx` — **Update:** Wire "Add to Cart" button to `addToCart` Server Action. Show toast on success.
- `src/app/layout.tsx` — **Update:** Add cart item count badge next to Cart nav link.
- `tests/cart.test.tsx` — Tests: add to cart, remove from cart, quantity update, empty cart state.

**Install shadcn components:** toast, separator, input (for quantity)

**Acceptance criteria:**
- "Add to Cart" button on product detail page works
- Cart page shows all cart items with quantities and totals
- +/- buttons update quantity
- Remove button removes item
- Adding same product twice updates quantity
- Cart total calculated correctly (sum of price * quantity)
- Session persists across navigations
- `pnpm test` passes

---

### Change 3: `orders-checkout`

> depends_on: cart-feature, products-page

Checkout: convert cart to order, manage stock, show order history.

**Create these files:**

- `src/actions/orders.ts` — Server Actions:
  - `placeOrder()` — Transactional (`prisma.$transaction`): get session cart items → verify each product has sufficient stock → create Order + OrderItems (snapshot current prices) → decrement product stock → clear cart. Return error if cart empty or any product has insufficient stock. The stock check and decrement must be inside the same transaction to prevent race conditions.
  - Calls `revalidatePath("/orders")` and `revalidatePath("/products")`
- `src/app/orders/page.tsx` — Order history page. Shows orders for current session: order ID, date, status badge, total. Link to detail.
- `src/app/orders/[id]/page.tsx` — Order detail: line items with product name, quantity, price, subtotal. Order total and status.
- `src/app/cart/page.tsx` — **Update:** Add "Place Order" button that calls `placeOrder`. Redirect to order detail on success. Show error toast on failure.
- `tests/orders.test.tsx` — Tests: place order, stock decremented, order in history, empty cart error, insufficient stock error.

**Install shadcn components:** table (for order items)

**Acceptance criteria:**
- "Place Order" on cart page creates order and clears cart
- Order creation is transactional (all or nothing)
- Stock decremented after order
- Empty cart → error message
- Insufficient stock → error message
- Orders page shows history with totals
- Order detail shows line items
- `pnpm test` passes

---

### Change 4: `admin-auth`

> depends_on: products-page

Admin authentication with NextAuth.js v5. **Only admin routes are protected** — the storefront (products, cart, orders) remains fully public.

**Create these files:**

- `src/lib/auth.ts` — NextAuth config: Credentials provider (email + password), JWT session strategy, bcryptjs for password hashing. Callbacks: include user.id and user.role in session/JWT.
- `src/app/api/auth/[...nextauth]/route.ts` — NextAuth route handler (`export { GET, POST } from "@/lib/auth"`)
- `src/app/admin/login/page.tsx` — Login form: email + password inputs, submit button, error display. Uses shadcn Input, Button, Label, Card.
- `src/app/admin/register/page.tsx` — Registration form: name, email, password. Creates user with hashed password, auto-login after register.
- `src/app/admin/page.tsx` — Admin dashboard. Shows: welcome message with user name, quick stats (product count, order count), nav links to admin sections.
- `src/app/admin/layout.tsx` — Admin layout: sidebar navigation (Dashboard, Products), user info in header, logout button. Distinct from storefront layout.
- `middleware.ts` — **CRITICAL:** Only match `/admin/:path*` EXCEPT `/admin/login` and `/admin/register`. Redirect unauthenticated users to `/admin/login`. Do NOT protect `/products`, `/cart`, `/orders`, or any storefront route.
- `tests/auth.test.tsx` — Tests: register creates user, login with correct password succeeds, login with wrong password fails, admin routes require auth, storefront routes remain public.

**Install shadcn components:** label, input (if not already installed), dialog

**Acceptance criteria:**
- Register: creates user, redirects to admin dashboard
- Login: correct credentials → admin, wrong credentials → error
- `/admin/*` routes require authentication (redirect to login)
- `/admin/login` and `/admin/register` are publicly accessible
- `/products`, `/cart`, `/orders` remain fully public — NO auth required
- Middleware ONLY protects admin routes
- `pnpm test` passes

---

### Change 5: `admin-products`

> depends_on: admin-auth, products-page

Admin CRUD panel for products with DataTable.

**Create these files:**

- `src/app/admin/products/page.tsx` — Product list with shadcn DataTable: columns for name, price, stock, actions (edit/delete). Server Component with Prisma query.
- `src/app/admin/products/columns.tsx` — Column definitions for DataTable (`"use client"`)
- `src/app/admin/products/data-table.tsx` — DataTable wrapper component (`"use client"`, uses `@tanstack/react-table`)
- `src/app/admin/products/new/page.tsx` — Create product form. Fields: name (required), description, price (required, > 0), stock (required, >= 0), imageUrl. Validation with zod schema + react-hook-form.
- `src/app/admin/products/[id]/edit/page.tsx` — Edit product form, pre-filled with existing data. Same validation.
- `src/actions/admin-products.ts` — Server Actions: `createProduct(formData)`, `updateProduct(id, formData)`, `deleteProduct(id)`. All require auth check (`const session = await auth()`). Validate with zod. `revalidatePath("/admin/products")` and `revalidatePath("/products")`.
- `tests/admin-products.test.tsx` — Tests: create product appears in catalog, edit updates data, delete removes product, validation errors shown.

**Install shadcn components:** dropdown-menu, table (if not already)

**Acceptance criteria:**
- Admin product list shows DataTable with all products
- Create form: validated, creates product visible in storefront
- Edit form: pre-filled, updates product
- Delete: removes product (with confirmation)
- All admin actions require authentication
- Form validation (zod + react-hook-form): name required, price > 0, stock >= 0
- `pnpm test` passes

---

### Change 6: `playwright-e2e`

> depends_on: products-page, cart-feature, orders-checkout, admin-auth, admin-products

Playwright E2E tests covering the full user journey.

**Create these files:**

- `playwright.config.ts` — Config: headless Chromium, baseURL `http://localhost:3000`, webServer `pnpm dev`, retries 0.
- `tests/e2e/storefront.spec.ts` — Products render with images, prices, stock badges. Navigation works.
- `tests/e2e/cart.spec.ts` — Add product to cart from detail page, quantity update, remove, total calculation.
- `tests/e2e/checkout.spec.ts` — Full checkout: add items → place order → verify stock decremented → order in history.
- `tests/e2e/admin.spec.ts` — Register admin → login → add product (visible in catalog) → edit → delete.
- `tests/e2e/responsive.spec.ts` — Mobile viewport (375px): layout adapts, nav works, cards stack vertically.
- `tests/e2e/capture-screenshots.ts` — Screenshot script: visit each main page (products, product detail, cart with items, orders, admin login, admin dashboard, admin products), save PNG to `e2e-screenshots/`.

**Acceptance criteria:**
- All E2E tests pass: `pnpm test:e2e`
- Full user journey covered: browse → cart → checkout → admin
- Mobile responsive layout verified
- Screenshots captured for all main pages
- Tests use fresh database state (Prisma reset in fixtures or beforeAll)

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
