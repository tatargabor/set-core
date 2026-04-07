---
description: MiniShop e-commerce project conventions
globs:
  - "src/**"
  - "prisma/**"
---

# MiniShop Conventions

## Recommended Change Decomposition

The minishop spec covers 6 functional areas. Ideal decomposition:

1. **foundation-setup** (Phase 1) — Prisma schema, seed data, package.json deps, Playwright/Vitest config, globals.css, layout
2. **auth-navigation** (Phase 1, parallel with foundation or Phase 1 sequential) — NextAuth, middleware, login/register pages, storefront navigation header
3. **product-catalog** (Phase 2) — Product grid, detail page, variant selector, catalog E2E tests
4. **shopping-cart** (Phase 2) — Cart session, add/remove/update, cart page, cart E2E tests
5. **admin-products** (Phase 2) — Admin CRUD for products/variants, DataTable, admin E2E tests
6. **checkout-orders** (Phase 3) — Order placement, order history, order detail page, checkout E2E tests

Keep foundation and auth SEPARATE. Keep cart and checkout SEPARATE. This prevents 100K+ token changes that are prone to integration failures.

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

## Admin Authentication

- bcrypt for password hashing (devDependency: `bcryptjs`)
- NextAuth with Credentials provider
- Admin registration: `/admin/register` (first user becomes admin)
- Session-based auth with JWT strategy
- Middleware protects `/admin/*` routes (except login/register)

## Seed Data

- `prisma/seed.ts` using `tsx` runner
- Idempotent: use `upsert` or check-before-insert
- Creates: 6 products, 3 attribute types, variants for each product, 1 admin user (admin@example.com / password123)
