---
description: MiniShop e-commerce project conventions
globs:
  - "src/**"
  - "prisma/**"
---

# MiniShop Conventions

## Recommended Change Decomposition

The minishop spec covers 7 functional areas. Ideal decomposition:

1. **foundation-setup** (Phase 1) — Prisma schema (Order.userId is REQUIRED, not optional), seed data, package.json deps, Playwright/Vitest config, globals.css, layout
2. **auth-navigation** (Phase 1, after foundation) — NextAuth v5 Credentials + JWT, `/login` + `/register` (customer), `/admin` + `/admin/register` (admin), middleware for `/admin/*` + role gating (USER → 403 on admin), storefront Navbar with signed-in/signed-out variants, Orders link visibility rule
3. **product-catalog** (Phase 2) — Product grid, detail page, variant selector, catalog E2E tests
4. **shopping-cart** (Phase 2) — Cart session (httpOnly `session_id` cookie), add/remove/update, cart page, cart E2E tests. **Cart browsing is anonymous; checkout is login-gated (handled in checkout-orders, not here).**
5. **checkout-orders** (Phase 3) — `placeOrder` server action asserts auth → creates Order with `userId`, clears cart. `/cart` "Place Order" button swaps to "Sign in to checkout" for anonymous users. Customer `/orders` + `/orders/[id]` with ownership check. On login, the existing `session_id` cookie is preserved so the anonymous cart lineage carries over.
6. **admin-products** (Phase 3) — Admin CRUD for products/variants, DataTable, admin E2E tests
7. **admin-orders** (Phase 4, after checkout-orders) — `/admin/orders` list (status filter, sorted by createdAt DESC), `/admin/orders/[id]` detail with customer block + session trace, AdminSidebar "Orders" entry active on descendant routes, Admin Dashboard "Total Orders" card links to /admin/orders

Keep foundation and auth SEPARATE. Keep cart and checkout SEPARATE — login-gating lives in checkout, not cart. Keep admin-products and admin-orders SEPARATE — they share only the AdminSidebar (which auth-navigation owns). This prevents 100K+ token changes that are prone to integration failures.

## Auth-flow contract

- The anonymous `session_id` cookie is NEVER rotated on login — both customer login and register must preserve it so CartItem rows tied to `sessionId` remain visible after sign-in.
- `placeOrder()` MUST start with `const session = await auth(); if (!session) return { error: "Please sign in to place an order" }` — do NOT create a guest Order with `userId = null` (the schema forbids it).
- `/orders` and `/orders/[id]` server components MUST redirect to `/login?returnTo=<current>` when unauthenticated — not render an empty state.
- `/admin/*` middleware MUST return 403 (not redirect to /admin) when a USER-role session hits admin routes — silent redirects hide privilege errors.

## Product Data

- 6 seed products with variants (e.g., Mechanical Keyboard, Wireless Mouse, 4K Webcam)
- 3 attribute types: Size, Color, Material — each with 2-4 values
- Prisma schema: Product → ProductVariant → AttributeType → ProductAttribute → VariantAttributeValue
- Product basePrice in cents (integer), variant price overrides optional
- Stock tracked per variant, not per product

## Currency & Formatting

- EUR currency — prices displayed as `€X.XX`
- `formatPrice(cents: number)`: divide by 100, format with 2 decimals, prepend €
- Price ranges: `€89.99` (single) or `€129.99 – €134.99` (variant range)
- Use `src/lib/format.ts` for all price formatting

## Images

- Product images use placeholder service: `https://placehold.co/400x300/EEE/999?text=Product+Name`
- NEVER reference local files like `/images/product.jpg`
- Seed data `imageUrl` fields must use working placeholder URLs

## UI Components

- ALL UI components MUST use shadcn/ui: Button, Card, Input, Label, Table, Dialog, Select, etc.
- Import from `@/components/ui/<component>` — install first with `npx shadcn@latest add <component>`
- Use `cn()` from `@/lib/utils` for conditional class merging
- Do NOT use plain HTML `<button>`, `<input>`, `<select>` — always use shadcn equivalents
- Do NOT delete `components.json` or `src/lib/utils.ts` — these are required

## Authentication

Single `User` model, role-based. Two audiences share the auth pipeline.

- bcrypt for password hashing (devDependency: `bcryptjs`)
- NextAuth v5 Credentials provider, JWT strategy
- Customer routes: `/login`, `/register` (creates role=USER)
- Admin routes: `/admin` (login), `/admin/register` (creates role=ADMIN — v1 demo policy, no hardening)
- Middleware `src/middleware.ts` handles `/admin/*`: unauthenticated → `/admin`; role=USER → 403 page
- Server actions that mutate user data (`placeOrder`, all `/admin/*` actions) re-check the session — middleware is not the only line of defense
- `/orders` + `/orders/[id]` are server components that redirect to `/login?returnTo=…` when unauthenticated

## Seed auth users

- 1 admin: `admin@example.com` / `password123` (role=ADMIN)
- 1 customer: `alice@example.com` / `password123` (role=USER) — pre-seeded so E2E tests can log in without going through registration

## Seed Data

- `prisma/seed.ts` using `tsx` runner
- Idempotent: use `upsert` or check-before-insert
- Creates: 6 products, 3 attribute types, variants for each product, 1 admin user (admin@example.com / password123)
