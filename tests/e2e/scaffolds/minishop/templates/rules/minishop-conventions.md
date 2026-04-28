---
description: MiniShop e-commerce project conventions
globs:
  - "src/**"
  - "prisma/**"
---

# MiniShop Conventions

## Recommended Change Decomposition

The minishop spec covers 6 functional areas. Ideal decomposition:

1. **foundation-setup** (Phase 1) — Prisma schema (Order.userId is REQUIRED, shipping fields all required), seed data, package.json deps, Playwright/Vitest config, globals.css, root layout, `/api/health`. Generate Prisma client and run seed as part of this change.
2. **auth-navigation** (Phase 1, after foundation) — NextAuth v5 Credentials + JWT, `/login` + `/register`, single-form auth shared by customers and admins (admin redirected to `/admin/orders` after login), middleware for `/admin/*` (returns 403 for USER role, NOT silent redirect), storefront header with signed-in/signed-out variants, Orders link visibility rule.
3. **product-catalog** (Phase 2) — Product grid, detail page, JSON-attribute variant picker, catalog E2E tests. Products with empty `attributes: {}` show no picker.
4. **shopping-cart** (Phase 2) — Cart session (httpOnly `session_id` cookie), add/remove/update server actions, cart page with line totals + grand total, cart E2E tests. **Cart browsing is anonymous; checkout is login-gated (handled in checkout-orders, not here).**
5. **checkout-orders** (Phase 3) — `/checkout` shipping form (zod-validated), `placeOrder` server action asserts auth → creates Order with userId + shipping fields → snapshots variant label/product name/price → decrements stock → clears cart. `/orders/[id]/thanks` confirmation page. `/orders` + `/orders/[id]` with ownership check (404 if not yours). On login, the existing `session_id` cookie is preserved so the anonymous cart lineage carries over.
6. **admin-orders** (Phase 4, after checkout-orders) — `/admin/orders` list sorted by `createdAt` DESC, `/admin/orders/[id]` read-only detail with customer info + shipping address. `/admin/products` read-only overview (Alert banner + product table with variant count, total stock, status badge — no actions, no forms). AdminSidebar layout with three nav items: Orders, Products, Sign Out. No mutations anywhere on the admin surface.

Keep foundation and auth SEPARATE. Keep cart and checkout SEPARATE — login-gating lives in checkout. The admin-orders change owns BOTH `/admin/orders*` and `/admin/products` — they're tiny, read-only, and share the AdminSidebar layout, so splitting them adds overhead without value.

## Out-of-scope reminders

The spec explicitly excludes Stripe / online payments (cash on delivery only), admin product CRUD, status mutations, search, filters, discounts, password reset, email verification, guest checkout. Do NOT scope-creep these in.

## Auth-flow contract

- A single `/login` page handles both audiences. `/register` always creates a `USER` (no admin self-registration).
- The anonymous `session_id` cookie is NEVER rotated on login — both login and register must preserve it so `CartItem` rows tied to `sessionId` remain visible after sign-in.
- `placeOrder()` MUST start with `const session = await auth(); if (!session) return { error: "Please sign in to place an order" }` — do NOT create a guest Order with `userId = null` (the schema forbids it).
- `/checkout`, `/orders`, `/orders/[id]`, `/orders/[id]/thanks` MUST redirect to `/login?returnTo=<current>` when unauthenticated — not render an empty state.
- `/admin/*` middleware MUST return 403 (a real page with "Admin access required") when a USER-role session hits admin routes — silent redirects hide privilege errors.
- After successful login with no `returnTo`, ADMIN role redirects to `/admin/orders`; USER role redirects to `/products`.

## Product Data

- 5 seed products, 11 variants total. Some products have NO variants (`attributes: {}`) — the UI must not render an empty picker for those.
- Variant attributes are stored as JSON on `ProductVariant.attributes` — there are NO normalized AttributeType / ProductAttribute / VariantAttributeValue tables.
- Each variant has a human-readable `label` snapshot ("Black", "Red Switches"). Use `label` directly — do not derive from `attributes` keys.
- `ProductVariant.price` is nullable; `null` means use `Product.basePrice`. Compute `effectivePrice = variant.price ?? product.basePrice`.
- Stock tracked per variant. Catalog OOS badge only when ALL variants of the product are stock=0.
- The `STAND-ROSE` variant is seeded with stock=0 to exercise the per-variant disabled-picker path.

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
- Import from `@/components/ui/<component>` — install first with `pnpm dlx shadcn@latest add <component>`
- Use `cn()` from `@/lib/utils` for conditional class merging
- Do NOT use plain HTML `<button>`, `<input>`, `<select>` — always use shadcn equivalents
- Do NOT delete `components.json` or `src/lib/utils.ts` — these are required

## Authentication

Single `User` model, role-based. Two audiences share one auth pipeline AND one login page.

- bcrypt for password hashing (devDependency: `bcryptjs`)
- NextAuth v5 Credentials provider, JWT strategy
- Customer routes: `/login`, `/register` (creates role=USER)
- Admin sign-in: same `/login` form. After login, ADMIN role lands on `/admin/orders` (when no `returnTo` is set).
- Middleware `src/middleware.ts` handles `/admin/*`: unauthenticated → `/login?returnTo=<current>`; role=USER → 403 page (a real component, not a redirect)
- Server actions that mutate user data (`placeOrder`) re-check the session — middleware is not the only line of defense
- `/checkout`, `/orders`, `/orders/[id]`, `/orders/[id]/thanks` are server components that redirect to `/login?returnTo=…` when unauthenticated

## Seed auth users

- 1 admin: `admin@example.com` / `password123` (role=ADMIN)
- 1 customer: `alice@example.com` / `password123` (role=USER) — pre-seeded so E2E tests can log in without going through registration

## Seed Data

- `prisma/seed.ts` using `tsx` runner
- Idempotent: use `upsert` for users; `deleteMany` + `createMany` for products and variants
- Creates: 5 products, 11 variants, 1 admin user, 1 customer user

## See also — universal web anti-patterns

The framework-level `rules/web-conventions.md` (deployed by `set-project init`)
codifies e2e-failure-prone anti-patterns that apply to every web scaffold:

1. Never `navigator.sendBeacon` for cart/order mutations — await `fetch()` instead.
2. Upsert with composite unique key that includes the owning entity (sessionId/userId).
3. `data-testid="<feature>-<element>"` naming, kept in sync between component and test.
4. Use Playwright `storageState` via `lib/auth/storage-state.ts` for admin auth.
5. Annotate e2e spec files with `// @REQ-...` tags so the orchestrator can
   attribute failing tests to their owning change.

These apply here too — follow them alongside this scaffold's specific rules.
